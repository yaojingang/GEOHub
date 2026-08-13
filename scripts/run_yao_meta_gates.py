#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ("geo", "geo-discover", "geo-diagnose", "geo-content", "geo-measure", "geo-strategy", "geo-knowledge")
REPORT_SCHEMA_VERSION = "2.0.0"
WAIVER_PATH = ROOT / "reports" / "review-waivers.json"
WAIVER_SCHEMA_PATH = ROOT / "reports" / "review-waivers.schema.json"
GATE_SCHEMA_PATH = ROOT / "reports" / "yao-meta-gates.schema.json"
WAIVABLE_REVIEW_GATES = {"operations-loop", "release-notes"}
SUITE_WAIVER_GATES = {
    "human-blind-review",
    "real-platform-benchmark",
    "commercial-legal-review",
}
EXPECTED_WAIVER_PAIRS = {
    *((skill_id, gate) for skill_id in SKILLS for gate in WAIVABLE_REVIEW_GATES),
    *(("suite", gate) for gate in SUITE_WAIVER_GATES),
}
DETERMINISTIC_EVIDENCE_PATHS = (
    "reports/eval-summary.json",
    "reports/package-verification.json",
    "reports/install-simulation.json",
    "reports/python-compatibility.json",
)
OPERATION_REPORT_FIELDS: dict[str, dict[str, type]] = {
    "skill-ir": {"schema_version": str, "name": str, "workflow": dict, "resources": dict, "targets": list, "source_files": list},
    "output-eval": {"ok": bool, "cases": str, "summary": dict, "results": list, "failures": list, "blind_review": dict, "artifacts": dict},
    "trust": {"ok": bool, "summary": dict, "failures": list, "warnings": list, "scripts": list, "dependencies": dict, "network_policy": dict, "permission_governance": dict, "artifacts": dict},
    "review-studio": {"schema_version": str, "ok": bool, "summary": dict, "gates": list, "blockers": list, "warnings": list, "review_actions": list, "artifacts": dict},
    "compile-skill": {"schema_version": str, "ok": bool, "summary": dict, "targets": list, "failures": list, "warnings": list, "artifacts": dict},
    "conformance": {"ok": bool, "skill": str, "targets": list, "summary": dict, "artifacts": dict},
    "skill-atlas": {"ok": bool, "workspace_root": str, "summary": dict, "catalog": dict, "route_collisions": list, "dependency_graph": dict, "artifacts": dict},
}


def positive_count(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def operation_report_semantics(report: dict, operation: str) -> bool:
    summary = report.get("summary")
    if operation == "skill-ir":
        return (
            report.get("schema_version") == "2.0.0"
            and bool(report.get("name"))
            and bool(report.get("workflow"))
            and bool(report.get("resources"))
            and bool(report.get("targets"))
            and bool(report.get("source_files"))
        )
    if not isinstance(summary, dict):
        return False
    if operation == "output-eval":
        return (
            bool(report.get("cases"))
            and bool(report.get("results"))
            and positive_count(summary.get("case_count"))
            and summary["case_count"] == len(report["results"])
            and summary.get("gate_pass") is True
            and summary.get("regression_count") == 0
            and bool(report.get("artifacts"))
        )
    if operation == "trust":
        package_hash = summary.get("package_sha256")
        return (
            positive_count(summary.get("scanned_files"))
            and isinstance(summary.get("script_count"), int)
            and summary["script_count"] == len(report["scripts"])
            and positive_count(summary.get("package_hash_file_count"))
            and isinstance(package_hash, str)
            and re.fullmatch(r"[0-9a-f]{64}", package_hash) is not None
            and bool(report.get("artifacts"))
        )
    if operation == "review-studio":
        return (
            report.get("schema_version") == "2.0"
            and summary.get("decision") in {"pass", "approved", "approve", "review"}
            and positive_count(summary.get("gate_count"))
            and summary["gate_count"] == len(report["gates"])
            and summary.get("gate_contract_ok") is True
            and summary.get("blocker_count") == len(report["blockers"])
            and summary.get("warning_count") == len(report["warnings"])
            and bool(report.get("artifacts"))
        )
    if operation == "compile-skill":
        targets = report.get("targets", [])
        return (
            report.get("schema_version") == "1.0"
            and bool(targets)
            and positive_count(summary.get("target_count"))
            and summary["target_count"] == len(targets)
            and summary.get("pass_count") == len(targets)
            and summary.get("failure_count") == 0
            and summary.get("block_count") == 0
            and all(isinstance(target, dict) and target.get("status") == "pass" for target in targets)
            and bool(report.get("artifacts"))
        )
    if operation == "conformance":
        targets = report.get("targets", [])
        return (
            bool(report.get("skill"))
            and bool(targets)
            and positive_count(summary.get("target_count"))
            and summary["target_count"] == len(targets)
            and summary.get("pass_count") == len(targets)
            and summary.get("fail_count") == 0
            and all(isinstance(target, dict) and target.get("status") == "pass" and bool(target.get("checks")) for target in targets)
            and bool(report.get("artifacts"))
        )
    if operation == "skill-atlas":
        catalog = report.get("catalog", {})
        skills = catalog.get("skills", []) if isinstance(catalog, dict) else []
        return (
            bool(report.get("workspace_root"))
            and bool(catalog)
            and isinstance(skills, list)
            and positive_count(summary.get("skill_count"))
            and summary["skill_count"] == len(skills)
            and bool(report.get("artifacts"))
        )
    return False


def portable_text(value: str, meta_root: Path) -> str:
    schema_root = (
        (meta_root / "skill-ir").resolve().parent
        if (meta_root / "skill-ir").exists()
        else meta_root.resolve()
    )
    linked_roots = tuple(
        (str(child.resolve()) + "/", f"<yao-meta-root>/{child.name}/")
        for child in (meta_root.iterdir() if meta_root.is_dir() else ())
        if child.is_symlink()
    )
    replacements = (
        (str(ROOT.resolve()) + "/", ""),
        (str(schema_root) + "/", "<yao-meta-root>/"),
        *linked_roots,
        (str(meta_root.resolve()) + "/", "<yao-meta-root>/"),
        (str(Path(sys.executable).resolve()), "python3"),
    )
    for source, replacement in replacements:
        value = value.replace(source, replacement)
    return value


def report_path_from_command(command: list[str]) -> Path | None:
    for flag in ("--output-json", "--report-json"):
        if flag in command:
            candidate = Path(command[command.index(flag) + 1]).resolve()
            if candidate == ROOT or ROOT in candidate.parents:
                return candidate
    return None


def structured_report_status(path: Path, operation: str | None = None) -> str:
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return "fail"
    if not isinstance(report, dict) or not report:
        return "fail"
    if operation is not None:
        contract = OPERATION_REPORT_FIELDS.get(operation)
        if contract is None or any(key not in report or not isinstance(report[key], expected_type) for key, expected_type in contract.items()):
            return "fail"
        if not operation_report_semantics(report, operation):
            return "fail"
    explicit_status = report.get("status")
    if explicit_status is not None and explicit_status != "pass":
        return "fail"
    if report.get("ok") is False:
        return "fail"
    if report.get("failures") or report.get("blockers"):
        return "fail"
    summary = report.get("summary", {})
    if isinstance(summary, dict):
        if summary.get("fail_count", 0) or summary.get("blocker_count", 0):
            return "fail"
        decision = summary.get("decision")
        if decision == "review":
            return "review"
        if decision is not None and decision not in {"pass", "approved", "approve"}:
            return "fail"
    if explicit_status == "pass" or report.get("ok") is True:
        return "pass"
    if path.name.endswith("skill-ir.json"):
        required = {"schema_version", "name", "workflow", "resources", "source_files"}
        return "pass" if report.get("schema_version") == "2.0.0" and required <= set(report) else "fail"
    return "fail"


def command_operation(command: object) -> str | None:
    if not isinstance(command, list) or len(command) < 3 or not all(isinstance(part, str) for part in command):
        return None
    if command[1].endswith("yao.py"):
        return command[2]
    return None


def execute(command: list[str], meta_root: Path) -> dict:
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    report_path = report_path_from_command(command)
    structured = structured_report_status(report_path, command_operation(command)) if result.returncode == 0 and report_path else None
    failed = result.returncode != 0 or structured == "fail"
    return {
        "command": [portable_text(part, meta_root) for part in command],
        "exit_code": result.returncode,
        "status": "fail" if failed else (structured or "pass"),
        "structured_status": structured,
        "report_path": report_path.relative_to(ROOT).as_posix() if report_path else None,
        "stdout_tail": portable_text(result.stdout[-2000:], meta_root),
        "stderr_tail": portable_text(result.stderr[-2000:], meta_root),
    }


def sanitize_generated_reports(paths: list[Path], meta_root: Path) -> None:
    for path in paths:
        if path.is_file() and path.suffix in {".json", ".md", ".html"}:
            text = path.read_text(encoding="utf-8")
            portable = re.sub(
                r"[ \t]+(?=\r?$)",
                "",
                portable_text(text, meta_root),
                flags=re.MULTILINE,
            )
            if portable != text:
                path.write_text(portable, encoding="utf-8")


def file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_digest_paths() -> list[Path]:
    tracked = subprocess.run(["git", "ls-files", "-z", "--cached"], cwd=ROOT, check=True, capture_output=True).stdout.split(b"\0")
    exact = {
        "pyproject.toml",
        ".github/workflows/ci.yml",
        "scripts/run_yao_meta_gates.py",
        "scripts/package.py",
        "scripts/verify_packages.py",
        "scripts/install_simulation.py",
        "scripts/run_evals.py",
        "scripts/verify_repository.py",
        "scripts/verify_all.py",
        "scripts/generate_sbom.py",
        "scripts/generate_provenance.py",
        "scripts/verify_provenance.py",
        "scripts/render_production_readiness.py",
        ".github/workflows/release.yml",
        "CHANGELOG.md",
        "docs/migration-0.5.md",
        "docs/decisions/0001-four-plane-modularization.md",
        "docs/decisions/0002-artifact-protocol-compatibility.md",
        "docs/decisions/0003-evaluation-and-measurement.md",
        "docs/decisions/0004-provider-privacy-boundary.md",
        "docs/decisions/0005-production-promotion.md",
        "reports/review-waivers.json",
        "reports/review-waivers.schema.json",
        "reports/yao-meta-gates.schema.json",
        *DETERMINISTIC_EVIDENCE_PATHS,
    }
    prefixes = ("registry/", "schemas/", "src/geo_seo_hub/", "evals/")
    paths = []
    for raw in tracked:
        if not raw:
            continue
        relative = Path(raw.decode())
        name = relative.as_posix()
        skill_source = name.startswith("skills/") and "/reports/" not in name and "__pycache__" not in relative.parts
        if name in exact or name.startswith(prefixes) or skill_source:
            path = ROOT / relative
            if path.is_file() and not any(part.endswith(".egg-info") for part in relative.parts) and "__pycache__" not in relative.parts:
                paths.append(path)
    return sorted(set(paths))


def current_source_digest() -> str:
    paths = source_digest_paths()
    digest = hashlib.sha256()
    for path in sorted(set(paths)):
        digest.update(path.relative_to(ROOT).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def expected_command_inventory() -> set[tuple[str, str, str | None]]:
    expected: set[tuple[str, str, str | None]] = set()
    for skill_id in SKILLS:
        expected.update(
            {
                (skill_id, "validate", None),
                (skill_id, "trigger-eval", None),
                (skill_id, "skill-ir", f"skills/{skill_id}/reports/skill-ir.json"),
                (skill_id, "skill-ir", f"reports/yao-meta/{skill_id}-skill-ir.json"),
                (skill_id, "output-eval", f"reports/yao-meta/{skill_id}-output-eval.json"),
                (skill_id, "trust", f"reports/yao-meta/{skill_id}-trust.json"),
                (skill_id, "review-studio", f"reports/yao-meta/{skill_id}-review-studio.json"),
            }
        )
        for target in ("generic", "openai", "claude"):
            expected.add((skill_id, f"compile-skill:{target}", f"reports/yao-meta/{skill_id}-compiled-{target}.json"))
            expected.add((skill_id, f"conformance:{target}", f"reports/yao-meta/{skill_id}-conformance-{target}.json"))
    expected.add(("suite", "skill-atlas", "reports/skill-atlas.json"))
    return expected


def expected_command_records() -> set[tuple[str, tuple[str, ...], str | None]]:
    records: set[tuple[str, tuple[str, ...], str | None]] = set()
    yao = "<yao-meta-root>/scripts/yao.py"
    trigger_eval = "<yao-meta-root>/scripts/trigger_eval.py"
    for skill_id in SKILLS:
        skill = f"skills/{skill_id}"
        prefix = f"reports/yao-meta/{skill_id}"
        frontmatter = yaml.safe_load((ROOT / skill / "SKILL.md").read_text(encoding="utf-8").split("---", 2)[1])
        commands = [
            (["<python>", yao, "validate", skill, "--require-manifest"], None),
            (["<python>", trigger_eval, "--description", frontmatter["description"], "--cases", f"{skill}/evals/trigger_cases.json", "--semantic-config", f"{skill}/evals/semantic_config.json", "--threshold", "0.2"], None),
            (["<python>", yao, "skill-ir", skill, "--output-json", f"{skill}/reports/skill-ir.json"], f"{skill}/reports/skill-ir.json"),
            (["<python>", yao, "skill-ir", skill, "--output-json", f"{prefix}-skill-ir.json"], f"{prefix}-skill-ir.json"),
            (["<python>", yao, "output-eval", "--cases", f"{skill}/evals/output/cases.jsonl", "--output-json", f"{prefix}-output-eval.json", "--output-md", f"{prefix}-output-eval.md", "--blind-pack-json", f"{prefix}-blind-pack.json", "--blind-pack-md", f"{prefix}-blind-pack.md", "--blind-answer-key-json", f"{prefix}-blind-answer-key.json"], f"{prefix}-output-eval.json"),
            (["<python>", yao, "trust", skill, "--output-json", f"{prefix}-trust.json", "--output-md", f"{prefix}-trust.md"], f"{prefix}-trust.json"),
            (["<python>", yao, "review-studio", skill, "--output-json", f"{prefix}-review-studio.json", "--output-html", f"{prefix}-review-studio.html"], f"{prefix}-review-studio.json"),
        ]
        for target in ("generic", "openai", "claude"):
            commands.extend(
                [
                    (["<python>", yao, "compile-skill", skill, "--target", target, "--output-json", f"{prefix}-compiled-{target}.json", "--output-md", f"{prefix}-compiled-{target}.md"], f"{prefix}-compiled-{target}.json"),
                    (["<python>", yao, "conformance", skill, "--target", target, "--output-json", f"{prefix}-conformance-{target}.json", "--output-md", f"{prefix}-conformance-{target}.md"], f"{prefix}-conformance-{target}.json"),
                ]
            )
        records.update((skill_id, tuple(command), report_path) for command, report_path in commands)
    atlas = ["<python>", yao, "skill-atlas", "--workspace-root", "skills", "--report-json", "reports/skill-atlas.json", "--report-html", "reports/skill-atlas.html"]
    records.add(("suite", tuple(atlas), "reports/skill-atlas.json"))
    return records


def canonical_command(command: object) -> tuple[str, ...] | None:
    if not isinstance(command, list) or len(command) < 2 or not all(isinstance(part, str) for part in command):
        return None
    if not Path(command[0]).name.startswith("python"):
        return None
    return ("<python>", *command[1:])


def command_identity(item: dict) -> tuple[str, str, str | None] | None:
    command = item.get("command")
    if not isinstance(command, list) or len(command) < 2 or not all(isinstance(part, str) for part in command):
        return None
    if command[1].endswith("trigger_eval.py"):
        operation = "trigger-eval"
    elif command[1].endswith("yao.py") and len(command) >= 3:
        operation = command[2]
        if operation in {"compile-skill", "conformance"} and "--target" in command:
            operation = f"{operation}:{command[command.index('--target') + 1]}"
    else:
        return None
    return item.get("skill_id"), operation, item.get("report_path")


def validate_command_inventory(commands: list[dict]) -> list[str]:
    failures = []
    identities = [command_identity(item) for item in commands]
    expected = expected_command_inventory()
    if len(commands) != len(expected):
        failures.append(f"expected {len(expected)} command records; found {len(commands)}")
    if any(identity is None for identity in identities):
        failures.append("unrecognized command identity")
    observed = {identity for identity in identities if identity is not None}
    if len(observed) != len(identities):
        failures.append("duplicate command identity")
    if observed != expected:
        failures.append("command identity set mismatch")
    records = [(item.get("skill_id"), canonical_command(item.get("command")), item.get("report_path")) for item in commands]
    expected_records = expected_command_records()
    if any(command is None for _, command, _ in records):
        failures.append("invalid command argv")
    observed_records = {(skill_id, command, report_path) for skill_id, command, report_path in records if command is not None}
    if len(observed_records) != len(records):
        failures.append("duplicate full command record")
    if observed_records != expected_records:
        failures.append("full command argv set mismatch")
    for item, identity in zip(commands, identities, strict=True):
        if identity is None:
            continue
        if identity[2] is None:
            if item.get("structured_status") is not None or item.get("report_digest") is not None:
                failures.append(f"unstructured command evidence must be null: {identity}")
            continue
        digest = item.get("report_digest")
        if item.get("structured_status") not in {"pass", "review"} or not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            failures.append(f"structured command evidence is incomplete: {identity}")
    return sorted(set(failures))


def deterministic_evidence_digests() -> dict[str, str]:
    return {relative: file_digest(ROOT / relative) for relative in DETERMINISTIC_EVIDENCE_PATHS}


def load_waiver_ledger(path: Path = WAIVER_PATH, *, today: date | None = None) -> list[dict]:
    ledger = json.loads(path.read_text(encoding="utf-8"))
    schema = json.loads(WAIVER_SCHEMA_PATH.read_text(encoding="utf-8"))
    errors = sorted(Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(ledger), key=lambda item: list(item.path))
    if errors:
        raise ValueError("invalid waiver ledger: " + "; ".join(error.message for error in errors))
    current = today or date.today()
    waivers = ledger["waivers"]
    pairs = [(item["skill_id"], item["gate"]) for item in waivers]
    if not waivers:
        raise ValueError("invalid waiver ledger: waiver inventory must not be empty")
    if len(pairs) != len(set(pairs)):
        raise ValueError("invalid waiver ledger: duplicate semantic waiver pair")
    observed_pairs = set(pairs)
    if observed_pairs != EXPECTED_WAIVER_PAIRS:
        unknown = sorted(observed_pairs - EXPECTED_WAIVER_PAIRS)
        missing = sorted(EXPECTED_WAIVER_PAIRS - observed_pairs)
        raise ValueError(f"invalid waiver ledger: inventory mismatch; unknown={unknown}, missing={missing}")
    identifiers = [item["id"] for item in waivers]
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("invalid waiver ledger: duplicate waiver id")
    expired = [item["id"] for item in waivers if date.fromisoformat(item["expires_on"]) < current]
    if expired:
        raise ValueError(f"expired review waivers: {expired}")
    return waivers


def deterministic_review_evidence(skill_id: str, gate: str) -> list[Path]:
    prefix = ROOT / "reports" / "yao-meta" / skill_id
    skill = ROOT / "skills" / skill_id
    mapping = {
        "intent-canvas": [skill / "SKILL.md", skill / "manifest.json"],
        "trigger-lab": [skill / "evals" / "trigger_cases.json", skill / "evals" / "semantic_config.json"],
        "output-lab": [Path(str(prefix) + "-output-eval.json"), skill / "reports" / "output_quality_scorecard.md"],
        "context-budget": [skill / "manifest.json", skill / "agents" / "interface.yaml"],
        "runtime-matrix": [Path(str(prefix) + f"-conformance-{target}.json") for target in ("generic", "openai", "claude")],
        "trust-report": [Path(str(prefix) + "-trust.json"), skill / "reports" / "trust-report.md"],
        "python-compat": [ROOT / "reports" / "python-compatibility.json"],
        "architecture-maintainability": [ROOT / "docs" / "architecture.md", ROOT / "reports" / "output_quality_scorecard.md"],
        "permission-gates": [skill / "manifest.json", skill / "agents" / "interface.yaml"],
        "permission-runtime": [Path(str(prefix) + "-trust.json"), skill / "agents" / "interface.yaml"],
        "skill-atlas": [ROOT / "reports" / "skill-atlas.json"],
        "review-waivers": [WAIVER_PATH, WAIVER_SCHEMA_PATH],
        "registry-audit": [ROOT / "reports" / "package-verification.json", ROOT / "reports" / "install-simulation.json"],
    }
    return mapping.get(gate, [])


def deterministic_evidence_is_green(path: Path) -> bool:
    if not path.is_file() or path.stat().st_size == 0:
        return False
    if path.suffix == ".json":
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return False
        if not payload:
            return False
        relative = path.relative_to(ROOT)
        is_generated_report = (
            relative.parts[:2] == ("reports", "yao-meta")
            or relative.as_posix() in DETERMINISTIC_EVIDENCE_PATHS
            or relative.as_posix() == "reports/skill-atlas.json"
        )
        return structured_report_status(path) == "pass" if is_generated_report else True
    return True


def classify_review_studio(skill_id: str, review: dict, waivers: list[dict]) -> dict:
    available_waivers = {(item["skill_id"], item["gate"]) for item in waivers}
    classified = {"deterministic_pass": [], "waived_missing_evidence": [], "release_blocking": []}
    seen: set[str] = set()
    for warning in review.get("warnings", []):
        gate = warning.get("key")
        if not gate:
            classified["release_blocking"].append("unkeyed-review-warning")
        elif gate in seen:
            classified["release_blocking"].append(f"duplicate-review-warning:{gate}")
        elif gate in WAIVABLE_REVIEW_GATES and (skill_id, gate) in available_waivers:
            classified["waived_missing_evidence"].append(gate)
        else:
            evidence = deterministic_review_evidence(skill_id, gate)
            target = "deterministic_pass" if evidence and all(deterministic_evidence_is_green(path) for path in evidence) else "release_blocking"
            classified[target].append(gate)
        if gate:
            seen.add(gate)
    for key in classified:
        classified[key] = sorted(set(classified[key]))
    classified["review_warning_count"] = len(review.get("warnings", []))
    classified["classified_warning_count"] = sum(len(classified[key]) for key in ("deterministic_pass", "waived_missing_evidence", "release_blocking"))
    if classified["classified_warning_count"] != classified["review_warning_count"]:
        classified["release_blocking"].append("review-warning-count-mismatch")
    return classified


def review_classifications(waivers: list[dict]) -> dict[str, dict]:
    classifications = {}
    for skill_id in SKILLS:
        path = ROOT / "reports" / "yao-meta" / f"{skill_id}-review-studio.json"
        review = json.loads(path.read_text(encoding="utf-8"))
        classifications[skill_id] = classify_review_studio(skill_id, review, waivers)
    return classifications


def verify_existing() -> int:
    report_path = ROOT / "reports" / "yao-meta-gates.json"
    failures = []
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"existing yao-meta gate report is invalid: {exc}", file=sys.stderr)
        return 2
    gate_schema = json.loads(GATE_SCHEMA_PATH.read_text(encoding="utf-8"))
    schema_errors = sorted(Draft202012Validator(gate_schema).iter_errors(report), key=lambda item: list(item.path))
    if schema_errors:
        failures.append("recorded gate report violates its schema")
    if report.get("schema_version") != REPORT_SCHEMA_VERSION:
        failures.append("recorded gate report schema version is invalid")
    if report.get("status") not in {"pass", "pass-with-waivers"} or report.get("failed_commands") != 0 or report.get("release_blocking"):
        failures.append("recorded gate status is release-blocking")
    commands = report.get("commands", [])
    failures.extend(validate_command_inventory(commands))
    if any(item.get("exit_code") != 0 or item.get("structured_status") == "fail" for item in commands):
        failures.append("recorded deterministic command evidence is incomplete")
    for item in commands:
        relative = item.get("report_path")
        if not relative:
            continue
        path = ROOT / relative
        operation = command_operation(item.get("command"))
        if not path.is_file() or structured_report_status(path, operation) != item.get("structured_status") or file_digest(path) != item.get("report_digest"):
            failures.append(f"structured report evidence is stale or invalid: {relative}")
    if report.get("source_digest") != current_source_digest():
        failures.append("recorded source digest is stale")
    try:
        evidence_digests = deterministic_evidence_digests()
    except OSError as exc:
        failures.append(f"deterministic evidence is missing: {exc}")
        evidence_digests = {}
    if report.get("evidence_digests") != evidence_digests:
        failures.append("deterministic evidence digests are stale")
    if report.get("gate_schema_digest") != file_digest(GATE_SCHEMA_PATH):
        failures.append("recorded gate report schema digest is stale")
    try:
        waivers = load_waiver_ledger()
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        failures.append(str(exc))
        waivers = []
    if WAIVER_PATH.is_file():
        if report.get("waiver_digest") != file_digest(WAIVER_PATH):
            failures.append("recorded waiver digest is stale")
    else:
        failures.append("review waiver ledger is missing")
    current_reviews = review_classifications(waivers)
    if current_reviews != report.get("review_classifications"):
        failures.append("review warning classifications are stale")
    if any(item["release_blocking"] for item in current_reviews.values()):
        failures.append("review warnings contain release-blocking items")
    expected_deterministic = sorted(f"{skill_id}:{gate}" for skill_id, classified in current_reviews.items() for gate in classified["deterministic_pass"])
    expected_waived = sorted({*(f"{skill_id}:{gate}" for skill_id, classified in current_reviews.items() for gate in classified["waived_missing_evidence"]), *(f"suite:{item['gate']}" for item in waivers if item["skill_id"] == "suite")})
    if report.get("deterministic_pass") != expected_deterministic:
        failures.append("deterministic Review Studio dispositions are stale")
    if report.get("waived_missing_evidence") != expected_waived:
        failures.append("waived or missing evidence summary is stale")
    machine_markers = ("/" + "Users/", "AI Coding/03-Development/Skills", "C:" + "\\Users\\")
    surfaces = list((ROOT / "reports").rglob("*.json")) + list((ROOT / "reports").rglob("*.md")) + list((ROOT / "reports").rglob("*.html"))
    if any(marker in path.read_text(encoding="utf-8") for path in surfaces for marker in machine_markers):
        failures.append("machine-local path remains in public reports")
    if failures:
        print(json.dumps({"status": "fail", "failures": sorted(set(failures))}, indent=2, allow_nan=False), file=sys.stderr)
        return 2
    print(json.dumps({"status": report["status"], "commands": len(commands), "source_digest": report["source_digest"], "waived_missing_evidence": len(report["waived_missing_evidence"]), "release_blocking": 0}, indent=2, allow_nan=False))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--meta-root", type=Path)
    parser.add_argument("--verify-existing", action="store_true")
    args = parser.parse_args()
    if args.verify_existing:
        return verify_existing()
    if args.meta_root is None:
        parser.error("--meta-root is required unless --verify-existing is used")
    yao = args.meta_root.resolve() / "scripts" / "yao.py"
    if not yao.is_file():
        raise SystemExit(f"yao-meta CLI not found: {yao}")
    out = ROOT / "reports" / "yao-meta"
    out.mkdir(parents=True, exist_ok=True)
    results = []
    for skill_id in SKILLS:
        skill = ROOT / "skills" / skill_id
        prefix = out / skill_id
        frontmatter = yaml.safe_load((skill / "SKILL.md").read_text(encoding="utf-8").split("---", 2)[1])
        commands = [
            [sys.executable, str(yao), "validate", str(skill), "--require-manifest"],
            [sys.executable, str(args.meta_root.resolve() / "scripts" / "trigger_eval.py"), "--description", frontmatter["description"], "--cases", str(skill / "evals" / "trigger_cases.json"), "--semantic-config", str(skill / "evals" / "semantic_config.json"), "--threshold", "0.2"],
            [sys.executable, str(yao), "skill-ir", str(skill), "--output-json", str(skill / "reports" / "skill-ir.json")],
            [sys.executable, str(yao), "skill-ir", str(skill), "--output-json", str(prefix) + "-skill-ir.json"],
            [sys.executable, str(yao), "output-eval", "--cases", str(skill / "evals" / "output" / "cases.jsonl"), "--output-json", str(prefix) + "-output-eval.json", "--output-md", str(prefix) + "-output-eval.md", "--blind-pack-json", str(prefix) + "-blind-pack.json", "--blind-pack-md", str(prefix) + "-blind-pack.md", "--blind-answer-key-json", str(prefix) + "-blind-answer-key.json"],
            [sys.executable, str(yao), "trust", str(skill), "--output-json", str(prefix) + "-trust.json", "--output-md", str(prefix) + "-trust.md"],
            [sys.executable, str(yao), "review-studio", str(skill), "--output-json", str(prefix) + "-review-studio.json", "--output-html", str(prefix) + "-review-studio.html"],
        ]
        for target in ("generic", "openai", "claude"):
            commands.append([sys.executable, str(yao), "compile-skill", str(skill), "--target", target, "--output-json", str(prefix) + f"-compiled-{target}.json", "--output-md", str(prefix) + f"-compiled-{target}.md"])
            commands.append([sys.executable, str(yao), "conformance", str(skill), "--target", target, "--output-json", str(prefix) + f"-conformance-{target}.json", "--output-md", str(prefix) + f"-conformance-{target}.md"])
        results.extend({"skill_id": skill_id, **execute(command, args.meta_root)} for command in commands)
    atlas_command = [sys.executable, str(yao), "skill-atlas", "--workspace-root", str(ROOT / "skills"), "--report-json", str(ROOT / "reports" / "skill-atlas.json"), "--report-html", str(ROOT / "reports" / "skill-atlas.html")]
    results.append({"skill_id": "suite", **execute(atlas_command, args.meta_root)})
    generated = list(out.rglob("*")) + [ROOT / "reports" / "skill-atlas.json", ROOT / "reports" / "skill-atlas.html"]
    sanitize_generated_reports(generated, args.meta_root)
    for item in results:
        if item["report_path"]:
            path = ROOT / item["report_path"]
            item["structured_status"] = structured_report_status(path, command_operation(item["command"]))
            item["status"] = "fail" if item["structured_status"] == "fail" or item["exit_code"] else item["structured_status"]
            item["report_digest"] = file_digest(path)
        else:
            item["report_digest"] = None
    waivers = load_waiver_ledger()
    classifications = review_classifications(waivers)
    command_failures = [item for item in results if item["exit_code"] != 0 or item["structured_status"] == "fail"]
    release_blocking = sorted(f"{skill_id}:{gate}" for skill_id, classified in classifications.items() for gate in classified["release_blocking"])
    deterministic_pass = sorted(f"{skill_id}:{gate}" for skill_id, classified in classifications.items() for gate in classified["deterministic_pass"])
    waived = sorted(f"{skill_id}:{gate}" for skill_id, classified in classifications.items() for gate in classified["waived_missing_evidence"])
    waived.extend(sorted(f"suite:{item['gate']}" for item in waivers if item["skill_id"] == "suite"))
    blocked = bool(command_failures or release_blocking)
    report = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "status": "fail" if blocked else ("pass-with-waivers" if waived else "pass"),
        "commands": results,
        "failed_commands": len(command_failures),
        "source_digest": current_source_digest(),
        "evidence_digests": deterministic_evidence_digests(),
        "gate_schema_digest": file_digest(GATE_SCHEMA_PATH),
        "waiver_digest": file_digest(WAIVER_PATH),
        "deterministic_pass": deterministic_pass,
        "waived_missing_evidence": sorted(set(waived)),
        "release_blocking": release_blocking,
        "review_classifications": classifications,
        "note": "Deterministic report failures and unclassified Review Studio warnings block release. External evidence waivers remain explicit and expire.",
    }
    (ROOT / "reports" / "yao-meta-gates.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    lines = ["# yao-meta Gates", "", f"Status: **{report['status']}**", "", f"Commands: {len(results)}; deterministic failures: {len(command_failures)}.", "", f"Deterministic Review Studio dispositions: {len(deterministic_pass)}.", f"Waived or missing external evidence: {len(report['waived_missing_evidence'])}.", f"Release-blocking items: {len(release_blocking)}.", "", "| Skill | Command | Exit | Structured status |", "| --- | --- | ---: | --- |"]
    for item in results:
        lines.append(f"| {item['skill_id']} | `{' '.join(item['command'][2:4])}` | {item['exit_code']} | {item['status']} |")
    (ROOT / "reports" / "yao-meta-gates.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "commands": len(results), "deterministic_failures": len(command_failures), "waived_missing_evidence": len(report["waived_missing_evidence"]), "release_blocking": len(release_blocking)}, indent=2, allow_nan=False))
    return 2 if blocked else 0


if __name__ == "__main__":
    raise SystemExit(main())
