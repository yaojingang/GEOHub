import json
import sys
import zipfile
from pathlib import Path

from geo_seo_hub.cli import main
from geo_seo_hub.validation import validate_artifact


def _write_minimal_wheel(path: Path, version: str) -> None:
    distribution = "geo_seo_hub"
    dist_info = f"{distribution}-{version}.dist-info"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("geo_seo_hub/__init__.py", f"__version__ = {version!r}\n")
        archive.writestr(
            f"{dist_info}/METADATA",
            f"Metadata-Version: 2.1\nName: geo-seo-hub\nVersion: {version}\n",
        )
        archive.writestr(
            f"{dist_info}/WHEEL",
            "Wheel-Version: 1.0\nGenerator: GEOHub tests\nRoot-Is-Purelib: true\nTag: py3-none-any\n",
        )
        archive.writestr(f"{dist_info}/RECORD", "")


def test_eval_cli_runs_recorded_fixture_suite_through_public_contract(tmp_path, capsys):
    suite = Path(__file__).parents[1] / "evals" / "quality" / "benchmark-suite.yaml"
    output = tmp_path / "quality-lab"

    assert main(
        [
            "eval",
            "--suite",
            str(suite),
            "--output",
            str(output),
            "--execution-mode",
            "deterministic",
        ]
    ) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "completed-with-missing-evidence"
    assert payload["case_count"] == 5
    assert payload["pair_count"] == 20
    assert payload["execution_kinds"] == ["recorded_fixture"]

    result = json.loads((output / "eval-result.json").read_text(encoding="utf-8"))
    validate_artifact("eval-result", result)
    assert result["summary"]["with_skill_pass_rate"] - result["summary"]["baseline_pass_rate"] >= 0.15
    assert result["summary"]["fabricated_citations"] == 0
    assert result["human_review"]["status"] == "missing-evidence"

    pack = json.loads((output / "blind-review-pack.json").read_text(encoding="utf-8"))
    answer_key = json.loads((output / "blind-answer-key.json").read_text(encoding="utf-8"))
    assert len(pack["pairs"]) == 20
    assert len(answer_key["pairs"]) == 20
    assert all("with_skill_variant" not in pair for pair in pack["pairs"])
    assert all(pair["with_skill_variant"] in {"A", "B"} for pair in answer_key["pairs"])


def test_private_holdout_is_loaded_only_from_environment_and_redacted(tmp_path, monkeypatch, capsys):
    private_root = tmp_path / "private-holdout"
    private_root.mkdir()
    private_task = {
        "protocol_version": "1.0.0",
        "task_id": "private-boundary-01",
        "skill_id": "geo-content",
        "case_type": "boundary",
        "prompt": "PRIVATE PROMPT MATERIAL",
        "input_files": [],
        "limits": {"max_input_bytes": 32768, "max_output_tokens": 2048},
        "variants": {
            "baseline": {"output": {"answer": "PRIVATE BASELINE MATERIAL"}},
            "with_skill": {
                "output": {
                    "answer": "PRIVATE SKILLED MATERIAL with missing evidence",
                    "status": "blocked",
                    "evidence_status": "missing-evidence",
                }
            },
        },
        "assertions": {
            "required_json_paths": ["status", "evidence_status"],
            "required_terms": ["missing evidence"],
            "forbidden_terms": ["fabricated"],
            "allowed_source_ids": [],
        },
        "rubric": "Prefer the evidence-safe result.",
        "tags": ["private-holdout"],
    }
    (private_root / "case.json").write_text(json.dumps(private_task), encoding="utf-8")
    monkeypatch.setenv("GEOHUB_PRIVATE_EVAL_ROOT", str(private_root))
    suite = Path(__file__).parents[1] / "evals" / "quality" / "benchmark-suite.yaml"
    output = tmp_path / "private-result"

    assert main(["eval", "--suite", str(suite), "--output", str(output)]) == 0

    capsys.readouterr()
    result = json.loads((output / "eval-result.json").read_text(encoding="utf-8"))
    assert result["summary"]["case_count"] == 6
    assert result["summary"]["private_holdout_case_count"] == 1
    private_runs = [run for run in result["runs"] if run["task_id"] == "private-boundary-01"]
    assert len(private_runs) == 2
    assert all(run["output"]["redacted"] is True for run in private_runs)
    public_artifacts = "\n".join(path.read_text(encoding="utf-8") for path in output.glob("*.json"))
    assert "PRIVATE PROMPT MATERIAL" not in public_artifacts
    assert "PRIVATE BASELINE MATERIAL" not in public_artifacts
    assert "PRIVATE SKILLED MATERIAL" not in public_artifacts


def test_eval_cli_runs_command_runner_and_records_distinct_wheels(tmp_path, capsys):
    suite = Path(__file__).parents[1] / "evals" / "quality" / "benchmark-suite.yaml"
    runner = tmp_path / "runner.py"
    runner.write_text(
        "import json,sys\n"
        "request=json.load(sys.stdin)\n"
        "output=request['task']['variants'][request['variant']]['output']\n"
        "json.dump({'output':output,'execution_kind':'command','usage':"
        "{'input_tokens':0,'output_tokens':0,'total_tokens':0}},sys.stdout)\n",
        encoding="utf-8",
    )
    baseline_wheel = tmp_path / "geo_seo_hub-0.2.0-py3-none-any.whl"
    candidate_wheel = tmp_path / "geo_seo_hub-0.3.0-py3-none-any.whl"
    _write_minimal_wheel(baseline_wheel, "0.2.0")
    _write_minimal_wheel(candidate_wheel, "0.3.0")
    output = tmp_path / "command-result"

    assert main(
        [
            "eval",
            "--suite",
            str(suite),
            "--output",
            str(output),
            "--execution-mode",
            "command",
            "--runner-command-json",
            json.dumps(["{python}", str(runner)]),
            "--baseline-wheel",
            str(baseline_wheel),
            "--candidate-wheel",
            str(candidate_wheel),
        ]
    ) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["execution_kinds"] == ["command"]
    result = json.loads((output / "eval-result.json").read_text(encoding="utf-8"))
    assert result["environments"]["baseline"]["status"] == "verified"
    assert result["environments"]["candidate"]["status"] == "verified"
    assert result["environments"]["baseline"]["wheel_sha256"] != result["environments"]["candidate"]["wheel_sha256"]
    assert {run["execution_kind"] for run in result["runs"]} == {"command"}


def test_provider_mode_refuses_to_run_without_credentials_and_models(tmp_path, monkeypatch, capsys):
    for name in (
        "OPENAI_API_KEY",
        "GEOHUB_GENERATOR_MODEL_A",
        "GEOHUB_GENERATOR_MODEL_B",
    ):
        monkeypatch.delenv(name, raising=False)
    suite = Path(__file__).parents[1] / "evals" / "quality" / "benchmark-suite.yaml"
    output = tmp_path / "provider-result"

    assert main(
        [
            "eval",
            "--suite",
            str(suite),
            "--output",
            str(output),
            "--execution-mode",
            "provider",
        ]
    ) == 2

    payload = json.loads(capsys.readouterr().err)
    assert payload["status"] == "error"
    assert "OPENAI_API_KEY" in payload["message"]
    assert not output.exists()


def test_provider_mode_requires_explicit_prices_before_any_request(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("OPENAI_API_KEY", "fixture-key")
    monkeypatch.setenv("GEOHUB_GENERATOR_MODEL_A", "fixture-a")
    monkeypatch.setenv("GEOHUB_GENERATOR_MODEL_B", "fixture-b")
    for name in (
        "GEOHUB_MODEL_A_INPUT_USD_PER_1M",
        "GEOHUB_MODEL_A_OUTPUT_USD_PER_1M",
        "GEOHUB_MODEL_B_INPUT_USD_PER_1M",
        "GEOHUB_MODEL_B_OUTPUT_USD_PER_1M",
    ):
        monkeypatch.delenv(name, raising=False)
    suite = Path(__file__).parents[1] / "evals" / "quality" / "benchmark-suite.yaml"
    output = tmp_path / "provider-pricing"
    assert main(["eval", "--suite", str(suite), "--output", str(output), "--execution-mode", "provider"]) == 2
    assert "GEOHUB_MODEL_A_INPUT_USD_PER_1M" in json.loads(capsys.readouterr().err)["message"]
    assert not output.exists()


def test_provider_mode_blocks_private_holdout_without_transmission_consent(tmp_path, monkeypatch, capsys):
    private_root = tmp_path / "private"
    private_root.mkdir()
    task = json.loads((Path(__file__).parents[1] / "evals" / "quality" / "public" / "route.json").read_text())
    task["task_id"] = "private-provider-01"
    (private_root / "case.json").write_text(json.dumps(task), encoding="utf-8")
    monkeypatch.setenv("GEOHUB_PRIVATE_EVAL_ROOT", str(private_root))
    monkeypatch.setenv("OPENAI_API_KEY", "fixture-key")
    monkeypatch.setenv("GEOHUB_GENERATOR_MODEL_A", "fixture-a")
    monkeypatch.setenv("GEOHUB_GENERATOR_MODEL_B", "fixture-b")
    for name in (
        "GEOHUB_MODEL_A_INPUT_USD_PER_1M",
        "GEOHUB_MODEL_A_OUTPUT_USD_PER_1M",
        "GEOHUB_MODEL_B_INPUT_USD_PER_1M",
        "GEOHUB_MODEL_B_OUTPUT_USD_PER_1M",
    ):
        monkeypatch.setenv(name, "1")
    monkeypatch.delenv("GEOHUB_PRIVATE_PROVIDER_CONSENT", raising=False)
    suite = Path(__file__).parents[1] / "evals" / "quality" / "benchmark-suite.yaml"
    output = tmp_path / "private-provider"
    assert main(["eval", "--suite", str(suite), "--output", str(output), "--execution-mode", "provider"]) == 2
    assert "excludes private holdouts" in json.loads(capsys.readouterr().err)["message"]
    assert not output.exists()
