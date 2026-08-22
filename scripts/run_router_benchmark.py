#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from geo_seo_hub.control.routing import FastEmbedSemanticScorer  # noqa: E402
from geo_seo_hub.quality.routing_eval import evaluate_routing_cases  # noqa: E402
from geo_seo_hub.registry import load_registry  # noqa: E402
from geo_seo_hub.router import route  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate GEOHub routing on the grouped 600-case dataset")
    parser.add_argument(
        "--split",
        choices=("calibration", "public-test", "private-holdout", "all"),
        default="public-test",
    )
    parser.add_argument("--semantic-cache", type=Path)
    parser.add_argument("--lexical-only", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    payload = json.loads((ROOT / "evals" / "router_natural_cases.json").read_text(encoding="utf-8"))
    cases = payload["cases"]
    if args.split != "all":
        cases = [item for item in cases if item["split"] == args.split]

    scorer = None
    model_status = "lexical-only"
    if not args.lexical_only:
        try:
            scorer = FastEmbedSemanticScorer(load_registry(), cache_dir=args.semantic_cache)
            model_status = "cached-model-ready"
        except (RuntimeError, OSError, ValueError) as exc:
            result = {
                "status": "missing-evidence",
                "dataset_id": payload["dataset_id"],
                "split": args.split,
                "case_count": len(cases),
                "model_status": "unavailable",
                "human_label_status": payload["label_policy"]["status"],
                "reason": f"Cached semantic model unavailable: {type(exc).__name__}.",
            }
            serialized = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n"
            if args.output:
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_text(serialized, encoding="utf-8")
            print(serialized, end="")
            return 2

    def route_request(text: str):
        return route(text, hybrid_scorer=scorer) if scorer is not None else route(text)

    metrics = evaluate_routing_cases(cases, route_request)
    metrics.pop("results")
    result = {
        "status": "pending-human-review",
        "dataset_id": payload["dataset_id"],
        "split": args.split,
        "model_status": model_status,
        "model_id": scorer.model_id if scorer is not None else None,
        "human_label_status": payload["label_policy"]["status"],
        "promotion_gate": "locked-until-human-adjudication",
        "metrics": metrics,
    }
    serialized = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized, encoding="utf-8")
    print(serialized, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
