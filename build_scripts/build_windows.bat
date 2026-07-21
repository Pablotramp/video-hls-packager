@echo off
REM Build HLS Video Packager for Windows
REM Run from the repository root

echo === HLS Video Packager - Windows Build ===

pip install pyinstaller flet --upgrade

python -m PyInstaller video_hls_packager.spec --clean --noconfirm

echo.
echo === Build complete ===
echo Executable: dist\HLSPackager\HLSPackager.exe
