#!/usr/bin/env bash
# Build HLS Video Packager for Linux
# Run from the repository root

set -e

echo "=== HLS Video Packager - Linux Build ==="

pip install pyinstaller flet --upgrade

pyinstaller video_hls_packager.spec --clean --noconfirm

echo ""
echo "=== Build complete ==="
echo "Binary: dist/HLSPackager/HLSPackager"
echo ""
echo "To make it executable:"
echo "  chmod +x dist/HLSPackager/HLSPackager"
