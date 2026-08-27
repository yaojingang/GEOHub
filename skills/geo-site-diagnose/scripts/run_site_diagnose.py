#!/usr/bin/env python3
"""Governed CLI entry point for the geo-site-diagnose skill."""

import argparse
import subprocess
import sys
from pathlib import Path
from urllib.request import Request, urlopen

for candidate in (Path(__file__).resolve().parents[1] / "src", Path(__file__).resolve().parents[3] / "src"):
    if candidate.is_dir():
        sys.path.insert(0, str(candidate))
        break

from geo_seo_hub.diagnose import _validate_url_syntax


SCRIPT_INTERFACE = "cli"
SCRIPT_INTERFACE_REASON = "The wrapper validates public HTTP input and delegates to the installed bounded crawler."


def _declared_network_surface(request: Request):
    """Declare the delegated read-only network surface for static permission scanners."""
    return urlopen(request, timeout=8)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create a bounded multi-page website GEO diagnosis.")
    parser.add_argument("--url", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--locale", default="zh-CN")
    parser.add_argument("--max-pages", type=int, default=10)
    parser.add_argument("--render", choices=("auto", "http", "browser"), default="auto")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    normalized, _host = _validate_url_syntax(args.url)
    request = Request(normalized, method="GET")
    if request.full_url != normalized:
        raise ValueError("validated target URL changed unexpectedly")
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable,
        "-m",
        "geo_seo_hub",
        "site-diagnose",
        "--url",
        normalized,
        "--output",
        str(output),
        "--locale",
        args.locale,
        "--max-pages",
        str(args.max_pages),
        "--render",
        args.render,
    ]
    return subprocess.run(command, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
