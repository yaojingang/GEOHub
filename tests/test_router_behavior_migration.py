from __future__ import annotations

import json

from geo_seo_hub.paths import repository_root
from geo_seo_hub.router import route


def test_every_legacy_router_change_has_a_reviewed_migration_entry():
    root = repository_root()
    cases = json.loads((root / "evals" / "router_cases.json").read_text(encoding="utf-8"))
    migration = json.loads(
        (root / "evals" / "router_behavior_migration_0.6.json").read_text(encoding="utf-8")
    )
    indexed = {item["id"]: item for item in migration["changes"]}
    assert migration["change_count"] == len(indexed)
    assert len(indexed) > 0

    for case in cases:
        observed = route(case["text"])
        current = {
            "skill_id": observed["skill_id"],
            "workflow_id": (observed.get("workflow") or {}).get("id"),
            "runnable": observed["runnable"],
        }
        assert current == case["expected"]
        if case["id"] in indexed:
            change = indexed[case["id"]]
            assert change["current"] == current
            assert change["previous"]["runnable"] is True
            assert change["current"]["runnable"] is False
            assert change["previous"]["skill_id"] == change["current"]["skill_id"]
