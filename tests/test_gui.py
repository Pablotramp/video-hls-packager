"""Smoke tests for GUI module compatibility."""
import ast
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

    tree = ast.parse(inspect.getsource(gui))
    padding_calls = 0
    legacy_calls = 0

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        func = node.func
        if not isinstance(func.value, ast.Attribute):
            continue
        if not isinstance(func.value.value, ast.Name) or func.value.value.id != "ft":
            continue
        if func.value.attr == "Padding" and func.attr == "symmetric":
            padding_calls += 1
        if func.value.attr == "padding" and func.attr == "symmetric":
            legacy_calls += 1

    assert legacy_calls == 0
    assert padding_calls >= 2
    assert hasattr(ft.Padding, "symmetric")
