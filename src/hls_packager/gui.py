"""Flet desktop GUI for HLS Video Packager."""
from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Dict, List, Optional

import flet as ft

from .ffmpeg import check_ffmpeg
from .ffprobe import check_ffprobe
from .file_utils import get_output_root
from .models import FileItem, FileStatus, PackageResult
from .packager import EngineCallbacks, PackagerEngine
from .report import write_reports

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Status display helpers
# ---------------------------------------------------------------------------

_STATUS_COLOR: Dict[FileStatus, str] = {
    FileStatus.PENDING:    ft.colors.GREY_500,
    FileStatus.PROCESSING: ft.colors.BLUE_400,
    FileStatus.DONE:       ft.colors.GREEN_600,
    FileStatus.COPIED:     ft.colors.TEAL_400,
    FileStatus.SKIPPED:    ft.colors.AMBER_600,
    FileStatus.ERROR:      ft.colors.RED_600,
}

_STATUS_ICON: Dict[FileStatus, str] = {
    FileStatus.PENDING:    ft.icons.HOURGLASS_EMPTY,
    FileStatus.PROCESSING: ft.icons.SYNC,
    FileStatus.DONE:       ft.icons.CHECK_CIRCLE,
    FileStatus.COPIED:     ft.icons.CONTENT_COPY,
    FileStatus.SKIPPED:    ft.icons.SKIP_NEXT,
    FileStatus.ERROR:      ft.icons.ERROR,
}

MAX_LOG_LINES = 500


# ---------------------------------------------------------------------------
# Main GUI application
# ---------------------------------------------------------------------------

def main(page: ft.Page) -> None:
    page.title = "HLS Video Packager"
    page.theme_mode = ft.ThemeMode.DARK
    page.window.width = 900
    page.window.height = 720
    page.window.min_width = 700
    page.window.min_height = 500
    page.padding = 16
    page.scroll = None

    # ---- State ----
    engine = PackagerEngine()
    file_items: List[FileItem] = []
    _file_row_map: Dict[str, ft.Row] = {}  # source_path str → row widget
    _log_lock = threading.Lock()

    # ---- File picker ----
    folder_picker = ft.FilePicker()
    page.overlay.append(folder_picker)

    # ---- Controls ----
    input_field = ft.TextField(
        label="Carpeta de origen",
        hint_text="Selecciona la carpeta que contiene los videos…",
        expand=True,
        read_only=False,
        border_color=ft.colors.BLUE_400,
        on_change=lambda e: _on_input_changed(),
    )
    output_field = ft.TextField(
        label="Carpeta de salida (auto)",
        read_only=True,
        expand=True,
        border_color=ft.colors.GREY_600,
        color=ft.colors.GREY_400,
    )
    overwrite_cb = ft.Checkbox(
        label="Sobrescribir archivos existentes",
        value=False,
    )

    btn_browse = ft.ElevatedButton(
        "Seleccionar…",
        icon=ft.icons.FOLDER_OPEN,
        on_click=lambda e: folder_picker.get_directory_path(
            dialog_title="Selecciona la carpeta de origen"
        ),
    )
    btn_start = ft.ElevatedButton(
        "Iniciar",
        icon=ft.icons.PLAY_ARROW,
        bgcolor=ft.colors.GREEN_700,
        color=ft.colors.WHITE,
        disabled=True,
        on_click=lambda e: _start(),
    )
    btn_cancel = ft.ElevatedButton(
        "Cancelar",
        icon=ft.icons.STOP,
        bgcolor=ft.colors.RED_700,
        color=ft.colors.WHITE,
        disabled=True,
        on_click=lambda e: _cancel(),
    )

    progress_bar = ft.ProgressBar(value=0, expand=True, color=ft.colors.BLUE_400)
    progress_label = ft.Text("", size=12, color=ft.colors.GREY_400)

    file_status_list = ft.ListView(expand=True, spacing=2, padding=4)
    log_list = ft.ListView(expand=True, spacing=1, padding=4, auto_scroll=True)

    ffmpeg_banner = ft.Container(visible=False)

    # ---- File picker callback ----
    def _on_folder_picked(e: ft.FilePickerResultEvent) -> None:
        if e.path:
            input_field.value = e.path
            _on_input_changed()
            page.update()

    folder_picker.on_result = _on_folder_picked

    def _on_input_changed() -> None:
        path_str = (input_field.value or "").strip()
        if path_str:
            out = get_output_root(Path(path_str))
            output_field.value = str(out)
            btn_start.disabled = engine.is_running()
        else:
            output_field.value = ""
            btn_start.disabled = True
        page.update()

    # ---- Preflight checks ----
    def _check_tools() -> None:
        missing = []
        if not check_ffmpeg():
            missing.append("ffmpeg")
        if not check_ffprobe():
            missing.append("ffprobe")

        if missing:
            tools_str = " y ".join(missing)
            ffmpeg_banner.content = ft.Container(
                content=ft.Row([
                    ft.Icon(ft.icons.WARNING_AMBER, color=ft.colors.AMBER_400, size=20),
                    ft.Text(
                        f"⚠ {tools_str.upper()} no encontrado(s). "
                        "Instala FFmpeg y asegúrate de que esté en el PATH del sistema. "
                        "Descarga: https://ffmpeg.org/download.html",
                        color=ft.colors.AMBER_300,
                        size=13,
                        expand=True,
                    ),
                ]),
                bgcolor=ft.colors.AMBER_900,
                border_radius=6,
                padding=ft.padding.symmetric(horizontal=12, vertical=8),
            )
            ffmpeg_banner.visible = True
            btn_start.disabled = True
            page.update()

    # ---- Log helper ----
    def _log(msg: str) -> None:
        with _log_lock:
            log_list.controls.append(
                ft.Text(msg, size=11, color=ft.colors.GREY_300, selectable=True)
            )
            if len(log_list.controls) > MAX_LOG_LINES:
                log_list.controls.pop(0)
        page.update()

    # ---- File row helpers ----
    def _make_file_row(item: FileItem) -> ft.Row:
        status = item.status
        row = ft.Row(
            controls=[
                ft.Icon(
                    _STATUS_ICON[status],
                    color=_STATUS_COLOR[status],
                    size=16,
                ),
                ft.Text(
                    item.source_path.name,
                    size=12,
                    expand=True,
                    overflow=ft.TextOverflow.ELLIPSIS,
                ),
                ft.Text(
                    status.value,
                    size=11,
                    color=_STATUS_COLOR[status],
                    width=90,
                    text_align=ft.TextAlign.RIGHT,
                ),
            ],
            spacing=8,
        )
        return row

    def _update_file_row(item: FileItem) -> None:
        key = str(item.source_path)
        if key not in _file_row_map:
            return
        row = _file_row_map[key]
        status = item.status
        row.controls[0].name = _STATUS_ICON[status]    # type: ignore[attr-defined]
        row.controls[0].color = _STATUS_COLOR[status]  # type: ignore[attr-defined]
        row.controls[2].value = status.value            # type: ignore[attr-defined]
        row.controls[2].color = _STATUS_COLOR[status]  # type: ignore[attr-defined]
        if item.error_msg and len(row.controls) < 4:
            row.controls.append(
                ft.Text(
                    f"  {item.error_msg}",
                    size=10,
                    color=ft.colors.RED_400,
                    italic=True,
                )
            )

    # ---- Engine callbacks ----
    def _on_scan_done(items: List[FileItem]) -> None:
        nonlocal file_items
        file_items = items
        _file_row_map.clear()
        file_status_list.controls.clear()

        for item in items:
            row = _make_file_row(item)
            key = str(item.source_path)
            _file_row_map[key] = row
            file_status_list.controls.append(
                ft.Container(
                    content=row,
                    padding=ft.padding.symmetric(horizontal=8, vertical=2),
                )
            )

        progress_bar.value = 0
        progress_label.value = f"0 / {len(items)}"
        page.update()

    def _on_file_start(item: FileItem, idx: int, total: int) -> None:
        item.status = FileStatus.PROCESSING
        _update_file_row(item)
        page.update()

    def _on_file_progress(pct: float) -> None:
        # pct is per-file progress (0.0–1.0); reflected in progress bar label
        pass  # overall progress updated in on_file_done

    def _on_file_done(item: FileItem, done: int, total: int) -> None:
        _update_file_row(item)
        if total > 0:
            progress_bar.value = done / total
            progress_label.value = f"{done} / {total}"
        page.update()

    def _on_done(result: PackageResult) -> None:
        # Write reports
        out_root_str = (output_field.value or "").strip()
        if out_root_str and file_items:
            try:
                write_reports(Path(out_root_str), result, file_items)
                _log(f"📄 Informe guardado en: {out_root_str}")
            except Exception as exc:  # noqa: BLE001
                _log(f"No se pudo guardar el informe: {exc}")

        # Summary
        summary = (
            f"\n✅ Convertidos: {result.converted}  "
            f"📋 Copiados: {result.copied}  "
            f"⏭ Omitidos: {result.skipped}  "
            f"❌ Errores: {result.errors}"
        )
        _log(summary)

        btn_start.disabled = False
        btn_cancel.disabled = True
        progress_bar.value = 1.0
        page.update()

    callbacks = EngineCallbacks(
        on_scan_done=_on_scan_done,
        on_file_start=_on_file_start,
        on_file_progress=_on_file_progress,
        on_file_done=_on_file_done,
        on_log=_log,
        on_done=_on_done,
    )

    # ---- Start / Cancel ----
    def _start() -> None:
        input_path_str = (input_field.value or "").strip()
        if not input_path_str:
            _log("⚠ Selecciona una carpeta de origen primero.")
            return

        input_root = Path(input_path_str)
        if not input_root.is_dir():
            _log(f"⚠ La ruta no existe o no es una carpeta: {input_path_str}")
            return

        output_root = get_output_root(input_root)
        overwrite = overwrite_cb.value or False

        file_status_list.controls.clear()
        log_list.controls.clear()
        progress_bar.value = 0
        progress_label.value = ""
        btn_start.disabled = True
        btn_cancel.disabled = False
        page.update()

        engine.start(input_root, output_root, overwrite, callbacks)

    def _cancel() -> None:
        engine.cancel()
        btn_cancel.disabled = True
        _log("⚠ Cancelando…")
        page.update()

    # ---- Layout ----
    page.add(
        ft.Column(
            expand=True,
            spacing=12,
            controls=[
                # Header
                ft.Row([
                    ft.Icon(ft.icons.VIDEO_LIBRARY, color=ft.colors.BLUE_400, size=28),
                    ft.Text(
                        "HLS Video Packager",
                        size=22,
                        weight=ft.FontWeight.BOLD,
                        color=ft.colors.BLUE_300,
                    ),
                ]),

                ffmpeg_banner,

                ft.Divider(height=1, color=ft.colors.GREY_800),

                # Input row
                ft.Row([input_field, btn_browse], spacing=8),

                # Output row
                output_field,

                # Options row
                ft.Row([
                    overwrite_cb,
                    ft.Container(expand=True),
                    btn_start,
                    btn_cancel,
                ], spacing=12),

                ft.Divider(height=1, color=ft.colors.GREY_800),

                # Progress
                ft.Row([
                    ft.Text("Progreso:", size=12, color=ft.colors.GREY_400),
                    progress_bar,
                    progress_label,
                ], spacing=8),

                ft.Divider(height=1, color=ft.colors.GREY_800),

                # Files + Logs (two-panel)
                ft.Row(
                    expand=True,
                    spacing=12,
                    controls=[
                        ft.Column(
                            expand=2,
                            spacing=4,
                            controls=[
                                ft.Text(
                                    "Archivos",
                                    size=13,
                                    weight=ft.FontWeight.BOLD,
                                    color=ft.colors.GREY_400,
                                ),
                                ft.Container(
                                    content=file_status_list,
                                    expand=True,
                                    bgcolor=ft.colors.GREY_900,
                                    border_radius=6,
                                    border=ft.border.all(1, ft.colors.GREY_800),
                                ),
                            ],
                        ),
                        ft.Column(
                            expand=3,
                            spacing=4,
                            controls=[
                                ft.Text(
                                    "Log",
                                    size=13,
                                    weight=ft.FontWeight.BOLD,
                                    color=ft.colors.GREY_400,
                                ),
                                ft.Container(
                                    content=log_list,
                                    expand=True,
                                    bgcolor=ft.colors.GREY_900,
                                    border_radius=6,
                                    border=ft.border.all(1, ft.colors.GREY_800),
                                ),
                            ],
                        ),
                    ],
                ),
            ],
        )
    )

    # Run preflight checks after layout is rendered
    page.run_thread(_check_tools)


def run_app() -> None:
    """Entry point for the Flet desktop app."""
    ft.app(target=main)
