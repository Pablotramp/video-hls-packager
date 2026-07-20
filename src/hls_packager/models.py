"""Data models for HLS Packager."""
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import List


class FileStatus(Enum):
    PENDING = "Pendiente"
    PROCESSING = "Procesando"
    DONE = "Listo"
    COPIED = "Copiado"
    SKIPPED = "Omitido"
    ERROR = "Error"


@dataclass
class Rendition:
    """A single HLS quality variant."""
    name: str           # e.g. "1080p", "720p", "480p", "low"
    height: int         # target height in pixels
    video_bitrate: int  # target video bitrate in kbps


@dataclass
class VideoInfo:
    """Probed metadata for a video file."""
    width: int
    height: int
    fps: float
    duration: float   # seconds
    has_audio: bool


@dataclass
class FileItem:
    """Represents one file in the scan queue."""
    source_path: Path
    output_path: Path   # for video: output directory; for non-video: output file
    is_video: bool
    is_audio: bool = False
    status: FileStatus = FileStatus.PENDING
    error_msg: str = ""


@dataclass
class PackageResult:
    """Aggregated results from a packaging run."""
    converted: int = 0
    copied: int = 0
    skipped: int = 0
    errors: int = 0
    error_details: List[str] = field(default_factory=list)


# Standard rendition ladder (no upscaling — filtered by source height at runtime)
STANDARD_RENDITIONS: List[Rendition] = [
    Rendition(name="1080p", height=1080, video_bitrate=5000),
    Rendition(name="720p",  height=720,  video_bitrate=3000),
    Rendition(name="480p",  height=480,  video_bitrate=1200),
]

VIDEO_EXTENSIONS = frozenset({".mp4", ".mov", ".mkv", ".m4v", ".avi", ".webm"})

# Lossless / uncompressed audio formats that benefit from AAC conversion
AUDIO_EXTENSIONS = frozenset({".wav", ".aif", ".aiff", ".flac"})

HLS_SEGMENT_DURATION = 6  # seconds per HLS segment

# Bitrate options (kbps) offered for audio optimization
AUDIO_BITRATE_OPTIONS: List[int] = [96, 128, 160, 192, 256]
AUDIO_BITRATE_DEFAULT: int = 160
