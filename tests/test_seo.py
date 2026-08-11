from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from geo_seo_hub.seo import seo
from geo_seo_hub.validation import ArtifactValidationError, validate_artifact

FIXTURE = Path(__file__).parent / "fixtures" / "seo-brief.json"

def _clock():
    return datetime(2026, 8, 11, 12, 0, tzinfo=timezone.utc)

def _read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))

def test_one_line_seo_builds_an_honest_advisory_run(tmp_path):
    result = seo(FIXTURE, tmp_path / "runs", clock=_clock)
    run = Path(result["output"])
    assert result["status"] == "completed-with-warnings"
    assert result["work_mode"] == "technical-audit"
    plan = _read(run / "seo-plan.json")
    assert plan["claim_status"] == "advisory"
    assert plan["write_authorized"] is False
    assert plan["search_surfaces"] == ["organic-search"]
    assert "rendered page or crawl evidence" in plan["missing_evidence"]
    assert not plan["findings"]
    assert [item["stage"] for item in plan["action_plan"]][:3] == ["scope", "access-and-discovery", "fetch-render-and-indexability"]
    expected = {"input/seo-brief.json", "seo-plan.json", "report.md", "evidence-ledger.json", "quality-report.json", "run-manifest.json"}
    assert {path.relative_to(run).as_posix() for path in run.rglob("*") if path.is_file()} == expected
    for filename, schema in {"input/seo-brief.json":"seo-brief", "seo-plan.json":"seo-plan", "evidence-ledger.json":"evidence-ledger", "quality-report.json":"quality-report", "run-manifest.json":"run-manifest"}.items():
        validate_artifact(schema, _read(run / filename))

@pytest.mark.parametrize(("prompt_text", "mode"), [("为产品做关键词研究和 keyword-to-page map", "keyword-map"), ("分析 Search Console 导出里自然流量下降的原因", "incident"), ("为网站迁移生成 redirect map 和回滚方案", "migration"), ("设计一个有对照组和停止规则的 SEO 实验", "experiment"), ("检查多语言电商站的 hreflang 和商品变体", "international-commerce")])
def test_one_line_seo_classifies_bounded_work_modes(tmp_path, prompt_text, mode):
    payload = _read(FIXTURE)
    payload["brief_id"] = f"mode-{mode}"
    payload["request"] = prompt_text
    path = tmp_path / f"{mode}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    assert seo(path, tmp_path / mode, clock=_clock)["work_mode"] == mode

def test_one_line_seo_preserves_evidence_without_promoting_a_finding(tmp_path):
    payload = _read(FIXTURE)
    payload["evidence"] = [{"evidence_id":"ev-response", "claim":"The supplied snapshot returned HTTP 200.", "source_uri":"urn:seo-fixture:response", "evidence_type":"http"}]
    path = tmp_path / "with-evidence.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    run = Path(seo(path, tmp_path / "runs", clock=_clock)["output"])
    assert _read(run / "evidence-ledger.json")["records"][0]["status"] == "provided"
    plan = _read(run / "seo-plan.json")
    assert plan["findings"] == []
    assert "indexation outcome evidence" in plan["missing_evidence"]

def test_one_line_seo_rejects_write_claim_without_explicit_authorization(tmp_path):
    payload = _read(FIXTURE)
    payload["request"] = "直接修复 canonical、sitemap 和 robots.txt"
    path = tmp_path / "write-request.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    run = Path(seo(path, tmp_path / "runs", clock=_clock)["output"])
    plan = _read(run / "seo-plan.json")
    assert plan["work_mode"] == "implementation-request"
    assert plan["write_authorized"] is False
    assert "explicit write authorization, target URL, and rollback boundary" in plan["missing_evidence"]

def test_one_line_seo_requires_matching_mode_authorization_and_rollback(tmp_path):
    payload = _read(FIXTURE)
    payload.update({"request":"Implement the canonical fix", "authorized_action":"implementation"})
    missing_rollback = tmp_path / "missing-rollback.json"
    missing_rollback.write_text(json.dumps(payload), encoding="utf-8")
    missing_plan = _read(Path(seo(missing_rollback, tmp_path / "missing", clock=_clock)["output"]) / "seo-plan.json")
    assert missing_plan["write_authorized"] is False
    assert "explicit write authorization, target URL, and rollback boundary" in missing_plan["missing_evidence"]

    payload["rollback_boundary"] = "Revert the exact changed files to the recorded before-state if verification fails."
    authorized = tmp_path / "authorized.json"
    authorized.write_text(json.dumps(payload), encoding="utf-8")
    authorized_plan = _read(Path(seo(authorized, tmp_path / "authorized", clock=_clock)["output"]) / "seo-plan.json")
    assert authorized_plan["write_authorized"] is True
    assert authorized_plan["rollback_boundary"] == payload["rollback_boundary"]
    assert "explicit write authorization, target URL, and rollback boundary" not in authorized_plan["missing_evidence"]

    payload["target_urls"] = []
    missing_target = tmp_path / "missing-target.json"
    missing_target.write_text(json.dumps(payload), encoding="utf-8")
    missing_target_plan = _read(Path(seo(missing_target, tmp_path / "missing-target", clock=_clock)["output"]) / "seo-plan.json")
    assert missing_target_plan["write_authorized"] is False
    assert "explicit write authorization, target URL, and rollback boundary" in missing_target_plan["missing_evidence"]

    payload["request"] = "Run a technical SEO audit"
    advisory = tmp_path / "authorized-audit.json"
    advisory.write_text(json.dumps(payload), encoding="utf-8")
    advisory_plan = _read(Path(seo(advisory, tmp_path / "advisory", clock=_clock)["output"]) / "seo-plan.json")
    assert advisory_plan["work_mode"] == "technical-audit"
    assert advisory_plan["write_authorized"] is False

def test_one_line_seo_uses_bounded_english_markers_and_engine_aliases(tmp_path):
    payload = _read(FIXTURE)
    payload["request"] = "Audit URL prefix handling and indexability for ChatGPT"
    path = tmp_path / "bounded-markers.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    run = Path(seo(path, tmp_path / "runs", clock=_clock)["output"])
    plan = _read(run / "seo-plan.json")
    assert plan["work_mode"] == "technical-audit"
    assert plan["engine_scope"] == ["openai"]

    payload["brief_id"] = "search-console-engine"
    payload["request"] = "Analyze a Search Console traffic drop"
    search_console = tmp_path / "search-console.json"
    search_console.write_text(json.dumps(payload), encoding="utf-8")
    search_console_plan = _read(Path(seo(search_console, tmp_path / "search-console-runs", clock=_clock)["output"]) / "seo-plan.json")
    assert search_console_plan["work_mode"] == "incident"
    assert search_console_plan["engine_scope"] == ["google"]

def test_seo_plan_schema_rejects_runtime_findings(tmp_path):
    run = Path(seo(FIXTURE, tmp_path / "runs", clock=_clock)["output"])
    plan = _read(run / "seo-plan.json")
    plan["findings"] = [{"claim":"Unsupported live-site conclusion"}]
    with pytest.raises(ArtifactValidationError):
        validate_artifact("seo-plan", plan)

def test_one_line_seo_rejects_credentials_and_nonfinite_json(tmp_path):
    payload = _read(FIXTURE)
    payload["target_urls"] = ["https://example.com/?token=secret"]
    credential = tmp_path / "credential.json"
    credential.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="credentials"):
        seo(credential, tmp_path / "credential-runs", clock=_clock)
    overflow = tmp_path / "overflow.json"
    overflow.write_text(FIXTURE.read_text(encoding="utf-8")[:-2] + ',"score":1e9999}\n', encoding="utf-8")
    with pytest.raises((ArtifactValidationError, ValueError)):
        seo(overflow, tmp_path / "overflow-runs", clock=_clock)

def test_one_line_seo_rejects_duplicate_evidence_ids(tmp_path):
    payload = _read(FIXTURE)
    item = {"evidence_id":"same", "claim":"One observation.", "source_uri":"urn:seo:test:one", "evidence_type":"other"}
    payload["evidence"] = [item, {**item, "claim":"Another observation.", "source_uri":"urn:seo:test:two"}]
    path = tmp_path / "duplicate-evidence.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate evidence_id"):
        seo(path, tmp_path / "runs", clock=_clock)
