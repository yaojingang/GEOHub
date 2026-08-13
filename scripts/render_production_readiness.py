#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from geo_seo_hub.quality.release import build_production_readiness  # noqa: E402
from geo_seo_hub.validation import strict_json_loads  # noqa: E402


def _load(relative: str) -> dict:
    return strict_json_loads((ROOT / relative).read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-json", type=Path, default=ROOT / "reports" / "production-readiness.json")
    parser.add_argument("--output-md", type=Path, default=ROOT / "reports" / "production-readiness.md")
    args = parser.parse_args()
    eval_report = _load("reports/eval-summary.json")
    package_report = _load("reports/package-verification.json")
    install_report = _load("reports/install-simulation.json")
    meta_report = _load("reports/yao-meta-gates.json")
    provenance_report = _load("reports/release-provenance-verification.json")
    sbom = _load("reports/release-sbom.json")
    deterministic = {
        "output-eval": "pass" if eval_report.get("status") == "pass" else "fail",
        "package": "pass" if package_report.get("status") == "pass" and package_report.get("package_count") == 11 else "fail",
        "install": "pass" if install_report.get("status") == "pass" else "fail",
        "provenance": "pass" if provenance_report.get("status") == "pass" else "fail",
        "sbom": "pass" if len(sbom.get("components", [])) >= 2 else "fail",
        "trust-and-permissions": "pass" if meta_report.get("status") in {"pass", "pass-with-waivers"} and not meta_report.get("release_blocking") else "fail",
    }
    external = {
        "ci-attestation": "missing evidence",
        "human-blind-review": "missing evidence",
        "real-platform-benchmark": "missing evidence",
        "adoption-evidence": "missing evidence",
        "commercial-legal-review": "missing evidence",
        "strategy-external-effect": "missing evidence",
        "knowledge-production-eval": "missing evidence",
    }
    payload = build_production_readiness(deterministic_statuses=deterministic, external_statuses=external)
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    lines = [
        "# GEO SEO Hub Production Readiness Review",
        "",
        f"Version: `{payload['product']['version']}` · Maturity: **{payload['product']['maturity']}**",
        "",
        f"Production decision: **{payload['production_decision']}**",
        f"Experimental release decision: **{payload['experimental_release_decision']}**",
        "",
        "The deterministic engineering and distribution evidence supports an Experimental release. Production promotion remains blocked by the external evidence gates listed below.",
        "",
        "| Gate | Status | Owner | Evidence | Verification | Required source fix |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for gate in payload["gates"]:
        lines.append(f"| {gate['name']} | {gate['status']} | {gate['owner']} | `{gate['evidence']}` | `{gate['verification_command']}` | {gate['source_fix']} |")
    lines.extend(
        [
            "",
            "## Claim boundary",
            "",
            "Builder trust is local and unsigned. No SLSA level is claimed. External GEO effect remains missing evidence. CI artifact attestation must be verified independently before any trusted-builder statement.",
        ]
    )
    args.output_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"status": "pass", "production_decision": payload["production_decision"], "experimental_release_decision": payload["experimental_release_decision"], "missing_evidence": payload["summary"]["missing_evidence"]}, indent=2, allow_nan=False))
    return 0 if payload["experimental_release_decision"] == "eligible" else 2


if __name__ == "__main__":
    raise SystemExit(main())
