from __future__ import annotations

import sys
from pathlib import Path


def repository_root() -> Path:
    """Return the source checkout or installed data root."""
    source_root = Path(__file__).resolve().parents[2]
    if (source_root / "registry" / "skills.yaml").is_file():
        return source_root
    installed_root = Path(sys.prefix) / "share" / "geo-seo-hub"
    if (installed_root / "registry" / "skills.yaml").is_file():
        return installed_root
    raise FileNotFoundError(
        "GEOHub registry data is missing; reinstall the package from an official source archive."
    )
