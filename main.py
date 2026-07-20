"""Entry point for HLS Video Packager."""
import sys
from pathlib import Path

# Allow running directly as `python main.py` from the repo root
sys.path.insert(0, str(Path(__file__).parent / "src"))

from hls_packager.gui import run_app

if __name__ == "__main__":
    run_app()
