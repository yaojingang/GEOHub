#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
import tomllib
from datetime import date
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from geo_seo_hub.registry import load_registry  # noqa: E402
from geo_seo_hub.router import (  # noqa: E402
    GOVERNED_ACTION_OBJECT_ARTICLES,
    GOVERNED_ADDITIVE_CONNECTORS,
    GOVERNED_EN_ACTION_LEAD_INS,
    GOVERNED_SEQUENCE_CONNECTORS,
    GOVERNED_ZH_ACTION_LEAD_INS,
    GOVERNED_ZH_INTENT_SUFFIX_BLOCKS,
    _ACTION_LEAD_IN_RE,
    _ACTION_OBJECT_ARTICLE_RE,
    _ADDITIVE_CONNECTOR_RE,
    _CLAUSE_BOUNDARY_RE,
    _GOVERNED_ADDITIVE_PATTERN,
    _GOVERNED_EN_ACTION_LEAD_IN_PATTERN,
    _GOVERNED_SEQUENCE_PATTERN,
    _GOVERNED_SEQUENCE_EXCLUSIVITY_TOKENS,
    _GOVERNED_ZH_ACTION_LEAD_IN_PATTERN,
    _EN_ACTION_LEAD_IN_RE,
    _SEQUENCE_CONNECTOR_RE,
    _SEQUENCE_SCOPE_TOKENS,
    _WORKFLOW_CONNECTOR_RE,
    _ZH_ACTION_LEAD_IN_TOKEN_RE,
    build_action_phrase_index,
    build_intent_index,
)
from geo_seo_hub.validation import load_schema  # noqa: E402


def fail(message: str) -> None:
    raise SystemExit(f"repository verification failed: {message}")


EXPECTED_GOVERNED_ADDITIVE_CONNECTORS = (
    ("and also", r"\band\s+also\b", True),
    ("also", r"\balso\b", True),
    ("and", r"\band\b", False),
    ("plus", r"\bplus\b(?!-size\b)", False),
    ("还要", r"还要", True),
    ("也要", r"也要", True),
    ("还需", r"还需", True),
    ("同时", r"同时", True),
    ("并且", r"并且", False),
    ("以及", r"以及", False),
    ("并", r"并", False),
    ("且", r"且", False),
    ("和", r"和", False),
    ("加", r"加", False),
    ("及", r"及", False),
)
EXPECTED_GOVERNED_SEQUENCE_CONNECTORS = (
    ("and then", r"\band\s+then\b", True),
    ("then", r"\bthen\b", True),
    ("followed by", r"\bfollowed\s+by\b", True),
    ("然后", r"然后", True),
    ("再", r"再", True),
)
EXPECTED_GOVERNED_EN_ACTION_LEAD_INS = ("need", "want", "plan", "intend", "prepare")
EXPECTED_GOVERNED_ZH_ACTION_LEAD_INS = (
    "单独",
    "仅仅",
    "需要",
    "继续",
    "打算",
    "准备",
    "页面",
    "请",
    "想",
    "去",
    "要",
    "做",
    "仅",
    "再",
    "只",
    "光",
)
EXPECTED_GOVERNED_ACTION_OBJECT_ARTICLES = ("a", "an", "the", "一个", "个")
EXPECTED_GOVERNED_ZH_INTENT_SUFFIX_BLOCKS = (("发布", ("会", "者")),)
EXPECTED_EN_ACTION_LEAD_IN_PATTERN = (
    r"(?:need|want|plan|intend|prepare)\b\s+(?:to\b\s+)?"
)
EXPECTED_ZH_ACTION_LEAD_IN_PATTERN = (
    r"(?:单\s*独|仅仅|需要|继续|打算|准备|页面|请|想|去|要|做|仅|再|只|光)\s*"
)
EXPECTED_ACTION_OBJECT_ARTICLE_PATTERN = r"(?:(?:a|an|the)\b|一个|个)\s*"
ACTIVE_SKILLS = ("geo", "geo-discover", "geo-diagnose", "geo-content", "geo-measure", "seo")
CANONICAL_DISTRIBUTION = "geo-seo-hub"
CANONICAL_MODULE = "geo_seo_hub"
LEGACY_DISTRIBUTION = "yao" + "-geo"
LEGACY_MODULE = "yao" + "_geo"
HISTORICAL_NAMESPACE_FILES = {
    "THIRD_PARTY_NOTICES.md",
    "docs/migration-source-ledger.md",
}
NAMESPACE_TEXT_SUFFIXES = {".html", ".json", ".jsonl", ".md", ".py", ".toml", ".txt", ".yaml", ".yml"}


def verify_namespace_consistency(root: Path = ROOT) -> None:
    project_path = root / "pyproject.toml"
    if not project_path.is_file():
        fail("pyproject.toml is missing")
    project = tomllib.loads(project_path.read_text(encoding="utf-8"))
    metadata = project.get("project", {})
    if metadata.get("name") != CANONICAL_DISTRIBUTION:
        fail("distribution name must be geo-seo-hub")
    if metadata.get("scripts") != {CANONICAL_DISTRIBUTION: f"{CANONICAL_MODULE}.cli:main"}:
        fail("CLI and module entrypoint must use the canonical namespace")
    if not (root / "src" / CANONICAL_MODULE).is_dir() or (root / "src" / LEGACY_MODULE).exists():
        fail("Python package directory must use only geo_seo_hub")

    data_files = project.get("tool", {}).get("setuptools", {}).get("data-files", {})
    if not data_files or any(
        destination != "share/geo-seo-hub" and not destination.startswith("share/geo-seo-hub/")
        for destination in data_files
    ):
        fail("installed data destinations must use share/geo-seo-hub")

    candidates = [
        root / name
        for name in (
            "README.md",
            "SECURITY.md",
            "COMMERCIAL-LICENSING.md",
            "CONTRIBUTING.md",
            "LICENSE-SCOPE.md",
            "Makefile",
            "VERSION",
            "pyproject.toml",
        )
    ]
    for directory in (".github", "docs", "reports", "scripts", "skills", "src", "tests"):
        base = root / directory
        if base.is_dir():
            candidates.extend(
                path
                for path in base.rglob("*")
                if path.is_file() and path.suffix.casefold() in NAMESPACE_TEXT_SUFFIXES
            )

    offenders = []
    for path in candidates:
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        if relative in HISTORICAL_NAMESPACE_FILES:
            continue
        text = path.read_text(encoding="utf-8")
        if LEGACY_DISTRIBUTION in text or LEGACY_MODULE in text:
            offenders.append(relative)
    if offenders:
        fail("legacy namespace marker found outside historical evidence: " + ", ".join(sorted(set(offenders))))


def verify_version_consistency(root: Path = ROOT) -> str:
    version_path = root / "VERSION"
    if not version_path.is_file():
        fail("VERSION is missing")
    version = version_path.read_text(encoding="utf-8").strip()
    if not re.fullmatch(r"(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)", version):
        fail("VERSION must be a stable semantic version")

    project_path = root / "pyproject.toml"
    if not project_path.is_file():
        fail("pyproject.toml is missing")
    project = tomllib.loads(project_path.read_text(encoding="utf-8"))
    if project.get("project", {}).get("version") != version:
        fail("pyproject.toml version must match VERSION")

    for skill_id in ACTIVE_SKILLS:
        manifest_path = root / "skills" / skill_id / "manifest.json"
        if not manifest_path.is_file():
            fail(f"{skill_id} manifest is missing")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("version") != version:
            fail(f"{skill_id} manifest version must match VERSION")
    return version


def verify_additive_connector_parity() -> None:
    tokens = [token for token, _, _ in GOVERNED_ADDITIVE_CONNECTORS]
    patterns = [pattern for _, pattern, _ in GOVERNED_ADDITIVE_CONNECTORS]
    if tuple(GOVERNED_ADDITIVE_CONNECTORS) != EXPECTED_GOVERNED_ADDITIVE_CONNECTORS:
        fail("governed additive connector inventory is invalid")
    compiled = "(?:" + "|".join(patterns) + ")"
    if (
        compiled != _GOVERNED_ADDITIVE_PATTERN
        or _ADDITIVE_CONNECTOR_RE.pattern != compiled
        or compiled not in _CLAUSE_BOUNDARY_RE.pattern
        or compiled not in _WORKFLOW_CONNECTOR_RE.pattern
        or set(tokens) & _SEQUENCE_SCOPE_TOKENS
    ):
        fail("governed additive connector parity is broken")


def verify_sequence_connector_parity() -> None:
    if tuple(GOVERNED_SEQUENCE_CONNECTORS) != EXPECTED_GOVERNED_SEQUENCE_CONNECTORS:
        fail("governed sequence connector inventory is invalid")
    patterns = [pattern for _, pattern, _ in GOVERNED_SEQUENCE_CONNECTORS]
    tokens = {token for token, _, _ in GOVERNED_SEQUENCE_CONNECTORS}
    exclusivity_tokens = frozenset(
        token
        for token, _, preserves_exclusivity in GOVERNED_SEQUENCE_CONNECTORS
        if preserves_exclusivity
    )
    compiled = "(?:" + "|".join(patterns) + ")"
    if (
        compiled != _GOVERNED_SEQUENCE_PATTERN
        or _SEQUENCE_CONNECTOR_RE.pattern != compiled
        or compiled not in _CLAUSE_BOUNDARY_RE.pattern
        or compiled not in _WORKFLOW_CONNECTOR_RE.pattern
        or tokens & _SEQUENCE_SCOPE_TOKENS
        or _GOVERNED_SEQUENCE_EXCLUSIVITY_TOKENS != exclusivity_tokens
    ):
        fail("governed sequence connector parity is broken")


def verify_action_language_parity() -> None:
    if (
        tuple(GOVERNED_EN_ACTION_LEAD_INS) != EXPECTED_GOVERNED_EN_ACTION_LEAD_INS
        or tuple(GOVERNED_ZH_ACTION_LEAD_INS) != EXPECTED_GOVERNED_ZH_ACTION_LEAD_INS
        or tuple(GOVERNED_ACTION_OBJECT_ARTICLES)
        != EXPECTED_GOVERNED_ACTION_OBJECT_ARTICLES
        or tuple(GOVERNED_ZH_INTENT_SUFFIX_BLOCKS)
        != EXPECTED_GOVERNED_ZH_INTENT_SUFFIX_BLOCKS
        or _GOVERNED_EN_ACTION_LEAD_IN_PATTERN != EXPECTED_EN_ACTION_LEAD_IN_PATTERN
        or _GOVERNED_ZH_ACTION_LEAD_IN_PATTERN != EXPECTED_ZH_ACTION_LEAD_IN_PATTERN
        or _ZH_ACTION_LEAD_IN_TOKEN_RE.pattern != EXPECTED_ZH_ACTION_LEAD_IN_PATTERN
        or EXPECTED_EN_ACTION_LEAD_IN_PATTERN not in _ACTION_LEAD_IN_RE.pattern
        or EXPECTED_ZH_ACTION_LEAD_IN_PATTERN not in _ACTION_LEAD_IN_RE.pattern
        or _EN_ACTION_LEAD_IN_RE.pattern
        != rf"(?:please\s+|{EXPECTED_EN_ACTION_LEAD_IN_PATTERN})"
        or _ACTION_OBJECT_ARTICLE_RE.pattern != EXPECTED_ACTION_OBJECT_ARTICLE_PATTERN
    ):
        fail("governed action language inventory is invalid")


def main() -> int:
    verify_additive_connector_parity()
    verify_sequence_connector_parity()
    verify_action_language_parity()
    verify_namespace_consistency()
    verify_version_consistency()
    if "GNU AFFERO GENERAL PUBLIC LICENSE" not in (ROOT / "LICENSE").read_text(encoding="utf-8"):
        fail("LICENSE is not the GNU AGPLv3 text")

    schemas = sorted((ROOT / "schemas").glob("*.schema.json"))
    expected_schema_names = {
        "brand-fact-card.schema.json",
        "content-spec.schema.json",
        "content-evidence-units.schema.json",
        "diagnosis-funnel.schema.json",
        "evidence-ledger.schema.json",
        "geo-brief.schema.json",
        "measurement-brief.schema.json",
        "measurement-report.schema.json",
        "opportunity-map.schema.json",
        "quality-report.schema.json",
        "query-map.schema.json",
        "research-context.schema.json",
        "research-evidence-registry.schema.json",
        "run-manifest.schema.json",
        "seo-brief.schema.json",
        "seo-plan.schema.json",
    }
    actual_schema_names = {path.name for path in schemas}
    if actual_schema_names != expected_schema_names:
        fail(
            "protocol schema inventory differs; "
            f"missing={sorted(expected_schema_names - actual_schema_names)}, "
            f"extra={sorted(actual_schema_names - expected_schema_names)}"
        )
    for path in schemas:
        schema = json.loads(path.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        if (
            path.name != "research-evidence-registry.schema.json"
            and schema.get("properties", {}).get("protocol_version", {}).get("const") != "1.0.0"
        ):
            fail(f"{path.name} does not pin protocol_version 1.0.0")

    registry = load_registry(ROOT / "registry" / "skills.yaml")
    registered = {item["id"]: item for item in registry["skills"]}
    action_index = build_action_phrase_index(registry)
    intent_index = build_intent_index(registry)
    registered_intents = {
        " ".join(intent.casefold().split())
        for skill in registry["skills"]
        for intent in skill["intents"]
    }
    missing_action_intents = registered_intents - action_index.phrases
    if missing_action_intents:
        fail(
            "registry intents missing from router action index: "
            + ", ".join(sorted(missing_action_intents))
        )
    indexed_intents = {
        skill_id: {phrase for phrase, _ in patterns}
        for skill_id, patterns in intent_index.patterns_by_skill.items()
    }
    for skill in registry["skills"]:
        expected_intents = {
            " ".join(intent.casefold().split())
            for intent in skill["intents"]
            if intent.strip()
        }
        if indexed_intents.get(skill["id"]) != expected_intents:
            fail(f"{skill['id']} intent index parity is broken")
    for skill_id in ACTIVE_SKILLS:
        if registered[skill_id]["status"] != "active":
            fail(f"{skill_id} must be active")
    for skill in registry["skills"]:
        if skill["status"] != "active" and not all(skill.get(key) for key in ("nearest_active", "required_inputs", "closest_v0_artifact")):
            fail(f"{skill['id']} planned route metadata is incomplete")

    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    if project["project"].get("requires-python") != ">=3.11,<3.15":
        fail("supported Python range must be >=3.11,<3.15")

    required_files = {
        "geo": ("SKILL.md", "manifest.json", "agents/interface.yaml", "references/routing-contract.md", "scripts/run_route.py", "evals/trigger_cases.json", "evals/semantic_config.json", "evals/output/cases.jsonl", "reports/output_quality_scorecard.md", "reports/trust-report.md", "reports/skill-ir.json"),
        "geo-discover": (
            "SKILL.md",
            "manifest.json",
            "agents/interface.yaml",
            "references/discovery-method.md",
            "references/input-example.json",
            "scripts/run_discover.py",
            "evals/trigger_cases.json", "evals/semantic_config.json", "evals/output/cases.jsonl", "reports/output_quality_scorecard.md", "reports/trust-report.md", "reports/skill-ir.json",
        ),
        "geo-diagnose": (
            "SKILL.md",
            "manifest.json",
            "agents/interface.yaml",
            "references/diagnosis-method.md",
            "references/input-example.json",
            "scripts/run_diagnose.py",
            "evals/trigger_cases.json", "evals/semantic_config.json", "evals/output/cases.jsonl", "reports/output_quality_scorecard.md", "reports/trust-report.md", "reports/skill-ir.json",
        ),
        "geo-content": (
            "SKILL.md",
            "manifest.json",
            "agents/interface.yaml",
            "references/content-method.md",
            "references/modes.md",
            "references/evidence-policy.md",
            "references/output-contract.md",
            "references/input-example.json",
            "scripts/run_content.py",
            "evals/trigger_cases.json", "evals/semantic_config.json", "evals/output/cases.jsonl", "reports/output_quality_scorecard.md", "reports/trust-report.md", "reports/skill-ir.json",
        ),
        "geo-measure": (
            "SKILL.md",
            "manifest.json",
            "agents/interface.yaml",
            "references/measurement-method.md",
            "references/input-example.json",
            "scripts/run_measure.py",
            "evals/trigger_cases.json", "evals/semantic_config.json", "evals/output/cases.jsonl", "reports/output_quality_scorecard.md", "reports/trust-report.md", "reports/skill-ir.json",
        ),
    }
    for skill_id, relative_paths in required_files.items():
        skill_root = ROOT / "skills" / skill_id
        for relative in relative_paths:
            if not (skill_root / relative).is_file():
                fail(f"{skill_id} missing {relative}")
        manifest = json.loads((skill_root / "manifest.json").read_text(encoding="utf-8"))
        expected_contract = {
            "status": "experimental",
            "maturity_tier": "library",
            "lifecycle_stage": "library",
            "context_budget_tier": "production",
            "contract_version": "1.0.0",
            "availability": "active",
            "entrypoint": "SKILL.md",
        }
        for key, expected in expected_contract.items():
            if manifest.get(key) != expected:
                fail(f"{skill_id} manifest {key} must be {expected!r}")
        if not manifest.get("permission_profile"):
            fail(f"{skill_id} manifest missing permission_profile")
        if manifest.get("target_platforms") != ["openai", "claude", "generic"]:
            fail(f"{skill_id} manifest target_platforms are inconsistent")
        expected_license_fields = {
            "license_expression": "AGPL-3.0-only",
            "commercial_license_available": True,
            "commercial_license_status": "inquiry_only",
            "copyright_owner": "姚金刚 / Yao",
            "third_party_notice_required": True,
        }
        for key, expected in expected_license_fields.items():
            if manifest.get(key) != expected:
                fail(f"{skill_id} manifest {key} must be {expected!r}")
        for key in (
            "owner",
            "review_cadence",
            "input_files",
            "output_contract",
            "rollback_boundary",
        ):
            if not manifest.get(key):
                fail(f"{skill_id} manifest missing {key}")
        interface = yaml.safe_load((skill_root / "agents/interface.yaml").read_text(encoding="utf-8"))
        if interface.get("compatibility", {}).get("execution", {}).get("shell") != "bash":
            fail(f"{skill_id} interface execution.shell must be bash")
        for key in ("input_contract", "output_contract", "permission_contract"):
            if not interface.get("interface", {}).get(key):
                fail(f"{skill_id} interface missing {key}")
        trigger = json.loads((skill_root / "evals" / "trigger_cases.json").read_text(encoding="utf-8"))
        if sum(len(trigger.get(key, [])) for key in ("should_trigger", "should_not_trigger", "near_neighbor")) < 5:
            fail(f"{skill_id} needs at least five trigger cases")
        output_lines = [line for line in (skill_root / "evals" / "output" / "cases.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
        if len(output_lines) < 5:
            fail(f"{skill_id} needs at least five output cases")
        skill_text = (skill_root / "SKILL.md").read_text(encoding="utf-8")
        if "scripts/" not in skill_text:
            fail(f"{skill_id} SKILL.md must reference scripts/ wrapper")

    if not (ROOT / "skills" / "RESOLVER.md").is_file():
        fail("skills/RESOLVER.md is required")

    diagnose_manifest = json.loads(
        (ROOT / "skills" / "geo-diagnose" / "manifest.json").read_text(encoding="utf-8")
    )
    if diagnose_manifest.get("status") != "experimental":
        fail("geo-diagnose manifest status must be experimental")
    if diagnose_manifest.get("maturity") != "experimental":
        fail("geo-diagnose manifest maturity must be experimental")
    expected_outputs = {
        "input/diagnosis-brief.json",
        "input/sources/*.html",
        "report",
        "diagnosis",
        "diagnosis-funnel",
        "evidence-ledger",
        "query-map",
        "opportunity-map",
        "quality-report",
        "research-context",
        "run-manifest",
    }
    if set(diagnose_manifest.get("output_contract", [])) != expected_outputs:
        fail("geo-diagnose manifest output contract is incomplete")

    content_manifest = json.loads(
        (ROOT / "skills" / "geo-content" / "manifest.json").read_text(encoding="utf-8")
    )
    if content_manifest.get("status") != "experimental" or content_manifest.get("maturity") != "experimental":
        fail("geo-content manifest status and maturity must be experimental")
    expected_content_outputs = {
        "input/content-brief.json",
        "input/source.md",
        "content-spec.json",
        "content.json",
        "content-evidence-units.json",
        "content.md",
        "content.html",
        "content.docx",
        "content.pdf",
        "evidence-ledger.json",
        "research-context.json",
        "quality-report.json",
        "run-manifest.json",
    }
    if set(content_manifest.get("output_contract", [])) != expected_content_outputs:
        fail("geo-content manifest output contract is incomplete")

    measure_manifest = json.loads(
        (ROOT / "skills" / "geo-measure" / "manifest.json").read_text(encoding="utf-8")
    )
    expected_measure_outputs = {
        "input/measurement-brief.json",
        "measurement-report.json",
        "report.md",
        "evidence-ledger.json",
        "research-context.json",
        "quality-report.json",
        "run-manifest.json",
    }
    if set(measure_manifest.get("output_contract", [])) != expected_measure_outputs:
        fail("geo-measure manifest output contract is incomplete")

    router_cases = json.loads((ROOT / "evals" / "router_cases.json").read_text(encoding="utf-8"))
    output_cases = json.loads((ROOT / "evals" / "output_cases.json").read_text(encoding="utf-8"))
    if len(router_cases) < 60 or len(output_cases) < 20:
        fail("suite eval case minimums are not met")

    machine_markers = ("/" + "Users/", "C:" + "\\Users\\")
    report_files = list((ROOT / "reports").rglob("*.json")) + list((ROOT / "reports").rglob("*.md")) + list((ROOT / "reports").rglob("*.html"))
    report_files.extend((ROOT / "skills" / skill_id / "reports" / "skill-ir.json") for skill_id in ACTIVE_SKILLS)
    for report_path in report_files:
        if report_path.is_file() and any(marker in report_path.read_text(encoding="utf-8") for marker in machine_markers):
            fail(f"machine-local path found in report: {report_path.relative_to(ROOT)}")

    meta_gate = json.loads((ROOT / "reports" / "yao-meta-gates.json").read_text(encoding="utf-8"))
    meta_schema = json.loads((ROOT / "reports" / "yao-meta-gates.schema.json").read_text(encoding="utf-8"))
    if list(Draft202012Validator(meta_schema).iter_errors(meta_gate)):
        fail("recorded yao-meta gate report violates its schema")
    if meta_gate.get("status") not in {"pass", "pass-with-waivers"} or meta_gate.get("failed_commands") != 0 or meta_gate.get("release_blocking"):
        fail("recorded yao-meta gate report is not green")
    if any(item.get("exit_code") != 0 or item.get("structured_status") == "fail" for item in meta_gate.get("commands", [])):
        fail("recorded yao-meta command failure found")
    waiver = json.loads((ROOT / "reports" / "review-waivers.json").read_text(encoding="utf-8"))
    waiver_schema = json.loads((ROOT / "reports" / "review-waivers.schema.json").read_text(encoding="utf-8"))
    waiver_errors = list(Draft202012Validator(waiver_schema, format_checker=FormatChecker()).iter_errors(waiver))
    expected_waivers = {
        *((skill_id, gate) for skill_id in ACTIVE_SKILLS for gate in ("operations-loop", "release-notes")),
        *(("suite", gate) for gate in ("human-blind-review", "real-platform-benchmark", "commercial-legal-review")),
    }
    observed_waivers = [(item.get("skill_id"), item.get("gate")) for item in waiver.get("waivers", [])]
    try:
        expired_waivers = any(
            date.fromisoformat(item["expires_on"]) < date.today()
            for item in waiver.get("waivers", [])
        )
    except (KeyError, TypeError, ValueError):
        expired_waivers = True
    if (
        waiver_errors
        or len(observed_waivers) != len(set(observed_waivers))
        or set(observed_waivers) != expected_waivers
        or expired_waivers
    ):
        fail("review waiver ledger is invalid or expired")

    print("repository verification passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
