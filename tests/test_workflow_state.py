from __future__ import annotations

import json
import hashlib
from concurrent.futures import ThreadPoolExecutor

import pytest

from geo_seo_hub.control.workflow import WorkflowRunner, create_workflow_state
from geo_seo_hub.paths import repository_root
from geo_seo_hub.registry import load_registry
from geo_seo_hub.validation import validate_artifact


def _workflow():
    return load_registry()["workflows"][0]


def _write_publication_receipt(path):
    receipt = {
        "protocol_version": "1.0.0",
        "publication_id": "publication-1",
        "candidate_digest": "a" * 64,
        "handoff_digest": "b" * 64,
        "target_uri": "https://example.invalid/publication",
        "published_at": "2026-08-12T00:00:00Z",
        "status": "verified",
    }
    receipt["semantic_digest"] = hashlib.sha256(
        json.dumps(receipt, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()
    path.write_text(json.dumps(receipt), encoding="utf-8")


def test_workflow_checkpoint_resume_and_complete_across_instances(tmp_path):
    state_path = tmp_path / "workflow-state.json"
    state = create_workflow_state(
        _workflow(),
        run_id="run-workflow-1",
        inputs={"brief": "input/geo-brief.json"},
    )
    validate_artifact("workflow-state", state)
    runner = WorkflowRunner.create(state_path, state)
    checkpoint = runner.complete_step("discover", ["run-a/query-map.json"])
    assert checkpoint["status"] == "running"
    assert checkpoint["current_step"] == "diagnose"
    checkpoint_id = checkpoint["checkpoints"][-1]["checkpoint_id"]

    resumed = WorkflowRunner(state_path).resume(checkpoint_id)
    assert resumed["status"] == "running"
    assert resumed["current_step"] == "diagnose"
    completed = WorkflowRunner(state_path).complete_step("diagnose", ["run-b/diagnosis.json"])
    assert completed["status"] == "completed"
    assert completed["current_step"] is None
    validate_artifact("workflow-state", completed)


def test_external_wait_and_approval_are_recoverable(tmp_path):
    state_path = tmp_path / "workflow-state.json"
    runner = WorkflowRunner.create(
        state_path,
        create_workflow_state(_workflow(), run_id="run-workflow-2", inputs={}),
    )
    waiting = runner.wait_for_external("publication")
    assert waiting["status"] == "awaiting_external_publication"
    assert WorkflowRunner(state_path).load()["status"] == "awaiting_external_publication"
    _write_publication_receipt(tmp_path / "publication-receipt.json")
    resumed = WorkflowRunner(state_path).resume_external(
        waiting["checkpoints"][-1]["checkpoint_id"],
        "publication-receipt.json",
    )
    assert resumed["status"] == "running"

    approval = WorkflowRunner(state_path).request_approval("approve diagnosis handoff")
    assert approval["status"] == "awaiting_approval"
    approved = WorkflowRunner(state_path).decide_approval(approved=True, reviewer="reviewer-1")
    assert approved["status"] == "running"
    assert approved["approval"]["decision"] == "approved"


def test_retry_abort_rejection_and_duplicate_resume_have_deterministic_states(tmp_path):
    state_path = tmp_path / "workflow-state.json"
    runner = WorkflowRunner.create(
        state_path,
        create_workflow_state(_workflow(), run_id="run-workflow-3", inputs={}),
    )
    failed = runner.fail("step-timeout", "discover exceeded its time budget")
    assert failed["status"] == "failed"
    retried = runner.retry()
    assert retried["status"] == "running"
    assert retried["failure_boundary"]["attempt"] == 2

    waiting = runner.wait_for_external("publication")
    checkpoint_id = waiting["checkpoints"][-1]["checkpoint_id"]
    _write_publication_receipt(tmp_path / "publication-receipt.json")
    runner.resume_external(checkpoint_id, "publication-receipt.json")
    with pytest.raises(ValueError, match="already resumed"):
        runner.resume_external(checkpoint_id, "publication-receipt.json")

    runner.request_approval("review")
    rejected = runner.decide_approval(approved=False, reviewer="reviewer-2")
    assert rejected["status"] == "aborted"
    with pytest.raises(ValueError, match="terminal"):
        runner.abort("second abort")


def test_corrupted_checkpoint_and_incompatible_version_fail_closed(tmp_path):
    state_path = tmp_path / "workflow-state.json"
    runner = WorkflowRunner.create(
        state_path,
        create_workflow_state(_workflow(), run_id="run-workflow-4", inputs={}),
    )
    waiting = runner.wait_for_external("publication")
    checkpoint_id = waiting["checkpoints"][-1]["checkpoint_id"]

    payload = json.loads(state_path.read_text())
    payload["checkpoints"][-1]["checksum"] = "0" * 64
    state_path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="checkpoint checksum"):
        WorkflowRunner(state_path).resume(checkpoint_id)

    payload["checkpoints"][-1]["checksum"] = waiting["checkpoints"][-1]["checksum"]
    payload["workflow_version"] = "9.0.0"
    state_path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="incompatible workflow version"):
        WorkflowRunner(state_path).load()


def test_registry_workflow_ids_accept_bounded_slug_and_reject_unsafe_id(tmp_path):
    import yaml

    root = tmp_path / "repo"
    (root / "registry").mkdir(parents=True)
    (root / "skills").mkdir()
    source = load_registry()
    source["workflows"][0]["id"] = "brand-baseline-v2"
    for skill in source["skills"]:
        if skill["entry"]:
            target = root / skill["entry"]
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(f"---\nname: {skill['id']}\ndescription: fixture\n---\n", encoding="utf-8")
    (root / "registry" / "skills.yaml").write_text(yaml.safe_dump(source, allow_unicode=True), encoding="utf-8")
    schema = (repository_root() / "registry" / "skills.schema.json").read_text()
    (root / "registry" / "skills.schema.json").write_text(schema, encoding="utf-8")
    assert load_registry(root / "registry" / "skills.yaml")["workflows"][0]["id"] == "brand-baseline-v2"

    source["workflows"][0]["id"] = "../unsafe"
    (root / "registry" / "skills.yaml").write_text(yaml.safe_dump(source, allow_unicode=True), encoding="utf-8")
    with pytest.raises(ValueError, match="Invalid registry"):
        load_registry(root / "registry" / "skills.yaml")


def test_external_resume_requires_latest_boundary_checkpoint(tmp_path):
    state_path = tmp_path / "workflow-state.json"
    runner = WorkflowRunner.create(
        state_path,
        create_workflow_state(_workflow(), run_id="run-workflow-5", inputs={}),
    )
    progressed = runner.complete_step("discover", ["run-a/query-map.json"])
    old_checkpoint = progressed["checkpoints"][-1]["checkpoint_id"]
    runner.wait_for_external("publication")
    _write_publication_receipt(tmp_path / "publication-receipt.json")
    with pytest.raises(ValueError, match="latest boundary checkpoint"):
        runner.resume_external(old_checkpoint, "publication-receipt.json")


def test_generic_resume_cannot_cross_external_boundary_without_evidence(tmp_path):
    state_path = tmp_path / "workflow-state.json"
    runner = WorkflowRunner.create(
        state_path,
        create_workflow_state(_workflow(), run_id="run-workflow-evidence", inputs={}),
    )
    waiting = runner.wait_for_external("publication")
    with pytest.raises(ValueError, match="resume_external"):
        runner.resume(waiting["checkpoints"][-1]["checkpoint_id"])


def test_concurrent_workflow_create_allows_one_writer(tmp_path):
    state_path = tmp_path / "workflow-state.json"

    def create_once(index: int):
        state = create_workflow_state(_workflow(), run_id=f"run-workflow-create-{index}", inputs={})
        try:
            WorkflowRunner.create(state_path, state)
            return "created"
        except ValueError:
            return "rejected"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(create_once, (1, 2)))
    assert sorted(results) == ["created", "rejected"]
