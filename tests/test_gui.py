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

    def _is_ft_call(node: ast.AST, owner: str, method: str) -> bool:
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            return False
        owner_node = node.func.value
        return (
            isinstance(owner_node, ast.Attribute)
            and isinstance(owner_node.value, ast.Name)
            and owner_node.value.id == "ft"
            and owner_node.attr == owner
            and node.func.attr == method
        )

    for node in ast.walk(tree):
        if _is_ft_call(node, "Padding", "symmetric"):
            padding_calls += 1
        if _is_ft_call(node, "padding", "symmetric"):
            legacy_calls += 1

    assert legacy_calls == 0
    assert padding_calls > 0
    assert hasattr(ft.Padding, "symmetric")
