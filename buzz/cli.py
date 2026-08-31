import enum
import logging
import sys
import typing
import urllib.parse

from PyQt6.QtCore import QCommandLineParser, QCommandLineOption

from buzz.model_loader import (
    ModelType,
    WhisperModelSize,
    TranscriptionModel,
    ModelDownloader,
)
from buzz.store.keyring_store import get_password, Key
from buzz.transcriber.transcriber import (
    Task,
    FileTranscriptionTask,
    FileTranscriptionOptions,
    TranscriptionOptions,
    LANGUAGES,
    OutputFormat,
)
from buzz.widgets.application import Application
from buzz.multi_speaker_merge import merge_multi_speaker_transcriptions


class CommandLineError(Exception):
    def __init__(self, message: str):
        super().__init__(message)


class CommandLineModelType(enum.Enum):
    WHISPER = "whisper"
    WHISPER_CPP = "whispercpp"
    HUGGING_FACE = "huggingface"
    FASTER_WHISPER = "fasterwhisper"
    OPEN_AI_WHISPER_API = "openaiapi"


def parse_command_line(app: Application):
    parser = QCommandLineParser()
    try:
        parse(app, parser)
    except CommandLineError as exc:
        print(f"Error: {str(exc)}\n", file=sys.stderr)
        print(parser.helpText())
        sys.exit(1)

def is_url(path: str) -> bool:
    parsed = urllib.parse.urlparse(path)
    return all([parsed.scheme, parsed.netloc])

def _add_command_options(parser: QCommandLineParser):
    task_option = QCommandLineOption(
        ["t", "task"],
        f"The task to perform. Allowed: {join_values(Task)}. Default: {Task.TRANSCRIBE.value}.",
        "task",
        Task.TRANSCRIBE.value,
    )
    model_type_option = QCommandLineOption(
        ["m", "model-type"],
        f"Model type. Allowed: {join_values(CommandLineModelType)}. Default: {CommandLineModelType.WHISPER.value}.",
        "model-type",
        CommandLineModelType.WHISPER.value,
    )
    model_size_option = QCommandLineOption(
        ["s", "model-size"],
        f"Model size. Use only when --model-type is whisper, whispercpp, or fasterwhisper. Allowed: {join_values(WhisperModelSize)}. Default: {WhisperModelSize.TINY.value}.",
        "model-size",
        WhisperModelSize.TINY.value,
    )
    hugging_face_model_id_option = QCommandLineOption(
        ["hfid"],
        'Hugging Face model ID. Use only when --model-type is huggingface. Example: "openai/whisper-tiny"',
        "id",
    )
    language_option = QCommandLineOption(
        ["l", "language"],
        f'Language code. Allowed: {", ".join(sorted([k + " (" + LANGUAGES[k].title() + ")" for k in LANGUAGES]))}. Leave empty to detect language.',
        "code",
        "",
    )
    initial_prompt_option = QCommandLineOption(
        ["p", "prompt"], "Initial prompt.", "prompt", ""
    )
    word_timestamp_option = QCommandLineOption(
        ["w", "word-timestamps"], "Generate word-level timestamps."
    )
    extract_speech_option = QCommandLineOption(
        ["e", "extract-speech"], "Extract speech from audio before transcribing."
    )
    open_ai_access_token_option = QCommandLineOption(
        "openai-token",
        f"OpenAI access token. Use only when --model-type is {CommandLineModelType.OPEN_AI_WHISPER_API.value}. Defaults to your previously saved access token, if one exists.",
        "token",
    )
    output_directory_option = QCommandLineOption(
        ["d", "output-directory"], "Output directory", "directory"
    )
    srt_option = QCommandLineOption(["srt"], "Output result in an SRT file.")
    vtt_option = QCommandLineOption(["vtt"], "Output result in a VTT file.")
    txt_option = QCommandLineOption("txt", "Output result in a TXT file.")
    hide_gui_option = QCommandLineOption("hide-gui", "Hide the main application window.")

    parser.addOptions(
        [
            task_option,
            model_type_option,
            model_size_option,
            hugging_face_model_id_option,
            language_option,
            initial_prompt_option,
            word_timestamp_option,
            extract_speech_option,
            open_ai_access_token_option,
            output_directory_option,
            srt_option,
            vtt_option,
            txt_option,
            hide_gui_option,
        ]
    )

    return {
        "task": task_option,
        "model_type": model_type_option,
        "model_size": model_size_option,
        "hugging_face_model_id": hugging_face_model_id_option,
        "language": language_option,
        "initial_prompt": initial_prompt_option,
        "word_timestamps": word_timestamp_option,
        "extract_speech": extract_speech_option,
        "openai_token": open_ai_access_token_option,
        "output_directory": output_directory_option,
        "srt": srt_option,
        "vtt": vtt_option,
        "txt": txt_option,
        "hide_gui": hide_gui_option,
    }


def _resolve_model(
    model_type: CommandLineModelType,
    model_size: WhisperModelSize,
    hugging_face_model_id: str,
):
    if hugging_face_model_id == "" and model_type == CommandLineModelType.HUGGING_FACE:
        raise CommandLineError("--hfid is required when --model-type is huggingface")
    model = TranscriptionModel(
        model_type=ModelType[model_type.name],
        whisper_model_size=model_size,
        hugging_face_model_id=hugging_face_model_id,
    )
    model_path = model.get_local_model_path()
    if model_path is None:
        ModelDownloader(model=model).run()
        model_path = model.get_local_model_path()
    if model_path is None:
        raise CommandLineError("Model not found")
    return model_path, model


def _add_transcription_tasks(
    app: Application,
    file_paths: typing.List[str],
    model_path: str,
    transcription_options: TranscriptionOptions,
    output_formats: typing.Set[OutputFormat],
    output_directory: str = "",
):
    for file_path in file_paths:
        path_is_url = is_url(file_path)
        file_transcription_options = FileTranscriptionOptions(
            file_paths=[file_path] if not path_is_url else None,
            url=file_path if path_is_url else None,
            output_formats=output_formats,
        )
        transcription_task = FileTranscriptionTask(
            file_path=file_path if not path_is_url else None,
            url=file_path if path_is_url else None,
            source=FileTranscriptionTask.Source.FILE_IMPORT
            if not path_is_url
            else FileTranscriptionTask.Source.URL_IMPORT,
            model_path=model_path,
            transcription_options=transcription_options,
            file_transcription_options=file_transcription_options,
            output_directory=output_directory if output_directory != "" else None,
        )
        app.add_task(transcription_task, quit_on_complete=True)


def _process_add_output_formats(parser, opts) -> typing.Set[OutputFormat]:
    output_formats: typing.Set[OutputFormat] = set()
    if parser.isSet(opts["srt"]):
        output_formats.add(OutputFormat.SRT)
    if parser.isSet(opts["vtt"]):
        output_formats.add(OutputFormat.VTT)
    if parser.isSet(opts["txt"]):
        output_formats.add(OutputFormat.TXT)
    return output_formats


def _handle_add_command(app: Application, parser: QCommandLineParser):
    parser.clearPositionalArguments()
    parser.addPositionalArgument("files", "Input file paths", "[file file file...]")

    opts = _add_command_options(parser)
    parser.addHelpOption()
    parser.addVersionOption()
    parser.process(app)

    file_paths = parser.positionalArguments()[1:]
    if len(file_paths) == 0:
        raise CommandLineError("No input files")

    task = parse_enum_option(opts["task"], parser, Task)
    model_type = parse_enum_option(opts["model_type"], parser, CommandLineModelType)
    model_size = parse_enum_option(opts["model_size"], parser, WhisperModelSize)

    model_path, model = _resolve_model(
        model_type, model_size, parser.value(opts["hugging_face_model_id"])
    )

    language = parser.value(opts["language"])
    if language == "":
        language = None
    elif LANGUAGES.get(language) is None:
        raise CommandLineError("Invalid language option")

    output_formats = _process_add_output_formats(parser, opts)

    openai_access_token = parser.value(opts["openai_token"])
    if model.model_type == ModelType.OPEN_AI_WHISPER_API and openai_access_token == "":
        openai_access_token = get_password(key=Key.OPENAI_API_KEY)
        if openai_access_token == "":
            raise CommandLineError("No OpenAI access token found")

    transcription_options = TranscriptionOptions(
        model=model,
        task=task,
        language=language,
        initial_prompt=parser.value(opts["initial_prompt"]),
        word_level_timings=parser.isSet(opts["word_timestamps"]),
        extract_speech=parser.isSet(opts["extract_speech"]),
        openai_access_token=openai_access_token,
    )

    _add_transcription_tasks(
        app,
        file_paths,
        model_path,
        transcription_options,
        output_formats,
        parser.value(opts["output_directory"]),
    )

    if parser.isSet(opts["hide_gui"]):
        app.hide_main_window = True


def add_merge_parser(subparsers):
    """Add multi-speaker merge command to CLI"""
    merge_parser = subparsers.add_parser(
        'merge',
        help='Merge multiple speaker transcriptions into a single file'
    )
    
    merge_parser.add_argument(
        'output',
        type=str,
        help='Output file path'
    )
    
    merge_parser.add_argument(
        'transcriptions',
        nargs='+',
        type=str,
        help='Transcription files in format: filepath:SpeakerName (e.g., track1.srt:John track2.srt:Mary)'
    )
    
    merge_parser.add_argument(
        '--time-delta',
        type=float,
        default=2.0,
        help='Maximum pause (seconds) between segments to merge from same speaker (default: 2.0)'
    )
    
    merge_parser.add_argument(
        '--no-consolidate',
        action='store_true',
        help='Do not consolidate consecutive lines from same speaker'
    )
    
    merge_parser.add_argument(
        '--format',
        choices=['txt', 'srt', 'json'],
        default='txt',
        help='Output format (default: txt)'
    )
    
    merge_parser.add_argument(
        '--no-timestamps',
        action='store_true',
        help='Exclude timestamps from text output'
    )
    
    merge_parser.add_argument(
        '--no-speaker',
        action='store_true',
        help='Exclude speaker labels from text output'
    )
    
    return merge_parser


def handle_merge_command(args):
    """Handle the merge subcommand"""
    # Parse transcription file arguments
    transcription_files = []
    for arg in args.transcriptions:
        if ':' not in arg:
            print(f"Error: Invalid format for transcription file: {arg}")
            print("Expected format: filepath:SpeakerName")
            sys.exit(1)
        
        file_path, speaker_id = arg.split(':', 1)
        transcription_files.append((file_path, speaker_id))
    
    try:
        merge_multi_speaker_transcriptions(
            transcription_files=transcription_files,
            output_path=args.output,
            time_delta=args.time_delta,
            consolidate=not args.no_consolidate,
            output_format=args.format,
            include_timestamps=not args.no_timestamps,
            include_speaker=not args.no_speaker
        )
    except Exception as e:
        print(f"Error merging transcriptions: {e}")
        logging.exception("Merge failed")
        sys.exit(1)


def parse(app: Application, parser: QCommandLineParser):
    parser.addPositionalArgument("<command>", "One of the following commands:\n- add")
    parser.parse(app.arguments())

    args = parser.positionalArguments()
    if len(args) == 0:
        parser.addHelpOption()
        parser.addVersionOption()
        parser.process(app)
        return

    command = args[0]
    if command == "add":
        _handle_add_command(app, parser)
    elif command == "merge":
        parser.clearPositionalArguments()
        parser.addPositionalArgument("transcriptions", "Transcription files", "[file:file ...]")
        parser.addPositionalArgument("output", "Output file")
        parser.process(app)

        class MergeArgs:
            pass

        merge_args = MergeArgs()
        merge_args.transcriptions = parser.positionalArguments()[:-1]
        merge_args.output = parser.positionalArguments()[-1]
        merge_args.time_delta = 2.0
        merge_args.no_consolidate = False
        merge_args.format = "txt"
        merge_args.no_timestamps = False
        merge_args.no_speaker = False

        for opt in parser.options():
            if opt.isSet():
                if opt == parser.optionForName("time-delta"):
                    merge_args.time_delta = opt.value()
                elif opt == parser.optionForName("no-consolidate"):
                    merge_args.no_consolidate = True
                elif opt == parser.optionForName("format"):
                    merge_args.format = opt.value()
                elif opt == parser.optionForName("no-timestamps"):
                    merge_args.no_timestamps = True
                elif opt == parser.optionForName("no-speaker"):
                    merge_args.no_speaker = True

        handle_merge_command(merge_args)

T = typing.TypeVar("T", bound=enum.Enum)


def parse_enum_option(
    option: QCommandLineOption, parser: QCommandLineParser, enum_class: typing.Type[T]
) -> T:
    try:
        return enum_class(parser.value(option))
    except ValueError:
        raise CommandLineError(f"Invalid value for --{option.names()[-1]} option.")


def join_values(enum_class: typing.Type[enum.Enum]) -> str:
    return ", ".join([v.value for v in enum_class])
