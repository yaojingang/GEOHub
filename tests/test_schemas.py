import json
import ast
import subprocess
import zipfile
from copy import deepcopy
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft202012Validator

from geo_seo_hub.paths import repository_root
from geo_seo_hub.registry import RegistryError, load_registry
from geo_seo_hub.validation import (
    ArtifactValidationError,
    load_schema,
    strict_json_loads,
    validate_artifact,
)
from scripts.package_repository import build_archive, trusted_files


def test_all_protocol_schemas_are_valid():
    expected = {
        "geo-brief",
        "run-manifest",
        "evidence-ledger",
        "brand-fact-card",
        "query-map",
        "opportunity-map",
        "content-spec",
        "content-evidence-units",
        "diagnosis-funnel",
        "quality-report",
        "research-context",
        "research-evidence-registry",
    }
    actual = {path.name.removesuffix(".schema.json") for path in (repository_root() / "schemas").glob("*.schema.json")}
    assert actual == expected
    for name in expected:
        schema = load_schema(name)
        Draft202012Validator.check_schema(schema)
        if name == "research-evidence-registry":
            assert "registry_version" in schema["properties"]
        else:
            assert schema["properties"]["protocol_version"]["const"] == "1.0.0"


def test_all_runtime_and_gate_json_writers_emit_standard_json():
    root = repository_root()
    for source in [*(root / "src" / "geo_seo_hub").glob("*.py"), *(root / "scripts").glob("*.py")]:
        tree = ast.parse(source.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            if not isinstance(node.func.value, ast.Name) or node.func.value.id != "json" or node.func.attr != "dumps":
                continue
            allow_nan = next((keyword.value for keyword in node.keywords if keyword.arg == "allow_nan"), None)
            assert isinstance(allow_nan, ast.Constant) and allow_nan.value is False, f"{source}:{node.lineno}"


def test_runtime_json_loads_are_centralized_in_strict_helper():
    runtime = repository_root() / "src" / "geo_seo_hub"
    observed = []
    for source in runtime.glob("*.py"):
        tree = ast.parse(source.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "json"
                and node.func.attr == "loads"
            ):
                observed.append((source.name, node.lineno))
    assert len(observed) == 1
    assert observed[0][0] == "validation.py"


@pytest.mark.parametrize("literal", ("1e9999", "-1e9999"))
def test_strict_json_rejects_nested_numeric_overflow(literal):
    with pytest.raises(ValueError, match="non-finite JSON number"):
        strict_json_loads(f'{{"outer":[{{"value":{literal}}}]}}')


def test_reserved_schemas_accept_protocol_examples():
    validate_artifact(
        "brand-fact-card",
        {
            "protocol_version": "1.0.0",
            "brand_id": "brand-1",
            "facts": [
                {
                    "fact_id": "fact-1",
                    "statement": "A sourced statement.",
                    "evidence_ids": ["ev-1"],
                    "status": "verified",
                }
            ],
        },
    )


def test_run_manifest_accepts_explicit_optional_renderer_degradation():
    validate_artifact(
        "run-manifest",
        {
            "protocol_version": "1.0.0",
            "run_id": "run-degraded",
            "created_at": "2026-08-08T00:00:00Z",
            "generator": {"name": "geo-seo-hub-content", "version": "0.2.0"},
            "input_artifact": "input/content-brief.json",
            "artifacts": ["content.md"],
            "status": "completed-with-warnings",
            "degraded": True,
            "missing_dependencies": ["python-docx", "reportlab", "weasyprint"],
            "renderer_errors": [],
        },
    )
    validate_artifact(
        "content-spec",
        {
            "protocol_version": "1.0.0",
            "spec_id": "spec-1",
            "title": "A useful guide",
            "target_query_ids": ["qry-1"],
            "required_evidence_ids": ["ev-1"],
            "sections": [{"heading": "Evidence", "purpose": "Answer with sourced facts."}],
            "status": "ready",
        },
    )


def test_protocol_mismatch_is_rejected():
    with pytest.raises(ArtifactValidationError, match="1.0.0"):
        validate_artifact(
            "geo-brief",
            {
                "protocol_version": "2.0.0",
                "brief_id": "bad",
                "subject": "bad protocol",
                "seed_queries": ["test"],
            },
        )


def test_registry_validates_and_unavailable_routes_have_no_entry():
    registry = load_registry()
    assert registry["protocol_version"] == "1.0.0"
    for skill in registry["skills"]:
        if skill["status"] != "active":
            assert skill["entry"] is None
            assert skill["active_placeholder"] is False


def test_skill_manifests_declare_license_governance():
    expected = {
        "license_expression": "AGPL-3.0-only",
        "commercial_license_available": True,
        "commercial_license_status": "inquiry_only",
        "copyright_owner": "姚金刚 / Yao",
        "third_party_notice_required": True,
    }
    for skill_id in ("geo", "geo-discover", "geo-diagnose"):
        path = repository_root() / "skills" / skill_id / "manifest.json"
        manifest = json.loads(path.read_text(encoding="utf-8"))
        assert {key: manifest[key] for key in expected} == expected

    diagnose_manifest = json.loads((repository_root() / "skills" / "geo-diagnose" / "manifest.json").read_text(encoding="utf-8"))
    assert diagnose_manifest["status"] == "experimental"
    assert diagnose_manifest["maturity"] == "experimental"
    assert diagnose_manifest["maturity_tier"] == "library"
    assert diagnose_manifest["lifecycle_stage"] == "library"
    assert diagnose_manifest["context_budget_tier"] == "production"


def _write_test_registry(tmp_path, registry):
    registry_dir = tmp_path / "registry"
    registry_dir.mkdir()
    schema_source = repository_root() / "registry" / "skills.schema.json"
    (registry_dir / "skills.schema.json").write_text(
        schema_source.read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    for skill in registry["skills"]:
        if skill["status"] == "active" and skill["entry"]:
            expected = tmp_path / "skills" / skill["id"] / "SKILL.md"
            expected.parent.mkdir(parents=True, exist_ok=True)
            expected.write_text("# test skill\n", encoding="utf-8")
    path = registry_dir / "skills.yaml"
    path.write_text(yaml.safe_dump(registry, allow_unicode=True), encoding="utf-8")
    return path


@pytest.mark.parametrize("malicious_entry", ["/tmp/outside/SKILL.md", "../outside/SKILL.md"])
def test_registry_rejects_unsafe_active_entry(tmp_path, malicious_entry):
    registry = deepcopy(load_registry())
    registry["skills"][0]["entry"] = malicious_entry
    path = _write_test_registry(tmp_path, registry)
    with pytest.raises(RegistryError, match="must be skills/geo/SKILL.md"):
        load_registry(path)


def test_registry_rejects_entry_symlink_that_resolves_outside_root(tmp_path):
    registry = deepcopy(load_registry())
    path = _write_test_registry(tmp_path, registry)
    entry = tmp_path / "skills" / "geo" / "SKILL.md"
    entry.unlink()
    outside = tmp_path.parent / f"{tmp_path.name}-outside-skill.md"
    outside.write_text("# outside\n", encoding="utf-8")
    entry.symlink_to(outside)
    with pytest.raises(RegistryError, match="unsafe or missing entry"):
        load_registry(path)


def test_registry_rejects_missing_core_geo_route(tmp_path):
    registry = deepcopy(load_registry())
    registry["skills"] = [skill for skill in registry["skills"] if skill["id"] != "geo"]
    path = _write_test_registry(tmp_path, registry)
    with pytest.raises(RegistryError, match="active runnable geo route"):
        load_registry(path)


def test_registry_rejects_unrunnable_discover_suggestion(tmp_path):
    registry = deepcopy(load_registry())
    discover_skill = next(skill for skill in registry["skills"] if skill["id"] == "geo-discover")
    discover_skill["status"] = "planned"
    discover_skill["entry"] = None
    discover_skill["nearest_active"] = "geo"
    discover_skill["required_inputs"] = ["subject"]
    discover_skill["closest_v0_artifact"] = "query-map"
    path = _write_test_registry(tmp_path, registry)
    with pytest.raises(RegistryError, match="suggestion must exist and be runnable"):
        load_registry(path)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("brief_id", " "),
        ("subject", "\t"),
        ("seed_queries", ["   "]),
    ],
)
def test_geo_brief_rejects_blank_required_text(field, value):
    artifact = {
        "protocol_version": "1.0.0",
        "brief_id": "brief",
        "subject": "subject",
        "seed_queries": ["query"],
    }
    artifact[field] = value
    with pytest.raises(ArtifactValidationError):
        validate_artifact("geo-brief", artifact)


def test_geo_brief_rejects_invalid_source_uri():
    artifact = {
        "protocol_version": "1.0.0",
        "brief_id": "brief",
        "subject": "subject",
        "seed_queries": ["query"],
        "evidence": [
            {
                "evidence_id": "ev-1",
                "claim": "claim",
                "source_uri": "not a uri",
            }
        ],
    }
    with pytest.raises(ArtifactValidationError, match="source_uri"):
        validate_artifact("geo-brief", artifact)


def test_query_map_rejects_blank_question():
    artifact = {
        "protocol_version": "1.0.0",
        "run_id": "run-1",
        "queries": [
            {
                "query_id": "query-1",
                "question": " ",
                "intent": "learn",
                "audience": "buyer",
                "scenario": "research",
                "parent_query_id": None,
                "rewrites": {
                    "standalone": "question",
                    "retrieval": "query",
                    "evidence": "source",
                },
                "evidence_status": "provided",
            }
        ],
    }
    with pytest.raises(ArtifactValidationError, match="question"):
        validate_artifact("query-map", artifact)


def _git(repo, *arguments):
    return subprocess.run(
        ["git", *arguments],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )


def test_package_uses_exact_tracked_regular_file_allowlist(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    (repo / "VERSION").write_text("0.2.0\n", encoding="utf-8")
    (repo / ".gitignore").write_text("ignored.txt\n", encoding="utf-8")
    (repo / "tracked.txt").write_text("trusted\n", encoding="utf-8")
    (repo / "untracked.txt").write_text("untrusted\n", encoding="utf-8")
    (repo / "ignored.txt").write_text("ignored\n", encoding="utf-8")
    outside = tmp_path / "outside.txt"
    outside.write_text("outside\n", encoding="utf-8")
    (repo / "external-link").symlink_to(outside)
    _git(repo, "add", "VERSION", ".gitignore", "tracked.txt")

    archive = tmp_path / "package.zip"
    allowlist = build_archive(repo, archive)
    assert allowlist == [Path(".gitignore"), Path("VERSION"), Path("tracked.txt")]
    with zipfile.ZipFile(archive) as package:
        names = package.namelist()
    assert names == [
        "geo-seo-hub-0.2.0/.gitignore",
        "geo-seo-hub-0.2.0/VERSION",
        "geo-seo-hub-0.2.0/tracked.txt",
    ]
    assert all(name not in "\n".join(names) for name in ("untracked.txt", "ignored.txt", "external-link"))


def test_package_rejects_tracked_symlink(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    outside = tmp_path / "outside.txt"
    outside.write_text("outside\n", encoding="utf-8")
    (repo / "external-link").symlink_to(outside)
    _git(repo, "add", "external-link")
    with pytest.raises(ValueError, match="regular file"):
        trusted_files(repo)


def test_package_rejects_tracked_file_beneath_external_parent_symlink(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    (repo / "VERSION").write_text("0.2.0\n", encoding="utf-8")
    nested = repo / "nested"
    nested.mkdir()
    (nested / "file.txt").write_text("trusted\n", encoding="utf-8")
    _git(repo, "add", "VERSION", "nested/file.txt")

    nested.rename(repo / "original-nested")
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "file.txt").write_text("external secret\n", encoding="utf-8")
    nested.symlink_to(outside, target_is_directory=True)
    archive = tmp_path / "package.zip"

    with pytest.raises(ValueError, match="parent must be a regular directory"):
        build_archive(repo, archive)
    assert not archive.exists()
