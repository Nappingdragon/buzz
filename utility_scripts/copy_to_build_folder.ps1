# Simple copy script - copies existing dist\Buzz to Buzz_build folder
# Run this AFTER you've already built with PyInstaller

Write-Host "=== Buzz Portable Copy to Buzz_build ===" -ForegroundColor Cyan
Write-Host ""

$SourceFolder = "dist\Buzz"
$TargetFolder = "..\Buzz_build"

# Check if source exists
if (-not (Test-Path $SourceFolder)) {
    Write-Host "ERROR: Source folder not found: $SourceFolder" -ForegroundColor Red
    Write-Host ""
    Write-Host "You need to build first. Run one of these commands:" -ForegroundColor Yellow
    Write-Host "  uv run pyinstaller --noconfirm Buzz.spec" -ForegroundColor White
    Write-Host "  OR" -ForegroundColor Yellow
    Write-Host "  uv run make dist/Buzz" -ForegroundColor White
    exit 1
}

if (-not (Test-Path "$SourceFolder\Buzz.exe")) {
    Write-Host "ERROR: Buzz.exe not found in $SourceFolder" -ForegroundColor Red
    exit 1
}

Write-Host "Source folder found: $SourceFolder" -ForegroundColor Green
Write-Host ""

# Clean target folder
if (Test-Path $TargetFolder) {
    Write-Host "Cleaning target folder: $TargetFolder" -ForegroundColor Yellow
    Remove-Item "$TargetFolder\*" -Recurse -Force -ErrorAction SilentlyContinue
} else {
    Write-Host "Creating target folder: $TargetFolder" -ForegroundColor Yellow
    New-Item -ItemType Directory -Path $TargetFolder | Out-Null
}

# Copy all files
Write-Host "Copying files..." -ForegroundColor Yellow
Copy-Item "$SourceFolder\*" -Destination $TargetFolder -Recurse -Force

# Verify copy
if (Test-Path "$TargetFolder\Buzz.exe") {
    Write-Host "Copy successful!" -ForegroundColor Green
    
    # Calculate size
    $TotalSize = (Get-ChildItem $TargetFolder -Recurse | Measure-Object -Property Length -Sum).Sum
    $SizeGB = [math]::Round($TotalSize / 1GB, 2)
    Write-Host "Total size: $SizeGB GB" -ForegroundColor Gray
} else {
    Write-Host "ERROR: Failed to copy files" -ForegroundColor Red
    exit 1
}

# Create README
Write-Host "Creating README..." -ForegroundColor Yellow
$ReadmeContent = @"
# Buzz Portable Build - Multi-Speaker Merge Edition

This is a portable build of Buzz with the multi-speaker transcription merge feature.

## How to Run

Simply double-click `Buzz.exe` to start the application.

## New Feature: Multi-Speaker Merge

Access via: **Tools → Merge Multi-Speaker Transcriptions...**

This feature allows you to:
- Combine transcriptions from multiple speaker tracks
- Automatically synchronize by timestamps
- Consolidate consecutive lines from the same speaker
- Detect and merge overlapping speech
- Export to TXT, SRT, or JSON formats

## Settings

Settings are saved to: `%LOCALAPPDATA%\Buzz\multi_speaker_merge.json`

You can edit this JSON file manually if needed.

## Supported Input Formats

- SRT (SubRip)
- VTT (WebVTT)
- JSON (Whisper format)
- TXT (with timestamps)

## System Requirements

- Windows 10/11 (64-bit)
- 8GB RAM minimum (16GB recommended)
- GPU with Vulkan support (optional, for faster transcription)

## Notes

- This is a portable build - no installation required
- You can move this entire folder anywhere
- First run may take a moment to initialize
- FFmpeg is included for audio processing

Built on: $(Get-Date -Format "yyyy-MM-dd HH:mm")

## Documentation

See docs\MULTI_SPEAKER_MERGE.md for detailed usage instructions.
"@

Set-Content -Path "$TargetFolder\README.txt" -Value $ReadmeContent

# Success!
Write-Host "`n=== Copy Complete! ===" -ForegroundColor Green
Write-Host ""
Write-Host "Portable build location:" -ForegroundColor Cyan
Write-Host "  $(Resolve-Path $TargetFolder)" -ForegroundColor White
Write-Host ""
Write-Host "To run Buzz:" -ForegroundColor Yellow
Write-Host "  1. Open: $TargetFolder" -ForegroundColor White
Write-Host "  2. Double-click: Buzz.exe" -ForegroundColor White
Write-Host ""
Write-Host "To create a ZIP archive:" -ForegroundColor Yellow
Write-Host "  Compress-Archive -Path '$TargetFolder' -DestinationPath 'Buzz-Portable.zip'" -ForegroundColor White
Write-Host ""
