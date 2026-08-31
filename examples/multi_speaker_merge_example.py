#!/usr/bin/env python3
"""
Example script demonstrating multi-speaker transcription merging.
Creates sample transcription files and merges them.
"""

import tempfile
from pathlib import Path
from buzz.multi_speaker_merge import merge_multi_speaker_transcriptions


def create_sample_srt(file_path: Path, segments: list):
    """Create a sample SRT file"""
    with open(file_path, 'w', encoding='utf-8') as f:
        for i, (start, end, text) in enumerate(segments, 1):
            f.write(f"{i}\n")
            f.write(f"{format_srt_time(start)} --> {format_srt_time(end)}\n")
            f.write(f"{text}\n\n")


def format_srt_time(seconds: float) -> str:
    """Format seconds as SRT timestamp"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds % 1) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def main():
    # Create temporary directory for sample files
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        
        print("Creating sample transcription files...")
        
        # Speaker 1 segments
        speaker1_segments = [
            (0.0, 3.5, "Hello, how are you doing today?"),
            (8.0, 11.5, "That's great to hear. I wanted to discuss our project."),
            (16.0, 20.0, "We need to finalize the timeline by next week."),
            (25.0, 28.5, "Exactly. Let's schedule a follow-up meeting."),
        ]
        
        # Speaker 2 segments
        speaker2_segments = [
            (4.0, 7.5, "I'm doing great, thanks for asking!"),
            (12.0, 15.5, "Sure, I have my notes ready. What's the priority?"),
            (21.0, 24.5, "I agree. I'll review the requirements this week."),
            (29.0, 32.0, "Sounds good. I'll send you some available times."),
        ]
        
        speaker1_file = tmpdir / "speaker1.srt"
        speaker2_file = tmpdir / "speaker2.srt"
        output_file = tmpdir / "merged_conversation.txt"
        
        create_sample_srt(speaker1_file, speaker1_segments)
        create_sample_srt(speaker2_file, speaker2_segments)
        
        print(f"Created: {speaker1_file}")
        print(f"Created: {speaker2_file}")
        print()
        
        # Merge transcriptions
        print("Merging transcriptions...")
        merge_multi_speaker_transcriptions(
            transcription_files=[
                (str(speaker1_file), "Alice"),
                (str(speaker2_file), "Bob")
            ],
            output_path=str(output_file),
            time_delta=2.0,
            consolidate=True,
            output_format="txt",
            include_timestamps=True,
            include_speaker=True
        )
        
        # Display result
        print("\n" + "="*70)
        print("MERGED TRANSCRIPTION:")
        print("="*70 + "\n")
        
        with open(output_file, 'r', encoding='utf-8') as f:
            print(f.read())
        
        print("="*70)
        print(f"\nMerged file saved to: {output_file}")
        print("\nExample completed successfully!")
        
        # Keep files for inspection
        input("\nPress Enter to clean up temporary files and exit...")


if __name__ == "__main__":
    main()
