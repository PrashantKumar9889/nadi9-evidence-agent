"""Convenience root runner for the Nadi-9 Agent.

Allows running directly on Windows, macOS, or Linux without setting PYTHONPATH:
    python run.py run
    python run.py inspect
    python run.py explain --subtitle S001
"""
import sys
from pathlib import Path

# Add src/ to sys.path so nadi9 is always importable
src_dir = Path(__file__).resolve().parent / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

from nadi9.cli import main

if __name__ == "__main__":
    sys.exit(main())
