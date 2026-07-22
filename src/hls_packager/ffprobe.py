"""FFprobe wrapper — probes video metadata."""
import json
import logging
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

from .models import VideoInfo

logger = logging.getLogger(__name__)


def _find_exe(name: str) -> str:
    """Return path to *name* executable, preferring the app's own directory.

    When running as a PyInstaller bundle, checks the directory that contains
    the frozen executable before falling back to the system PATH.  This allows
    shipping ``ffmpeg.exe`` / ``ffprobe.exe`` alongside ``HLSPackager.exe``
    without requiring them to be installed system-wide.
    """
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).parent
        suffix = ".exe" if sys.platform == "win32" else ""
        candidate = exe_dir / (name + suffix)
        if candidate.is_file():
            return str(candidate)
    return name


def check_ffprobe() -> bool:
    """Return True if ``ffprobe`` is available (app dir or PATH)."""
    exe = _find_exe("ffprobe")
    return Path(exe).is_absolute() or shutil.which(exe) is not None


def get_video_info(path: Path) -> Optional[VideoInfo]:
    """Probe *path* with ffprobe and return a :class:`VideoInfo` on success.

    Returns ``None`` if the file cannot be probed or has no video stream.
    """
    cmd = [
        _find_exe("ffprobe"), "-v", "quiet",
        "-print_format", "json",
        "-show_streams", "-show_format",
        str(path),
    ]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=60
        )
    except FileNotFoundError:
        logger.error("ffprobe not found — please install FFmpeg.")
        return None
    except subprocess.TimeoutExpired:
        logger.error(f"ffprobe timed out probing {path}")
        return None

    if result.returncode != 0:
        logger.error(f"ffprobe error for {path}:\n{result.stderr.strip()}")
        return None

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        logger.error(f"Cannot parse ffprobe output for {path}: {exc}")
        return None

    video_stream = None
    has_audio = False

    for stream in data.get("streams", []):
        codec_type = stream.get("codec_type", "")
        if codec_type == "video" and video_stream is None:
            video_stream = stream
        elif codec_type == "audio":
            has_audio = True

    if video_stream is None:
        logger.warning(f"No video stream found in {path}")
        return None

    width = int(video_stream.get("width", 0))
    height = int(video_stream.get("height", 0))
    fps = _parse_fps(video_stream.get("r_frame_rate", "25/1"))
    duration = float(
        video_stream.get("duration")
        or data.get("format", {}).get("duration")
        or 0
    )

    return VideoInfo(
        width=width,
        height=height,
        fps=fps,
        duration=duration,
        has_audio=has_audio,
    )


def _parse_fps(fps_str: str) -> float:
    """Parse a fractional FPS string like ``"30000/1001"`` into a float."""
    try:
        if "/" in fps_str:
            num, den = fps_str.split("/", 1)
            val = float(num) / float(den)
        else:
            val = float(fps_str)
        return round(val, 3) if val > 0 else 25.0
    except (ValueError, ZeroDivisionError):
        return 25.0
