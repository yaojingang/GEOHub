from __future__ import annotations

import json
from pathlib import Path

from geo_seo_hub.content import content
from geo_seo_hub.validation import validate_artifact


def _write_brief(path: Path, *, with_evidence: bool = True) -> Path:
    brief = {
        "mode": "explainer",
        "topic": "证据化内容",
        "evidence": (
            [{"label": "ev-1", "claim": "产品支持离线运行", "source_uri": "https://example.com/evidence"}]
            if with_evidence
            else []
        ),
    }
    path.write_text(json.dumps(brief, ensure_ascii=False), encoding="utf-8")
    return path


def test_claim_map_covers_supported_factual_claims_without_fabricated_sources(tmp_path):
    result = content(
        _write_brief(tmp_path / "brief.json"),
        tmp_path / "runs",
        execution_mode="deterministic",
    )
    run = Path(result["output"])
    claim_map = json.loads((run / "claim-map.json").read_text())
    ledger = json.loads((run / "evidence-ledger.json").read_text())
    validate_artifact("claim-map", claim_map)
    assert claim_map["summary"]["support_rate"] == 1.0
    assert claim_map["summary"]["fabricated_citations"] == 0
    assert {source_id for claim in claim_map["claims"] for source_id in claim["source_ids"]} <= {
        item["evidence_id"] for item in ledger["records"]
    }
    assert "claim-map.json" in json.loads((run / "run-manifest.json").read_text())["artifacts"]


def test_claim_map_marks_unverified_source_claim_with_repair_action(tmp_path):
    brief = {
        "mode": "refine",
        "topic": "待核验内容",
        "source_content": "该能力覆盖全部市场。",
    }
    path = tmp_path / "brief.json"
    path.write_text(json.dumps(brief, ensure_ascii=False), encoding="utf-8")
    result = content(path, tmp_path / "runs", execution_mode="deterministic")
    claim_map = json.loads((Path(result["output"]) / "claim-map.json").read_text())
    assert claim_map["claims"][0]["support_status"] == "unsupported"
    assert claim_map["claims"][0]["source_ids"] == []
    assert claim_map["claims"][0]["repair_action"]

