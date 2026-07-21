"""Runtime hook for PyInstaller.

Ensures that ``exit`` and ``quit`` are available as builtins in the frozen
executable.  The standard Python interpreter injects these via the ``site``
module, but PyInstaller's bootloader may not always do so — causing
``NameError: name 'exit' is not defined`` in libraries (e.g. flet.utils.pip)
that rely on them.
"""
import builtins
import sys

if not hasattr(builtins, "exit"):
    builtins.exit = sys.exit  # type: ignore[attr-defined]
if not hasattr(builtins, "quit"):
    builtins.quit = sys.exit  # type: ignore[attr-defined]
