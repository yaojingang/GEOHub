from __future__ import annotations

import json
from pathlib import Path

from geo_seo_hub.diagnose import diagnose
from geo_seo_hub.intelligence.audit.audits import AUDIT_CATALOG, evaluate_audit
from geo_seo_hub.intelligence.audit.scoring import score_audits


FIXTURES = Path(__file__).parent / "fixtures"


def test_audit_score_retains_reconstructable_components_and_excludes_missing():
    first, second, missing = sorted(AUDIT_CATALOG)[:3]
    audits = [
        evaluate_audit(first, 1.0, applicable=True, evidence_ids=["ev-1"]),
        evaluate_audit(second, 0.0, applicable=True, evidence_ids=["ev-1"]),
        evaluate_audit(missing, None, applicable=True, evidence_ids=[]),
    ]
    report = score_audits(audits)
    reconstructed = sum(item["weighted_value"] for item in report["components"]) / report["denominator"]
    assert round(reconstructed * 100, 6) == report["score"]
    excluded = next(item for item in report["components"] if item["audit_id"] == missing)
    assert excluded["included"] is False
    assert excluded["weighted_value"] == 0


def test_diagnosis_v2_records_catalog_policy_digest_and_traceable_remediation(tmp_path):
    result = diagnose(
        FIXTURES / "diagnosis-page.json",
        tmp_path / "runs",
        execution_mode="deterministic",
    )
    diagnosis = json.loads((Path(result["output"]) / "diagnosis.json").read_text())
    assert result["execution_mode"] == "deterministic"
    assert result["semantic_digest"] == diagnosis["semantic_digest"]
    assert diagnosis["audit_catalog_version"] == "1.0.0"
    assert diagnosis["scoring_policy_version"] == "1.0.0"
    assert len(diagnosis["audit_results"]) == len(AUDIT_CATALOG)
    assert diagnosis["audit_score"]["denominator"] > 0
    for audit in diagnosis["audit_results"]:
        assert audit["remediation"]["audit_id"] == audit["audit_id"]
        if audit["status"] in {"pass", "fail"}:
            assert audit["evidence_ids"]


def test_provider_mode_without_adapter_is_explicitly_degraded(tmp_path):
    result = diagnose(
        FIXTURES / "diagnosis-brand.json",
        tmp_path / "runs",
        execution_mode="provider",
    )
    diagnosis = json.loads((Path(result["output"]) / "diagnosis.json").read_text())
    assert result["status"] == "completed-with-warnings"
    assert diagnosis["execution"]["status"] == "degraded"
    assert diagnosis["execution"]["failures"] == ["provider mode has no configured audit adapter; deterministic audits completed"]

