# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for HLS Video Packager.

Builds a one-folder distribution that bundles the Flet runtime.
Run:  pyinstaller video_hls_packager.spec --clean --noconfirm
"""
import sys
from pathlib import Path

block_cipher = None

# Collect Flet assets (Flutter engine, renderer, etc.)
try:
    import flet
    flet_dir = Path(flet.__file__).parent
except ImportError:
    flet_dir = None

datas = []
if flet_dir:
    # Include Flet's built-in assets (controls/, utils/ exist in 0.86.x; app/ is now app.py)
    for pattern in ("controls/", "utils/"):
        target = flet_dir / pattern
        if target.exists():
            datas.append((str(target), f"flet/{pattern}"))

a = Analysis(
    ["main.py"],
    pathex=[str(Path(".") / "src")],
    binaries=[],
    datas=datas,
    hiddenimports=[
        "flet",
        "flet.app",
        "flet_core",
        "flet_desktop",
        "hls_packager",
        "hls_packager.gui",
        "hls_packager.packager",
        "hls_packager.ffmpeg",
        "hls_packager.ffprobe",
        "hls_packager.file_utils",
        "hls_packager.models",
        "hls_packager.report",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=["hooks/rthook_builtins.py"],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="HLSPackager",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,   # no console window on Windows/macOS
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="HLSPackager",
)

# macOS .app bundle
if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="HLSPackager.app",
        icon=None,
        bundle_identifier="com.pablotramp.hlspackager",
        info_plist={
            "CFBundleDisplayName": "HLS Video Packager",
            "CFBundleShortVersionString": "1.0.0",
            "NSHighResolutionCapable": True,
        },
    )
