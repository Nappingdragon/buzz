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
        self.overlap_threshold = 0.1  # Default overlap threshold in seconds
        self.duration_estimation_wpm = 150  # Words per minute for duration estimation
        self.sequential_spacing = 0.1  # Gap between consolidated speakers
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
    
    def detect_and_merge_overlapping_speech(self, segments: List[TimestampedSegment]) -> List[TimestampedSegment]:
        """
        Detect and intelligently merge segments where speakers talk simultaneously or in very rapid succession.
        
        When speakers overlap or speak with minimal gaps:
        - Groups segments that are very close together in time
        - Consolidates each speaker's text within the overlap
        - Orders by: shortest line first (typically interjections), then by who started first
        
        Args:
            segments: List of timestamped segments (should be sorted by time)
        
        Returns:
            List with overlapping speech consolidated
        """
        if not segments:
            return []
        
        result = []
        i = 0
        
        while i < len(segments):
            current = segments[i]
            overlapping_group = [current]
            
            # Find all segments that overlap or are very close in time
            j = i + 1
            while j < len(segments):
                next_seg = segments[j]
                
                # Check if next segment overlaps or is very close to any in the group
                is_related = False
                for seg in overlapping_group:
                    # Calculate overlap duration (can be negative for gap)
                    overlap_start = max(seg.start_time, next_seg.start_time)
                    overlap_end = min(seg.end_time, next_seg.end_time)
                    overlap_duration = overlap_end - overlap_start
                    
                    # Also check gap between segments (time between end of one and start of next)
                    gap = next_seg.start_time - seg.end_time
                    
                    # Consider related if:
                    # 1. They overlap (overlap_duration >= 0) OR
                    # 2. Gap is very small (less than overlap_threshold) AND they're different speakers
                    if (overlap_duration >= -self.overlap_threshold and 
                        next_seg.speaker_id != seg.speaker_id):
                        # Very close in time and different speakers = likely interleaved speech
                        is_related = True
                        break
                
                if is_related:
                    overlapping_group.append(next_seg)
                    j += 1
                else:
                    break
            
            # Process the overlapping group
            if len(overlapping_group) > 1:
                # Check if this is truly interleaved (multiple speakers in short timeframe)
                speakers_in_group = set(seg.speaker_id for seg in overlapping_group)
                if len(speakers_in_group) > 1:
                    # Multiple speakers in quick succession - merge intelligently
                    merged = self._merge_overlapping_group(overlapping_group)
                    result.extend(merged)
                else:
                    # Same speaker, just add all segments
                    result.extend(overlapping_group)
            else:
                # Single segment, no overlap
                result.append(current)
            
            i = j if j > i + 1 else i + 1
        
        self.logger.info(f"Processed overlapping speech: {len(segments)} -> {len(result)} segments")
        return result
    
    def _merge_overlapping_group(self, group: List[TimestampedSegment]) -> List[TimestampedSegment]:
        """
        Merge a group of overlapping segments intelligently.
        
        Strategy:
        1. Group segments by speaker
        2. Consolidate each speaker's text
        3. Sort by: text length (shorter first), then start time (earlier first)
        4. Adjust timestamps to be sequential
        """
        # Group by speaker
        speaker_segments = {}
        for seg in group:
            if seg.speaker_id not in speaker_segments:
                speaker_segments[seg.speaker_id] = []
            speaker_segments[seg.speaker_id].append(seg)
        
        # Consolidate each speaker's segments
        consolidated_speakers = []
        for speaker_id, segs in speaker_segments.items():
            # Sort by start time
            segs.sort(key=lambda x: x.start_time)
            
            # Merge all text for this speaker
            combined_text = ' '.join(seg.text for seg in segs)
            earliest_start = min(seg.start_time for seg in segs)
            latest_end = max(seg.end_time for seg in segs)
            
            consolidated_speakers.append({
                'speaker_id': speaker_id,
                'text': combined_text,
                'start_time': earliest_start,
                'end_time': latest_end,
                'text_length': len(combined_text.strip())
            })
        
        # Sort by: shortest text first (interjections), then earliest start time
        consolidated_speakers.sort(key=lambda x: (x['text_length'], x['start_time']))
        
        # Create output segments with adjusted timestamps
        result = []
        current_time = consolidated_speakers[0]['start_time']
        
        for speaker_data in consolidated_speakers:
            # Estimate duration based on text length (rough approximation)
            # Use instance variable for WPM
            text_length = len(speaker_data['text'].strip())
            estimated_duration = max(0.5, text_length / (self.duration_estimation_wpm * 5 / 60))  # minimum 0.5 seconds
            
            result.append(TimestampedSegment(
                start_time=current_time,
                end_time=current_time + estimated_duration,
                text=speaker_data['text'].strip(),
                speaker_id=speaker_data['speaker_id']
            ))
            
            current_time += estimated_duration + self.sequential_spacing  # Configurable gap between speakers
        
        return result
    
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
    fix_overlapping_speech: bool = True,
    overlap_threshold: float = 0.1,
    duration_estimation_wpm: int = 150,
    sequential_spacing: float = 0.1,
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
        fix_overlapping_speech: Whether to detect and intelligently merge overlapping speech
        overlap_threshold: Max time gap to consider as overlapping (seconds)
        duration_estimation_wpm: Speaking rate for duration estimation (words per minute)
        sequential_spacing: Gap between consolidated speakers (seconds)
        output_format: Output format ("txt", "srt", "json")
        include_timestamps: Include timestamps in text output
        include_speaker: Include speaker labels in text output
    """
    logging.basicConfig(level=logging.INFO)
    
    merger = MultiSpeakerTranscriptionMerger(time_delta=time_delta)
    
    # Set overlap parameters
    merger.overlap_threshold = overlap_threshold
    merger.duration_estimation_wpm = duration_estimation_wpm
    merger.sequential_spacing = sequential_spacing
    
    # Convert string paths to Path objects
    file_tuples = [(Path(f), speaker) for f, speaker in transcription_files]
    
    # Merge transcriptions
    segments = merger.merge_transcriptions(file_tuples)
    
    # Fix overlapping speech if requested (before consolidation)
    if fix_overlapping_speech:
        segments = merger.detect_and_merge_overlapping_speech(segments)
    
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
