#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from geo_seo_hub.quality.review import adjudicate_review  # noqa: E402
from geo_seo_hub.validation import strict_json_loads, validate_artifact  # noqa: E402


def _read_json(path: Path):
    try:
        return strict_json_loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"Unable to load {path}: {exc}") from exc


def _write_json(path: Path, value) -> None:
    descriptor, raw_temporary = tempfile.mkstemp(prefix=f".{path.name}.tmp-", dir=path.parent)
    temporary = Path(raw_temporary)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Adjudicate a GEOHub blind output review")
    parser.add_argument("--eval-result", required=True, type=Path)
    parser.add_argument("--pack", required=True, type=Path)
    parser.add_argument("--answer-key", required=True, type=Path)
    parser.add_argument("--decisions", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        eval_result = _read_json(args.eval_result)
        report = adjudicate_review(
            _read_json(args.pack),
            _read_json(args.answer_key),
            _read_json(args.decisions),
            eval_result=eval_result,
        )
        validate_artifact("eval-result", eval_result)
        args.output.mkdir(parents=True, exist_ok=True)
        _write_json(args.output / "review-adjudication.json", report)
        _write_json(args.output / "eval-result.json", eval_result)
    except ValueError as exc:
        print(json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False, allow_nan=False), file=sys.stderr)
        return 2
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
