# Quick build script for Buzz Windows - Portable Build to Buzz_build folder

Write-Host "=== Buzz Windows Portable Build Script ===" -ForegroundColor Cyan
Write-Host ""

$TargetFolder = "..\Buzz_build"

# Step 1: Clean PyInstaller output only.
# NOTE: 'make clean' is intentionally NOT used, because it deletes buzz\whisper_cpp
# and whisper.cpp\build, which are slow to rebuild and need a full toolchain.
Write-Host "[1/5] Cleaning previous PyInstaller output..." -ForegroundColor Yellow
if (Test-Path "dist") { Remove-Item "dist" -Recurse -Force -ErrorAction SilentlyContinue }
if (Test-Path "build\Buzz") { Remove-Item "build\Buzz" -Recurse -Force -ErrorAction SilentlyContinue }

# The target folder is cleaned later, only after PyInstaller has succeeded.

# Step 2: Build Whisper.cpp (if needed)
if (-not (Test-Path "buzz\whisper_cpp\whisper-cli.exe")) {
    Write-Host "`n[2/5] Building Whisper.cpp (this may take a while)..." -ForegroundColor Yellow
    uv run make buzz/whisper_cpp
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Whisper.cpp build failed!" -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "`n[2/5] Whisper.cpp already built, skipping..." -ForegroundColor Green
}

# Step 3: Build application
Write-Host "`n[3/5] Building application with PyInstaller (this will take 5-15 minutes)..." -ForegroundColor Yellow
uv run pyinstaller --noconfirm Buzz.spec
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: PyInstaller build failed!" -ForegroundColor Red
    exit 1
}

# Step 4: Verify build
if (Test-Path "dist\Buzz\Buzz.exe") {
    Write-Host "`nBuild verification: Buzz.exe found!" -ForegroundColor Green
} else {
    Write-Host "`nERROR: Buzz.exe not found in dist\Buzz\" -ForegroundColor Red
    exit 1
}

# Step 5: Copy to Buzz_build folder
Write-Host "`n[4/5] Copying portable build to $TargetFolder..." -ForegroundColor Yellow

# Create target folder if it doesn't exist
if (-not (Test-Path $TargetFolder)) {
    New-Item -ItemType Directory -Path $TargetFolder | Out-Null
} else {
    # Build succeeded, so it is now safe to clear the old portable build
    Write-Host "Cleaning target folder: $TargetFolder" -ForegroundColor Yellow
    Remove-Item "$TargetFolder\*" -Recurse -Force -ErrorAction SilentlyContinue
}

# Copy all files from dist\Buzz to Buzz_build
Copy-Item "dist\Buzz\*" -Destination $TargetFolder -Recurse -Force

if (Test-Path "$TargetFolder\Buzz.exe") {
    Write-Host "Portable build copied successfully!" -ForegroundColor Green
    
    # Calculate size
    $TotalSize = (Get-ChildItem $TargetFolder -Recurse | Measure-Object -Property Length -Sum).Sum
    $SizeGB = [math]::Round($TotalSize / 1GB, 2)
    Write-Host "Total size: $SizeGB GB" -ForegroundColor Gray
} else {
    Write-Host "ERROR: Failed to copy files to $TargetFolder" -ForegroundColor Red
    exit 1
}

# Step 6: Create a README in the portable folder
Write-Host "`n[5/5] Creating README..." -ForegroundColor Yellow
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
"@

Set-Content -Path "$TargetFolder\README.txt" -Value $ReadmeContent

# Success!
Write-Host "`n=== Build Complete! ===" -ForegroundColor Green
Write-Host ""
Write-Host "Portable build location:" -ForegroundColor Cyan
Write-Host "  $(Resolve-Path $TargetFolder)" -ForegroundColor White
Write-Host ""
Write-Host "To run Buzz:" -ForegroundColor Yellow
Write-Host "  1. Navigate to: $TargetFolder" -ForegroundColor White
Write-Host "  2. Double-click: Buzz.exe" -ForegroundColor White
Write-Host ""
Write-Host "To create a ZIP archive:" -ForegroundColor Yellow
Write-Host "  Compress-Archive -Path '$TargetFolder' -DestinationPath 'Buzz-Portable.zip'" -ForegroundColor White

Write-Host "  1. Test: dist\Buzz\Buzz.exe" -ForegroundColor White
Write-Host "  2. Install: dist\Buzz-Setup-*.exe" -ForegroundColor White
Write-Host ""
