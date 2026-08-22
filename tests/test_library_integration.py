from __future__ import annotations

import importlib.util
import inspect
import json
import re
import tomllib
import zipfile
from datetime import date
from pathlib import Path

import pytest
import yaml

from geo_seo_hub.registry import load_registry
from geo_seo_hub import __version__

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ("geo", "geo-discover", "geo-diagnose", "geo-content", "geo-measure", "geo-strategy", "geo-knowledge")


def test_geo_seo_hub_brand_and_compatibility_names_are_consistent():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    interfaces = [
        yaml.safe_load((ROOT / "skills" / skill_id / "agents" / "interface.yaml").read_text(encoding="utf-8"))
        for skill_id in SKILLS
    ]

    assert readme.startswith("# GEO SEO Hub\n")
    assert "GEO-first · SEO-ready" in readme
    assert "Dedicated SEO workflows and outcome claims" in readme
    assert project["name"] == "geo-seo-hub"
    assert project["scripts"] == {"geo-seo-hub": "geo_seo_hub.cli:main"}
    assert (ROOT / "src" / "geo_seo_hub").is_dir()
    assert not (ROOT / "src" / ("yao" + "_geo")).exists()
    assert project["urls"] == {
        "Homepage": "https://github.com/yaojingang/geo-seo-hub",
        "Repository": "https://github.com/yaojingang/geo-seo-hub",
    }
    assert all(item["interface"]["display_name"].startswith("GEO SEO Hub ") for item in interfaces)


@pytest.mark.parametrize("legacy_marker", ("yao" + "-geo", "yao" + "_geo"))
def test_repository_verifier_rejects_legacy_runtime_namespace(tmp_path, legacy_marker):
    verifier = load_script("verify_repository")
    (tmp_path / "src" / "geo_seo_hub").mkdir(parents=True)
    (tmp_path / "docs").mkdir()
    (tmp_path / "reports").mkdir()
    (tmp_path / "pyproject.toml").write_text(
        "\n".join(
            (
                "[project]",
                'name = "geo-seo-hub"',
                "[project.scripts]",
                'geo-seo-hub = "geo_seo_hub.cli:main"',
                "[tool.setuptools.data-files]",
                '"share/geo-seo-hub" = []',
            )
        )
        + "\n",
        encoding="utf-8",
    )
    (tmp_path / "README.md").write_text(f"legacy {legacy_marker}\n", encoding="utf-8")
    (tmp_path / "THIRD_PARTY_NOTICES.md").write_text(
        "yaojingang/" + legacy_marker + "-skills\n",
        encoding="utf-8",
    )
    (tmp_path / "docs" / "migration-source-ledger.md").write_text(
        legacy_marker + "-title-optimizer\n",
        encoding="utf-8",
    )

    with pytest.raises(SystemExit, match="legacy namespace marker"):
        verifier.verify_namespace_consistency(tmp_path)


def test_version_is_consistent_across_distribution_and_active_manifests():
    expected = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert project["project"]["version"] == expected
    assert __version__ == expected
    for skill_id in SKILLS:
        manifest = json.loads((ROOT / "skills" / skill_id / "manifest.json").read_text(encoding="utf-8"))
        assert manifest["version"] == expected

    for module_name in ("content", "discover", "diagnose"):
        module = __import__(f"geo_seo_hub.{module_name}", fromlist=[module_name])
        assert module.GENERATOR_VERSION == expected
        assert '"version": "0.2.0"' not in inspect.getsource(module)


@pytest.mark.parametrize(
    ("attack", "message"),
    [
        ("invalid-version", "semantic version"),
        ("project-drift", "pyproject.toml version"),
        ("manifest-drift", "geo-diagnose manifest version"),
    ],
)
def test_repository_verifier_rejects_version_drift(tmp_path, attack, message):
    verifier = load_script("verify_repository")
    version = "0.2.0"
    (tmp_path / "VERSION").write_text(
        "release-one\n" if attack == "invalid-version" else f"{version}\n",
        encoding="utf-8",
    )
    project_version = "0.1.1" if attack == "project-drift" else version
    (tmp_path / "pyproject.toml").write_text(
        f'[project]\nname = "fixture"\nversion = "{project_version}"\n',
        encoding="utf-8",
    )
    for skill_id in SKILLS:
        manifest = tmp_path / "skills" / skill_id / "manifest.json"
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest_version = "0.1.1" if attack == "manifest-drift" and skill_id == "geo-diagnose" else version
        manifest.write_text(json.dumps({"version": manifest_version}), encoding="utf-8")
    with pytest.raises(SystemExit, match=message):
        verifier.verify_version_consistency(tmp_path)


def load_script(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


def test_registry_workflows_are_valid_stable_dags():
    registry = load_registry()
    assert {item["id"] for item in registry["workflows"]} == {
        "brand-baseline-lite",
        "content-campaign",
        "brand-baseline-content",
        "strategy-observation-loop",
    }
    for workflow in registry["workflows"]:
        seen = set()
        for step in workflow["steps"]:
            assert set(step) == {"id", "skill_id", "depends_on"}
            assert set(step["depends_on"]) <= seen
            seen.add(step["id"])


def test_repository_verifier_fails_closed_on_additive_connector_drift(monkeypatch):
    verifier = load_script("verify_repository")
    verifier.verify_additive_connector_parity()
    monkeypatch.setattr(verifier, "_WORKFLOW_CONNECTOR_RE", re.compile(r"\band\b"))
    with pytest.raises(SystemExit, match="connector parity"):
        verifier.verify_additive_connector_parity()


def test_repository_verifier_rejects_additive_flag_and_order_drift(monkeypatch):
    verifier = load_script("verify_repository")
    original = verifier.GOVERNED_ADDITIVE_CONNECTORS
    attacks = (
        tuple(
            (token, pattern, not breaks_negation if token == "and" else breaks_negation)
            for token, pattern, breaks_negation in original
        ),
        tuple(
            (token, pattern, not breaks_negation if token == "also" else breaks_negation)
            for token, pattern, breaks_negation in original
        ),
        (original[2], original[1], original[0], *original[3:]),
        (original[0], original[1], original[0], *original[3:]),
        (
            original[0],
            original[1],
            (original[2][0], original[3][1], original[2][2]),
            *original[3:],
        ),
    )
    for attack in attacks:
        monkeypatch.setattr(verifier, "GOVERNED_ADDITIVE_CONNECTORS", attack)
        with pytest.raises(SystemExit, match="connector inventory"):
            verifier.verify_additive_connector_parity()


def test_repository_verifier_rejects_sequence_connector_metadata_drift(monkeypatch):
    verifier = load_script("verify_repository")
    verifier.verify_sequence_connector_parity()
    original = verifier.GOVERNED_SEQUENCE_CONNECTORS
    attacks = (
        tuple(
            (token, pattern, not preserves if token == "then" else preserves)
            for token, pattern, preserves in original
        ),
        (original[1], original[0], *original[2:]),
        (original[0], original[0], *original[2:]),
        (
            (original[0][0], original[1][1], original[0][2]),
            *original[1:],
        ),
    )
    for attack in attacks:
        monkeypatch.setattr(verifier, "GOVERNED_SEQUENCE_CONNECTORS", attack)
        with pytest.raises(SystemExit, match="sequence connector inventory"):
            verifier.verify_sequence_connector_parity()
    monkeypatch.setattr(verifier, "GOVERNED_SEQUENCE_CONNECTORS", original)
    monkeypatch.setattr(verifier, "_GOVERNED_SEQUENCE_EXCLUSIVITY_TOKENS", frozenset())
    with pytest.raises(SystemExit, match="sequence connector parity"):
        verifier.verify_sequence_connector_parity()


def test_repository_verifier_rejects_action_lead_in_or_article_drift(monkeypatch):
    verifier = load_script("verify_repository")
    verifier.verify_action_language_parity()
    monkeypatch.setattr(
        verifier,
        "GOVERNED_ZH_ACTION_LEAD_INS",
        (*verifier.GOVERNED_ZH_ACTION_LEAD_INS, "随便"),
    )
    with pytest.raises(SystemExit, match="action language inventory"):
        verifier.verify_action_language_parity()
    monkeypatch.setattr(
        verifier,
        "GOVERNED_ZH_ACTION_LEAD_INS",
        verifier.EXPECTED_GOVERNED_ZH_ACTION_LEAD_INS,
    )
    monkeypatch.setattr(
        verifier,
        "GOVERNED_ACTION_OBJECT_ARTICLES",
        (*verifier.GOVERNED_ACTION_OBJECT_ARTICLES, "some"),
    )
    with pytest.raises(SystemExit, match="action language inventory"):
        verifier.verify_action_language_parity()
    monkeypatch.setattr(
        verifier,
        "GOVERNED_ACTION_OBJECT_ARTICLES",
        verifier.EXPECTED_GOVERNED_ACTION_OBJECT_ARTICLES,
    )
    monkeypatch.setattr(
        verifier,
        "GOVERNED_ZH_INTENT_SUFFIX_BLOCKS",
        (("发布", ("会",)),),
    )
    with pytest.raises(SystemExit, match="action language inventory"):
        verifier.verify_action_language_parity()
    monkeypatch.setattr(
        verifier,
        "GOVERNED_ZH_INTENT_SUFFIX_BLOCKS",
        verifier.EXPECTED_GOVERNED_ZH_INTENT_SUFFIX_BLOCKS,
    )
    monkeypatch.setattr(verifier, "_EN_ACTION_LEAD_IN_RE", re.compile(r"wanted\s+"))
    with pytest.raises(SystemExit, match="action language inventory"):
        verifier.verify_action_language_parity()


def test_router_source_has_no_prefix_only_action_boolean():
    from geo_seo_hub import router

    source = inspect.getsource(router)
    assert "def _starts_registered_action" not in source
    assert "_starts_registered_action(" not in source


def test_yao_meta_report_sanitizer_removes_machine_paths_and_trailing_whitespace(
    tmp_path,
):
    gate = load_script("run_yao_meta_gates")
    report = tmp_path / "review.html"
    report.write_text(
        f"<p>{gate.ROOT.resolve()}/skills/geo</p>   \n<section>ok</section>\t\n",
        encoding="utf-8",
    )

    gate.sanitize_generated_reports([report], tmp_path / "yao-meta")

    assert report.read_text(encoding="utf-8") == (
        "<p>skills/geo</p>\n<section>ok</section>\n"
    )


def test_dev_extra_installs_build_backend_for_offline_wheel_smoke():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    build_requirements = project["build-system"]["requires"]
    dev_requirements = project["project"]["optional-dependencies"]["dev"]

    assert any(requirement.startswith("setuptools") for requirement in build_requirements)
    assert any(requirement.startswith("setuptools") for requirement in dev_requirements)


@pytest.mark.parametrize("skill_id", SKILLS)
def test_library_manifests_and_interfaces_are_consistent(skill_id):
    skill_root = ROOT / "skills" / skill_id
    manifest = json.loads((skill_root / "manifest.json").read_text())
    assert manifest["status"] == "experimental"
    assert manifest["maturity_tier"] == "library"
    assert manifest["lifecycle_stage"] == "library"
    assert manifest["context_budget_tier"] == "production"
    assert manifest["contract_version"] == "1.0.0"
    assert manifest["availability"] == "active"
    assert manifest["entrypoint"] == "SKILL.md"
    assert manifest["permission_profile"]
    interface = yaml.safe_load((skill_root / "agents" / "interface.yaml").read_text())
    assert interface["compatibility"]["execution"]["shell"] == "bash"
    assert interface["interface"]["input_contract"]
    assert interface["interface"]["output_contract"]
    assert interface["interface"]["permission_contract"]


def test_eval_case_minimums_and_taxonomy():
    router_cases = json.loads((ROOT / "evals" / "router_cases.json").read_text())
    output_cases = json.loads((ROOT / "evals" / "output_cases.json").read_text())
    assert len(router_cases) >= 60
    assert len(output_cases) >= 20
    for skill_id in SKILLS:
        types = {item["case_type"] for item in output_cases if item["skill_id"] == skill_id}
        assert types == {"happy", "missing_input", "boundary", "near_neighbor", "source_shortfall"}


def test_package_allowlist_excludes_private_surfaces_and_keeps_public_verification_inputs():
    package = load_script("package")
    for path in package.tracked_files():
        assert not ({".git", "runs", "dist"} & set(path.parts))
        assert "reports" not in path.parts or path.parts[0] == "skills"
    assert package.source_allowed(Path("tests/test_router.py"))
    assert package.source_allowed(Path("evals/router_cases.json"))


def test_source_package_allowlist_includes_security_and_governance():
    package = load_script("package")
    for relative in (
        "SECURITY.md",
        "CHANGELOG.md",
        ".github/dependabot.yml",
        ".github/ISSUE_TEMPLATE/commercial-licensing.yml",
        ".github/workflows/release.yml",
    ):
        assert package.source_allowed(Path(relative))


def test_repository_governance_and_verification_entrypoints_are_actionable():
    security = (ROOT / "SECURITY.md").read_text(encoding="utf-8")
    contributing = (ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")
    commercial = (ROOT / "COMMERCIAL-LICENSING.md").read_text(encoding="utf-8")
    issue_template = yaml.safe_load(
        (ROOT / ".github" / "ISSUE_TEMPLATE" / "commercial-licensing.yml").read_text(encoding="utf-8")
    )
    dependabot = yaml.safe_load((ROOT / ".github" / "dependabot.yml").read_text(encoding="utf-8"))
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "security/advisories/new" in security
    assert "SECURITY.md" in contributing
    assert "issues/new?template=commercial-licensing.yml" in commercial
    assert issue_template["labels"] == ["commercial-licensing"]
    assert all(update["open-pull-requests-limit"] == 0 for update in dependabot["updates"])
    assert "verify:\n\t$(PYTHON) scripts/verify_all.py" in makefile
    assert "repo-verify:\n\t$(PYTHON) scripts/verify_repository.py" in makefile
    assert "git clone https://github.com/yaojingang/geo-seo-hub.git" in readme
    assert ".venv/bin/python -m pip install ." in readme


def test_package_verifier_rejects_traversal(tmp_path):
    verifier = load_script("verify_packages")
    attack = tmp_path / "attack.zip"
    with zipfile.ZipFile(attack, "w") as archive:
        archive.writestr("../escape", "bad")
    with pytest.raises(ValueError, match="unsafe ZIP member"):
        verifier.verify_archive(attack)


def test_safe_extract_rejects_symlink(tmp_path):
    installer = load_script("install_simulation")
    attack = tmp_path / "symlink.zip"
    with zipfile.ZipFile(attack, "w") as archive:
        info = zipfile.ZipInfo("link")
        info.external_attr = 0o120777 << 16
        archive.writestr(info, "target")
    with pytest.raises(ValueError, match="symlink"):
        installer.safe_extract(attack, tmp_path / "out")


def test_legal_metadata_and_ci_contract():
    for skill_id in SKILLS:
        manifest = json.loads((ROOT / "skills" / skill_id / "manifest.json").read_text())
        assert manifest["license_expression"] == "AGPL-3.0-only"
        assert manifest["commercial_license_status"] == "inquiry_only"
    cla = (ROOT / "CONTRIBUTOR-LICENSE-AGREEMENT.md").read_text()
    assert "DRAFT" in cla and "PENDING LEGAL REVIEW" in cla
    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text()
    assert "3.11" in ci and "3.13" in ci and "macos-latest" in ci
    assert "actions/checkout@v4" in ci and "actions/setup-python@v5" in ci


def test_migration_ledger_has_exact_21_rows_and_baseline():
    ledger = (ROOT / "docs" / "migration-source-ledger.md").read_text()
    rows = [line for line in ledger.splitlines() if line.startswith("| ") and line.split("|")[1].strip().isdigit()]
    assert len(rows) == 21
    assert "201c0c45dcf09bb37bc46a467b4baf4d721db205" in ledger
    assert "内容主体 + 补充说明与参考来源" in ledger
    assert "font files" in ledger


def test_yao_meta_interface_uses_supported_shell_and_output_cases():
    for skill_id in SKILLS:
        interface = yaml.safe_load((ROOT / "skills" / skill_id / "agents" / "interface.yaml").read_text())
        assert interface["compatibility"]["execution"]["shell"] == "bash"
        lines = (ROOT / "skills" / skill_id / "evals" / "output" / "cases.jsonl").read_text().splitlines()
        assert len(lines) >= 5
        assert all(json.loads(line)["baseline_output"] != json.loads(line)["with_skill_output"] for line in lines)


def test_non_source_packages_have_self_contained_install_and_route_entries():
    package = load_script("package")
    collision_project = tomllib.loads(
        package.packaged_pyproject(
            {
                "SKILL.md": b"fixture",
                "references/providers/a/shared.md": b"a",
                "references/providers/b/shared.md": b"b",
            }
        ).decode()
    )
    collision_groups = collision_project["tool"]["setuptools"]["data-files"]
    assert collision_groups["share/geo-seo-hub/references/providers/a"] == ["references/providers/a/shared.md"]
    assert collision_groups["share/geo-seo-hub/references/providers/b"] == ["references/providers/b/shared.md"]
    archives = package.build("all")
    for path in archives:
        if path.name.startswith("geo-seo-hub-source-"):
            continue
        with zipfile.ZipFile(path) as archive:
            names = set(archive.namelist())
            project = tomllib.loads(archive.read("pyproject.toml").decode())
            assert project["project"]["requires-python"] == ">=3.11,<3.15"
            assert project["project"]["readme"] in names
            for destination, sources in project["tool"]["setuptools"]["data-files"].items():
                assert set(sources) <= names
                for source in sources:
                    relative_parent = Path(source).parent.as_posix()
                    expected_destination = "share/geo-seo-hub" if relative_parent == "." else f"share/geo-seo-hub/{relative_parent}"
                    assert destination == expected_destination
            registry = yaml.safe_load(archive.read("registry/skills.yaml"))
            for skill in registry["skills"]:
                if skill["status"] == "active":
                    assert skill["entry"] in names
                    entry_text = archive.read(skill["entry"]).decode()
                    frontmatter = yaml.safe_load(entry_text.split("---", 2)[1])
                    assert frontmatter["name"] == skill["id"]
                    referenced = set(re.findall(r"(?:references|scripts)/[A-Za-z0-9_.\-/]+", entry_text))
                    assert referenced <= names
        if "unified" in path.name or "codex" in path.name or "claude" in path.name:
            assert {f"scripts/run_{name}.py" for name in ("route", "discover", "diagnose", "content", "measure", "strategy", "knowledge")} <= names


def test_install_simulation_uses_each_extracted_package_and_real_provider_execution():
    installer = load_script("install_simulation")
    assert list(inspect.signature(installer.structural_smoke).parameters) == ["path", "temp_root", "wheelhouse"]
    assert "Path(raw).resolve()" not in inspect.getsource(installer.main)
    source = inspect.getsource(installer.structural_smoke)
    assert "install_extracted(destination" in source
    assert 'wrappers["run_route.py"]' in source
    assert all(f'"run_{provider}.py"' in source for provider in ("discover", "diagnose", "content", "measure", "strategy", "knowledge"))
    report = json.loads((ROOT / "reports" / "install-simulation.json").read_text())
    assert report["source"]["cli_smokes"] == ["version", "route", "route-plan", "workflow-start", "discover", "diagnose", "content", "measure", "strategy", "knowledge"]
    assert len(report["structural_packages"]) == 10
    assert all(item["installed_from"] == "." and item["installed_share_resolved"] and item["resolved_entry"] and item["provider_executions"] == ["geo-discover", "geo-diagnose", "geo-content", "geo-measure", "geo-strategy", "geo-knowledge"] for item in report["structural_packages"])


def test_supported_python_range_and_governance_contracts():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())
    assert project["project"]["requires-python"] == ">=3.11,<3.15"
    assert "3.11-3.14" in (ROOT / "README.md").read_text()
    assert "3.11-3.14" in (ROOT / "docs" / "installation.md").read_text()
    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text()
    assert all(f'"{version}"' in ci for version in ("3.11", "3.12", "3.13", "3.14"))

    cla = (ROOT / "CONTRIBUTOR-LICENSE-AGREEMENT.md").read_text()
    assert "Harmony 1.0" in cla and "Individual" in cla and "Entity" in cla
    assert "not enabled" in cla and "not offered for acceptance" in cla
    notices = (ROOT / "THIRD_PARTY_NOTICES.md").read_text()
    assert "CC BY 3.0" in notices and "Creative Commons Attribution 3.0" in notices
    contributing = (ROOT / "CONTRIBUTING.md").read_text()
    assert "DCO" in contributing and "CLA" in contributing
    commercial = (ROOT / "COMMERCIAL-LICENSING.md").read_text()
    assert "GitHub" in commercial and "Issue" in commercial
    scope = (ROOT / "LICENSE-SCOPE.md").read_text()
    for boundary in ("code", "documentation", "templates", "generated outputs", "user data", "trademarks"):
        assert boundary in scope.casefold()


def test_yao_meta_structured_status_and_waiver_ledger_fail_closed(tmp_path):
    gate = load_script("run_yao_meta_gates")
    failed = tmp_path / "failed.json"
    failed.write_text(json.dumps({"ok": False, "summary": {"decision": "pass"}}))
    assert gate.structured_report_status(failed) == "fail"
    for payload in ({"status": "blocked"}, {"status": "partial"}, {"hello": "world"}):
        unknown = tmp_path / f"unknown-{len(list(tmp_path.iterdir()))}.json"
        unknown.write_text(json.dumps(payload))
        assert gate.structured_report_status(unknown) == "fail"
    operation_reports = {
        "skill-ir": ROOT / "reports" / "yao-meta" / "geo-skill-ir.json",
        "output-eval": ROOT / "reports" / "yao-meta" / "geo-output-eval.json",
        "trust": ROOT / "reports" / "yao-meta" / "geo-trust.json",
        "review-studio": ROOT / "reports" / "yao-meta" / "geo-review-studio.json",
        "compile-skill": ROOT / "reports" / "yao-meta" / "geo-compiled-generic.json",
        "conformance": ROOT / "reports" / "yao-meta" / "geo-conformance-generic.json",
        "skill-atlas": ROOT / "reports" / "skill-atlas.json",
    }
    for operation, positive in operation_reports.items():
        expected = "review" if operation == "review-studio" else "pass"
        assert gate.structured_report_status(positive, operation) == expected
        for index, payload in enumerate(({"status": "pass"}, {"ok": True})):
            skeletal = tmp_path / f"skeletal-{operation}-{index}.json"
            skeletal.write_text(json.dumps(payload))
            assert gate.structured_report_status(skeletal, operation) == "fail"
        typed_empty = {
            key: (True if expected_type is bool else expected_type())
            for key, expected_type in gate.OPERATION_REPORT_FIELDS[operation].items()
        }
        typed_empty_path = tmp_path / f"typed-empty-{operation}.json"
        typed_empty_path.write_text(json.dumps(typed_empty))
        assert gate.structured_report_status(typed_empty_path, operation) == "fail"

    waivers = gate.load_waiver_ledger(ROOT / "reports" / "review-waivers.json", today=date(2026, 8, 8))
    assert waivers
    assert all({"id", "skill_id", "gate", "owner", "reason", "expires_on", "recheck"} <= set(item) for item in waivers)
    review = {
        "ok": True,
        "summary": {"decision": "review"},
        "warnings": [{"key": "operations-loop"}, {"key": "release-notes"}],
    }
    classified = gate.classify_review_studio("geo", review, waivers)
    assert classified["release_blocking"] == []
    assert classified["waived_missing_evidence"] == ["operations-loop", "release-notes"]
    assert classified["review_warning_count"] == classified["classified_warning_count"] == 2

    ledger = json.loads((ROOT / "reports" / "review-waivers.json").read_text())
    attacks = []
    unknown = json.loads(json.dumps(ledger))
    unknown["waivers"][0]["gate"] = "unknown-suite-gate"
    attacks.append(unknown)
    duplicate_pair = json.loads(json.dumps(ledger))
    duplicate_pair["waivers"][1]["skill_id"] = duplicate_pair["waivers"][0]["skill_id"]
    duplicate_pair["waivers"][1]["gate"] = duplicate_pair["waivers"][0]["gate"]
    attacks.append(duplicate_pair)
    empty = {"schema_version": "1.0.0", "waivers": []}
    attacks.append(empty)
    for index, attack in enumerate(attacks):
        attack_path = tmp_path / f"waiver-attack-{index}.json"
        attack_path.write_text(json.dumps(attack))
        with pytest.raises(ValueError, match="waiver ledger"):
            gate.load_waiver_ledger(attack_path, today=date(2026, 8, 8))


def test_yao_meta_digest_and_command_inventory_are_complete():
    gate = load_script("run_yao_meta_gates")
    paths = {path.relative_to(ROOT).as_posix() for path in gate.source_digest_paths()}
    assert not any(".egg-info/" in path for path in paths)
    assert {
        "scripts/package.py",
        "scripts/verify_packages.py",
        "scripts/install_simulation.py",
        "reports/package-verification.json",
        "reports/install-simulation.json",
    } <= paths

    report = json.loads((ROOT / "reports" / "yao-meta-gates.json").read_text())
    assert gate.validate_command_inventory(report["commands"]) == []
    duplicated = [dict(report["commands"][0]) for _ in range(53)]
    assert gate.validate_command_inventory(duplicated)
    extra_flag = json.loads(json.dumps(report["commands"]))
    extra_flag[0]["command"].append("--unknown-flag")
    assert gate.validate_command_inventory(extra_flag)
    wrong_skill_path = json.loads(json.dumps(report["commands"]))
    wrong_skill_path[0]["command"][3] = "skills/geo-content"
    assert gate.validate_command_inventory(wrong_skill_path)
    unknown_unstructured_status = json.loads(json.dumps(report["commands"]))
    unknown_unstructured_status[0]["structured_status"] = "mystery"
    assert gate.validate_command_inventory(unknown_unstructured_status)
    trigger_structured_status = json.loads(json.dumps(report["commands"]))
    trigger_structured_status[1]["structured_status"] = "pass"
    assert gate.validate_command_inventory(trigger_structured_status)
    assert gate.deterministic_evidence_is_green(ROOT / "skills" / "geo" / "manifest.json")
    assert gate.deterministic_evidence_is_green(ROOT / "skills" / "geo" / "evals" / "semantic_config.json")
