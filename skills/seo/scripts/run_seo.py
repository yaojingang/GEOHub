#!/usr/bin/env python3
"""Thin entry point for the one-line SEO skill."""
from __future__ import annotations
import sys
from pathlib import Path

for parent in Path(__file__).resolve().parents:
    source = parent / "src"
    if (source / "geo_seo_hub").is_dir():
        sys.path.insert(0, str(source))
        break

from geo_seo_hub.cli import main

if __name__ == "__main__":
    raise SystemExit(main(["seo", *sys.argv[1:]]))
