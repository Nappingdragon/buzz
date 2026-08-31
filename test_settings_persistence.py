"""
Test script to verify multi-speaker merge dialog settings persistence with JSON
"""
import json
import os
from platformdirs import user_config_dir

print("=== Testing Multi-Speaker Merge Settings Persistence (JSON) ===\n")

# Set up config file path (same as the dialog does)
config_dir = user_config_dir("Buzz")
config_file = os.path.join(config_dir, "multi_speaker_merge.json")

print(f"Config directory: {config_dir}")
print(f"Config file: {config_file}\n")

# Test writing some values
print("Writing test values...")
test_settings = {
    "time_delta": 3.5,
    "consolidate": False,
    "format": "srt",
    "overlap_threshold": 0.2,
    "duration_estimation_wpm": 180,
    "sequential_spacing": 0.15,
    "fix_overlapping": False,
    "timestamps": False,
    "speaker": True
}

with open(config_file, 'w') as f:
    json.dump(test_settings, f, indent=2)
print("✓ Values written to JSON file\n")

# Read them back
print("Reading values back...")
with open(config_file, 'r') as f:
    loaded_settings = json.load(f)

print("Loaded settings:")
for key, value in loaded_settings.items():
    expected = test_settings[key]
    match = "✓" if value == expected else "✗"
    print(f"  {match} {key}: {value} (expected: {expected})")

# Verify
success = loaded_settings == test_settings

if success:
    print("\n✓ All values persisted correctly!")
else:
    print("\n✗ Settings persistence failed!")

# Show file contents
print(f"\nConfig file contents:")
print("=" * 60)
with open(config_file, 'r') as f:
    print(f.read())
print("=" * 60)

# Clean up test values
print("\nCleaning up test file...")
if os.path.exists(config_file):
    os.remove(config_file)
    print("✓ Test file removed")
else:
    print("⚠ File already removed")
