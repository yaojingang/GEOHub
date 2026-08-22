#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from geo_seo_hub.router import route  # noqa: E402


CASES_PATH = ROOT / "evals" / "router_cases.json"
MIGRATION_PATH = ROOT / "evals" / "router_behavior_migration_0.6.json"
ALLOWED_DECISIONS = {"abstain", "clarify", "unavailable"}


def main() -> int:
    raw_cases = CASES_PATH.read_text(encoding="utf-8")
    cases = json.loads(raw_cases)
    existing_changes: dict[str, dict[str, object]] = {}
    if MIGRATION_PATH.is_file():
        existing = json.loads(MIGRATION_PATH.read_text(encoding="utf-8"))
        existing_changes = {item["id"]: item for item in existing.get("changes", [])}
    migrations: list[dict[str, object]] = []
    replacements: list[str] = []
    for case in cases:
        previous = dict(case["expected"])
        observed = route(case["text"])
        current = {
            "skill_id": observed["skill_id"],
            "workflow_id": (observed.get("workflow") or {}).get("id"),
            "runnable": observed["runnable"],
        }
        if current == previous:
            existing = existing_changes.get(case["id"])
            if existing is not None and existing.get("current") == current:
                migrations.append(existing)
            continue
        decision_type = observed["decision"]["type"]
        safe_contract_change = (
            previous["skill_id"] == current["skill_id"]
            and previous.get("workflow_id") == current["workflow_id"]
            and previous["runnable"] is True
            and current["runnable"] is False
            and decision_type in ALLOWED_DECISIONS
        )
        if not safe_contract_change:
            raise RuntimeError(
                f"unreviewed router behavior change for {case['id']}: "
                f"{previous!r} -> {current!r} ({decision_type})"
            )
        reason = {
            "abstain": "No positive GEO intent remains after negation and OOD checks.",
            "clarify": "Multiple supported intents lack an exact active workflow recipe.",
            "unavailable": "The selected capability or workflow has no active executor.",
        }[decision_type]
        migrations.append(
            {
                "id": case["id"],
                "text": case["text"],
                "previous": previous,
                "current": current,
                "decision_type": decision_type,
                "reason": reason,
            }
        )
        case["expected"] = current
        replacements.append(case["id"])

    manifest = {
        "schema_version": "1.0.0",
        "release": "0.6.0",
        "policy": "Every legacy expectation change must preserve the selected Skill and workflow and may only close execution authority.",
        "change_count": len(migrations),
        "changes": migrations,
    }
    for identifier in replacements:
        marker = f'"id": "{identifier}"'
        start = raw_cases.find(marker)
        next_case = raw_cases.find('"id": "', start + len(marker))
        runnable = raw_cases.find('"runnable": true', start)
        if start < 0 or runnable < 0 or (next_case >= 0 and runnable > next_case):
            raise RuntimeError(f"unable to preserve router case formatting for {identifier}")
        raw_cases = raw_cases[:runnable] + '"runnable": false' + raw_cases[runnable + len('"runnable": true'):]
    CASES_PATH.write_text(raw_cases, encoding="utf-8")
    MIGRATION_PATH.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(f"recorded {len(migrations)} reviewed router behavior changes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
