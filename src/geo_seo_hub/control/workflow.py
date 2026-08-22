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


WORKFLOW_VERSION = "2.0.0"
LEGACY_WORKFLOW_VERSION = "1.0.0"
TERMINAL_STATES = {"completed", "aborted"}
EXTERNAL_STATES = {
    "awaiting_external_publication",
    "awaiting_external_observation",
}
GATE_KINDS = {"approval", "external-publication", "external-observation"}


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


def _validate_checkpoint_checksums(state: dict[str, Any]) -> None:
    for checkpoint in state["checkpoints"]:
        if checkpoint["checksum"] != _canonical_digest(_checkpoint_payload(checkpoint)):
            raise ValueError(f"checkpoint checksum mismatch: {checkpoint['checkpoint_id']}")


def _validate_external_checkpoint_artifacts(state_path: Path, state: dict[str, Any]) -> None:
    for checkpoint in state["checkpoints"]:
        if checkpoint["kind"] not in {"external-publication", "external-observation"}:
            continue
        if not checkpoint["resumed"]:
            continue
        if len(checkpoint["artifact_refs"]) != 1 or set(checkpoint["artifact_refs"]) != set(
            checkpoint["artifact_digests"]
        ):
            raise ValueError(
                f"external checkpoint evidence is incomplete: {checkpoint['checkpoint_id']}"
            )
        reference = checkpoint["artifact_refs"][0]
        raw = read_bounded_regular_file(
            state_path.parent / reference,
            max_bytes=4 * 1024 * 1024,
            field="external workflow evidence",
        )
        if hashlib.sha256(raw).hexdigest() != checkpoint["artifact_digests"][reference]:
            raise ValueError(
                f"external workflow evidence digest changed: {reference}"
            )


def _safe_artifact_ref(value: str) -> bool:
    return bool(value) and not Path(value).is_absolute() and ".." not in Path(value).parts


def _validate_ordered_nodes(nodes: list[dict[str, Any]]) -> None:
    observed: set[str] = set()
    for node in nodes:
        if not isinstance(node, dict):
            raise ValueError("workflow node must be an object")
        node_id = node.get("id")
        depends_on = node.get("depends_on")
        if (
            not isinstance(node_id, str)
            or not node_id
            or not isinstance(depends_on, list)
            or any(not isinstance(item, str) or not item for item in depends_on)
            or node_id in observed
            or any(item not in observed for item in depends_on)
        ):
            raise ValueError("workflow nodes must form a stable ordered DAG")
        observed.add(node_id)


def validate_task_plan_semantics(plan: dict[str, Any]) -> None:
    """Validate cross-field execution invariants that JSON Schema cannot express."""
    nodes = plan["nodes"]
    if plan["status"] != "ready":
        if nodes:
            raise ValueError("non-ready task plan must not contain executable nodes")
        return
    if not nodes:
        raise ValueError("ready task plan must contain executable nodes")
    _validate_ordered_nodes(nodes)
    outputs_by_node: dict[str, dict[str, dict[str, Any]]] = {}
    ancestors_by_node: dict[str, set[str]] = {}
    request_inputs: set[str] = set()
    for node in nodes:
        ancestors = set(node["depends_on"])
        for dependency in node["depends_on"]:
            ancestors.update(ancestors_by_node[dependency])
        ancestors_by_node[node["id"]] = ancestors

        output_names = [item["artifact"] for item in node["expected_outputs"]]
        if len(output_names) != len(set(output_names)):
            raise ValueError(f"task plan node has duplicate outputs: {node['id']}")
        outputs_by_node[node["id"]] = {
            item["artifact"]: item for item in node["expected_outputs"]
        }

        binding_names = [item["artifact"] for item in node["input_bindings"]]
        if len(binding_names) != len(set(binding_names)):
            raise ValueError(f"task plan node has duplicate input bindings: {node['id']}")
        for binding in node["input_bindings"]:
            source_kind, remainder = binding["source"].split(":", 1)
            if source_kind in {"request", "external"}:
                request_inputs.add(remainder)
                continue
            producer_id, artifact = remainder.split(":", 1)
            if producer_id not in ancestors:
                raise ValueError(
                    f"task plan binding does not reference a dependency ancestor: {node['id']}"
                )
            producer_output = outputs_by_node.get(producer_id, {}).get(artifact)
            if producer_output is None or producer_output["schema"] != binding["schema"]:
                raise ValueError(
                    f"task plan binding does not match a declared producer output: {node['id']}"
                )

        execution = node["execution"]
        if node["kind"] == "skill":
            if (
                node["skill_id"] is None
                or execution["executor"] is None
                or execution["timeout_seconds"] is None
                or execution["max_attempts"] < 1
                or len(node["input_bindings"]) != 1
                or node["requires_approval"]
                or node["gate_request"] is not None
                or node["evidence_schema"] is not None
            ):
                raise ValueError(f"task plan Skill node execution contract is invalid: {node['id']}")
        else:
            if (
                node["skill_id"] is not None
                or execution != {
                    "executor": None,
                    "timeout_seconds": None,
                    "max_attempts": 0,
                    "idempotent": False,
                }
                or node["input_bindings"]
            ):
                raise ValueError(f"task plan gate execution contract is invalid: {node['id']}")
            if node["kind"] == "approval":
                if (
                    not node["requires_approval"]
                    or node["gate_request"] is None
                    or node["evidence_schema"] is not None
                    or node["expected_outputs"]
                ):
                    raise ValueError(f"task plan approval gate is invalid: {node['id']}")
            else:
                expected_schema = (
                    "publication-receipt"
                    if node["kind"] == "external-publication"
                    else "engine-observation-bundle"
                )
                if (
                    node["requires_approval"]
                    or node["gate_request"] is not None
                    or node["evidence_schema"] != expected_schema
                    or node["expected_outputs"]
                    != [{"artifact": expected_schema, "schema": expected_schema, "required": True}]
                ):
                    raise ValueError(f"task plan external gate is invalid: {node['id']}")

    if request_inputs != set(plan["required_inputs"]):
        raise ValueError("task plan required_inputs do not match request bindings")


def _validate_state_semantics(state: dict[str, Any]) -> None:
    _validate_ordered_nodes(state["steps"])
    steps = {step["id"]: step for step in state["steps"]}
    checkpoint_ids = [item["checkpoint_id"] for item in state["checkpoints"]]
    if len(checkpoint_ids) != len(set(checkpoint_ids)):
        raise ValueError("workflow checkpoint IDs must be unique")
    for checkpoint in state["checkpoints"]:
        if checkpoint["step_id"] is not None and checkpoint["step_id"] not in steps:
            raise ValueError("workflow checkpoint references an unknown step")
        if not set(checkpoint["artifact_digests"]) <= set(checkpoint["artifact_refs"]):
            raise ValueError("workflow checkpoint digests do not match artifact references")
    bound_inputs = {
        binding["source"].split(":", 1)[1]
        for step in state["steps"]
        for binding in step["input_bindings"]
        if binding["source"].split(":", 1)[0] in {"request", "external"}
    }
    if set(state["input_digests"]) != bound_inputs:
        raise ValueError("workflow input digests do not match request bindings")
    for step in state["steps"]:
        expected_key = hashlib.sha256(
            f"{state['run_id']}\x1f{state['plan_digest']}\x1f{step['id']}".encode("utf-8")
        ).hexdigest()
        if step["idempotency_key"] != expected_key:
            raise ValueError(f"workflow step idempotency key mismatch: {step['id']}")
        if step["status"] == "completed" and any(
            steps[dependency]["status"] != "completed" for dependency in step["depends_on"]
        ):
            raise ValueError(f"workflow completed step has incomplete dependencies: {step['id']}")
        allowed_outputs = {item["artifact"] for item in step["expected_outputs"]}
        if set(step["outputs"]) - allowed_outputs:
            raise ValueError(f"workflow step contains undeclared outputs: {step['id']}")
        if step["status"] == "completed":
            missing = {
                item["artifact"] for item in step["expected_outputs"] if item["required"]
            } - set(step["outputs"])
            if missing:
                raise ValueError(f"workflow completed step is missing outputs: {step['id']}")

    current_id = state["current_step"]
    if state["status"] == "completed":
        if current_id is not None or any(step["status"] != "completed" for step in state["steps"]):
            raise ValueError("completed workflow state is inconsistent")
        return
    if current_id is None or current_id not in steps:
        raise ValueError("non-completed workflow state requires a current step")
    current = steps[current_id]
    if any(
        step["status"] in {"running", "waiting", "failed"}
        for step_id, step in steps.items()
        if step_id != current_id
    ):
        raise ValueError("workflow has more than one active step")
    allowed_current_statuses = {
        "running": {"running"},
        "failed": {"failed"},
        "awaiting_approval": {"running", "waiting"},
        "awaiting_external_publication": {"running", "waiting"},
        "awaiting_external_observation": {"running", "waiting"},
        "aborted": {"aborted"},
    }
    if current["status"] not in allowed_current_statuses[state["status"]]:
        raise ValueError("workflow status and current step status are inconsistent")
    waiting_kind = {
        "awaiting_approval": "approval",
        "awaiting_external_publication": "external-publication",
        "awaiting_external_observation": "external-observation",
    }.get(state["status"])
    if current["status"] == "waiting" and current["kind"] != waiting_kind:
        raise ValueError("workflow waiting status does not match its gate kind")


def _validate_workflow_definition(workflow: dict[str, Any]) -> None:
    allowed_fields = {
        "id",
        "status",
        "required_skills",
        "steps",
        "orchestration",
        "required_inputs",
        "closest_v0_artifact",
    }
    required_fields = {"id", "status", "required_skills", "steps"}
    if (
        not isinstance(workflow, dict)
        or not required_fields <= set(workflow)
        or set(workflow) - allowed_fields
    ):
        raise ValueError("workflow definition fields are invalid")
    if workflow["status"] != "active":
        raise ValueError(f"workflow is not active: {workflow['status']}")
    if not isinstance(workflow["id"], str) or not workflow["id"].strip():
        raise ValueError("workflow ID is invalid")
    required_skills = workflow["required_skills"]
    if not isinstance(required_skills, list) or any(not isinstance(item, str) or not item for item in required_skills):
        raise ValueError("workflow required_skills are invalid")
    steps = workflow["steps"]
    if not isinstance(steps, list) or not steps:
        raise ValueError("workflow must contain at least one step")
    _validate_ordered_nodes(steps)
    if any(set(step) != {"id", "skill_id", "depends_on"} for step in steps):
        raise ValueError("workflow step fields are invalid")
    if [step["skill_id"] for step in steps] != required_skills:
        raise ValueError("workflow required_skills must match step order")

    orchestration = workflow.get("orchestration")
    if orchestration is None:
        return
    if not isinstance(orchestration, dict) or set(orchestration) != {"nodes"}:
        raise ValueError("workflow orchestration fields are invalid")
    nodes = orchestration["nodes"]
    if not isinstance(nodes, list) or not nodes:
        raise ValueError("workflow orchestration must contain nodes")
    _validate_ordered_nodes(nodes)
    skill_ids: list[str] = []
    for node in nodes:
        kind = node.get("kind")
        allowed = {"id", "kind", "depends_on"}
        if kind == "skill":
            allowed.add("skill_id")
            skill_ids.append(node.get("skill_id"))
        elif kind == "approval":
            allowed.add("request")
        elif kind in {"external-publication", "external-observation"}:
            allowed.add("evidence_schema")
        else:
            raise ValueError(f"unsupported workflow node kind: {kind}")
        if set(node) != allowed:
            raise ValueError("workflow orchestration node fields are invalid")
    if skill_ids != required_skills:
        raise ValueError("orchestration skill nodes must match required_skills")


def _step_from_node(node: dict[str, Any], *, run_id: str, plan_digest: str) -> dict[str, Any]:
    execution = node.get("execution") or {}
    kind = node.get("kind", "skill")
    max_attempts = execution.get("max_attempts", 3 if kind == "skill" else 0)
    return {
        "id": node["id"],
        "kind": kind,
        "skill_id": node.get("skill_id"),
        "depends_on": list(node["depends_on"]),
        "status": "pending",
        "attempt": 1 if kind == "skill" else 0,
        "max_attempts": max_attempts,
        "executor": execution.get("executor"),
        "timeout_seconds": execution.get("timeout_seconds"),
        "idempotent": bool(execution.get("idempotent", kind == "skill")),
        "input_bindings": copy.deepcopy(node.get("input_bindings") or []),
        "expected_outputs": copy.deepcopy(node.get("expected_outputs") or []),
        "outputs": {},
        "idempotency_key": hashlib.sha256(
            f"{run_id}\x1f{plan_digest}\x1f{node['id']}".encode("utf-8")
        ).hexdigest(),
        "gate_request": node.get("gate_request") or node.get("request"),
        "evidence_schema": node.get("evidence_schema"),
    }


def _activate_step(state: dict[str, Any], step: dict[str, Any]) -> None:
    state["current_step"] = step["id"]
    if step["kind"] == "skill":
        step["status"] = "running"
        state["status"] = "running"
        state["failure_boundary"] = {
            "step_id": step["id"],
            "error_class": None,
            "message": None,
            "attempt": step["attempt"],
        }
        return
    step["status"] = "waiting"
    if step["kind"] == "approval":
        state["status"] = "awaiting_approval"
        state["approval"] = {
            "required": True,
            "request": step["gate_request"] or "Approve workflow continuation.",
            "decision": "pending",
            "reviewer": None,
        }
        return
    boundary = step["kind"].removeprefix("external-")
    state["status"] = f"awaiting_external_{boundary}"
    _append_checkpoint(
        state,
        kind=step["kind"],
        step_id=step["id"],
        artifact_refs=[],
    )


def _advance(state: dict[str, Any]) -> None:
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
        state["failure_boundary"] = {
            "step_id": None,
            "error_class": None,
            "message": None,
            "attempt": 0,
        }
        return
    _activate_step(state, next_step)


def _append_checkpoint(
    state: dict[str, Any],
    *,
    kind: str,
    step_id: str | None,
    artifact_refs: list[str],
    artifact_digests: dict[str, str] | None = None,
) -> None:
    seed = f"{state['run_id']}\x1f{kind}\x1f{len(state['checkpoints'])}\x1f{step_id or ''}"
    checkpoint = {
        "checkpoint_id": f"cp-{hashlib.sha256(seed.encode('utf-8')).hexdigest()[:16]}",
        "kind": kind,
        "step_id": step_id,
        "state_status": state["status"],
        "artifact_refs": sorted(set(artifact_refs)),
        "artifact_digests": dict(artifact_digests or {}),
        "checksum": "",
        "resumed": False,
    }
    checkpoint["checksum"] = _canonical_digest(_checkpoint_payload(checkpoint))
    state["checkpoints"].append(checkpoint)


def create_workflow_state_from_plan(
    plan: dict[str, Any],
    *,
    run_id: str,
    inputs: dict[str, str | int | float | bool | None],
) -> dict[str, Any]:
    validate_artifact("task-plan", plan)
    validate_task_plan_semantics(plan)
    semantic = {key: value for key, value in plan.items() if key != "plan_digest"}
    if plan["plan_digest"] != _canonical_digest(semantic):
        raise ValueError("task plan digest mismatch")
    if plan["status"] != "ready" or not plan["nodes"]:
        raise ValueError(f"task plan is not executable: {plan['status']}")
    missing_inputs = sorted(set(plan["required_inputs"]) - set(inputs))
    if missing_inputs:
        raise ValueError(f"task plan inputs are missing required artifacts: {missing_inputs}")
    input_digests: dict[str, str] = {}
    for name in plan["required_inputs"]:
        raw_path = inputs[name]
        if not isinstance(raw_path, str):
            raise ValueError(f"task plan input path must be a string: {name}")
        raw = read_bounded_regular_file(
            Path(raw_path),
            max_bytes=64 * 1024 * 1024,
            field=f"workflow input {name}",
        )
        input_digests[name] = hashlib.sha256(raw).hexdigest()
    steps = [
        _step_from_node(node, run_id=run_id, plan_digest=plan["plan_digest"])
        for node in plan["nodes"]
    ]
    state = {
        "protocol_version": "1.0.0",
        "workflow_id": plan["workflow_id"] or f"single-{steps[0]['skill_id']}",
        "workflow_version": WORKFLOW_VERSION,
        "plan_id": plan["plan_id"],
        "plan_digest": plan["plan_digest"],
        "run_id": run_id,
        "status": "running",
        "current_step": None,
        "steps": steps,
        "inputs": dict(inputs),
        "input_digests": input_digests,
        "artifact_refs": [],
        "checkpoints": [],
        "approval": {"required": False, "request": None, "decision": None, "reviewer": None},
        "failure_boundary": {"step_id": None, "error_class": None, "message": None, "attempt": 0},
    }
    _advance(state)
    validate_artifact("workflow-state", state)
    _validate_state_semantics(state)
    return state


def create_workflow_state(
    workflow: dict[str, Any],
    *,
    run_id: str,
    inputs: dict[str, str | int | float | bool | None],
) -> dict[str, Any]:
    """Create v2 state from a registry recipe; TaskPlan execution uses the companion constructor."""
    _validate_workflow_definition(workflow)
    definitions = workflow.get("orchestration", {}).get("nodes", workflow["steps"])
    plan_seed = {"workflow": workflow, "inputs": inputs}
    plan_digest = _canonical_digest(plan_seed)
    plan_id = f"plan-{plan_digest[:16]}"
    steps = [_step_from_node(node, run_id=run_id, plan_digest=plan_digest) for node in definitions]
    state = {
        "protocol_version": "1.0.0",
        "workflow_id": workflow["id"],
        "workflow_version": WORKFLOW_VERSION,
        "plan_id": plan_id,
        "plan_digest": plan_digest,
        "run_id": run_id,
        "status": "running",
        "current_step": None,
        "steps": steps,
        "inputs": dict(inputs),
        "input_digests": {},
        "artifact_refs": [],
        "checkpoints": [],
        "approval": {"required": False, "request": None, "decision": None, "reviewer": None},
        "failure_boundary": {"step_id": None, "error_class": None, "message": None, "attempt": 0},
    }
    _advance(state)
    validate_artifact("workflow-state", state)
    _validate_state_semantics(state)
    return state


def migrate_v1_state(state: dict[str, Any]) -> dict[str, Any]:
    required = {
        "protocol_version",
        "workflow_id",
        "workflow_version",
        "run_id",
        "status",
        "current_step",
        "steps",
        "inputs",
        "artifact_refs",
        "checkpoints",
        "approval",
        "failure_boundary",
    }
    if not isinstance(state, dict) or set(state) != required or state.get("workflow_version") != LEGACY_WORKFLOW_VERSION:
        raise ValueError("legacy workflow state fields are invalid")
    if (
        state.get("protocol_version") != "1.0.0"
        or not isinstance(state.get("steps"), list)
        or not state["steps"]
        or not isinstance(state.get("checkpoints"), list)
        or not isinstance(state.get("inputs"), dict)
        or not isinstance(state.get("artifact_refs"), list)
    ):
        raise ValueError("legacy workflow state values are invalid")
    for checkpoint in state["checkpoints"]:
        checkpoint_fields = {
            "checkpoint_id",
            "kind",
            "step_id",
            "state_status",
            "artifact_refs",
            "artifact_digests",
            "checksum",
            "resumed",
        }
        if not isinstance(checkpoint, dict) or set(checkpoint) != checkpoint_fields:
            raise ValueError("legacy workflow checkpoint fields are invalid")
        if checkpoint.get("checksum") != _canonical_digest(_checkpoint_payload(checkpoint)):
            raise ValueError(f"checkpoint checksum mismatch: {checkpoint.get('checkpoint_id')}")
    seed = {"legacy_state": state}
    plan_digest = _canonical_digest(seed)
    migrated = copy.deepcopy(state)
    migrated["workflow_version"] = WORKFLOW_VERSION
    migrated["plan_id"] = f"plan-{plan_digest[:16]}"
    migrated["plan_digest"] = plan_digest
    migrated["input_digests"] = {}
    migrated_steps = []
    for legacy in state["steps"]:
        if (
            not isinstance(legacy, dict)
            or set(legacy) != {"id", "skill_id", "depends_on", "status", "attempt"}
            or not isinstance(legacy.get("id"), str)
            or not isinstance(legacy.get("skill_id"), str)
            or not isinstance(legacy.get("depends_on"), list)
            or isinstance(legacy.get("attempt"), bool)
            or not isinstance(legacy.get("attempt"), int)
            or legacy["attempt"] < 1
        ):
            raise ValueError("legacy workflow step fields are invalid")
        attempt = legacy["attempt"]
        migrated_steps.append(
            {
                "id": legacy["id"],
                "kind": "skill",
                "skill_id": legacy["skill_id"],
                "depends_on": list(legacy["depends_on"]),
                "status": legacy["status"],
                "attempt": attempt,
                "max_attempts": max(3, attempt),
                "executor": legacy["skill_id"].removeprefix("geo-"),
                "timeout_seconds": None,
                "idempotent": True,
                "input_bindings": [],
                "expected_outputs": [],
                "outputs": {},
                "idempotency_key": hashlib.sha256(
                    f"{state['run_id']}\x1f{plan_digest}\x1f{legacy['id']}".encode("utf-8")
                ).hexdigest(),
                "gate_request": None,
                "evidence_schema": None,
            }
        )
    migrated["steps"] = migrated_steps
    validate_artifact("workflow-state", migrated)
    _validate_state_semantics(migrated)
    return migrated


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
        _validate_state_semantics(state)
        _validate_external_checkpoint_artifacts(self.state_path, state)
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
        state = load_bounded_json(self.state_path, max_bytes=4 * 1024 * 1024, field="workflow state")
        if state.get("workflow_version") != WORKFLOW_VERSION:
            suffix = "; run workflow migrate first" if state.get("workflow_version") == LEGACY_WORKFLOW_VERSION else ""
            raise ValueError(f"incompatible workflow version: {state.get('workflow_version')!r}{suffix}")
        validate_artifact("workflow-state", state)
        _validate_checkpoint_checksums(state)
        _validate_state_semantics(state)
        _validate_external_checkpoint_artifacts(self.state_path, state)
        return state

    @contextmanager
    def _lock(self) -> Iterator[None]:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        if self.state_path.parent.is_symlink():
            raise ValueError("workflow lock path parent is unsafe")
        descriptor = os.open(self.lock_path, os.O_CREAT | os.O_RDWR | os.O_CLOEXEC | os.O_NOFOLLOW, 0o600)
        try:
            metadata = os.fstat(descriptor)
            if not stat.S_ISREG(metadata.st_mode):
                raise ValueError("workflow lock must be a regular file")
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            yield
        finally:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
            os.close(descriptor)

    def migrate(self) -> dict[str, Any]:
        with self._lock():
            raw = load_bounded_json(self.state_path, max_bytes=4 * 1024 * 1024, field="workflow state")
            if raw.get("workflow_version") == WORKFLOW_VERSION:
                validate_artifact("workflow-state", raw)
                _validate_checkpoint_checksums(raw)
                _validate_state_semantics(raw)
                _validate_external_checkpoint_artifacts(self.state_path, raw)
                return raw
            migrated = migrate_v1_state(raw)
            backup = self.state_path.with_suffix(self.state_path.suffix + ".v1.backup")
            if backup.exists() or backup.is_symlink():
                raise ValueError("legacy workflow backup already exists")
            payload = json.dumps(raw, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False).encode("utf-8") + b"\n"
            descriptor = os.open(backup, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_CLOEXEC | os.O_NOFOLLOW, 0o600)
            try:
                offset = 0
                while offset < len(payload):
                    written = os.write(descriptor, payload[offset:])
                    if written <= 0:
                        raise OSError("unable to write legacy workflow backup")
                    offset += written
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
            directory_descriptor = os.open(
                self.state_path.parent,
                os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW,
            )
            try:
                os.fsync(directory_descriptor)
            finally:
                os.close(directory_descriptor)
            self._write(migrated)
            return copy.deepcopy(migrated)

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

    def complete_step(
        self,
        step_id: str,
        artifact_refs: list[str],
        outputs: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        if len(artifact_refs) > 500:
            raise ValueError("workflow emitted too many artifact references")
        if any(not _safe_artifact_ref(item) for item in artifact_refs):
            raise ValueError("workflow artifact references must be safe relative paths")
        outputs = dict(outputs or {})
        if any(not _safe_artifact_ref(item) for item in outputs.values()):
            raise ValueError("workflow output references must be safe relative paths")
        if not set(outputs.values()) <= set(artifact_refs):
            raise ValueError("workflow outputs must reference declared artifacts")

        def mutate(state: dict[str, Any]) -> None:
            self._require_running(state)
            if state["current_step"] != step_id:
                raise ValueError(f"step is not current: {step_id}")
            current = next(step for step in state["steps"] if step["id"] == step_id)
            if current["kind"] != "skill":
                raise ValueError("only a Skill step can be completed directly")
            allowed_outputs = {item["artifact"] for item in current["expected_outputs"]}
            if set(outputs) - allowed_outputs:
                raise ValueError("workflow output map contains undeclared artifacts")
            missing_outputs = {
                item["artifact"]
                for item in current["expected_outputs"]
                if item["required"]
            } - set(outputs)
            if missing_outputs:
                raise ValueError(f"workflow output map is missing required artifacts: {sorted(missing_outputs)}")
            artifact_digests: dict[str, str] = {}
            for reference in artifact_refs:
                artifact_path = self.state_path.parent / reference
                if not current["expected_outputs"] and not (
                    artifact_path.exists() or artifact_path.is_symlink()
                ):
                    continue
                raw = read_bounded_regular_file(
                    artifact_path,
                    max_bytes=64 * 1024 * 1024,
                    field="workflow artifact",
                )
                artifact_digests[reference] = hashlib.sha256(raw).hexdigest()
            current["status"] = "completed"
            current["outputs"] = outputs
            state["artifact_refs"] = sorted(set([*state["artifact_refs"], *artifact_refs]))
            _append_checkpoint(
                state,
                kind="step",
                step_id=step_id,
                artifact_refs=artifact_refs,
                artifact_digests=artifact_digests,
            )
            _advance(state)

        return self._update(mutate)

    def wait_for_external(self, boundary: str) -> dict[str, Any]:
        if boundary not in {"publication", "observation"}:
            raise ValueError("external boundary must be publication or observation")

        def mutate(state: dict[str, Any]) -> None:
            self._require_running(state)
            state["status"] = f"awaiting_external_{boundary}"
            _append_checkpoint(state, kind=f"external-{boundary}", step_id=state["current_step"], artifact_refs=[])

        return self._update(mutate)

    def resume(self, checkpoint_id: str) -> dict[str, Any]:
        def mutate(state: dict[str, Any]) -> None:
            checkpoint = next((item for item in state["checkpoints"] if item["checkpoint_id"] == checkpoint_id), None)
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
        if not isinstance(evidence_ref, str) or not _safe_artifact_ref(evidence_ref):
            raise ValueError("external evidence reference must be a safe relative path")

        def mutate(state: dict[str, Any]) -> None:
            existing = next((item for item in state["checkpoints"] if item["checkpoint_id"] == checkpoint_id), None)
            if existing is not None and existing["resumed"]:
                raise ValueError(f"checkpoint already resumed: {checkpoint_id}")
            if state["status"] not in EXTERNAL_STATES:
                raise ValueError(f"workflow cannot resume externally from {state['status']}")
            required_kind = state["status"].removeprefix("awaiting_").replace("_", "-")
            if (
                existing is None
                or existing["resumed"]
                or state["checkpoints"][-1]["checkpoint_id"] != checkpoint_id
                or existing["kind"] != required_kind
                or existing["state_status"] != state["status"]
            ):
                raise ValueError("external workflow resume requires its latest boundary checkpoint")
            current = next(item for item in state["steps"] if item["id"] == state["current_step"])
            schema_name = current["evidence_schema"] if current["kind"] == required_kind else None
            schema_name = schema_name or ("publication-receipt" if required_kind == "external-publication" else "engine-observation-bundle")
            evidence_path = self.state_path.parent / evidence_ref
            raw = read_bounded_regular_file(
                evidence_path,
                max_bytes=4 * 1024 * 1024,
                field="external workflow evidence",
            )
            evidence = strict_json_loads(raw)
            if not isinstance(evidence, dict):
                raise ValueError("external workflow evidence must be a JSON object")
            evidence_digest = hashlib.sha256(raw).hexdigest()
            validate_artifact(schema_name, evidence)
            if schema_name == "publication-receipt":
                semantic = {key: value for key, value in evidence.items() if key != "semantic_digest"}
                if evidence["semantic_digest"] != _canonical_digest(semantic):
                    raise ValueError("external workflow evidence semantic digest mismatch")
            existing["artifact_refs"] = [evidence_ref]
            existing["artifact_digests"] = {evidence_ref: evidence_digest}
            existing["checksum"] = _canonical_digest(_checkpoint_payload(existing))
            existing["resumed"] = True
            state["artifact_refs"] = sorted(set([*state["artifact_refs"], evidence_ref]))
            if current["kind"] == required_kind:
                current["status"] = "completed"
                current["outputs"] = {schema_name: evidence_ref}
                _advance(state)
            else:
                state["status"] = "running"

        return self._update(mutate)

    def request_approval(self, request: str) -> dict[str, Any]:
        if not isinstance(request, str) or not request.strip():
            raise ValueError("approval request must be non-blank")

        def mutate(state: dict[str, Any]) -> None:
            self._require_running(state)
            state["status"] = "awaiting_approval"
            state["approval"] = {"required": True, "request": request.strip(), "decision": "pending", "reviewer": None}

        return self._update(mutate)

    def decide_approval(self, *, approved: bool, reviewer: str) -> dict[str, Any]:
        if not isinstance(reviewer, str) or not reviewer.strip():
            raise ValueError("approval reviewer must be non-blank")

        def mutate(state: dict[str, Any]) -> None:
            if state["status"] != "awaiting_approval" or state["approval"]["decision"] != "pending":
                raise ValueError("workflow is not awaiting approval")
            state["approval"]["decision"] = "approved" if approved else "rejected"
            state["approval"]["reviewer"] = reviewer.strip()
            current = next(item for item in state["steps"] if item["id"] == state["current_step"])
            if not approved:
                state["status"] = "aborted"
                current["status"] = "aborted"
                state["failure_boundary"] = {
                    "step_id": current["id"],
                    "error_class": "approval-rejected",
                    "message": "Workflow approval was rejected.",
                    "attempt": current["attempt"],
                }
            elif current["kind"] == "approval":
                current["status"] = "completed"
                _advance(state)
            else:
                state["status"] = "running"

        return self._update(mutate)

    def fail(self, error_class: str, message: str) -> dict[str, Any]:
        if not error_class or not message:
            raise ValueError("failure class and message are required")

        def mutate(state: dict[str, Any]) -> None:
            self._require_running(state)
            step = next(item for item in state["steps"] if item["id"] == state["current_step"])
            if step["kind"] != "skill":
                raise ValueError("only a Skill step can fail")
            step["status"] = "failed"
            state["status"] = "failed"
            state["failure_boundary"] = {
                "step_id": step["id"],
                "error_class": error_class,
                "message": message[:1000],
                "attempt": step["attempt"],
            }

        return self._update(mutate)

    def retry(self) -> dict[str, Any]:
        def mutate(state: dict[str, Any]) -> None:
            if state["status"] != "failed":
                raise ValueError("workflow retry requires failed status")
            step = next(item for item in state["steps"] if item["id"] == state["current_step"])
            if not step["idempotent"]:
                raise ValueError("workflow step is not declared idempotent")
            if step["attempt"] >= step["max_attempts"]:
                raise ValueError("workflow step exhausted its retry budget")
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
                if step["status"] in {"running", "waiting", "failed"}:
                    step["status"] = "aborted"
            state["failure_boundary"] = {
                "step_id": state["current_step"],
                "error_class": "operator-abort",
                "message": reason[:1000],
                "attempt": state["failure_boundary"]["attempt"],
            }

        return self._update(mutate)
