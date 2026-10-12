"""Writable user data paths, independent of the installed package location."""

from __future__ import annotations

import os
import sys
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
STATIC_DIR = PACKAGE_DIR / "static"
SAMPLE_FILE = PACKAGE_DIR / "resources" / "sample.bib"


def data_directory() -> Path:
    """Resolve the data directory without creating it or touching an existing DB."""
    override = os.environ.get("BIBTEX_FETCH_DATA_DIR") or os.environ.get("BIBCLEAN_DATA_DIR")
    if override:
        return Path(override).expanduser().resolve()
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
        return base / "BibTeXFetch"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "BibTeXFetch"
    base = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    return base / "bibtex-fetch"
