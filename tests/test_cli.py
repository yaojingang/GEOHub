import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from geo_seo_hub.cli import main
from geo_seo_hub.paths import repository_root
from geo_seo_hub.registry import RegistryError


def test_route_cli_prints_json(capsys):
    assert main(["route", "--text", "query research"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["skill_id"] == "geo-discover"


def test_route_cli_writes_valid_task_plan(tmp_path, capsys):
    target = tmp_path / "task-plan.json"
    assert main(
        [
            "route",
            "--text",
            "先拓词，再诊断网站",
            "--lexical-only",
            "--plan-output",
            str(target),
        ]
    ) == 0
    payload = json.loads(capsys.readouterr().out)
    plan = json.loads(target.read_text(encoding="utf-8"))
    assert payload["decision"]["semantic_status"] == "disabled"
    assert payload["task_plan"]["plan_id"] == plan["plan_id"]
    assert plan["workflow_id"] == "brand-baseline-lite"
    assert plan["status"] == "ready"


def test_route_cli_refuses_to_overwrite_task_plan(tmp_path, capsys):
    target = tmp_path / "task-plan.json"
    target.write_text("{}\n", encoding="utf-8")
    assert main(
        [
            "route",
            "--text",
            "query research",
            "--plan-output",
            str(target),
        ]
    ) == 2
    payload = json.loads(capsys.readouterr().err)
    assert "already exists" in payload["message"]


def test_workflow_cli_starts_single_skill_plan_to_completion(tmp_path, capsys):
    plan_path = tmp_path / "task-plan.json"
    assert main(
        [
            "route",
            "--text",
            "query research",
            "--lexical-only",
            "--plan-output",
            str(plan_path),
        ]
    ) == 0
    capsys.readouterr()
    inputs_path = tmp_path / "inputs.json"
    fixture = Path(__file__).parent / "fixtures" / "brief.json"
    inputs_path.write_text(json.dumps({"geo-brief": str(fixture)}), encoding="utf-8")
    state_path = tmp_path / "workflow-state.json"
    assert main(
        [
            "workflow",
            "start",
            "--plan",
            str(plan_path),
            "--state",
            str(state_path),
            "--inputs",
            str(inputs_path),
            "--output",
            str(tmp_path / "runs"),
        ]
    ) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "completed"
    assert payload["steps"][0]["outputs"]["query-map"]

    assert main(["workflow", "status", "--state", str(state_path)]) == 0
    status = json.loads(capsys.readouterr().out)
    assert status["plan_digest"] == payload["plan_digest"]


def test_discover_cli_prints_summary(tmp_path, capsys):
    fixture = Path(__file__).parent / "fixtures" / "brief.json"
    runs_root = tmp_path / "runs"
    assert main(["discover", "--input", str(fixture), "--output", str(runs_root)]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["query_count"] == 4
    assert Path(payload["output"]).parent == runs_root
    assert Path(payload["output"]).name.startswith("run-")


def test_diagnose_cli_prints_summary(tmp_path, capsys):
    fixture = Path(__file__).parent / "fixtures" / "diagnosis-brand.json"
    runs_root = tmp_path / "runs"
    assert main(["diagnose", "--input", str(fixture), "--output", str(runs_root)]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["diagnosis_status"] == "completed"
    assert Path(payload["output"]).parent == runs_root


def test_diagnose_cli_validation_error_is_json(tmp_path, capsys):
    fixture = tmp_path / "invalid-diagnosis.json"
    fixture.write_text(json.dumps({"subject": "Acme", "scope": "page"}), encoding="utf-8")
    assert main(["diagnose", "--input", str(fixture), "--output", str(tmp_path / "runs")]) == 2
    payload = json.loads(capsys.readouterr().err)
    assert payload["status"] == "error"
    assert "at least one" in payload["message"]


def test_measure_cli_prints_summary(tmp_path, capsys):
    fixture = Path(__file__).parent / "fixtures" / "measurement-brief.json"
    runs_root = tmp_path / "runs"
    assert main(["measure", "--input", str(fixture), "--output", str(runs_root)]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["trial_count"] == 3
    assert payload["eligible_trial_count"] == 2
    assert Path(payload["output"]).parent == runs_root


def test_seo_cli_turns_one_line_brief_into_a_plan(tmp_path, capsys):
    fixture = Path(__file__).parent / "fixtures" / "seo-brief.json"
    runs_root = tmp_path / "runs"
    assert main(["seo", "--input", str(fixture), "--output", str(runs_root)]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["work_mode"] == "technical-audit"
    assert Path(payload["output"]).parent == runs_root


def test_route_cli_rejects_empty_text(capsys):
    assert main(["route", "--text", "   "]) == 2
    payload = json.loads(capsys.readouterr().err)
    assert payload["status"] == "error"


def test_registry_error_is_json(monkeypatch, capsys):
    def fail_route(_text):
        raise RegistryError("invalid test registry")

    monkeypatch.setattr("geo_seo_hub.cli.route", fail_route)
    assert main(["route", "--text", "GEO"]) == 2
    payload = json.loads(capsys.readouterr().err)
    assert payload == {"status": "error", "message": "invalid test registry"}


def _run_cli(*arguments: str) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(repository_root() / "src")
    return subprocess.run(
        [sys.executable, "-m", "geo_seo_hub", *arguments],
        cwd=repository_root(),
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.parametrize(
    "arguments",
    [
        (),
        ("route",),
        ("route", "--text", "GEO", "--unknown"),
    ],
)
def test_argparse_errors_are_json(arguments):
    result = _run_cli(*arguments)
    assert result.returncode == 2
    assert result.stdout == ""
    payload = json.loads(result.stderr)
    assert payload["status"] == "error"
    assert payload["message"]


def test_help_remains_standard_stdout():
    result = _run_cli("--help")
    assert result.returncode == 0
    assert result.stderr == ""
    assert result.stdout.startswith("usage: geo-seo-hub")


def test_version_is_installed_distribution_json():
    result = _run_cli("--version")
    assert result.returncode == 0
    assert result.stderr == ""
    assert json.loads(result.stdout) == {
        "distribution": "geo-seo-hub",
        "name": "GEOHub",
        "version": (repository_root() / "VERSION").read_text(encoding="utf-8").strip(),
    }
