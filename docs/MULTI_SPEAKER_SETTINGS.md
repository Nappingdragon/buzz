# Multi-Speaker Merge Dialog - Settings Persistence Implementation

## Overview
The multi-speaker merge dialog now uses a **local JSON configuration file** instead of Windows registry, with **automatic save on every change**.

## Changes Made

### 1. **Switched from QSettings to JSON file**
- **Location**: `%APPDATA%\Buzz\multi_speaker_merge.json` (Windows)
- Uses `platformdirs.user_config_dir("Buzz")` for cross-platform compatibility
- Human-readable JSON format for easy debugging/manual editing

### 2. **Auto-save on every change**
All settings are saved immediately when changed:
- ✅ Spin boxes (time_delta, overlap_threshold, WPM, spacing)
- ✅ Checkboxes (consolidate, fix_overlapping, timestamps, speaker)
- ✅ Combo box (output format)

### 3. **Save on dialog close**
Settings are saved when:
- ✅ Clicking the **"Close"** button (via `reject()`)
- ✅ Clicking the **X** button (via `closeEvent()`)
- ✅ Pressing **Escape** key (via `reject()`)
- ✅ After successful merge (backup save)

## Implementation Details

### Config File Location
```python
from platformdirs import user_config_dir
import os

config_dir = user_config_dir("Buzz")  # e.g., C:\Users\<user>\AppData\Local\Buzz
config_file = os.path.join(config_dir, "multi_speaker_merge.json")
```

### JSON Structure
```json
{
  "time_delta": 2.0,
  "overlap_threshold": 0.1,
  "duration_estimation_wpm": 150,
  "sequential_spacing": 0.1,
  "consolidate": true,
  "fix_overlapping": true,
  "timestamps": true,
  "speaker": true,
  "format": "txt"
}
```

### Auto-save Connections
```python
# All value changes trigger immediate save
self.time_delta_spin.valueChanged.connect(self._save_settings)
self.overlap_threshold_spin.valueChanged.connect(self._save_settings)
self.wpm_spin.valueChanged.connect(self._save_settings)
self.spacing_spin.valueChanged.connect(self._save_settings)
self.consolidate_check.toggled.connect(self._save_settings)
self.fix_overlapping_check.toggled.connect(self._save_settings)
self.timestamps_check.toggled.connect(self._save_settings)
self.speaker_check.toggled.connect(self._save_settings)
self.format_combo.currentTextChanged.connect(self._save_settings)
```

### Close Handlers
```python
def reject(self):
    """Handle Close button, Escape key"""
    self._save_settings()
    super().reject()

def closeEvent(self, event):
    """Handle X button"""
    self._save_settings()
    super().closeEvent(event)
```

## Benefits

### ✅ Local File Storage
- No registry clutter
- Easy to backup/restore settings
- Can be version controlled
- Easy to inspect and debug

### ✅ Immediate Persistence
- Settings saved on every change
- No risk of losing preferences
- Works even if app crashes

### ✅ Cross-Platform
- Uses `platformdirs` for proper OS-specific paths
- Works on Windows, macOS, Linux

### ✅ Reset to Defaults
- "Reset to Defaults" button restores factory settings
- Doesn't auto-save after reset (user can adjust before closing)

## Testing

To manually test:
1. Open the dialog: **Tools → Merge Multi-Speaker Transcriptions...**
2. Change any setting (e.g., time delta to 3.5)
3. Close the dialog with any method (Close button or X)
4. Check config file exists at: `%APPDATA%\Local\Buzz\multi_speaker_merge.json`
5. Reopen the dialog - settings should be restored

To view your config file on Windows:
```powershell
notepad "$env:LOCALAPPDATA\Buzz\multi_speaker_merge.json"
```

## Troubleshooting

### Settings not persisting?
- Check file exists: `%LOCALAPPDATA%\Buzz\multi_speaker_merge.json`
- Check file permissions (should be writable)
- Check file contents (should be valid JSON)

### Want to reset all settings?
- Use the "Reset to Defaults" button, OR
- Delete the config file manually

### Manual editing
You can edit the JSON file with any text editor while the app is closed.
Changes will be loaded next time you open the dialog.
