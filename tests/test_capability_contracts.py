from __future__ import annotations

import json

from geo_seo_hub.control.capabilities import verify_capability_contracts
from geo_seo_hub.paths import repository_root
from geo_seo_hub.registry import load_registry


def test_capability_contracts_match_packaged_skill_projections():
    result = verify_capability_contracts(repository_root())
    assert result["status"] == "pass"
    assert result["checked_skill_ids"] == [
        "geo",
        "geo-content",
        "geo-diagnose",
        "geo-discover",
        "geo-knowledge",
        "geo-measure",
        "geo-strategy",
    ]
    assert result["errors"] == []


def test_capability_contracts_report_manifest_drift(tmp_path):
    root = tmp_path / "repo"
    source = repository_root()
    (root / "registry").mkdir(parents=True)
    (root / "skills" / "geo").mkdir(parents=True)
    (root / "registry" / "skills.yaml").write_text(
        (source / "registry" / "skills.yaml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (root / "registry" / "skills.schema.json").write_text(
        (source / "registry" / "skills.schema.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    manifest = json.loads(
        (source / "skills" / "geo" / "manifest.json").read_text(encoding="utf-8")
    )
    manifest["availability"] = "planned"
    (root / "skills" / "geo" / "manifest.json").write_text(
        json.dumps(manifest),
        encoding="utf-8",
    )

    result = verify_capability_contracts(
        root,
        registry=load_registry(),
        skill_ids=("geo",),
    )

    assert result["status"] == "fail"
    assert any("availability" in error for error in result["errors"])
