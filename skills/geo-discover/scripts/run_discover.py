#!/usr/bin/env python3
"""Thin execution-mode-aware entry point for the geo-discover Skill."""

import sys
from pathlib import Path

for candidate in (Path(__file__).resolve().parents[1] / "src", Path(__file__).resolve().parents[3] / "src"):
    if candidate.is_dir():
        sys.path.insert(0, str(candidate))
        break

from geo_seo_hub.cli import main


if __name__ == "__main__":
    raise SystemExit(main(["discover", *sys.argv[1:]]))
