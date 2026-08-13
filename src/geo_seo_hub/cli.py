from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from .diagnose import diagnose
from .discover import discover
from .content import content
from .data_retention import apply_retention_policy, purge_batch, recover_batch
from .measure import measure
from .seo import seo
from .strategy import strategy
from .knowledge import knowledge
from .quality.evaluation import run_quality_lab
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
    discover_parser.add_argument(
        "--execution-mode",
        choices=("legacy", "deterministic", "research", "provider"),
        default="legacy",
        help="Discovery execution mode; provider degrades safely when no adapter is configured",
    )

    diagnose_parser = subparsers.add_parser("diagnose", help="Generate diagnosis artifacts")
    diagnose_parser.add_argument("--input", required=True, type=Path, help="Diagnosis brief JSON")
    diagnose_parser.add_argument("--output", required=True, type=Path, help="Runs root directory")
    diagnose_parser.add_argument(
        "--execution-mode",
        choices=("legacy", "deterministic", "research", "provider"),
        default="legacy",
        help="Diagnosis execution mode; provider degrades to deterministic audits when unconfigured",
    )

    content_parser = subparsers.add_parser("content", help="Generate evidence-lined content artifacts")
    content_parser.add_argument("--input", required=True, type=Path, help="Content brief JSON")
    content_parser.add_argument("--output", required=True, type=Path, help="Runs root directory")
    content_parser.add_argument(
        "--execution-mode",
        choices=("legacy", "deterministic", "research", "provider"),
        default="legacy",
        help="Content execution mode; provider degrades to the deterministic pipeline when unconfigured",
    )

    measure_parser = subparsers.add_parser("measure", help="Measure an imported GEO engine observation bundle")
    measure_parser.add_argument("--input", required=True, type=Path, help="Engine observation bundle JSON")
    measure_parser.add_argument("--output", required=True, type=Path, help="Runs root directory")

    seo_parser = subparsers.add_parser("seo", help="Turn a one-line SEO request into an evidence-bounded plan")
    seo_parser.add_argument("--input", required=True, type=Path, help="One-line SEO brief JSON")
    seo_parser.add_argument("--output", required=True, type=Path, help="Runs root directory")

    strategy_parser = subparsers.add_parser("strategy", help="Build an offline GEO optimization plan")
    strategy_parser.add_argument("--input", required=True, type=Path, help="Strategy request JSON")
    strategy_parser.add_argument("--output", required=True, type=Path, help="Runs root directory")

    knowledge_parser = subparsers.add_parser("knowledge", help="Build and query a governed GEO knowledge graph")
    knowledge_parser.add_argument("--input", required=True, type=Path, help="Knowledge request JSON")
    knowledge_parser.add_argument("--output", required=True, type=Path, help="Runs root directory")

    eval_parser = subparsers.add_parser("eval", help="Run the GEOHub Output Eval Lab")
    eval_parser.add_argument("--suite", required=True, type=Path, help="Evaluation suite YAML")
    eval_parser.add_argument("--output", required=True, type=Path, help="Evaluation output directory")
    eval_parser.add_argument(
        "--execution-mode",
        choices=("deterministic", "command", "provider"),
        default="deterministic",
        help="Evaluation runner mode",
    )
    eval_parser.add_argument(
        "--runner-command-json",
        help="Command runner as a JSON string list; shell execution is never used",
    )
    eval_parser.add_argument("--baseline-wheel", type=Path, help="Isolated baseline wheel")
    eval_parser.add_argument("--candidate-wheel", type=Path, help="Isolated candidate wheel")

    retention_parser = subparsers.add_parser(
        "data-retention",
        help="Preview, recover, or purge governed run-retention batches",
    )
    retention_parser.add_argument("--runs-root", required=True, type=Path, help="Bounded runs root")
    retention_action = retention_parser.add_mutually_exclusive_group(required=True)
    retention_action.add_argument("--apply-policy", action="store_true", help="Preview or apply retention policy")
    retention_action.add_argument("--recover-batch", help="Recover a batch from governed trash")
    retention_action.add_argument("--purge-batch", help="Permanently purge a batch after its grace period")
    retention_parser.add_argument(
        "--confirm",
        action="store_true",
        help="Confirm a move-to-trash or permanent purge operation",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "route":
            result = route(args.text)
        elif args.command == "discover":
            result = discover(args.input, args.output, execution_mode=args.execution_mode)
        elif args.command == "diagnose":
            result = diagnose(args.input, args.output, execution_mode=args.execution_mode)
        elif args.command == "content":
            result = content(args.input, args.output, execution_mode=args.execution_mode)
        elif args.command == "measure":
            result = measure(args.input, args.output)
        elif args.command == "seo":
            result = seo(args.input, args.output)
        elif args.command == "strategy":
            result = strategy(args.input, args.output)
        elif args.command == "knowledge":
            result = knowledge(args.input, args.output)
        elif args.command == "eval":
            result = run_quality_lab(
                args.suite,
                args.output,
                execution_mode=args.execution_mode,
                runner_command_json=args.runner_command_json,
                baseline_wheel=args.baseline_wheel,
                candidate_wheel=args.candidate_wheel,
            )
        elif args.apply_policy:
            result = apply_retention_policy(args.runs_root, confirm=args.confirm)
        elif args.recover_batch:
            result = recover_batch(args.runs_root, args.recover_batch)
        else:
            result = purge_batch(args.runs_root, args.purge_batch, confirm=args.confirm)
    except (OSError, ValueError) as exc:
        print(json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False, allow_nan=False), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False))
    return 0
