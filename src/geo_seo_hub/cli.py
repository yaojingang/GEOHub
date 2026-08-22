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
from .control.planning import compile_task_plan, write_task_plan
from .control.execution import abort_workflow, continue_workflow, start_workflow
from .control.workflow import WorkflowRunner
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
    route_parser.add_argument("--plan-output", type=Path, help="Write a validated TaskPlan JSON")
    route_parser.add_argument("--semantic-cache", type=Path, help="FastEmbed cache containing the prepared local model")
    route_parser.add_argument("--lexical-only", action="store_true", help="Disable cached semantic routing")

    workflow_parser = subparsers.add_parser("workflow", help="Run or resume a validated TaskPlan")
    workflow_actions = workflow_parser.add_subparsers(dest="workflow_action", required=True)
    workflow_start = workflow_actions.add_parser("start", help="Start a TaskPlan and run to its next gate")
    workflow_start.add_argument("--plan", required=True, type=Path)
    workflow_start.add_argument("--state", required=True, type=Path)
    workflow_start.add_argument("--inputs", required=True, type=Path)
    workflow_start.add_argument("--output", required=True, type=Path)
    workflow_start.add_argument("--run-id")
    workflow_status = workflow_actions.add_parser("status", help="Read durable workflow state")
    workflow_status.add_argument("--state", required=True, type=Path)
    workflow_approve = workflow_actions.add_parser("approve", help="Decide the current human approval gate")
    workflow_approve.add_argument("--state", required=True, type=Path)
    workflow_approve.add_argument("--reviewer", required=True)
    workflow_approve.add_argument("--reject", action="store_true")
    workflow_external = workflow_actions.add_parser("resume-external", help="Resume with validated external evidence")
    workflow_external.add_argument("--state", required=True, type=Path)
    workflow_external.add_argument("--checkpoint", required=True)
    workflow_external.add_argument("--evidence", required=True)
    workflow_retry = workflow_actions.add_parser("retry", help="Retry the current idempotent failed step")
    workflow_retry.add_argument("--state", required=True, type=Path)
    workflow_abort = workflow_actions.add_parser("abort", help="Abort a non-terminal workflow")
    workflow_abort.add_argument("--state", required=True, type=Path)
    workflow_abort.add_argument("--reason", required=True)
    workflow_migrate = workflow_actions.add_parser("migrate", help="Back up and migrate v1 state to v2")
    workflow_migrate.add_argument("--state", required=True, type=Path)

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
            semantic_scorer = None
            semantic_status = "disabled" if args.lexical_only else "unavailable"
            if not args.lexical_only:
                try:
                    from .control.routing import FastEmbedSemanticScorer
                    from .registry import load_registry

                    semantic_scorer = FastEmbedSemanticScorer(
                        load_registry(),
                        cache_dir=args.semantic_cache,
                    )
                    semantic_status = "active"
                except (ImportError, RuntimeError, OSError, ValueError):
                    semantic_scorer = None
            result = (
                route(args.text, hybrid_scorer=semantic_scorer)
                if semantic_scorer is not None
                else route(args.text)
            )
            result["decision"].setdefault("semantic_status", semantic_status)
            if args.plan_output is not None:
                task_plan = compile_task_plan(args.text, result)
                write_task_plan(args.plan_output, task_plan)
                result["task_plan"] = {
                    "plan_id": task_plan["plan_id"],
                    "status": task_plan["status"],
                    "plan_digest": task_plan["plan_digest"],
                    "path": str(args.plan_output),
                }
        elif args.command == "workflow":
            runner = WorkflowRunner(args.state)
            if args.workflow_action == "start":
                result = start_workflow(
                    args.plan,
                    args.state,
                    args.inputs,
                    args.output,
                    run_id=args.run_id,
                )
            elif args.workflow_action == "status":
                result = runner.load()
            elif args.workflow_action == "approve":
                result = runner.decide_approval(
                    approved=not args.reject,
                    reviewer=args.reviewer,
                )
                if result["status"] == "running":
                    result = continue_workflow(args.state)
            elif args.workflow_action == "resume-external":
                result = runner.resume_external(args.checkpoint, args.evidence)
                if result["status"] == "running":
                    result = continue_workflow(args.state)
            elif args.workflow_action == "retry":
                runner.retry()
                result = continue_workflow(args.state)
            elif args.workflow_action == "abort":
                result = abort_workflow(args.state, args.reason)
            else:
                result = runner.migrate()
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
