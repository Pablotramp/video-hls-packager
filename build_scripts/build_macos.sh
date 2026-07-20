#!/usr/bin/env bash
# Build HLS Video Packager for macOS
# Run from the repository root

set -e

echo "=== HLS Video Packager - macOS Build ==="

pip install pyinstaller flet --upgrade

pyinstaller video_hls_packager.spec --clean --noconfirm

echo ""
echo "=== Build complete ==="
echo "App bundle: dist/HLSPackager.app"
echo ""
echo "To create a distributable DMG (optional):"
echo "  hdiutil create -volname HLSPackager -srcfolder dist/HLSPackager.app -ov -format UDZO dist/HLSPackager.dmg"
