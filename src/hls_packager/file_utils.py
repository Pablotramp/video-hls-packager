"""File system utilities: scanning, path computation, and copying."""
import logging
import shutil
from pathlib import Path
from typing import List

from .models import AUDIO_EXTENSIONS, VIDEO_EXTENSIONS, FileItem

logger = logging.getLogger(__name__)


def is_video_file(path: Path) -> bool:
    """Return True if *path* is a recognised video file by extension."""
    return path.suffix.lower() in VIDEO_EXTENSIONS


def is_audio_file(path: Path) -> bool:
    """Return True if *path* is a lossless/uncompressed audio file by extension."""
    return path.suffix.lower() in AUDIO_EXTENSIONS


def get_output_root(input_root: Path) -> Path:
    """Compute the sibling output directory for *input_root*.

    Example: ``/home/user/project`` → ``/home/user/project_optimized``
    """
    return input_root.parent / f"{input_root.name}_optimized"


def scan_folder(input_root: Path, output_root: Path) -> List[FileItem]:
    """Recursively scan *input_root* and build the list of :class:`FileItem` objects.

    - Video files map to a subdirectory in *output_root* (no extension, same relative path).
    - Audio files (lossless) map to a sibling ``.m4a`` file in *output_root*.
    - Non-video/audio files mirror their path exactly under *output_root*.
    """
    items: List[FileItem] = []
    input_root = Path(input_root).resolve()
    output_root = Path(output_root).resolve()

    for src_path in sorted(input_root.rglob("*")):
        if not src_path.is_file():
            continue

        rel = src_path.relative_to(input_root)

        if is_video_file(src_path):
            # Output path is a *directory* named after the video stem
            out_path = output_root / rel.parent / src_path.stem
            items.append(FileItem(
                source_path=src_path,
                output_path=out_path,
                is_video=True,
            ))
        elif is_audio_file(src_path):
            # Output path mirrors the source but with .m4a extension
            out_path = output_root / rel.parent / (src_path.stem + ".m4a")
            items.append(FileItem(
                source_path=src_path,
                output_path=out_path,
                is_video=False,
                is_audio=True,
            ))
        else:
            out_path = output_root / rel
            items.append(FileItem(
                source_path=src_path,
                output_path=out_path,
                is_video=False,
            ))

    return items


def copy_file(src: Path, dst: Path, overwrite: bool = True) -> bool:
    """Copy *src* to *dst*, creating parent directories as needed.

    Returns ``True`` if the file was copied, ``False`` if it was skipped
    because it already exists and *overwrite* is ``False``.
    """
    if dst.exists() and not overwrite:
        logger.debug(f"Skipping existing file: {dst}")
        return False
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    logger.debug(f"Copied {src} → {dst}")
    return True
