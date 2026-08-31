import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple
from enum import Enum


class TranscriptionFormat(Enum):
    """Supported transcription formats"""
    SRT = "srt"
    VTT = "vtt"
    JSON = "json"
    TXT = "txt"


@dataclass
class TimestampedSegment:
    """Represents a transcription segment with timing information"""
    start_time: float  # in seconds
    end_time: float
    text: str
    speaker_id: str
    
    def __repr__(self):
        return f"[{self.speaker_id} {self.start_time:.2f}-{self.end_time:.2f}] {self.text}"


class MultiSpeakerTranscriptionMerger:
    """
    Merges multiple transcription files from different speakers into a single
    chronologically-ordered transcription with speaker identification.
    """
    
    def __init__(self, time_delta: float = 2.0):
        """
        Initialize the merger.
        
        Args:
            time_delta: Maximum pause (in seconds) between segments from the same speaker
                       before creating a line break. Default is 2.0 seconds.
        """
        self.time_delta = time_delta
        self.logger = logging.getLogger(__name__)
    
    def parse_srt_file(self, file_path: Path, speaker_id: str) -> List[TimestampedSegment]:
        """Parse SRT subtitle file into timestamped segments"""
        segments = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            blocks = content.strip().split('\n\n')
            
            for block in blocks:
                lines = block.strip().split('\n')
                if len(lines) >= 3:
                    # Parse timestamp line (format: 00:00:00,000 --> 00:00:05,000)
                    timestamp_line = lines[1]
                    if '-->' in timestamp_line:
                        start_str, end_str = timestamp_line.split('-->')
                        start_time = self._parse_srt_timestamp(start_str.strip())
                        end_time = self._parse_srt_timestamp(end_str.strip())
                        
                        # Combine remaining lines as text
                        text = ' '.join(lines[2:]).strip()
                        
                        if text:
                            segments.append(TimestampedSegment(
                                start_time=start_time,
                                end_time=end_time,
                                text=text,
                                speaker_id=speaker_id
                            ))
        except Exception as e:
            self.logger.error(f"Error parsing SRT file {file_path}: {e}")
            raise
        
        return segments
    
    def parse_vtt_file(self, file_path: Path, speaker_id: str) -> List[TimestampedSegment]:
        """Parse VTT subtitle file into timestamped segments"""
        segments = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            # Skip WEBVTT header
            start_idx = 0
            for i, line in enumerate(lines):
                if line.strip().startswith('WEBVTT'):
                    start_idx = i + 1
                    break
            
            i = start_idx
            while i < len(lines):
                line = lines[i].strip()
                
                # Look for timestamp line (format: 00:00:00.000 --> 00:00:05.000)
                if '-->' in line:
                    start_str, end_str = line.split('-->')
                    start_time = self._parse_vtt_timestamp(start_str.strip())
                    end_time = self._parse_vtt_timestamp(end_str.strip())
                    
                    # Collect text lines until empty line
                    text_lines = []
                    i += 1
                    while i < len(lines) and lines[i].strip():
                        text_lines.append(lines[i].strip())
                        i += 1
                    
                    text = ' '.join(text_lines).strip()
                    if text:
                        segments.append(TimestampedSegment(
                            start_time=start_time,
                            end_time=end_time,
                            text=text,
                            speaker_id=speaker_id
                        ))
                
                i += 1
                
        except Exception as e:
            self.logger.error(f"Error parsing VTT file {file_path}: {e}")
            raise
        
        return segments
    
    def parse_json_file(self, file_path: Path, speaker_id: str) -> List[TimestampedSegment]:
        """Parse JSON transcription file (Whisper format) into timestamped segments"""
        segments = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Handle Whisper JSON format
            if 'segments' in data:
                for segment in data['segments']:
                    segments.append(TimestampedSegment(
                        start_time=segment['start'],
                        end_time=segment['end'],
                        text=segment['text'].strip(),
                        speaker_id=speaker_id
                    ))
            else:
                self.logger.warning(f"JSON file {file_path} does not contain 'segments' key")
                
        except Exception as e:
            self.logger.error(f"Error parsing JSON file {file_path}: {e}")
            raise
        
        return segments
    
    def parse_txt_file(self, file_path: Path, speaker_id: str) -> List[TimestampedSegment]:
        """
        Parse plain text file with timestamps into timestamped segments.
        
        Supports formats like:
        - [00:00:05] Text here
        - 00:00:05 - Text here
        - (00:00:05) Text here
        - 00:00:05.123 --> 00:00:10.456\nText here
        """
        segments = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            i = 0
            while i < len(lines):
                line = lines[i].strip()
                
                if not line:
                    i += 1
                    continue
                
                # Try different timestamp formats
                start_time = None
                end_time = None
                text = None
                
                # Format 1: SRT-style with arrow (00:00:05.123 --> 00:00:10.456)
                if '-->' in line:
                    parts = line.split('-->')
                    if len(parts) == 2:
                        try:
                            start_time = self._parse_flexible_timestamp(parts[0].strip())
                            end_time = self._parse_flexible_timestamp(parts[1].strip())
                            # Text is on next line(s)
                            i += 1
                            text_lines = []
                            while i < len(lines) and lines[i].strip() and '-->' not in lines[i]:
                                text_lines.append(lines[i].strip())
                                i += 1
                            text = ' '.join(text_lines).strip()
                            i -= 1  # Back up one line for the outer loop increment
                        except:
                            pass
                
                # Format 2: Bracketed timestamp [00:00:05] or [00:00:05.123]
                elif line.startswith('[') and ']' in line:
                    try:
                        end_bracket = line.index(']')
                        timestamp_str = line[1:end_bracket]
                        start_time = self._parse_flexible_timestamp(timestamp_str)
                        end_time = start_time + 2.0  # Default 2 second duration
                        text = line[end_bracket + 1:].strip()
                    except:
                        pass
                
                # Format 3: Parenthesized timestamp (00:00:05) or (00:00:05.123)
                elif line.startswith('(') and ')' in line:
                    try:
                        end_paren = line.index(')')
                        timestamp_str = line[1:end_paren]
                        start_time = self._parse_flexible_timestamp(timestamp_str)
                        end_time = start_time + 2.0  # Default 2 second duration
                        text = line[end_paren + 1:].strip()
                    except:
                        pass
                
                # Format 4: Plain timestamp at start (00:00:05 Text here or 00:00:05 - Text here)
                else:
                    words = line.split(None, 1)
                    if len(words) >= 1:
                        try:
                            # Try to parse first word as timestamp
                            timestamp_str = words[0].rstrip('-:')
                            start_time = self._parse_flexible_timestamp(timestamp_str)
                            end_time = start_time + 2.0  # Default 2 second duration
                            if len(words) > 1:
                                text = words[1].lstrip('- ').strip()
                            else:
                                text = ""
                        except:
                            pass
                
                # Add segment if we successfully parsed it
                if start_time is not None and text:
                    segments.append(TimestampedSegment(
                        start_time=start_time,
                        end_time=end_time,
                        text=text,
                        speaker_id=speaker_id
                    ))
                
                i += 1
                
        except Exception as e:
            self.logger.error(f"Error parsing TXT file {file_path}: {e}")
            raise
        
        return segments
    
    def _parse_flexible_timestamp(self, timestamp: str) -> float:
        """
        Parse various timestamp formats to seconds.
        Supports: HH:MM:SS.mmm, HH:MM:SS,mmm, MM:SS.mmm, MM:SS, SS.mmm, SS
        """
        timestamp = timestamp.strip().replace(',', '.')
        
        parts = timestamp.split(':')
        
        if len(parts) == 3:  # HH:MM:SS or HH:MM:SS.mmm
            h, m, s = parts
            return int(h) * 3600 + int(m) * 60 + float(s)
        elif len(parts) == 2:  # MM:SS or MM:SS.mmm
            m, s = parts
            return int(m) * 60 + float(s)
        elif len(parts) == 1:  # SS or SS.mmm
            return float(parts[0])
        else:
            raise ValueError(f"Invalid timestamp format: {timestamp}")
    
    def _parse_srt_timestamp(self, timestamp: str) -> float:
        """Convert SRT timestamp (HH:MM:SS,mmm) to seconds"""
        time_part, ms_part = timestamp.replace(',', '.').rsplit('.', 1)
        h, m, s = map(int, time_part.split(':'))
        ms = int(ms_part)
        return h * 3600 + m * 60 + s + ms / 1000.0
    
    def _parse_vtt_timestamp(self, timestamp: str) -> float:
        """Convert VTT timestamp (HH:MM:SS.mmm or MM:SS.mmm) to seconds"""
        parts = timestamp.split(':')
        if len(parts) == 3:
            h, m, s = parts
            return int(h) * 3600 + int(m) * 60 + float(s)
        elif len(parts) == 2:
            m, s = parts
            return int(m) * 60 + float(s)
        else:
            raise ValueError(f"Invalid VTT timestamp format: {timestamp}")
    
    def _format_timestamp(self, seconds: float) -> str:
        """Format seconds as HH:MM:SS.mmm"""
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = seconds % 60
        return f"{h:02d}:{m:02d}:{s:06.3f}"
    
    def detect_format(self, file_path: Path) -> TranscriptionFormat:
        """Detect transcription file format based on extension and content"""
        extension = file_path.suffix.lower()
        
        if extension == '.srt':
            return TranscriptionFormat.SRT
        elif extension == '.vtt':
            return TranscriptionFormat.VTT
        elif extension == '.json':
            return TranscriptionFormat.JSON
        elif extension == '.txt':
            return TranscriptionFormat.TXT
        else:
            # Try to detect from content
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    first_lines = f.read(200)
                    
                if 'WEBVTT' in first_lines:
                    return TranscriptionFormat.VTT
                elif '-->' in first_lines and ',' in first_lines:
                    return TranscriptionFormat.SRT
                elif first_lines.strip().startswith('{'):
                    return TranscriptionFormat.JSON
            except:
                pass
        
        raise ValueError(f"Unable to detect format for file: {file_path}")
    
    def load_transcription(self, file_path: Path, speaker_id: str, 
                          format: Optional[TranscriptionFormat] = None) -> List[TimestampedSegment]:
        """
        Load a transcription file and return timestamped segments.
        
        Args:
            file_path: Path to the transcription file
            speaker_id: Identifier for this speaker (e.g., "Speaker 1", "John", etc.)
            format: File format (auto-detected if None)
        
        Returns:
            List of timestamped segments
        """
        if format is None:
            format = self.detect_format(file_path)
        
        self.logger.info(f"Loading {format.value} file for {speaker_id}: {file_path}")
        
        if format == TranscriptionFormat.SRT:
            return self.parse_srt_file(file_path, speaker_id)
        elif format == TranscriptionFormat.VTT:
            return self.parse_vtt_file(file_path, speaker_id)
        elif format == TranscriptionFormat.JSON:
            return self.parse_json_file(file_path, speaker_id)
        elif format == TranscriptionFormat.TXT:
            return self.parse_txt_file(file_path, speaker_id)
        else:
            raise ValueError(f"Unsupported format: {format}")
    
    def merge_transcriptions(self, transcription_files: List[Tuple[Path, str]]) -> List[TimestampedSegment]:
        """
        Merge multiple transcription files into a single chronologically-ordered list.
        
        Args:
            transcription_files: List of (file_path, speaker_id) tuples
        
        Returns:
            Merged list of segments sorted by timestamp
        """
        all_segments = []
        
        for file_path, speaker_id in transcription_files:
            segments = self.load_transcription(file_path, speaker_id)
            all_segments.extend(segments)
            self.logger.info(f"Loaded {len(segments)} segments for {speaker_id}")
        
        # Sort by start time
        all_segments.sort(key=lambda x: x.start_time)
        
        self.logger.info(f"Merged total of {len(all_segments)} segments")
        return all_segments
    
    def consolidate_speaker_lines(self, segments: List[TimestampedSegment]) -> List[TimestampedSegment]:
        """
        Consolidate consecutive segments from the same speaker into single lines.
        Segments are merged if the pause between them is less than time_delta.
        
        Args:
            segments: List of timestamped segments (should be sorted by time)
        
        Returns:
            Consolidated list of segments
        """
        if not segments:
            return []
        
        consolidated = []
        current = segments[0]
        
        for next_segment in segments[1:]:
            # Check if we should merge with current segment
            if (next_segment.speaker_id == current.speaker_id and 
                next_segment.start_time - current.end_time <= self.time_delta):
                # Merge segments
                current = TimestampedSegment(
                    start_time=current.start_time,
                    end_time=next_segment.end_time,
                    text=current.text + ' ' + next_segment.text,
                    speaker_id=current.speaker_id
                )
            else:
                # Save current and start new segment
                consolidated.append(current)
                current = next_segment
        
        # Don't forget the last segment
        consolidated.append(current)
        
        self.logger.info(f"Consolidated {len(segments)} segments into {len(consolidated)} lines")
        return consolidated
    
    def export_to_text(self, segments: List[TimestampedSegment], output_path: Path,
                      include_timestamps: bool = True, include_speaker: bool = True):
        """
        Export merged transcription to a text file.
        
        Args:
            segments: List of timestamped segments
            output_path: Path for output file
            include_timestamps: Whether to include timestamps in output
            include_speaker: Whether to include speaker labels
        """
        with open(output_path, 'w', encoding='utf-8') as f:
            for segment in segments:
                line_parts = []
                
                if include_timestamps:
                    line_parts.append(f"[{self._format_timestamp(segment.start_time)}]")
                
                if include_speaker:
                    line_parts.append(f"{segment.speaker_id}:")
                
                line_parts.append(segment.text)
                
                f.write(' '.join(line_parts) + '\n')
        
        self.logger.info(f"Exported transcription to {output_path}")
    
    def export_to_srt(self, segments: List[TimestampedSegment], output_path: Path):
        """Export merged transcription to SRT format with speaker labels"""
        with open(output_path, 'w', encoding='utf-8') as f:
            for i, segment in enumerate(segments, 1):
                # Sequence number
                f.write(f"{i}\n")
                
                # Timestamp
                start = self._format_srt_timestamp(segment.start_time)
                end = self._format_srt_timestamp(segment.end_time)
                f.write(f"{start} --> {end}\n")
                
                # Text with speaker label
                f.write(f"{segment.speaker_id}: {segment.text}\n\n")
        
        self.logger.info(f"Exported transcription to SRT: {output_path}")
    
    def _format_srt_timestamp(self, seconds: float) -> str:
        """Format seconds as SRT timestamp (HH:MM:SS,mmm)"""
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        ms = int((seconds % 1) * 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
    
    def export_to_json(self, segments: List[TimestampedSegment], output_path: Path):
        """Export merged transcription to JSON format"""
        data = {
            "segments": [
                {
                    "start": seg.start_time,
                    "end": seg.end_time,
                    "text": seg.text,
                    "speaker": seg.speaker_id
                }
                for seg in segments
            ]
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        self.logger.info(f"Exported transcription to JSON: {output_path}")


def merge_multi_speaker_transcriptions(
    transcription_files: List[Tuple[str, str]],
    output_path: str,
    time_delta: float = 2.0,
    consolidate: bool = True,
    output_format: str = "txt",
    include_timestamps: bool = True,
    include_speaker: bool = True
) -> None:
    """
    Convenience function to merge multiple speaker transcriptions.
    
    Args:
        transcription_files: List of (file_path, speaker_id) tuples
        output_path: Path for output file
        time_delta: Maximum pause between segments to merge (seconds)
        consolidate: Whether to consolidate consecutive speaker lines
        output_format: Output format ("txt", "srt", "json")
        include_timestamps: Include timestamps in text output
        include_speaker: Include speaker labels in text output
    """
    logging.basicConfig(level=logging.INFO)
    
    merger = MultiSpeakerTranscriptionMerger(time_delta=time_delta)
    
    # Convert string paths to Path objects
    file_tuples = [(Path(f), speaker) for f, speaker in transcription_files]
    
    # Merge transcriptions
    segments = merger.merge_transcriptions(file_tuples)
    
    # Consolidate if requested
    if consolidate:
        segments = merger.consolidate_speaker_lines(segments)
    
    # Export based on format
    output_path_obj = Path(output_path)
    
    if output_format == "txt":
        merger.export_to_text(segments, output_path_obj, include_timestamps, include_speaker)
    elif output_format == "srt":
        merger.export_to_srt(segments, output_path_obj)
    elif output_format == "json":
        merger.export_to_json(segments, output_path_obj)
    else:
        raise ValueError(f"Unsupported output format: {output_format}")
    
    print(f"Successfully merged {len(transcription_files)} transcription files")
    print(f"Output saved to: {output_path}")


if __name__ == "__main__":
    # Example usage
    import sys
    
    if len(sys.argv) < 3:
        print("Usage: python multi_speaker_merge.py output_file speaker1_file:Speaker1 speaker2_file:Speaker2 ...")
        print("Example: python multi_speaker_merge.py merged.txt track1.srt:John track2.srt:Mary")
        sys.exit(1)
    
    output_file = sys.argv[1]
    
    files = []
    for arg in sys.argv[2:]:
        if ':' in arg:
            file_path, speaker_id = arg.split(':', 1)
            files.append((file_path, speaker_id))
        else:
            print(f"Warning: Skipping invalid argument: {arg}")
    
    if not files:
        print("Error: No valid transcription files specified")
        sys.exit(1)
    
    merge_multi_speaker_transcriptions(
        transcription_files=files,
        output_path=output_file,
        time_delta=2.0,
        consolidate=True,
        output_format="txt"
    )
