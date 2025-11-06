"""Pytest configuration for backend tests."""

import sys
from pathlib import Path

def ensure_app_on_path() -> None:
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

ensure_app_on_path()
