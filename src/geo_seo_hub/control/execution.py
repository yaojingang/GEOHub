from __future__ import annotations

import hashlib
import fcntl
import json
import os
import selectors
import signal
import stat
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from ..validation import load_bounded_json, read_bounded_regular_file, strict_json_loads, validate_artifact
from .workflow import WorkflowRunner, create_workflow_state_from_plan, validate_task_plan_semantics


EXECUTORS = frozenset({"content", "diagnose", "discover", "knowledge", "measure", "strategy"})
MAX_EXECUTOR_CAPTURE_BYTES = 1024 * 1024
MAX_EXECUTOR_ARTIFACT_BYTES = 64 * 1024 * 1024
MAX_EXECUTOR_ARTIFACTS = 500


class NonRetryableExecutionError(ValueError):
    """Raised when retrying the same immutable plan and inputs cannot succeed."""


def load_task_plan(path: Path) -> dict[str, Any]:
    plan = load_bounded_json(Path(path), max_bytes=4 * 1024 * 1024, field="task plan")
    validate_artifact("task-plan", plan)
    semantic = {key: value for key, value in plan.items() if key != "plan_digest"}
    serialized = json.dumps(
        semantic,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    if plan["plan_digest"] != hashlib.sha256(serialized.encode("utf-8")).hexdigest():
        raise ValueError("task plan digest mismatch")
    validate_task_plan_semantics(plan)
    return plan


def load_runtime_inputs(path: Path, required_inputs: list[str]) -> dict[str, str]:
    input_file = Path(path)
    payload = load_bounded_json(input_file, max_bytes=1024 * 1024, field="workflow inputs")
    if not isinstance(payload, dict) or any(not isinstance(key, str) or not isinstance(value, str) for key, value in payload.items()):
        raise ValueError("workflow inputs must map artifact names to file paths")
    missing = sorted(set(required_inputs) - set(payload))
    if missing:
        raise ValueError(f"workflow inputs are missing required artifacts: {missing}")
    resolved: dict[str, str] = {}
    for name, raw_path in payload.items():
        candidate = Path(raw_path)
        if not candidate.is_absolute():
            candidate = input_file.parent / candidate
        read_bounded_regular_file(candidate, max_bytes=16 * 1024 * 1024, field=f"workflow input {name}")
        resolved[name] = str(candidate.resolve())
    return resolved


def _bounded_output_root(state_path: Path, output_root: Path) -> Path:
    state_parent = state_path.parent.resolve()
    candidate = output_root.resolve()
    if candidate != state_parent and state_parent not in candidate.parents:
        raise ValueError("workflow output must stay inside the workflow state directory")
    if output_root.is_symlink():
        raise ValueError("workflow output root cannot be a symlink")
    candidate.mkdir(parents=True, exist_ok=True)
    return candidate


def _relative_ref(state_path: Path, artifact: Path) -> str:
    try:
        return artifact.resolve().relative_to(state_path.parent.resolve()).as_posix()
    except ValueError as exc:
        raise ValueError("workflow artifact escaped the state directory") from exc


def _resolve_binding(state_path: Path, state: dict[str, Any], source: str) -> Path:
    source_kind, remainder = source.split(":", 1)
    if source_kind in {"request", "external"}:
        raw = state["inputs"].get(remainder)
        if not isinstance(raw, str):
            raise NonRetryableExecutionError(f"workflow input is unavailable: {remainder}")
        candidate = Path(raw)
        payload = read_bounded_regular_file(
            candidate,
            max_bytes=MAX_EXECUTOR_ARTIFACT_BYTES,
            field=f"workflow input {remainder}",
        )
        recorded_digest = state["input_digests"].get(remainder)
        if recorded_digest is None or hashlib.sha256(payload).hexdigest() != recorded_digest:
            raise NonRetryableExecutionError(
                f"workflow input digest changed: {remainder}"
            )
        return candidate
    if source_kind != "node" or ":" not in remainder:
        raise NonRetryableExecutionError(f"unsupported workflow binding source: {source}")
    node_id, artifact = remainder.split(":", 1)
    producer = next((item for item in state["steps"] if item["id"] == node_id), None)
    if producer is None or producer["status"] != "completed":
        raise NonRetryableExecutionError(f"workflow producer is incomplete: {node_id}")
    reference = producer["outputs"].get(artifact)
    if not isinstance(reference, str):
        raise NonRetryableExecutionError(f"workflow producer output is unavailable: {node_id}:{artifact}")
    candidate = state_path.parent / reference
    raw = read_bounded_regular_file(
        candidate,
        max_bytes=MAX_EXECUTOR_ARTIFACT_BYTES,
        field=f"workflow producer output {node_id}:{artifact}",
    )
    recorded_digest = next(
        (
            checkpoint["artifact_digests"].get(reference)
            for checkpoint in reversed(state["checkpoints"])
            if checkpoint["step_id"] == node_id and reference in checkpoint["artifact_digests"]
        ),
        None,
    )
    if recorded_digest is not None and hashlib.sha256(raw).hexdigest() != recorded_digest:
        raise NonRetryableExecutionError(
            f"workflow producer output digest changed: {node_id}:{artifact}"
        )
    return candidate


def _collect_outputs(state_path: Path, step: dict[str, Any], run_dir: Path) -> tuple[list[str], dict[str, str]]:
    state_parent = state_path.parent.resolve()
    resolved_run_dir = run_dir.resolve()
    if (
        run_dir.is_symlink()
        or (resolved_run_dir != state_parent and state_parent not in resolved_run_dir.parents)
        or not resolved_run_dir.is_dir()
    ):
        raise NonRetryableExecutionError("executor output directory is unavailable or outside the workflow boundary")
    run_dir = resolved_run_dir
    artifact_refs: list[str] = []
    observed_paths = 0
    for path in run_dir.rglob("*"):
        observed_paths += 1
        if observed_paths > MAX_EXECUTOR_ARTIFACTS * 4:
            raise NonRetryableExecutionError("executor output tree exceeds the bounded entry limit")
        metadata = path.lstat()
        if path.is_symlink():
            raise NonRetryableExecutionError("executor output contains a non-regular artifact")
        if stat.S_ISDIR(metadata.st_mode):
            continue
        if not stat.S_ISREG(metadata.st_mode):
            raise NonRetryableExecutionError("executor output contains a non-regular artifact")
        if metadata.st_size > MAX_EXECUTOR_ARTIFACT_BYTES:
            raise NonRetryableExecutionError("executor output contains an oversized artifact")
        artifact_refs.append(_relative_ref(state_path, path))
        if len(artifact_refs) > MAX_EXECUTOR_ARTIFACTS:
            raise NonRetryableExecutionError("executor emitted too many artifacts")
    outputs: dict[str, str] = {}
    suffixes = (".json", ".md", ".html", ".docx", ".pdf")
    for contract in step["expected_outputs"]:
        name = contract["artifact"]
        candidates = [run_dir / f"{name}{suffix}" for suffix in suffixes]
        path = next((item for item in candidates if item.is_file() and not item.is_symlink()), None)
        if path is None:
            if contract["required"]:
                raise NonRetryableExecutionError(f"executor omitted required artifact: {name}")
            continue
        reference = _relative_ref(state_path, path)
        outputs[name] = reference
    return sorted(set(artifact_refs)), outputs


@contextmanager
def _execution_lock(state_path: Path):
    lock_path = state_path.with_suffix(state_path.suffix + ".execute.lock")
    if lock_path.parent.is_symlink():
        raise ValueError("workflow execution lock parent is unsafe")
    descriptor = os.open(
        lock_path,
        os.O_CREAT | os.O_RDWR | os.O_CLOEXEC | os.O_NOFOLLOW,
        0o600,
    )
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise ValueError("workflow execution lock must be a regular file")
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


def _execute_skill(
    executor_name: str,
    input_path: Path,
    output_root: Path,
    timeout_seconds: int | None,
) -> dict[str, Any]:
    command = [
        sys.executable,
        "-m",
        "geo_seo_hub",
        executor_name,
        "--input",
        str(input_path),
        "--output",
        str(output_root),
    ]
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    streams = {
        process.stdout: bytearray(),
        process.stderr: bytearray(),
    }
    selector = selectors.DefaultSelector()
    for stream in streams:
        if stream is None:
            raise RuntimeError("executor capture pipe is unavailable")
        os.set_blocking(stream.fileno(), False)
        selector.register(stream, selectors.EVENT_READ)
    deadline = time.monotonic() + timeout_seconds if timeout_seconds is not None else None
    try:
        while selector.get_map():
            if deadline is not None and time.monotonic() >= deadline:
                raise TimeoutError(f"step exceeded declared timeout of {timeout_seconds} seconds")
            wait_seconds = 0.1 if deadline is None else max(0.0, min(0.1, deadline - time.monotonic()))
            events = selector.select(wait_seconds)
            for key, _mask in events:
                stream = key.fileobj
                chunk = os.read(stream.fileno(), 64 * 1024)
                if not chunk:
                    selector.unregister(stream)
                    stream.close()
                    continue
                captured = streams[stream]
                captured.extend(chunk)
                if sum(len(value) for value in streams.values()) > MAX_EXECUTOR_CAPTURE_BYTES:
                    raise NonRetryableExecutionError("executor output exceeded the bounded capture limit")
        remaining = None if deadline is None else max(0.0, deadline - time.monotonic())
        try:
            returncode = process.wait(timeout=remaining)
        except subprocess.TimeoutExpired as exc:
            raise TimeoutError(
                f"step exceeded declared timeout of {timeout_seconds} seconds"
            ) from exc
    except BaseException:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        if process.poll() is None:
            process.kill()
        process.wait()
        raise
    finally:
        selector.close()
        for stream in streams:
            if stream is not None and not stream.closed:
                stream.close()
    stdout = bytes(streams[process.stdout]).decode("utf-8", errors="replace")
    stderr = bytes(streams[process.stderr]).decode("utf-8", errors="replace")
    if returncode != 0:
        detail = stderr.strip() or stdout.strip() or f"exit code {returncode}"
        raise NonRetryableExecutionError(f"executor {executor_name} failed: {detail[:800]}")
    try:
        result = strict_json_loads(stdout)
    except ValueError as exc:
        raise NonRetryableExecutionError(
            f"executor {executor_name} returned invalid JSON"
        ) from exc
    if not isinstance(result, dict):
        raise NonRetryableExecutionError(f"executor {executor_name} returned a non-object result")
    return result


def start_workflow(
    plan_path: Path,
    state_path: Path,
    inputs_path: Path,
    output_root: Path,
    *,
    run_id: str | None = None,
) -> dict[str, Any]:
    plan = load_task_plan(plan_path)
    inputs = load_runtime_inputs(inputs_path, plan["required_inputs"])
    bounded_output = _bounded_output_root(Path(state_path), Path(output_root))
    inputs["runtime_output_root"] = str(bounded_output)
    effective_run_id = run_id or f"run-{plan['plan_id'].removeprefix('plan-')}-workflow"
    state = create_workflow_state_from_plan(plan, run_id=effective_run_id, inputs=inputs)
    WorkflowRunner.create(Path(state_path), state)
    return continue_workflow(Path(state_path))


def continue_workflow(state_path: Path) -> dict[str, Any]:
    with _execution_lock(Path(state_path)):
        return _continue_workflow_unlocked(Path(state_path))


def abort_workflow(state_path: Path, reason: str) -> dict[str, Any]:
    with _execution_lock(Path(state_path)):
        return WorkflowRunner(Path(state_path)).abort(reason)


def _continue_workflow_unlocked(state_path: Path) -> dict[str, Any]:
    runner = WorkflowRunner(Path(state_path))
    while True:
        state = runner.load()
        if state["status"] != "running":
            return state
        step = next(item for item in state["steps"] if item["id"] == state["current_step"])
        if step["kind"] != "skill":
            raise ValueError("running workflow state points to a non-Skill node")
        executor_name = step["executor"] or (step["skill_id"] or "").removeprefix("geo-")
        if executor_name not in EXECUTORS:
            return runner.fail("executor-unavailable", f"No local executor is registered for {step['skill_id']}")
        try:
            bindings = [
                _resolve_binding(Path(state_path), state, item["source"])
                for item in step["input_bindings"]
                if item["artifact"]
            ]
            if len(bindings) != 1:
                raise NonRetryableExecutionError(
                    f"Executor {executor_name} requires exactly one bound input artifact"
                )
            output_root = state["inputs"].get("runtime_output_root")
            if not isinstance(output_root, str):
                raise NonRetryableExecutionError("Workflow runtime output root is unavailable")
            bounded_output = _bounded_output_root(Path(state_path), Path(output_root))
            result = _execute_skill(
                executor_name,
                bindings[0],
                bounded_output,
                step["timeout_seconds"],
            )
            raw_run_dir = result.get("output")
            if not isinstance(raw_run_dir, str):
                raise NonRetryableExecutionError(
                    f"executor {executor_name} omitted its output directory"
                )
            run_dir = Path(raw_run_dir)
            artifact_refs, outputs = _collect_outputs(Path(state_path), step, run_dir)
            runner.complete_step(step["id"], artifact_refs, outputs)
        except Exception as exc:
            observed = runner.load()
            if observed["status"] != "running" or observed["current_step"] != step["id"]:
                return observed
            failed = runner.fail("execution-error", f"{type(exc).__name__}: {exc}"[:1000])
            current = next(item for item in failed["steps"] if item["id"] == failed["current_step"])
            if (
                isinstance(exc, TimeoutError)
                and current["idempotent"]
                and current["attempt"] < current["max_attempts"]
            ):
                runner.retry()
                continue
            return failed
