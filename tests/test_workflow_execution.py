from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import time

import pytest

from geo_seo_hub.control.execution import (
    NonRetryableExecutionError,
    _collect_outputs,
    _execute_skill,
    continue_workflow,
    start_workflow,
)
from geo_seo_hub.control.planning import compile_task_plan, write_task_plan
from geo_seo_hub.control.workflow import WorkflowRunner
from geo_seo_hub.paths import repository_root
from geo_seo_hub.router import route


def _write_receipt(path):
    receipt = {
        "protocol_version": "1.0.0",
        "publication_id": "publication-runtime-1",
        "candidate_digest": "a" * 64,
        "handoff_digest": "b" * 64,
        "target_uri": "https://example.invalid/runtime-publication",
        "published_at": "2026-08-22T00:00:00Z",
        "status": "verified",
    }
    receipt["semantic_digest"] = hashlib.sha256(
        json.dumps(receipt, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()
    path.write_text(json.dumps(receipt), encoding="utf-8")


def test_strategy_loop_executes_to_each_gate_and_completes(tmp_path):
    request = "Build a GEO strategy, then monitor AI visibility"
    plan = compile_task_plan(request, route(request))
    plan_path = tmp_path / "task-plan.json"
    write_task_plan(plan_path, plan)
    inputs_path = tmp_path / "inputs.json"
    strategy_fixture = repository_root() / "tests" / "fixtures" / "strategy-request.json"
    inputs_path.write_text(json.dumps({"strategy-request": str(strategy_fixture)}), encoding="utf-8")
    state_path = tmp_path / "workflow-state.json"

    awaiting_approval = start_workflow(plan_path, state_path, inputs_path, tmp_path / "runs")
    assert awaiting_approval["status"] == "awaiting_approval"
    assert awaiting_approval["current_step"] == "approve-publication"
    assert awaiting_approval["steps"][0]["outputs"]["publication-handoff"]

    awaiting_publication = WorkflowRunner(state_path).decide_approval(approved=True, reviewer="reviewer-1")
    assert awaiting_publication["status"] == "awaiting_external_publication"
    receipt_path = tmp_path / "publication-receipt.json"
    _write_receipt(receipt_path)
    awaiting_observation = WorkflowRunner(state_path).resume_external(
        awaiting_publication["checkpoints"][-1]["checkpoint_id"],
        receipt_path.name,
    )
    assert awaiting_observation["status"] == "awaiting_external_observation"

    observation_path = tmp_path / "engine-observation-bundle.json"
    shutil.copyfile(
        repository_root() / "tests" / "fixtures" / "engine-observation-bundle.json",
        observation_path,
    )
    resumed = WorkflowRunner(state_path).resume_external(
        awaiting_observation["checkpoints"][-1]["checkpoint_id"],
        observation_path.name,
    )
    assert resumed["status"] == "running"
    completed = continue_workflow(state_path)
    assert completed["status"] == "completed"
    assert completed["steps"][-1]["outputs"]["visibility-report"]


def test_workflow_runtime_fails_closed_when_required_input_is_missing(tmp_path):
    request = "query research"
    plan = compile_task_plan(request, route(request))
    plan_path = tmp_path / "task-plan.json"
    write_task_plan(plan_path, plan)
    inputs_path = tmp_path / "inputs.json"
    inputs_path.write_text("{}\n", encoding="utf-8")
    try:
        start_workflow(plan_path, tmp_path / "state.json", inputs_path, tmp_path / "runs")
    except ValueError as exc:
        assert "missing required artifacts" in str(exc)
    else:
        raise AssertionError("missing runtime input was accepted")


def test_workflow_runtime_retries_only_within_declared_budget(tmp_path, monkeypatch):
    request = "query research"
    plan = compile_task_plan(request, route(request))
    plan_path = tmp_path / "task-plan.json"
    write_task_plan(plan_path, plan)
    inputs_path = tmp_path / "inputs.json"
    fixture = repository_root() / "tests" / "fixtures" / "brief.json"
    inputs_path.write_text(json.dumps({"geo-brief": str(fixture)}), encoding="utf-8")
    attempts = []

    def timeout(*_args, **_kwargs):
        attempts.append("attempt")
        raise TimeoutError("fixture timeout")

    monkeypatch.setattr("geo_seo_hub.control.execution._execute_skill", timeout)
    failed = start_workflow(
        plan_path,
        tmp_path / "workflow-state.json",
        inputs_path,
        tmp_path / "runs",
    )
    assert failed["status"] == "failed"
    assert failed["steps"][0]["attempt"] == 2
    assert len(attempts) == 2


def test_non_idempotent_failed_step_cannot_be_retried(tmp_path):
    request = "query research"
    plan = compile_task_plan(request, route(request))
    plan["nodes"][0]["execution"]["idempotent"] = False
    semantic = {key: value for key, value in plan.items() if key != "plan_digest"}
    plan["plan_digest"] = hashlib.sha256(
        json.dumps(semantic, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()
    plan_path = tmp_path / "task-plan.json"
    write_task_plan(plan_path, plan)
    inputs_path = tmp_path / "inputs.json"
    fixture = repository_root() / "tests" / "fixtures" / "brief.json"
    inputs_path.write_text(json.dumps({"geo-brief": str(fixture)}), encoding="utf-8")

    from geo_seo_hub.control.execution import load_runtime_inputs, load_task_plan
    from geo_seo_hub.control.workflow import create_workflow_state_from_plan

    loaded = load_task_plan(plan_path)
    inputs = load_runtime_inputs(inputs_path, loaded["required_inputs"])
    inputs["runtime_output_root"] = str(tmp_path / "runs")
    state_path = tmp_path / "workflow-state.json"
    runner = WorkflowRunner.create(
        state_path,
        create_workflow_state_from_plan(loaded, run_id="run-non-idempotent", inputs=inputs),
    )
    runner.fail("execution-error", "fixture")
    with pytest.raises(ValueError, match="not declared idempotent"):
        runner.retry()


def test_missing_bound_input_fails_once_and_persists_failure_state(tmp_path):
    request = "query research"
    plan = compile_task_plan(request, route(request))
    plan_path = tmp_path / "task-plan.json"
    write_task_plan(plan_path, plan)
    inputs_path = tmp_path / "inputs.json"
    fixture = repository_root() / "tests" / "fixtures" / "brief.json"
    runtime_fixture = tmp_path / "brief.json"
    shutil.copyfile(fixture, runtime_fixture)
    inputs_path.write_text(json.dumps({"geo-brief": str(runtime_fixture)}), encoding="utf-8")
    state_path = tmp_path / "workflow-state.json"

    from geo_seo_hub.control.execution import load_runtime_inputs, load_task_plan
    from geo_seo_hub.control.workflow import create_workflow_state_from_plan

    loaded = load_task_plan(plan_path)
    inputs = load_runtime_inputs(inputs_path, loaded["required_inputs"])
    output_root = tmp_path / "runs"
    output_root.mkdir()
    inputs["runtime_output_root"] = str(output_root)
    WorkflowRunner.create(
        state_path,
        create_workflow_state_from_plan(loaded, run_id="run-missing-bound-input", inputs=inputs),
    )
    runtime_fixture.unlink()

    failed = continue_workflow(state_path)
    assert failed["status"] == "failed"
    assert failed["steps"][0]["attempt"] == 1
    assert WorkflowRunner(state_path).load()["status"] == "failed"


def test_changed_bound_input_fails_once_before_executor_runs(tmp_path):
    request = "query research"
    plan = compile_task_plan(request, route(request))
    plan_path = tmp_path / "task-plan.json"
    write_task_plan(plan_path, plan)
    fixture = repository_root() / "tests" / "fixtures" / "brief.json"
    runtime_fixture = tmp_path / "brief.json"
    shutil.copyfile(fixture, runtime_fixture)
    inputs_path = tmp_path / "inputs.json"
    inputs_path.write_text(json.dumps({"geo-brief": str(runtime_fixture)}), encoding="utf-8")

    from geo_seo_hub.control.execution import load_runtime_inputs, load_task_plan
    from geo_seo_hub.control.workflow import create_workflow_state_from_plan

    loaded = load_task_plan(plan_path)
    inputs = load_runtime_inputs(inputs_path, loaded["required_inputs"])
    output_root = tmp_path / "runs"
    output_root.mkdir()
    inputs["runtime_output_root"] = str(output_root)
    state_path = tmp_path / "workflow-state.json"
    WorkflowRunner.create(
        state_path,
        create_workflow_state_from_plan(loaded, run_id="run-changed-bound-input", inputs=inputs),
    )
    runtime_fixture.write_bytes(runtime_fixture.read_bytes() + b"\n")

    failed = continue_workflow(state_path)
    assert failed["status"] == "failed"
    assert failed["steps"][0]["attempt"] == 1
    assert "workflow input digest changed" in failed["failure_boundary"]["message"]


def test_runtime_rejects_tampered_output_root_before_executor_write(tmp_path):
    request = "query research"
    plan = compile_task_plan(request, route(request))
    plan_path = tmp_path / "task-plan.json"
    write_task_plan(plan_path, plan)
    inputs_path = tmp_path / "inputs.json"
    fixture = repository_root() / "tests" / "fixtures" / "brief.json"
    inputs_path.write_text(json.dumps({"geo-brief": str(fixture)}), encoding="utf-8")

    from geo_seo_hub.control.execution import load_runtime_inputs, load_task_plan
    from geo_seo_hub.control.workflow import create_workflow_state_from_plan

    loaded = load_task_plan(plan_path)
    inputs = load_runtime_inputs(inputs_path, loaded["required_inputs"])
    state_dir = tmp_path / "workflow"
    state_dir.mkdir()
    outside = tmp_path / "outside"
    inputs["runtime_output_root"] = str(outside)
    state_path = state_dir / "workflow-state.json"
    WorkflowRunner.create(
        state_path,
        create_workflow_state_from_plan(loaded, run_id="run-tampered-output-root", inputs=inputs),
    )

    failed = continue_workflow(state_path)
    assert failed["status"] == "failed"
    assert "workflow output must stay inside" in failed["failure_boundary"]["message"]
    assert not outside.exists()


def test_external_evidence_digest_is_rechecked_when_state_is_loaded(tmp_path):
    request = "Build a GEO strategy, then monitor AI visibility"
    plan = compile_task_plan(request, route(request))
    plan_path = tmp_path / "task-plan.json"
    write_task_plan(plan_path, plan)
    inputs_path = tmp_path / "inputs.json"
    strategy_fixture = repository_root() / "tests" / "fixtures" / "strategy-request.json"
    inputs_path.write_text(json.dumps({"strategy-request": str(strategy_fixture)}), encoding="utf-8")
    state_path = tmp_path / "workflow-state.json"

    approval = start_workflow(plan_path, state_path, inputs_path, tmp_path / "runs")
    publication = WorkflowRunner(state_path).decide_approval(approved=True, reviewer="reviewer-1")
    receipt_path = tmp_path / "publication-receipt.json"
    _write_receipt(receipt_path)
    observation = WorkflowRunner(state_path).resume_external(
        publication["checkpoints"][-1]["checkpoint_id"], receipt_path.name
    )
    observation_path = tmp_path / "engine-observation-bundle.json"
    shutil.copyfile(
        repository_root() / "tests" / "fixtures" / "engine-observation-bundle.json",
        observation_path,
    )
    WorkflowRunner(state_path).resume_external(
        observation["checkpoints"][-1]["checkpoint_id"], observation_path.name
    )
    observation_path.write_text("{}\n", encoding="utf-8")

    with pytest.raises(ValueError, match="external workflow evidence digest changed"):
        WorkflowRunner(state_path).load()


def test_executor_timeout_survives_child_closing_capture_streams(tmp_path, monkeypatch):
    real_popen = subprocess.Popen

    def close_streams_then_sleep(_command, **kwargs):
        return real_popen(
            [
                sys.executable,
                "-c",
                "import os,time; os.close(1); os.close(2); time.sleep(0.5)",
            ],
            **kwargs,
        )

    monkeypatch.setattr("geo_seo_hub.control.execution.subprocess.Popen", close_streams_then_sleep)
    started = time.monotonic()
    with pytest.raises(TimeoutError, match="declared timeout"):
        _execute_skill("discover", tmp_path / "input.json", tmp_path / "runs", 0.05)
    assert time.monotonic() - started < 0.4


def test_output_collection_rejects_symlinked_directory(tmp_path):
    run_dir = tmp_path / "runs" / "run-1"
    run_dir.mkdir(parents=True)
    outside = tmp_path / "outside"
    outside.mkdir()
    (run_dir / "linked-directory").symlink_to(outside, target_is_directory=True)

    with pytest.raises(NonRetryableExecutionError, match="non-regular artifact"):
        _collect_outputs(
            tmp_path / "workflow-state.json",
            {"expected_outputs": []},
            run_dir,
        )


def test_task_plan_step_cannot_complete_with_missing_artifacts(tmp_path):
    request = "query research"
    plan = compile_task_plan(request, route(request))
    plan_path = tmp_path / "task-plan.json"
    write_task_plan(plan_path, plan)
    fixture = repository_root() / "tests" / "fixtures" / "brief.json"
    inputs_path = tmp_path / "inputs.json"
    inputs_path.write_text(json.dumps({"geo-brief": str(fixture)}), encoding="utf-8")

    from geo_seo_hub.control.execution import load_runtime_inputs, load_task_plan
    from geo_seo_hub.control.workflow import create_workflow_state_from_plan

    loaded = load_task_plan(plan_path)
    inputs = load_runtime_inputs(inputs_path, loaded["required_inputs"])
    inputs["runtime_output_root"] = str(tmp_path / "runs")
    state_path = tmp_path / "workflow-state.json"
    runner = WorkflowRunner.create(
        state_path,
        create_workflow_state_from_plan(loaded, run_id="run-missing-artifacts", inputs=inputs),
    )
    refs = ["runs/missing-query-map.json", "runs/missing-opportunity-map.json"]
    with pytest.raises(ValueError, match="workflow artifact is unavailable"):
        runner.complete_step(
            "discover",
            refs,
            {"query-map": refs[0], "opportunity-map": refs[1]},
        )
