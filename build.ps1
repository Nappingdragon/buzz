# Quick build script for Buzz Windows

Write-Host "=== Buzz Windows Build Script ===" -ForegroundColor Cyan
Write-Host ""

# Step 1: Clean
Write-Host "[1/4] Cleaning previous builds..." -ForegroundColor Yellow
make clean
if ($LASTEXITCODE -ne 0) {
    Write-Host "Warning: Clean step had issues, continuing anyway..." -ForegroundColor Yellow
}

# Step 2: Build Whisper.cpp (if needed)
if (-not (Test-Path "buzz\whisper_cpp\whisper-cli.exe")) {
    Write-Host "`n[2/4] Building Whisper.cpp (this may take a while)..." -ForegroundColor Yellow
    uv run make buzz/whisper_cpp
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Whisper.cpp build failed!" -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "`n[2/4] Whisper.cpp already built, skipping..." -ForegroundColor Green
}

# Step 3: Build application
Write-Host "`n[3/4] Building application with PyInstaller (this will take 5-15 minutes)..." -ForegroundColor Yellow
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

# Step 5: Create installer
Write-Host "`n[4/4] Creating installer with Inno Setup..." -ForegroundColor Yellow
iscc installer.iss
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Installer creation failed!" -ForegroundColor Red
    Write-Host "Make sure Inno Setup is installed and in PATH" -ForegroundColor Yellow
    exit 1
}

# Success!
Write-Host "`n=== Build Complete! ===" -ForegroundColor Green
Write-Host ""
Write-Host "Output files:" -ForegroundColor Cyan
Get-ChildItem "dist\Buzz-Setup-*.exe" -ErrorAction SilentlyContinue | ForEach-Object {
    Write-Host "  Installer: $($_.FullName)" -ForegroundColor White
    Write-Host "  Size: $([math]::Round($_.Length / 1MB, 2)) MB" -ForegroundColor Gray
}
Write-Host "  Portable: $(Resolve-Path 'dist\Buzz')" -ForegroundColor White

Write-Host "`nYou can now:" -ForegroundColor Yellow
Write-Host "  1. Test: dist\Buzz\Buzz.exe" -ForegroundColor White
Write-Host "  2. Install: dist\Buzz-Setup-*.exe" -ForegroundColor White
Write-Host ""
