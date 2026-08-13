from __future__ import annotations

import pytest

from geo_seo_hub.diagnose import analyze_html
from geo_seo_hub.intelligence.audit.audits import AUDIT_CATALOG, evaluate_audit
from geo_seo_hub.intelligence.audit.gatherers import gather_page_observations


def test_gatherer_emits_observations_without_judgment_fields():
    metrics = analyze_html(
        "<title>Guide</title><main><h1>Guide</h1><h2>Evidence</h2><p>Source method updated 2026.</p></main>",
        "https://example.com",
    )
    gathered = gather_page_observations(metrics, source_id="source-1", evidence_id="ev-1")
    assert gathered["source_id"] == "source-1"
    assert set(gathered) == {"source_id", "evidence_id", "values", "applicability"}
    assert not ({"status", "severity", "remediation"} & set(gathered))
    assert set(gathered["values"]) == set(AUDIT_CATALOG)


@pytest.mark.parametrize("audit_id", sorted(AUDIT_CATALOG))
def test_every_audit_supports_pass_fail_not_applicable_and_missing_evidence(audit_id):
    assert evaluate_audit(audit_id, 1.0, applicable=True, evidence_ids=["ev-1"])["status"] == "pass"
    assert evaluate_audit(audit_id, 0.0, applicable=True, evidence_ids=["ev-1"])["status"] == "fail"
    assert evaluate_audit(audit_id, 1.0, applicable=False, evidence_ids=["ev-1"])["status"] == "not-applicable"
    assert evaluate_audit(audit_id, None, applicable=True, evidence_ids=[])["status"] == "missing-evidence"

