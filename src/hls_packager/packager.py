"""Packaging engine — orchestrates scanning, copying, and transcoding."""
import logging
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional

from .ffmpeg import (
    select_renditions,
    transcode_to_hls,
    write_master_playlist,
)
from .ffprobe import get_video_info
from .file_utils import copy_file, scan_folder
from .models import FileItem, FileStatus, PackageResult

logger = logging.getLogger(__name__)


@dataclass
class EngineCallbacks:
    """Callbacks invoked by :class:`PackagerEngine` during a run.

    All callbacks are called from the worker thread — implementations must
    be thread-safe (e.g. call ``page.update()`` after mutating Flet controls).
    """
    on_scan_done: Callable[[List[FileItem]], None] = lambda items: None
    on_file_start: Callable[[FileItem, int, int], None] = lambda item, idx, total: None
    on_file_progress: Callable[[float], None] = lambda pct: None
    on_file_done: Callable[[FileItem, int, int], None] = lambda item, idx, total: None
    on_log: Callable[[str], None] = lambda msg: None
    on_done: Callable[[PackageResult], None] = lambda result: None


class PackagerEngine:
    """Thread-safe engine that drives a complete packaging run."""

    def __init__(self) -> None:
        self._cancel_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(
        self,
        input_root: Path,
        output_root: Path,
        overwrite: bool,
        callbacks: EngineCallbacks,
    ) -> None:
        """Start the packaging run in a background thread."""
        self._cancel_event.clear()
        self._thread = threading.Thread(
            target=self._run,
            args=(input_root, output_root, overwrite, callbacks),
            daemon=True,
        )
        self._thread.start()

    def cancel(self) -> None:
        """Request cancellation of the current run."""
        self._cancel_event.set()

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    # ------------------------------------------------------------------
    # Worker
    # ------------------------------------------------------------------

    def _run(
        self,
        input_root: Path,
        output_root: Path,
        overwrite: bool,
        cb: EngineCallbacks,
    ) -> None:
        result = PackageResult()

        try:
            cb.on_log("Escaneando carpeta de origen…")
            items = scan_folder(input_root, output_root)
            total = len(items)
            cb.on_log(f"Encontrados {total} archivo(s).")
            cb.on_scan_done(items)

            for idx, item in enumerate(items):
                if self._cancel_event.is_set():
                    cb.on_log("⚠ Proceso cancelado por el usuario.")
                    break

                cb.on_file_start(item, idx, total)

                try:
                    if item.is_video:
                        self._process_video(item, overwrite, cb, result)
                    else:
                        self._process_non_video(item, overwrite, cb, result)
                except InterruptedError:
                    cb.on_log("⚠ Proceso cancelado por el usuario.")
                    break
                except (OSError, RuntimeError, ValueError, TypeError) as exc:
                    # Per-file errors must not abort the batch; log and continue
                    item.status = FileStatus.ERROR
                    item.error_msg = str(exc)
                    result.errors += 1
                    msg = f"✗ ERROR [{item.source_path.name}]: {exc}"
                    result.error_details.append(msg)
                    cb.on_log(msg)
                    logger.exception(f"Error processing {item.source_path}")
                except Exception as exc:  # unexpected — log and continue
                    item.status = FileStatus.ERROR
                    item.error_msg = str(exc)
                    result.errors += 1
                    msg = f"✗ ERROR inesperado [{item.source_path.name}]: {exc}"
                    result.error_details.append(msg)
                    cb.on_log(msg)
                    logger.exception(f"Unexpected error processing {item.source_path}")

                cb.on_file_done(item, idx + 1, total)

        except (OSError, RuntimeError) as exc:
            cb.on_log(f"✗ Error fatal: {exc}")
            logger.exception("Fatal error in packager engine")
        except Exception as exc:  # unexpected fatal — log and surface
            cb.on_log(f"✗ Error fatal inesperado: {exc}")
            logger.exception("Unexpected fatal error in packager engine")
        finally:
            cb.on_done(result)

    def _process_video(
        self,
        item: FileItem,
        overwrite: bool,
        cb: EngineCallbacks,
        result: PackageResult,
    ) -> None:
        master_pl = item.output_path / "master.m3u8"
        if master_pl.exists() and not overwrite:
            item.status = FileStatus.SKIPPED
            result.skipped += 1
            cb.on_log(f"→ Omitido (ya existe): {item.source_path.name}")
            return

        cb.on_log(f"→ Probando: {item.source_path.name}")
        info = get_video_info(item.source_path)
        if info is None:
            raise RuntimeError(
                f"No se pudo obtener información del video: {item.source_path.name}"
            )

        renditions = select_renditions(info.height)
        names = ", ".join(r.name for r in renditions)
        cb.on_log(
            f"→ {item.source_path.name} "
            f"({info.width}×{info.height} @ {info.fps:.2f}fps, "
            f"{info.duration:.1f}s) — variantes: {names}"
        )

        item.status = FileStatus.PROCESSING
        transcode_to_hls(
            input_path=item.source_path,
            output_dir=item.output_path,
            renditions=renditions,
            fps=info.fps,
            duration=info.duration,
            has_audio=info.has_audio,
            overwrite=overwrite,
            cancel_event=self._cancel_event,
            progress_cb=cb.on_file_progress,
            log_cb=cb.on_log,
        )

        write_master_playlist(
            output_dir=item.output_path,
            renditions=renditions,
            source_width=info.width,
            source_height=info.height,
            has_audio=info.has_audio,
        )

        item.status = FileStatus.DONE
        result.converted += 1
        cb.on_log(f"✓ Convertido: {item.source_path.name}")

    def _process_non_video(
        self,
        item: FileItem,
        overwrite: bool,
        cb: EngineCallbacks,
        result: PackageResult,
    ) -> None:
        copied = copy_file(item.source_path, item.output_path, overwrite)
        if copied:
            item.status = FileStatus.COPIED
            result.copied += 1
            cb.on_log(f"→ Copiado: {item.source_path.name}")
        else:
            item.status = FileStatus.SKIPPED
            result.skipped += 1
            cb.on_log(f"→ Omitido: {item.source_path.name}")
