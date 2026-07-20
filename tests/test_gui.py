"""Smoke tests for GUI module compatibility."""
import inspect
import sys
from pathlib import Path

import flet as ft

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def test_gui_module_imports_with_current_flet_api():
    import hls_packager.gui as gui

    assert gui.run_app is not None


def test_gui_uses_flet_padding_api_compatible_with_0861():
    import hls_packager.gui as gui

    source = inspect.getsource(gui)
    assert "ft.padding.symmetric(" not in source
    assert source.count("ft.Padding.symmetric(") >= 2
    assert hasattr(ft.Padding, "symmetric")
