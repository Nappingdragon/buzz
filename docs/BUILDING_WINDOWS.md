# Building Buzz for Windows

This guide explains how to build a Windows executable installer for Buzz with your multi-speaker merge feature.

## Prerequisites

You should already have these from development (based on CONTRIBUTING.md):
- ✅ Git
- ✅ Python
- ✅ Chocolatey
- ✅ Make, CMake
- ✅ FFmpeg
- ✅ Build Tools for Visual Studio 2022
- ✅ Vulkan SDK
- ✅ uv package manager

## Build Steps

### 1. Ensure Dependencies are Installed

Make sure you have PyInstaller:
```powershell
uv add pyinstaller
```

### 2. Clean Previous Builds (Optional but Recommended)

```powershell
make clean
```

This removes:
- `buzz/whisper_cpp/`
- `whisper.cpp/build/`
- `dist/*`
- Python cache files

### 3. Build Whisper.cpp (if not already built)

```powershell
uv run make buzz/whisper_cpp
```

This compiles Whisper.cpp with Vulkan support and copies the binaries to `buzz/whisper_cpp/`.

### 4. Update Version Number (Optional)

If you want to mark this as a custom version, edit these files:
- `buzz/__version__.py`
- `pyproject.toml`
- `Makefile` (first line: `version := 1.4.5`)

Example for a custom build:
```python
# buzz/__version__.py
VERSION = "1.4.5-multispeaker"
```

### 5. Build the Application

```powershell
uv run pyinstaller --noconfirm Buzz.spec
```

Or use the Makefile:
```powershell
make dist/Buzz
```

This will:
- Read `Buzz.spec` configuration
- Bundle all dependencies (PyQt6, torch, faster-whisper, etc.)
- Include whisper.cpp binaries
- Include FFmpeg binaries
- Include all plugin folders
- Create `dist/Buzz/` folder with all files

**Note**: This may take 5-15 minutes depending on your system.

### 6. Test the Build

Before creating the installer, test the executable:
```powershell
cd dist\Buzz
.\Buzz.exe
```

Verify:
- ✅ Application starts
- ✅ Tools → Merge Multi-Speaker Transcriptions opens
- ✅ Settings persist after closing
- ✅ Config file created at `%LOCALAPPDATA%\Buzz\multi_speaker_merge.json`

### 7. Create the Installer

```powershell
make bundle_windows
```

Or directly:
```powershell
iscc installer.iss
```

This uses Inno Setup to create an installer at:
```
dist/Buzz-Setup-<version>.exe
```

The installer will:
- Install to `C:\Program Files (x86)\Buzz\`
- Create Start Menu shortcuts
- Create Desktop shortcut (optional)
- Add uninstaller

## Troubleshooting

### Missing DLLs

If you get "DLL not found" errors:

1. Check `dll_backup/` folder exists with `SDL2.dll`
2. Ensure SSL libraries are included (the build checks for these)
3. Copy manually if needed:
```powershell
cp dll_backup/SDL2.dll dist/Buzz/
```

### PyInstaller Errors

If PyInstaller fails:

1. **Clear PyInstaller cache**:
```powershell
uv run pyinstaller --clean --noconfirm Buzz.spec
```

2. **Debug mode** (shows console for errors):
```powershell
$env:PYINSTALLER_DEBUG="1"
uv run pyinstaller --noconfirm Buzz.spec
```

### Import Errors

If the built app crashes on startup:

1. Check `dist/Buzz/_internal/` contains all required packages
2. Verify `Buzz.spec` includes your new imports
3. Add missing imports to `hiddenimports` in `Buzz.spec` if needed

### Missing Multi-Speaker Merge

If the menu item doesn't appear:

1. Ensure `buzz/multi_speaker_merge.py` exists
2. Verify `buzz/widgets/multi_speaker_merge_dialog.py` exists  
3. Check `buzz/widgets/main_window.py` has the menu integration
4. Rebuild from scratch with `make clean` then `make dist/Buzz`

## File Structure of Built Application

```
dist/Buzz/
├── Buzz.exe                    # Main executable
├── _internal/                  # All dependencies
│   ├── base_library.zip        # Python standard library
│   ├── buzz/                   # Your application code
│   │   ├── multi_speaker_merge.py
│   │   ├── widgets/
│   │   │   └── multi_speaker_merge_dialog.py
│   │   └── whisper_cpp/        # Whisper binaries
│   ├── PyQt6/                  # GUI framework
│   ├── torch/                  # Deep learning
│   ├── faster_whisper/         # Whisper implementation
│   ├── plugins/                # Plugin folders
│   └── [many DLL files]        # Dependencies
├── ffmpeg.exe                  # Audio processing
└── ffprobe.exe                 # Audio info
```

## Distribution

### For Personal Use

Just run the installer:
```
dist/Buzz-Setup-1.4.5.exe
```

### For Sharing

Create a zip file:
```powershell
Compress-Archive -Path "dist\Buzz" -DestinationPath "Buzz-1.4.5-multispeaker-windows.zip"
```

Or share the installer exe directly.

### Testing Installation

1. Uninstall any existing Buzz version
2. Run your new installer
3. Launch Buzz from Start Menu
4. Test the multi-speaker merge feature

## Quick Build Script

Save this as `build.ps1` for easy building:

```powershell
# Quick build script for Buzz

Write-Host "=== Buzz Windows Build Script ===" -ForegroundColor Cyan

# Step 1: Clean
Write-Host "`n[1/4] Cleaning previous builds..." -ForegroundColor Yellow
make clean

# Step 2: Build Whisper.cpp (if needed)
if (-not (Test-Path "buzz\whisper_cpp\whisper-cli.exe")) {
    Write-Host "`n[2/4] Building Whisper.cpp..." -ForegroundColor Yellow
    uv run make buzz/whisper_cpp
} else {
    Write-Host "`n[2/4] Whisper.cpp already built, skipping..." -ForegroundColor Green
}

# Step 3: Build application
Write-Host "`n[3/4] Building application with PyInstaller..." -ForegroundColor Yellow
uv run pyinstaller --noconfirm Buzz.spec

# Step 4: Create installer
Write-Host "`n[4/4] Creating installer..." -ForegroundColor Yellow
iscc installer.iss

Write-Host "`n=== Build Complete! ===" -ForegroundColor Green
Write-Host "Installer: dist\Buzz-Setup-*.exe" -ForegroundColor Cyan
Write-Host "Portable: dist\Buzz\" -ForegroundColor Cyan
```

Run with:
```powershell
.\build.ps1
```

## Notes

- The build includes GPU support (CUDA) automatically
- Plugin system is included
- All translations are compiled and included
- FFmpeg is bundled for audio processing
- Build size is typically 2-3 GB due to PyTorch and models

## Next Steps

After building successfully:
1. Test the installer on a clean Windows VM if possible
2. Document the multi-speaker merge feature in release notes
3. Consider creating a GitHub release with the installer
4. Update README.md with new feature information

Happy building! 🎉
