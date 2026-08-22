from __future__ import annotations

import json
from collections import Counter, defaultdict

from geo_seo_hub.paths import repository_root


def test_natural_router_dataset_has_declared_counts_and_grouped_splits():
    payload = json.loads(
        (repository_root() / "evals" / "router_natural_cases.json").read_text(
            encoding="utf-8"
        )
    )
    cases = payload["cases"]
    assert len(cases) == 600
    assert Counter(item["category"] for item in cases) == {
        "single-intent": 240,
        "near-neighbor": 120,
        "multi-intent": 80,
        "ambiguous": 80,
        "out-of-domain": 80,
    }
    assert Counter(item["split"] for item in cases) == payload["split_counts"]
    assert len({item["id"] for item in cases}) == len(cases)
    assert len({item["text"] for item in cases}) == len(cases)

    family_splits = defaultdict(set)
    for item in cases:
        family_splits[item["family_id"]].add(item["split"])
    assert all(len(splits) == 1 for splits in family_splits.values())
    assert payload["label_policy"]["status"] == "pending-human-review"
