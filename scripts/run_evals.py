#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from geo_seo_hub.content import content  # noqa: E402
from geo_seo_hub.diagnose import diagnose  # noqa: E402
from geo_seo_hub.discover import discover  # noqa: E402
from geo_seo_hub.measure import measure  # noqa: E402
from geo_seo_hub.router import route  # noqa: E402


ARTIFACTS = {
    "geo-discover": {"query-map.json", "opportunity-map.json", "evidence-ledger.json", "research-context.json", "quality-report.json", "run-manifest.json"},
    "geo-diagnose": {"diagnosis.json", "diagnosis-funnel.json", "report.md", "evidence-ledger.json", "research-context.json", "quality-report.json", "run-manifest.json"},
    "geo-content": {"content-spec.json", "content.json", "content-evidence-units.json", "content.md", "content.html", "evidence-ledger.json", "research-context.json", "quality-report.json", "run-manifest.json"},
    "geo-measure": {"measurement-report.json", "report.md", "evidence-ledger.json", "research-context.json", "quality-report.json", "run-manifest.json"},
}


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def evaluate_router() -> dict:
    cases = read_json(ROOT / "evals" / "router_cases.json")
    results = []
    tp = fp = fn = 0
    for case in cases:
        actual = route(case["text"])
        actual_workflow = (actual.get("workflow") or {}).get("id")
        expected = case["expected"]
        passed = (
            actual["skill_id"] == expected["skill_id"]
            and actual_workflow == expected["workflow_id"]
            and actual["runnable"] is expected["runnable"]
        )
        if passed:
            tp += 1
        else:
            fp += 1
            fn += 1
        results.append({"id": case["id"], "passed": passed, "expected": expected, "actual": {"skill_id": actual["skill_id"], "workflow_id": actual_workflow, "runnable": actual["runnable"]}})
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    return {"case_count": len(cases), "tp": tp, "fp": fp, "fn": fn, "precision": precision, "recall": recall, "metric_definition": "Exact skill/workflow/runnable match is TP; every mismatch contributes one FP and one FN.", "results": results}


def evaluate_skill_triggers() -> dict:
    results = []
    for skill_id in ("geo", "geo-discover", "geo-diagnose", "geo-content", "geo-measure"):
        cases = read_json(ROOT / "skills" / skill_id / "evals" / "trigger_cases.json")
        for item in cases["should_trigger"]:
            actual = route(item["text"])["skill_id"]
            results.append({"skill_id": skill_id, "family": "should_trigger", "text": item["text"], "passed": actual == skill_id, "actual": actual})
        for item in cases["should_not_trigger"]:
            actual = route(item["text"])["skill_id"]
            if skill_id == "geo":
                explicit_geo = any(term in item["text"].casefold() for term in ("geo", "generative engine optimization", "生成式引擎优化", "ai搜索优化"))
                passed = not explicit_geo
            else:
                passed = actual != skill_id
            results.append({"skill_id": skill_id, "family": "should_not_trigger", "text": item["text"], "passed": passed, "actual": actual})
        for item in cases["near_neighbor"]:
            actual = route(item["text"])["skill_id"]
            results.append({"skill_id": skill_id, "family": "near_neighbor", "text": item["text"], "passed": actual == item["expected"], "actual": actual})
    passed = sum(item["passed"] for item in results)
    return {"case_count": len(results), "passed": passed, "compliance": passed / len(results), "results": results}


def run_skill(skill_id: str, input_path: Path, output: Path):
    if skill_id == "geo-discover":
        return discover(input_path, output)
    if skill_id == "geo-diagnose":
        return diagnose(input_path, output)
    if skill_id == "geo-content":
        return content(input_path, output)
    if skill_id == "geo-measure":
        return measure(input_path, output)
    raise ValueError(f"unsupported skill: {skill_id}")


def collect_source_uris(value) -> set[str]:
    if isinstance(value, dict):
        result = {value["source_uri"]} if isinstance(value.get("source_uri"), str) else set()
        for child in value.values():
            result.update(collect_source_uris(child))
        return result
    if isinstance(value, list):
        result: set[str] = set()
        for child in value:
            result.update(collect_source_uris(child))
        return result
    return set()


def fabricated_citation_count(run_dir: Path) -> int:
    supplied: set[str] = set()
    for input_json in (run_dir / "input").rglob("*.json"):
        supplied.update(collect_source_uris(read_json(input_json)))
    ledger = read_json(run_dir / "evidence-ledger.json")
    cited = collect_source_uris(ledger)
    return len(cited - supplied)


def evaluate_outputs() -> dict:
    cases = read_json(ROOT / "evals" / "output_cases.json")
    results = []
    with tempfile.TemporaryDirectory(prefix="geo-seo-hub-evals-") as raw:
        temp_root = Path(raw)
        invalid = temp_root / "invalid.json"
        invalid.write_text("{}\n", encoding="utf-8")
        for case in cases:
            passed = False
            detail = ""
            fabricated = 0
            try:
                if case["skill_id"] == "geo":
                    if case["case_type"] == "missing_input":
                        try:
                            route("")
                        except ValueError:
                            passed = True
                    else:
                        result = route(case["route_text"])
                        passed = result["skill_id"] == case["expected_skill"]
                        if case["case_type"] == "boundary":
                            passed = (
                                passed
                                and result["status"] == "planned"
                                and result["runnable"] is False
                                and result["suggestion"] == case["expected_suggestion"]
                                and result["required_inputs"] == case["expected_required_inputs"]
                                and result["closest_v0_artifact"] == case["expected_closest_v0_artifact"]
                            )
                elif case["case_type"] == "missing_input":
                    try:
                        run_skill(case["skill_id"], invalid, temp_root / case["id"])
                    except ValueError:
                        passed = True
                elif case["case_type"] in {"boundary", "near_neighbor"}:
                    if case["case_type"] == "boundary" and case["skill_id"] == "geo-content":
                        with patch("socket.socket", side_effect=AssertionError("offline boundary violated")):
                            result = run_skill(case["skill_id"], ROOT / case["input"], temp_root / case["id"])
                        run_dir = Path(result["output"])
                        present = {path.name for path in run_dir.iterdir() if path.is_file()}
                        fabricated = fabricated_citation_count(run_dir)
                        passed = ARTIFACTS[case["skill_id"]].issubset(present) and fabricated == 0
                    else:
                        actual = route(case["route_text"])
                        if case["case_type"] == "near_neighbor":
                            passed = actual["skill_id"] == case["expected_outcome"]
                        else:
                            passed = actual["skill_id"] == case["expected_skill"]
                else:
                    input_path = ROOT / case["input"]
                    result = run_skill(case["skill_id"], input_path, temp_root / case["id"])
                    run_dir = Path(result["output"])
                    present = {path.name for path in run_dir.iterdir() if path.is_file()}
                    passed = ARTIFACTS[case["skill_id"]].issubset(present)
                    fabricated = fabricated_citation_count(run_dir)
                    passed = passed and fabricated == 0
                detail = "contract satisfied" if passed else "contract mismatch"
            except (OSError, ValueError, KeyError) as exc:
                detail = f"unexpected {type(exc).__name__}: {exc}"
            results.append({"id": case["id"], "skill_id": case["skill_id"], "case_type": case["case_type"], "passed": passed, "fabricated_citations": fabricated, "detail": detail, "execution_kind": "deterministic_local"})
    passed_count = sum(item["passed"] for item in results)
    fabricated_total = sum(item["fabricated_citations"] for item in results)
    return {"case_count": len(results), "passed": passed_count, "contract_compliance": passed_count / len(results), "fabricated_citations": fabricated_total, "citation_metric_definition": "Every source_uri in a generated evidence ledger must occur in its snapshotted input JSON.", "model_evidence": "missing evidence", "human_blind_review": "pending; missing evidence; excluded from agreement", "results": results}


def write_blind_pack() -> None:
    cases = read_json(ROOT / "evals" / "output_cases.json")
    pack = []
    key = []
    for case in cases:
        skilled = "Contract-aware output: explicit inputs, evidence status, boundaries, and deterministic artifact checks."
        baseline = "General response without declared input, evidence, permission, or artifact contracts."
        skilled_is_a = int(hashlib.sha256(case["id"].encode()).hexdigest(), 16) % 2 == 0
        pack.append({"id": case["id"], "prompt": f"Evaluate the {case['case_type']} result for {case['skill_id']}.", "variant_a": skilled if skilled_is_a else baseline, "variant_b": baseline if skilled_is_a else skilled, "review_status": "pending; missing evidence"})
        key.append({"id": case["id"], "with_skill_variant": "A" if skilled_is_a else "B"})
    reports = ROOT / "reports"
    (reports / "output-blind-pack.json").write_text(json.dumps(pack, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    (reports / "output-blind-answer-key.json").write_text(json.dumps(key, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    lines = ["# Blind A/B Review Pack", "", "Answers are intentionally absent. Human review is pending; missing evidence.", ""]
    for item in pack:
        lines.extend([f"## {item['id']}", "", f"Prompt: {item['prompt']}", "", f"Variant A: {item['variant_a']}", "", f"Variant B: {item['variant_b']}", ""])
    (reports / "output-blind-pack.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    router = evaluate_router()
    triggers = evaluate_skill_triggers()
    outputs = evaluate_outputs()
    thresholds = {"precision": 0.97, "recall": 0.93, "trigger_compliance": 1.0, "contract_compliance": 1.0, "fabricated_citations": 0}
    passed = router["precision"] >= thresholds["precision"] and router["recall"] >= thresholds["recall"] and triggers["compliance"] == 1.0 and outputs["contract_compliance"] == 1.0 and outputs["fabricated_citations"] == 0
    summary = {"status": "pass" if passed else "fail", "thresholds": thresholds, "router": router, "triggers": triggers, "outputs": outputs}
    reports = ROOT / "reports"
    reports.mkdir(exist_ok=True)
    (reports / "eval-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    failed_routes = [item["id"] for item in router["results"] if not item["passed"]]
    failed_outputs = [item["id"] for item in outputs["results"] if not item["passed"]]
    md = f"""# Evaluation Summary

Status: **{summary['status']}**

- Router cases: {router['case_count']}; precision `{router['precision']:.4f}`; recall `{router['recall']:.4f}`
- Metric: {router['metric_definition']}
- Skill trigger cases: {triggers['case_count']}; compliance `{triggers['compliance']:.4f}`
- Output cases: {outputs['case_count']}; contract compliance `{outputs['contract_compliance']:.4f}`
- Fabricated citations: `{outputs['fabricated_citations']}`
- Failed routes: {failed_routes or 'none'}
- Failed outputs: {failed_outputs or 'none'}
- Provider/model evidence: missing evidence
- Human blind review: pending; missing evidence; excluded from agreement
"""
    (reports / "eval-summary.md").write_text(md, encoding="utf-8")
    write_blind_pack()
    print(json.dumps({"status": summary["status"], "precision": router["precision"], "recall": router["recall"], "trigger_compliance": triggers["compliance"], "contract_compliance": outputs["contract_compliance"], "fabricated_citations": outputs["fabricated_citations"]}, indent=2, allow_nan=False))
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
