"""FFmpeg wrapper — multi-bitrate HLS transcoding with .ts segments."""
import json
import logging
import re
import shutil
import subprocess
import threading
from pathlib import Path
from typing import Callable, List, Optional

from .models import HLS_SEGMENT_DURATION, Rendition, STANDARD_RENDITIONS

logger = logging.getLogger(__name__)

# Bitrate calculation constants for the "low" fallback rendition
_MIN_LOW_BITRATE_KBPS = 400
_REFERENCE_BITRATE_480P_KBPS = 1200
_REFERENCE_HEIGHT_480P = 480


def check_ffmpeg() -> bool:
    """Return True if ``ffmpeg`` is available on PATH."""
    return shutil.which("ffmpeg") is not None


def convert_audio_to_m4a(
    input_path: Path,
    output_path: Path,
    bitrate_kbps: int,
    overwrite: bool,
    cancel_event: threading.Event,
    progress_cb: Optional[Callable[[float], None]] = None,
    log_cb: Optional[Callable[[str], None]] = None,
) -> None:
    """Convert *input_path* to AAC M4A at *bitrate_kbps* kbps.

    Raises :class:`InterruptedError` on user cancellation or
    :class:`RuntimeError` on FFmpeg failure.
    """
    if output_path.exists() and not overwrite:
        raise FileExistsError(f"Ya existe: {output_path.name}")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        "ffmpeg",
        "-y" if overwrite else "-n",
        "-i", str(input_path),
        "-c:a", "aac",
        "-b:a", f"{bitrate_kbps}k",
        "-movflags", "+faststart",
        str(output_path),
    ]

    logger.debug("FFmpeg audio command:\n  " + " \\\n  ".join(cmd))
    if log_cb:
        log_cb(f"Iniciando conversión de audio: {input_path.name}")

    # Probe duration for progress reporting
    duration = _probe_audio_duration(input_path)

    proc = subprocess.Popen(
        cmd,
        stderr=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        text=True,
        bufsize=1,
    )

    try:
        for line in proc.stderr:  # type: ignore[union-attr]
            line = line.rstrip()
            if cancel_event.is_set():
                proc.kill()
                raise InterruptedError("Cancelado por el usuario")

            if progress_cb and duration > 0:
                m = re.search(r"time=(\d+):(\d+):([\d.]+)", line)
                if m:
                    h, mn, s = int(m.group(1)), int(m.group(2)), float(m.group(3))
                    current_sec = h * 3600 + mn * 60 + s
                    pct = min(1.0, current_sec / duration)
                    progress_cb(pct)

            if log_cb and line:
                logger.debug(f"ffmpeg audio: {line}")
    finally:
        proc.wait()

    if proc.returncode != 0 and not cancel_event.is_set():
        raise RuntimeError(
            f"FFmpeg finalizó con código de error {proc.returncode} "
            f"al procesar {input_path.name}"
        )

    if progress_cb:
        progress_cb(1.0)


def _probe_audio_duration(path: Path) -> float:
    """Return the audio duration of *path* in seconds, or 0 on failure."""
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "quiet",
                "-print_format", "json",
                "-show_format",
                str(path),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            dur = data.get("format", {}).get("duration")
            if dur is not None:
                return float(dur)
    except Exception:
        pass
    return 0.0


def select_renditions(source_height: int) -> List[Rendition]:
    """Choose which renditions to produce for a source of *source_height* pixels.

    Rules:
    - No upscaling: only include renditions whose height <= source height.
    - If source < 480p, produce one "low" rendition at source height with a
      proportionally scaled bitrate (minimum 400 kbps).
    """
    applicable = [r for r in STANDARD_RENDITIONS if r.height <= source_height]
    if not applicable:
        low_bitrate = max(
            _MIN_LOW_BITRATE_KBPS,
            int(_REFERENCE_BITRATE_480P_KBPS * source_height / _REFERENCE_HEIGHT_480P),
        )
        applicable = [Rendition(name="low", height=source_height, video_bitrate=low_bitrate)]
    return applicable


def transcode_to_hls(
    input_path: Path,
    output_dir: Path,
    renditions: List[Rendition],
    fps: float,
    duration: float,
    has_audio: bool,
    overwrite: bool,
    cancel_event: threading.Event,
    progress_cb: Optional[Callable[[float], None]] = None,
    log_cb: Optional[Callable[[str], None]] = None,
) -> None:
    """Transcode *input_path* to a set of HLS variants inside *output_dir*.

    All renditions are produced in a single FFmpeg pass (one decode, multiple
    scaled outputs) for efficiency.  Segments are named ``<rendition>_NNN.ts``
    and individual playlists are written as ``<rendition>.m3u8``.

    Raises :class:`InterruptedError` if *cancel_event* is set during encoding,
    or :class:`RuntimeError` on FFmpeg failure.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    gop = max(1, round(fps * HLS_SEGMENT_DURATION))
    cmd = _build_cmd(input_path, output_dir, renditions, gop, has_audio, overwrite)

    logger.debug("FFmpeg command:\n  " + " \\\n  ".join(cmd))
    if log_cb:
        log_cb(f"Iniciando FFmpeg para: {input_path.name}")

    proc = subprocess.Popen(
        cmd,
        stderr=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        text=True,
        bufsize=1,
    )

    try:
        for line in proc.stderr:  # type: ignore[union-attr]
            line = line.rstrip()
            if cancel_event.is_set():
                proc.kill()
                raise InterruptedError("Cancelado por el usuario")

            if progress_cb and duration > 0:
                m = re.search(r"time=(\d+):(\d+):([\d.]+)", line)
                if m:
                    h, mn, s = int(m.group(1)), int(m.group(2)), float(m.group(3))
                    current_sec = h * 3600 + mn * 60 + s
                    pct = min(1.0, current_sec / duration)
                    progress_cb(pct)

            if log_cb and line:
                logger.debug(f"ffmpeg: {line}")
    finally:
        proc.wait()

    if proc.returncode != 0 and not cancel_event.is_set():
        raise RuntimeError(
            f"FFmpeg finalizó con código de error {proc.returncode} "
            f"al procesar {input_path.name}"
        )

    if progress_cb:
        progress_cb(1.0)


def capture_frame_jpg(
    input_path: Path,
    output_dir: Path,
    duration: float,
    log_cb: Optional[Callable[[str], None]] = None,
) -> None:
    """Capture a single frame between second 3 and 5 and save as ``frame.jpg``.

    Chooses a timestamp of 4 s when the video is long enough, falls back to
    3 s, then to the mid-point for very short clips.  The result is written as
    ``<output_dir>/frame.jpg``.

    Non-fatal: logs a warning on failure instead of raising.
    """
    if duration >= 5.0:
        ts = 4.0
    elif duration >= 3.0:
        ts = 3.0
    elif duration > 0:
        ts = duration / 2.0
    else:
        ts = 0.0

    frame_path = output_dir / "frame.jpg"
    cmd = [
        "ffmpeg", "-y",
        "-ss", f"{ts:.3f}",
        "-i", str(input_path),
        "-frames:v", "1",
        "-q:v", "2",
        str(frame_path),
    ]

    logger.debug("FFmpeg capture frame command:\n  " + " \\\n  ".join(cmd))
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            timeout=60,
        )
        if result.returncode == 0:
            if log_cb:
                log_cb(f"📸 Fotograma guardado: {frame_path}")
        else:
            msg = f"⚠ No se pudo capturar fotograma de {input_path.name} (código {result.returncode})"
            logger.warning(msg)
            if log_cb:
                log_cb(msg)
    except Exception as exc:
        msg = f"⚠ No se pudo capturar fotograma de {input_path.name}: {exc}"
        logger.warning(msg)
        if log_cb:
            log_cb(msg)


def write_master_playlist(
    output_dir: Path,
    renditions: List[Rendition],
    source_width: int,
    source_height: int,
    has_audio: bool,
) -> None:
    """Write ``master.m3u8`` referencing all produced variant playlists."""
    lines = ["#EXTM3U", "#EXT-X-VERSION:3", ""]

    codecs = "avc1.640028,mp4a.40.2" if has_audio else "avc1.640028"

    for r in renditions:
        # Compute output width from scale=-2:height (preserve AR, even width)
        if source_height > 0 and source_width > 0:
            out_w = round(source_width * r.height / source_height)
            if out_w % 2 != 0:
                out_w += 1
        else:
            out_w = 0

        bw = (r.video_bitrate + (128 if has_audio else 0)) * 1000  # bps

        if out_w > 0:
            lines.append(
                f"#EXT-X-STREAM-INF:BANDWIDTH={bw},"
                f"RESOLUTION={out_w}x{r.height},"
                f'CODECS="{codecs}"'
            )
        else:
            lines.append(f'#EXT-X-STREAM-INF:BANDWIDTH={bw},CODECS="{codecs}"')

        lines.append(f"{r.name}.m3u8")
        lines.append("")

    master_path = output_dir / "master.m3u8"
    master_path.write_text("\n".join(lines), encoding="utf-8")
    logger.debug(f"Master playlist written: {master_path}")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_cmd(
    input_path: Path,
    output_dir: Path,
    renditions: List[Rendition],
    gop: int,
    has_audio: bool,
    overwrite: bool,
) -> List[str]:
    """Build the FFmpeg command for multi-output HLS transcoding."""
    n = len(renditions)
    cmd: List[str] = ["ffmpeg", "-y" if overwrite else "-n", "-i", str(input_path)]

    # ---- filter_complex: split + scale each rendition ----
    if n > 1:
        # Split into N branches, then scale each
        splits = "".join(f"[v{i}]" for i in range(n))
        fc_parts = [f"[0:v]split={n}{splits}"]
        for i, r in enumerate(renditions):
            fc_parts.append(f"[v{i}]scale=-2:{r.height}:flags=lanczos[v{i}s]")
        cmd += ["-filter_complex", ";".join(fc_parts)]
    else:
        # Single rendition — no split needed
        cmd += [
            "-filter_complex",
            f"[0:v]scale=-2:{renditions[0].height}:flags=lanczos[v0s]",
        ]

    # ---- per-rendition output sections ----
    for i, r in enumerate(renditions):
        seg_file = str(output_dir / f"{r.name}_%03d.ts")
        pl_file = str(output_dir / f"{r.name}.m3u8")

        cmd += ["-map", f"[v{i}s]"]
        if has_audio:
            cmd += ["-map", "0:a:0"]

        cmd += [
            "-c:v", "libx264",
            "-preset", "fast",
            "-b:v", f"{r.video_bitrate}k",
            "-maxrate", f"{int(r.video_bitrate * 1.2)}k",
            "-bufsize", f"{r.video_bitrate * 2}k",
            "-g", str(gop),
            "-keyint_min", str(gop),
            "-sc_threshold", "0",
        ]

        if has_audio:
            cmd += ["-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "2"]

        cmd += [
            "-hls_time", str(HLS_SEGMENT_DURATION),
            "-hls_playlist_type", "vod",
            "-hls_segment_type", "mpegts",
            "-hls_flags", "independent_segments",
            "-hls_segment_filename", seg_file,
            pl_file,
        ]

    return cmd
