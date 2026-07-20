"""Smoke tests for GUI module compatibility."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def test_gui_module_imports_with_current_flet_api():
    import hls_packager.gui as gui

    assert gui.run_app is not None
