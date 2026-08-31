# Multi-Speaker Transcription Merging

Buzz now supports merging multiple transcription files from different speakers into a single, chronologically-ordered transcription with speaker identification.

## Quick Start

**GUI**: Tools → Merge Multi-Speaker Transcriptions...

**CLI**: `python -m buzz merge output.txt track1.srt:Speaker1 track2.srt:Speaker2`

**Supported formats**: SRT, VTT, JSON (Whisper), TXT (with timestamps)

## Use Case

When you have multiple audio tracks from the same conversation, with each track containing a different speaker's voice (for 100% speaker identification), you can:
1. Transcribe each track separately
2. Merge the transcriptions into a single file with proper timestamp synchronization
3. Automatically consolidate consecutive lines from the same speaker

## Features

- **Multi-format support**: Works with SRT, VTT, JSON (Whisper format), and TXT (plain text with timestamps) transcription files
- **Timestamp synchronization**: Merges segments chronologically based on timestamps
- **Speaker consolidation**: Combines consecutive segments from the same speaker based on configurable time delta
- **Multiple output formats**: Export to TXT, SRT, or JSON
- **Flexible timestamp formats**: Supports various timestamp notations in TXT files
- **Flexible options**: Control timestamps, speaker labels, and consolidation behavior

## Usage

### GUI Method

1. Open Buzz application
2. Go to **Tools → Merge Multi-Speaker Transcriptions...**
3. Click **Add File...** to add transcription files (at least 2 required)
4. For each file, specify the speaker name
5. Configure options:
   - **Time delta**: Maximum pause (in seconds) between segments before creating a line break (default: 2.0s)
   - **Consolidate consecutive speaker lines**: Merge segments from same speaker (recommended)
   - **Output format**: Choose between TXT, SRT, or JSON
   - **Include timestamps/speaker labels**: For text output
6. Choose output file location
7. Click **Merge**

### Command Line Method

```bash
# Basic usage
python -m buzz merge output.txt track1.srt:Speaker1 track2.srt:Speaker2

# With custom time delta
python -m buzz merge output.txt track1.srt:John track2.srt:Mary --time-delta 3.0

# Mix different input formats (SRT, VTT, JSON, TXT)
python -m buzz merge output.txt track1.srt:Alice track2.vtt:Bob track3.json:Charlie track4.txt:Diana

# Export as SRT
python -m buzz merge output.srt track1.json:Alice track2.json:Bob --format srt

# Without consolidation
python -m buzz merge output.txt track1.srt:Speaker1 track2.srt:Speaker2 --no-consolidate

# Text output without timestamps
python -m buzz merge output.txt track1.srt:A track2.srt:B --no-timestamps
```

### Python API

```python
from buzz.multi_speaker_merge import merge_multi_speaker_transcriptions

# Merge transcriptions
merge_multi_speaker_transcriptions(
    transcription_files=[
        ("path/to/speaker1.srt", "John"),
        ("path/to/speaker2.srt", "Mary"),
        ("path/to/speaker3.json", "Alice")
    ],
    output_path="merged_conversation.txt",
    time_delta=2.0,
    consolidate=True,
    output_format="txt",
    include_timestamps=True,
    include_speaker=True
)
```

### Advanced Usage

For more control, use the `MultiSpeakerTranscriptionMerger` class directly:

```python
from buzz.multi_speaker_merge import MultiSpeakerTranscriptionMerger
from pathlib import Path

merger = MultiSpeakerTranscriptionMerger(time_delta=2.5)

# Load and merge
segments = merger.merge_transcriptions([
    (Path("speaker1.srt"), "John"),
    (Path("speaker2.vtt"), "Mary")
])

# Consolidate
consolidated = merger.consolidate_speaker_lines(segments)

# Export
merger.export_to_text(consolidated, Path("output.txt"))
merger.export_to_srt(consolidated, Path("output.srt"))
merger.export_to_json(consolidated, Path("output.json"))
```

## Workflow Example

### 1. Prepare Audio Tracks
- `john_track.mp3` - Audio containing only John's voice
- `mary_track.mp3` - Audio containing only Mary's voice

### 2. Transcribe Each Track Separately
Use Buzz to transcribe each audio file:
- `john_track.mp3` → `john_track.srt`
- `mary_track.mp3` → `mary_track.srt`

### 3. Merge Transcriptions
```bash
python -m buzz merge conversation.txt john_track.srt:John mary_track.srt:Mary
```

### 4. Result
```
[00:00:02.150] John: Hello, how are you doing today?
[00:00:05.320] Mary: I'm doing great, thanks for asking!
[00:00:08.100] John: That's wonderful to hear. I wanted to discuss the project timeline.
[00:00:13.450] Mary: Sure, I have my notes ready. Let me pull them up.
```

## Parameters

### Time Delta
The `time_delta` parameter (default: 2.0 seconds) determines how consecutive segments from the same speaker are merged:
- If the pause between two segments from the same speaker is **≤ time_delta**, they are combined into one line
- If the pause is **> time_delta**, they remain separate lines

Example with `time_delta=2.0`:
```
[0.0-2.0] John: Hello
[2.5-4.0] John: How are you  # Merged (pause = 0.5s ≤ 2.0s)
[7.0-9.0] John: Great        # Not merged (pause = 3.0s > 2.0s)
```

### Consolidation
When enabled (default), consecutive segments from the same speaker are merged based on time_delta. When disabled, each original segment remains separate even if from the same speaker.

## Output Formats

### Text Format (.txt)
```
[00:00:02.150] John: Hello, how are you doing today?
[00:00:05.320] Mary: I'm doing great, thanks for asking!
```

### SRT Format (.srt)
```
1
00:00:02,150 --> 00:00:04,800
John: Hello, how are you doing today?

2
00:00:05,320 --> 00:00:08,100
Mary: I'm doing great, thanks for asking!
```

### JSON Format (.json)
```json
{
  "segments": [
    {
      "start": 2.15,
      "end": 4.8,
      "text": "Hello, how are you doing today?",
      "speaker": "John"
    },
    {
      "start": 5.32,
      "end": 8.1,
      "text": "I'm doing great, thanks for asking!",
      "speaker": "Mary"
    }
  ]
}
```

## Supported Input Formats

### SRT Format (`.srt`)
SubRip subtitle format with timestamps:
```
1
00:00:02,150 --> 00:00:04,800
Hello, how are you doing today?

2
00:00:05,320 --> 00:00:08,100
I'm doing great, thanks for asking!
```

### VTT Format (`.vtt`)
WebVTT subtitle format:
```
WEBVTT

00:00:02.150 --> 00:00:04.800
Hello, how are you doing today?

00:00:05.320 --> 00:00:08.100
I'm doing great, thanks for asking!
```

### JSON Format (`.json`)
Whisper JSON format with segments array:
```json
{
  "segments": [
    {
      "start": 2.15,
      "end": 4.8,
      "text": "Hello, how are you doing today?"
    },
    {
      "start": 5.32,
      "end": 8.1,
      "text": "I'm doing great, thanks for asking!"
    }
  ]
}
```

### TXT Format (`.txt`)
Plain text files with timestamps. Supports multiple timestamp formats:

**Format 1: Bracketed timestamps**
```
[00:00:02.150] Hello, how are you doing today?
[00:00:05.320] I'm doing great, thanks for asking!
[00:00:08.100] That's wonderful to hear.
```

**Format 2: Parenthesized timestamps**
```
(00:00:02.150) Hello, how are you doing today?
(00:00:05.320) I'm doing great, thanks for asking!
```

**Format 3: Plain timestamps with dash**
```
00:00:02.150 - Hello, how are you doing today?
00:00:05.320 - I'm doing great, thanks for asking!
```

**Format 4: SRT-style in TXT**
```
00:00:02.150 --> 00:00:04.800
Hello, how are you doing today?

00:00:05.320 --> 00:00:08.100
I'm doing great, thanks for asking!
```

**Supported timestamp formats in TXT files:**
- `HH:MM:SS.mmm` (e.g., `01:23:45.678`)
- `HH:MM:SS,mmm` (e.g., `01:23:45,678`)
- `MM:SS.mmm` (e.g., `23:45.678`)
- `MM:SS` (e.g., `23:45`)
- `SS.mmm` (e.g., `145.678`)
- `SS` (e.g., `145`)

All input formats must include timing information for proper synchronization.

## Tips

1. **Accurate timestamps**: Ensure your original transcriptions have accurate timestamps for best results
2. **Consistent timing**: All audio tracks should be synchronized (start at the same time)
3. **Speaker naming**: Use clear, consistent speaker names for easy identification
4. **Time delta tuning**: Adjust time_delta based on speaking pace (shorter for fast conversations, longer for slow)
5. **Quality check**: Always review the merged output to verify accuracy
6. **Mix formats freely**: You can merge files in different formats (e.g., SRT + VTT + JSON + TXT) in a single operation
7. **TXT file flexibility**: When using TXT files, you can use any supported timestamp format - the parser will auto-detect it
8. **Manual transcription edits**: TXT format is useful for manually edited transcriptions or when you only have simple timestamped text

## Troubleshooting

**Problem**: Segments are not merging properly
- **Solution**: Adjust the `time_delta` parameter. Try increasing it if segments should be merged, or decreasing if they shouldn't.

**Problem**: Timestamps are out of sync
- **Solution**: Ensure all source audio files started recording at the same time. You may need to manually adjust timestamps in source transcriptions.

**Problem**: Format not recognized
- **Solution**: Ensure files have correct extensions (.srt, .vtt, .json) or check file content follows the expected format.

**Problem**: Missing segments
- **Solution**: Verify all source transcription files contain timing information and are not empty.
