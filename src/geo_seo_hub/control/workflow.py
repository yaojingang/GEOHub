from __future__ import annotations

import copy
import fcntl
import hashlib
import json
import os
import stat
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Iterator

from ..validation import load_bounded_json, read_bounded_regular_file, strict_json_loads, validate_artifact


WORKFLOW_VERSION = "1.0.0"
TERMINAL_STATES = {"completed", "aborted"}
EXTERNAL_STATES = {
    "awaiting_external_publication",
    "awaiting_external_observation",
}


def _canonical_digest(payload: dict[str, Any]) -> str:
    serialized = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _checkpoint_payload(checkpoint: dict[str, Any]) -> dict[str, Any]:
    return {
        key: checkpoint[key]
        for key in ("checkpoint_id", "kind", "step_id", "state_status", "artifact_refs", "artifact_digests")
    }


def _validate_workflow_definition(workflow: dict[str, Any]) -> None:
    if not isinstance(workflow, dict) or set(workflow) != {"id", "required_skills", "steps"}:
        raise ValueError("workflow definition fields are invalid")
    if not isinstance(workflow["id"], str) or not workflow["id"].strip():
        raise ValueError("workflow ID is invalid")
    if not isinstance(workflow["required_skills"], list) or any(not isinstance(item, str) or not item for item in workflow["required_skills"]):
        raise ValueError("workflow required_skills are invalid")
    if not isinstance(workflow["steps"], list) or not workflow["steps"]:
        raise ValueError("workflow must contain at least one step")
    observed: set[str] = set()
    step_skills: list[str] = []
    for step in workflow["steps"]:
        if not isinstance(step, dict) or set(step) != {"id", "skill_id", "depends_on"}:
            raise ValueError("workflow step fields are invalid")
        if (
            not isinstance(step["id"], str)
            or not step["id"]
            or not isinstance(step["skill_id"], str)
            or not step["skill_id"]
            or not isinstance(step["depends_on"], list)
            or any(not isinstance(item, str) or not item for item in step["depends_on"])
        ):
            raise ValueError("workflow step values are invalid")
        if step["id"] in observed or any(item not in observed for item in step["depends_on"]):
            raise ValueError("workflow steps must form a stable ordered DAG")
        observed.add(step["id"])
        step_skills.append(step["skill_id"])
    if step_skills != workflow["required_skills"]:
        raise ValueError("workflow required_skills must match step order")


def create_workflow_state(
    workflow: dict[str, Any],
    *,
    run_id: str,
    inputs: dict[str, str | int | float | bool | None],
) -> dict[str, Any]:
    _validate_workflow_definition(workflow)
    steps = [
        {
            "id": step["id"],
            "skill_id": step["skill_id"],
            "depends_on": list(step["depends_on"]),
            "status": "running" if index == 0 else "pending",
            "attempt": 1,
        }
        for index, step in enumerate(workflow["steps"])
    ]
    state = {
        "protocol_version": "1.0.0",
        "workflow_id": workflow["id"],
        "workflow_version": WORKFLOW_VERSION,
        "run_id": run_id,
        "status": "running",
        "current_step": steps[0]["id"],
        "steps": steps,
        "inputs": dict(inputs),
        "artifact_refs": [],
        "checkpoints": [],
        "approval": {
            "required": False,
            "request": None,
            "decision": None,
            "reviewer": None,
        },
        "failure_boundary": {
            "step_id": steps[0]["id"],
            "error_class": None,
            "message": None,
            "attempt": 1,
        },
    }
    validate_artifact("workflow-state", state)
    return state


class WorkflowRunner:
    def __init__(self, state_path: Path):
        self.state_path = Path(state_path)
        self.lock_path = self.state_path.with_suffix(self.state_path.suffix + ".lock")

    @classmethod
    def create(cls, state_path: Path, state: dict[str, Any]) -> "WorkflowRunner":
        runner = cls(state_path)
        validate_artifact("workflow-state", state)
        runner.state_path.parent.mkdir(parents=True, exist_ok=True)
        if runner.state_path.parent.is_symlink():
            raise ValueError("workflow state path parent is unsafe")
        with runner._lock():
            if runner.state_path.exists() or runner.state_path.is_symlink():
                raise ValueError("workflow state path already exists or is unsafe")
            runner._write(state)
        return runner

    def _write(self, state: dict[str, Any]) -> None:
        validate_artifact("workflow-state", state)
        descriptor, raw_temporary = tempfile.mkstemp(prefix=f".{self.state_path.name}.tmp-", dir=self.state_path.parent)
        temporary = Path(raw_temporary)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                stream.write(json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.state_path)
            directory_descriptor = os.open(
                self.state_path.parent,
                os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW,
            )
            try:
                os.fsync(directory_descriptor)
            finally:
                os.close(directory_descriptor)
        except BaseException:
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass
            raise

    def load(self) -> dict[str, Any]:
        state = load_bounded_json(
            self.state_path,
            max_bytes=4 * 1024 * 1024,
            field="workflow state",
        )
        if state.get("workflow_version") != WORKFLOW_VERSION:
            raise ValueError(
                f"incompatible workflow version: {state.get('workflow_version')!r}"
            )
        validate_artifact("workflow-state", state)
        for checkpoint in state["checkpoints"]:
            if checkpoint["checksum"] != _canonical_digest(_checkpoint_payload(checkpoint)):
                raise ValueError(
                    f"checkpoint checksum mismatch: {checkpoint['checkpoint_id']}"
                )
        return state

    @contextmanager
    def _lock(self) -> Iterator[None]:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(
            self.lock_path,
            os.O_CREAT | os.O_RDWR | os.O_CLOEXEC | os.O_NOFOLLOW,
            0o600,
        )
        try:
            metadata = os.fstat(descriptor)
            if not stat.S_ISREG(metadata.st_mode):
                raise ValueError("workflow lock must be a regular file")
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            yield
        finally:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
            os.close(descriptor)

    def _update(self, mutation: Callable[[dict[str, Any]], None]) -> dict[str, Any]:
        with self._lock():
            state = self.load()
            mutation(state)
            self._write(state)
            return copy.deepcopy(state)

    @staticmethod
    def _require_running(state: dict[str, Any]) -> None:
        if state["status"] in TERMINAL_STATES:
            raise ValueError(f"workflow is terminal: {state['status']}")
        if state["status"] != "running":
            raise ValueError(f"workflow is not running: {state['status']}")

    @staticmethod
    def _append_checkpoint(
        state: dict[str, Any],
        *,
        kind: str,
        step_id: str | None,
        artifact_refs: list[str],
    ) -> None:
        seed = f"{state['run_id']}\x1f{kind}\x1f{len(state['checkpoints'])}\x1f{step_id or ''}"
        checkpoint = {
            "checkpoint_id": f"cp-{hashlib.sha256(seed.encode('utf-8')).hexdigest()[:16]}",
            "kind": kind,
            "step_id": step_id,
            "state_status": state["status"],
            "artifact_refs": sorted(set(artifact_refs)),
            "artifact_digests": {},
            "checksum": "",
            "resumed": False,
        }
        checkpoint["checksum"] = _canonical_digest(_checkpoint_payload(checkpoint))
        state["checkpoints"].append(checkpoint)

    def complete_step(self, step_id: str, artifact_refs: list[str]) -> dict[str, Any]:
        def mutate(state: dict[str, Any]) -> None:
            self._require_running(state)
            if state["current_step"] != step_id:
                raise ValueError(f"step is not current: {step_id}")
            current = next(step for step in state["steps"] if step["id"] == step_id)
            current["status"] = "completed"
            state["artifact_refs"] = sorted(set([*state["artifact_refs"], *artifact_refs]))
            completed = {step["id"] for step in state["steps"] if step["status"] == "completed"}
            next_step = next(
                (
                    step
                    for step in state["steps"]
                    if step["status"] == "pending" and set(step["depends_on"]) <= completed
                ),
                None,
            )
            if next_step is None:
                state["status"] = "completed"
                state["current_step"] = None
                state["failure_boundary"]["step_id"] = None
            else:
                next_step["status"] = "running"
                state["current_step"] = next_step["id"]
                state["failure_boundary"] = {
                    "step_id": next_step["id"],
                    "error_class": None,
                    "message": None,
                    "attempt": next_step["attempt"],
                }
            self._append_checkpoint(
                state,
                kind="step",
                step_id=step_id,
                artifact_refs=artifact_refs,
            )

        return self._update(mutate)

    def wait_for_external(self, boundary: str) -> dict[str, Any]:
        if boundary not in {"publication", "observation"}:
            raise ValueError("external boundary must be publication or observation")

        def mutate(state: dict[str, Any]) -> None:
            self._require_running(state)
            state["status"] = f"awaiting_external_{boundary}"
            self._append_checkpoint(
                state,
                kind=f"external-{boundary}",
                step_id=state["current_step"],
                artifact_refs=[],
            )

        return self._update(mutate)

    def resume(self, checkpoint_id: str) -> dict[str, Any]:
        def mutate(state: dict[str, Any]) -> None:
            checkpoint = next(
                (item for item in state["checkpoints"] if item["checkpoint_id"] == checkpoint_id),
                None,
            )
            if checkpoint is None:
                raise ValueError(f"checkpoint does not exist: {checkpoint_id}")
            if checkpoint["resumed"]:
                raise ValueError(f"checkpoint already resumed: {checkpoint_id}")
            resumable_step = (
                state["status"] == "running"
                and checkpoint["kind"] == "step"
                and state["checkpoints"][-1]["checkpoint_id"] == checkpoint_id
            )
            if state["status"] in EXTERNAL_STATES:
                raise ValueError("external workflow boundaries require resume_external with validated evidence")
            if not resumable_step:
                raise ValueError(f"workflow cannot resume from {state['status']}")
            checkpoint["resumed"] = True

        return self._update(mutate)

    def resume_external(self, checkpoint_id: str, evidence_ref: str) -> dict[str, Any]:
        if (
            not isinstance(evidence_ref, str)
            or not evidence_ref
            or Path(evidence_ref).is_absolute()
            or ".." in Path(evidence_ref).parts
        ):
            raise ValueError("external evidence reference must be a safe relative path")
        evidence_path = self.state_path.parent / evidence_ref
        raw = read_bounded_regular_file(evidence_path, max_bytes=4 * 1024 * 1024, field="external workflow evidence")
        evidence = strict_json_loads(raw)
        if not isinstance(evidence, dict):
            raise ValueError("external workflow evidence must be a JSON object")
        evidence_digest = hashlib.sha256(raw).hexdigest()

        def mutate(state: dict[str, Any]) -> None:
            existing = next((item for item in state["checkpoints"] if item["checkpoint_id"] == checkpoint_id), None)
            if existing is not None and existing["resumed"]:
                raise ValueError(f"checkpoint already resumed: {checkpoint_id}")
            if state["status"] not in EXTERNAL_STATES:
                raise ValueError(f"workflow cannot resume externally from {state['status']}")
            checkpoint = existing
            required_kind = state["status"].removeprefix("awaiting_").replace("_", "-")
            if (
                checkpoint is None
                or checkpoint["resumed"]
                or state["checkpoints"][-1]["checkpoint_id"] != checkpoint_id
                or checkpoint["kind"] != required_kind
                or checkpoint["state_status"] != state["status"]
            ):
                raise ValueError("external workflow resume requires its latest boundary checkpoint")
            schema_name = "publication-receipt" if required_kind == "external-publication" else "visibility-report"
            validate_artifact(schema_name, evidence)
            if schema_name == "publication-receipt":
                semantic = {key: value for key, value in evidence.items() if key != "semantic_digest"}
            else:
                semantic = {
                    key: evidence[key]
                    for key in ("bundle_id", "panel_version", "query_panel", "metrics", "by_engine", "query_components", "gaps")
                }
            if evidence["semantic_digest"] != _canonical_digest(semantic):
                raise ValueError("external workflow evidence semantic digest mismatch")
            checkpoint["artifact_refs"] = [evidence_ref]
            checkpoint["artifact_digests"] = {evidence_ref: evidence_digest}
            checkpoint["checksum"] = _canonical_digest(_checkpoint_payload(checkpoint))
            checkpoint["resumed"] = True
            state["artifact_refs"] = sorted(set([*state["artifact_refs"], evidence_ref]))
            state["status"] = "running"

        return self._update(mutate)

    def request_approval(self, request: str) -> dict[str, Any]:
        if not isinstance(request, str) or not request.strip():
            raise ValueError("approval request must be non-blank")

        def mutate(state: dict[str, Any]) -> None:
            self._require_running(state)
            state["status"] = "awaiting_approval"
            state["approval"] = {
                "required": True,
                "request": request.strip(),
                "decision": "pending",
                "reviewer": None,
            }

        return self._update(mutate)

    def decide_approval(self, *, approved: bool, reviewer: str) -> dict[str, Any]:
        if not isinstance(reviewer, str) or not reviewer.strip():
            raise ValueError("approval reviewer must be non-blank")

        def mutate(state: dict[str, Any]) -> None:
            if state["status"] != "awaiting_approval" or state["approval"]["decision"] != "pending":
                raise ValueError("workflow is not awaiting approval")
            state["approval"]["decision"] = "approved" if approved else "rejected"
            state["approval"]["reviewer"] = reviewer.strip()
            state["status"] = "running" if approved else "aborted"
            if not approved:
                for step in state["steps"]:
                    if step["status"] == "running":
                        step["status"] = "aborted"

        return self._update(mutate)

    def fail(self, error_class: str, message: str) -> dict[str, Any]:
        if not error_class or not message:
            raise ValueError("failure class and message are required")

        def mutate(state: dict[str, Any]) -> None:
            self._require_running(state)
            step = next(item for item in state["steps"] if item["id"] == state["current_step"])
            step["status"] = "failed"
            state["status"] = "failed"
            state["failure_boundary"] = {
                "step_id": step["id"],
                "error_class": error_class,
                "message": message,
                "attempt": step["attempt"],
            }

        return self._update(mutate)

    def retry(self) -> dict[str, Any]:
        def mutate(state: dict[str, Any]) -> None:
            if state["status"] != "failed":
                raise ValueError("workflow retry requires failed status")
            step = next(item for item in state["steps"] if item["id"] == state["current_step"])
            step["attempt"] += 1
            step["status"] = "running"
            state["status"] = "running"
            state["failure_boundary"] = {
                "step_id": step["id"],
                "error_class": None,
                "message": None,
                "attempt": step["attempt"],
            }

        return self._update(mutate)

    def abort(self, reason: str) -> dict[str, Any]:
        if not reason:
            raise ValueError("abort reason is required")

        def mutate(state: dict[str, Any]) -> None:
            if state["status"] in TERMINAL_STATES:
                raise ValueError(f"workflow is terminal: {state['status']}")
            state["status"] = "aborted"
            for step in state["steps"]:
                if step["status"] in {"running", "failed"}:
                    step["status"] = "aborted"
            state["failure_boundary"] = {
                "step_id": state["current_step"],
                "error_class": "operator-abort",
                "message": reason,
                "attempt": state["failure_boundary"]["attempt"],
            }

        return self._update(mutate)
