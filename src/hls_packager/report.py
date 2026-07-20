"""Report generation — writes conversion_report.json and conversion_report.txt."""
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import List

from .models import FileItem, FileStatus, PackageResult

logger = logging.getLogger(__name__)


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
