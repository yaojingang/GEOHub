from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from ..registry import load_registry
from ..validation import validate_artifact


PLAN_VERSION = "1.0.0"


def _digest(payload: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def _permission_profile(skill: dict[str, Any]) -> str:
    permissions = skill["permissions"]
    return "/".join(
        (
            permissions["filesystem"],
            permissions["network"],
            permissions["shell"],
            "approval" if permissions["approval_required"] else "no-approval",
        )
    )


def _skill_is_locally_executable(skill: dict[str, Any] | None) -> bool:
    return bool(
        skill is not None
        and skill["status"] == "active"
        and skill["entry"]
        and skill["execution"]["executor"]
        and skill["execution"]["executor"] != "route"
        and sum(artifact["required"] for artifact in skill["input_artifacts"]) == 1
    )


def _node_for_skill(
    skill: dict[str, Any],
    *,
    node_id: str,
    depends_on: list[str],
    available_outputs: list[tuple[str, dict[str, Any]]],
) -> tuple[dict[str, Any], set[str]]:
    bindings: list[dict[str, Any]] = []
    required_inputs: set[str] = set()
    for artifact in skill["input_artifacts"]:
        if not artifact["required"]:
            continue
        compatible = next(
            (
                (producer_id, output)
                for producer_id, output in reversed(available_outputs)
                if artifact["schema"] is not None and output["schema"] == artifact["schema"]
            ),
            None,
        )
        if compatible is None:
            source = f"request:{artifact['name']}"
            required_inputs.add(artifact["name"])
        else:
            producer_id, output = compatible
            source = f"node:{producer_id}:{output['name']}"
        bindings.append(
            {
                "artifact": artifact["name"],
                "schema": artifact["schema"],
                "source": source,
            }
        )
    outputs = [
        {
            "artifact": artifact["name"],
            "schema": artifact["schema"],
            "required": artifact["required"],
        }
        for artifact in skill["output_artifacts"]
    ]
    return (
        {
            "id": node_id,
            "kind": "skill",
            "skill_id": skill["id"],
            "depends_on": depends_on,
            "input_bindings": bindings,
            "expected_outputs": outputs,
            "permission_profile": _permission_profile(skill),
            "execution": dict(skill["execution"]),
            "requires_approval": bool(skill["permissions"]["approval_required"]),
            "gate_request": None,
            "evidence_schema": None,
        },
        required_inputs,
    )


def _compose_dynamic_nodes(
    skill_ids: list[str],
    skills: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], set[str]] | None:
    nodes: list[dict[str, Any]] = []
    available_outputs: list[tuple[str, dict[str, Any]]] = []
    required_inputs: set[str] = set()
    previous: str | None = None
    for index, skill_id in enumerate(skill_ids):
        skill = skills.get(skill_id)
        if not _skill_is_locally_executable(skill):
            return None
        node_id = f"dynamic-{index + 1}-{skill_id.removeprefix('geo-')}"
        node, node_inputs = _node_for_skill(
            skill,
            node_id=node_id,
            depends_on=[previous] if previous else [],
            available_outputs=available_outputs,
        )
        if index > 0 and all(binding["source"].startswith("request:") for binding in node["input_bindings"]):
            return None
        nodes.append(node)
        required_inputs.update(node_inputs)
        available_outputs.extend((node_id, output) for output in skill["output_artifacts"])
        previous = node_id
    return nodes, required_inputs


def _gate_node(definition: dict[str, Any]) -> dict[str, Any]:
    kind = definition["kind"]
    expected_outputs: list[dict[str, Any]] = []
    if kind.startswith("external-"):
        schema = definition["evidence_schema"]
        expected_outputs = [{"artifact": schema, "schema": schema, "required": True}]
    return {
        "id": definition["id"],
        "kind": kind,
        "skill_id": None,
        "depends_on": list(definition["depends_on"]),
        "input_bindings": [],
        "expected_outputs": expected_outputs,
        "permission_profile": "human-review" if kind == "approval" else "external-evidence/read-only",
        "execution": {
            "executor": None,
            "timeout_seconds": None,
            "max_attempts": 0,
            "idempotent": False,
        },
        "requires_approval": kind == "approval",
        "gate_request": definition.get("request"),
        "evidence_schema": definition.get("evidence_schema"),
    }


def compile_task_plan(
    request: str,
    route_result: dict[str, Any],
    registry: dict[str, Any] | None = None,
) -> dict[str, Any]:
    registry = registry or load_registry()
    skills = {item["id"]: item for item in registry["skills"]}
    workflows = {item["id"]: item for item in registry["workflows"]}
    decision = route_result["decision"]
    decision_type = decision["type"]
    nodes: list[dict[str, Any]] = []
    required_inputs: set[str] = set()
    workflow_id = (route_result.get("workflow") or {}).get("id")
    status = "needs-clarification"

    if decision_type == "single_skill":
        skill = skills.get(route_result.get("skill_id"))
        if _skill_is_locally_executable(skill):
            node, required_inputs = _node_for_skill(
                skill,
                node_id=skill["id"].removeprefix("geo-") or "geo",
                depends_on=[],
                available_outputs=[],
            )
            nodes = [node]
            status = "ready"
        elif skill is not None and skill["status"] != "active":
            status = "unavailable"
            required_inputs.update(route_result.get("required_inputs") or [])
    elif decision_type == "workflow":
        workflow = workflows.get(workflow_id)
        definitions = (
            workflow.get("orchestration", {}).get("nodes", workflow["steps"])
            if workflow is not None
            else []
        )
        executable = workflow is not None and workflow["status"] == "active" and all(
            step.get("kind", "skill") != "skill"
            or _skill_is_locally_executable(skills.get(step["skill_id"]))
            for step in definitions
        )
        if not executable:
            status = "unavailable"
            required_inputs.update(route_result.get("required_inputs") or [])
            definitions = []
        outputs_by_node: dict[str, list[dict[str, Any]]] = {}
        ancestors_by_node: dict[str, set[str]] = {}
        for step in definitions:
            ancestors = set(step["depends_on"])
            for dependency in step["depends_on"]:
                ancestors.update(ancestors_by_node[dependency])
            ancestors_by_node[step["id"]] = ancestors
            available_outputs = [
                (producer_id, output)
                for producer_id, producer_outputs in outputs_by_node.items()
                if producer_id in ancestors
                for output in producer_outputs
            ]
            if step.get("kind", "skill") == "skill":
                skill = skills[step["skill_id"]]
                node, node_inputs = _node_for_skill(
                    skill,
                    node_id=step["id"],
                    depends_on=list(step["depends_on"]),
                    available_outputs=available_outputs,
                )
                outputs_by_node[step["id"]] = list(skill["output_artifacts"])
            else:
                node = _gate_node(step)
                node_inputs = set()
                outputs_by_node[step["id"]] = [
                    {
                        "name": output["artifact"],
                        "schema": output["schema"],
                        "required": output["required"],
                    }
                    for output in node["expected_outputs"]
                ]
            nodes.append(node)
            required_inputs.update(node_inputs)
        if executable:
            status = "ready"
    elif decision_type == "clarify" and len(decision["matched_intents"]) > 1:
        dynamic = _compose_dynamic_nodes(decision["matched_intents"], skills)
        if dynamic is not None:
            nodes, required_inputs = dynamic
            status = "ready"
    elif decision_type == "unavailable":
        status = "unavailable"
        required_inputs.update(route_result.get("required_inputs") or [])

    seed = {
        "request": request,
        "registry_version": registry["registry_version"],
        "decision": decision,
        "workflow_id": workflow_id,
        "nodes": nodes,
    }
    plan = {
        "protocol_version": "1.0.0",
        "plan_version": PLAN_VERSION,
        "plan_id": f"plan-{_digest(seed)[:16]}",
        "registry_version": registry["registry_version"],
        "request": request,
        "status": status,
        "decision": {
            "type": decision_type,
            "score": decision.get("score"),
            "threshold_version": decision["threshold_version"],
            "matched_intents": list(decision.get("matched_intents") or []),
            "alternatives": list(decision.get("alternatives") or []),
        },
        "workflow_id": workflow_id,
        "nodes": nodes,
        "required_inputs": sorted(required_inputs),
        "uncovered_intents": list(decision.get("uncovered_intents") or []),
        "plan_digest": "",
    }
    plan["plan_digest"] = _digest({key: value for key, value in plan.items() if key != "plan_digest"})
    validate_artifact("task-plan", plan)
    return plan


def write_task_plan(path: Path, plan: dict[str, Any]) -> Path:
    validate_artifact("task-plan", plan)
    semantic = {key: value for key, value in plan.items() if key != "plan_digest"}
    if plan["plan_digest"] != _digest(semantic):
        raise ValueError("task plan digest mismatch")
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.parent.is_symlink() or target.exists() or target.is_symlink():
        raise ValueError("task plan output already exists or is unsafe")
    descriptor, raw_temporary = tempfile.mkstemp(prefix=f".{target.name}.tmp-", dir=target.parent)
    temporary = Path(raw_temporary)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(json.dumps(plan, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
        directory_descriptor = os.open(
            target.parent,
            os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW,
        )
        try:
            os.fsync(directory_descriptor)
        finally:
            os.close(directory_descriptor)
        return target
    except BaseException:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
        raise
