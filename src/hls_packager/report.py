"""Report generation for conversion reports and final output manifest."""
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Set

from .models import FileItem, FileStatus, PackageResult

logger = logging.getLogger(__name__)

_MANIFEST_FILENAME = "_manifest.json"
_TEMP_FILE_SUFFIXES = (
    ".tmp",
    ".temp",
    ".partial",
    ".part",
    ".swp",
    ".swo",
    ".crdownload",
)
_TEMP_FILE_PREFIXES = ("~$", ".~")


def _is_temporary_file(path: Path) -> bool:
    """Return True when *path* looks like a temporary/intermediate file."""
    name = path.name.lower()
    if name.endswith("~"):
        return True
    if any(name.startswith(prefix) for prefix in _TEMP_FILE_PREFIXES):
        return True
    if any(name.endswith(suffix) for suffix in _TEMP_FILE_SUFFIXES):
        return True
    return False


def _collect_manifest_files(output_root: Path) -> List[str]:
    """Return deterministic relative file list for ``_manifest.json``."""
    files: Set[str] = set()

    for abs_path in output_root.rglob("*"):
        if not abs_path.is_file():
            continue

        rel_path = abs_path.relative_to(output_root)
        if _is_temporary_file(rel_path):
            continue
        files.add(rel_path.as_posix())

    # Ensure the final inventory mirrors the finished output tree, including
    # the manifest file that is about to be written.
    files.add(_MANIFEST_FILENAME)
    return sorted(files)


def write_manifest(output_root: Path) -> None:
    """Write ``_manifest.json`` in *output_root* with file inventory.

    ``generatedAt`` is written as ISO-8601 in UTC with second precision.
    """
    output_root.mkdir(parents=True, exist_ok=True)
    manifest_path = output_root / _MANIFEST_FILENAME

    data = {
        "version": 1,
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "files": _collect_manifest_files(output_root),
    }

    try:
        manifest_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        logger.info("Manifest written: %s", manifest_path)
    except OSError as exc:
        raise RuntimeError(f"Could not generate {_MANIFEST_FILENAME}: {exc}") from exc


def write_reports(
    output_root: Path,
    result: PackageResult,
    items: List[FileItem],
) -> None:
    """Write ``conversion_report.json`` and ``conversion_report.txt`` to *output_root*."""
    output_root.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().isoformat(timespec="seconds")

    # ---- Build structured report data ----
    file_entries = []
    for item in items:
        file_entries.append({
            "source": str(item.source_path),
            "output": str(item.output_path),
            "type": "video" if item.is_video else ("audio" if item.is_audio else "file"),
            "status": item.status.value,
            "error": item.error_msg or None,
        })

    report_data = {
        "timestamp": timestamp,
        "summary": {
            "converted": result.converted,
            "copied": result.copied,
            "skipped": result.skipped,
            "errors": result.errors,
            "total": len(items),
        },
        "files": file_entries,
        "errors": result.error_details,
    }

    # ---- JSON ----
    json_path = output_root / "conversion_report.json"
    try:
        json_path.write_text(
            json.dumps(report_data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        logger.info(f"JSON report written: {json_path}")
    except OSError as exc:
        logger.error(f"Could not write JSON report: {exc}")

    # ---- TXT ----
    txt_path = output_root / "conversion_report.txt"
    try:
        lines = [
            "=" * 60,
            "  HLS Video Packager — Informe de Conversión",
            "=" * 60,
            f"  Fecha/Hora : {timestamp}",
            f"  Directorio : {output_root}",
            "-" * 60,
            "  RESUMEN",
            "-" * 60,
            f"  Convertidos : {result.converted}",
            f"  Copiados    : {result.copied}",
            f"  Omitidos    : {result.skipped}",
            f"  Errores     : {result.errors}",
            f"  Total       : {len(items)}",
            "-" * 60,
            "  DETALLE DE ARCHIVOS",
            "-" * 60,
        ]
        for entry in file_entries:
            status = entry["status"]
            src = Path(entry["source"]).name
            err = f"  → {entry['error']}" if entry["error"] else ""
            lines.append(f"  [{status:10s}] {src}{err}")

        if result.error_details:
            lines += ["-" * 60, "  ERRORES", "-" * 60]
            lines.extend(f"  {e}" for e in result.error_details)

        lines += ["=" * 60, ""]
        txt_path.write_text("\n".join(lines), encoding="utf-8")
        logger.info(f"TXT report written: {txt_path}")
    except OSError as exc:
        logger.error(f"Could not write TXT report: {exc}")

    write_manifest(output_root)
