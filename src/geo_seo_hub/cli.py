from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from .diagnose import diagnose
from .discover import discover
from .content import content
from .measure import measure
from .seo import seo
from .router import route
from .version import package_version


class JsonArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        print(
            json.dumps({"status": "error", "message": message}, ensure_ascii=False, allow_nan=False),
            file=sys.stderr,
        )
        raise SystemExit(2)


def build_parser() -> argparse.ArgumentParser:
    parser = JsonArgumentParser(prog="geo-seo-hub")
    parser.add_argument(
        "--version",
        action="version",
        version=json.dumps(
            {
                "distribution": "geo-seo-hub",
                "name": "GEOHub",
                "version": package_version(),
            },
            ensure_ascii=False,
            sort_keys=True,
            allow_nan=False,
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    route_parser = subparsers.add_parser("route", help="Route a GEO request")
    route_parser.add_argument("--text", required=True, help="Natural-language request")

    discover_parser = subparsers.add_parser("discover", help="Generate discover artifacts")
    discover_parser.add_argument("--input", required=True, type=Path, help="GEO brief JSON")
    discover_parser.add_argument("--output", required=True, type=Path, help="Runs root directory")

    diagnose_parser = subparsers.add_parser("diagnose", help="Generate diagnosis artifacts")
    diagnose_parser.add_argument("--input", required=True, type=Path, help="Diagnosis brief JSON")
    diagnose_parser.add_argument("--output", required=True, type=Path, help="Runs root directory")

    content_parser = subparsers.add_parser("content", help="Generate evidence-lined content artifacts")
    content_parser.add_argument("--input", required=True, type=Path, help="Content brief JSON")
    content_parser.add_argument("--output", required=True, type=Path, help="Runs root directory")

    measure_parser = subparsers.add_parser("measure", help="Aggregate bounded measurement observations")
    measure_parser.add_argument("--input", required=True, type=Path, help="Measurement brief JSON")
    measure_parser.add_argument("--output", required=True, type=Path, help="Runs root directory")

    seo_parser = subparsers.add_parser("seo", help="Turn a one-line SEO request into an evidence-bounded plan")
    seo_parser.add_argument("--input", required=True, type=Path, help="One-line SEO brief JSON")
    seo_parser.add_argument("--output", required=True, type=Path, help="Runs root directory")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "route":
            result = route(args.text)
        elif args.command == "discover":
            result = discover(args.input, args.output)
        elif args.command == "diagnose":
            result = diagnose(args.input, args.output)
        elif args.command == "content":
            result = content(args.input, args.output)
        elif args.command == "measure":
            result = measure(args.input, args.output)
        else:
            result = seo(args.input, args.output)
    except (OSError, ValueError) as exc:
        print(json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False, allow_nan=False), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False))
    return 0
