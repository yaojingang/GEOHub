from __future__ import annotations

import hashlib
import json
import math
import os
import platform
import secrets
import stat
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

import yaml

from ..validation import (
    load_bounded_json,
    read_bounded_regular_file,
    strict_json_loads,
    validate_artifact,
)
from .metrics import score_output


MAX_SUITE_BYTES = 64 * 1024
MAX_EVAL_TASKS = 25
MAX_RUNNER_OUTPUT_BYTES = 4 * 1024 * 1024
DEFAULT_MAX_EVAL_COST_USD = 25.0


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _write_json(path: Path, value: Any) -> None:
    serialized = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n"
    descriptor, raw_temporary = tempfile.mkstemp(prefix=f".{path.name}.tmp-", dir=path.parent)
    temporary = Path(raw_temporary)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(serialized)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except BaseException:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
        raise


def _load_suite(suite_path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    try:
        suite = yaml.safe_load(
            read_bounded_regular_file(suite_path, max_bytes=MAX_SUITE_BYTES, field="evaluation suite").decode("utf-8")
        )
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as exc:
        raise ValueError(f"Unable to load evaluation suite: {exc}") from exc
    if not isinstance(suite, dict) or not isinstance(suite.get("tasks"), list):
        raise ValueError("Evaluation suite must contain a tasks list")
    if not 1 <= len(suite["tasks"]) <= MAX_EVAL_TASKS:
        raise ValueError(f"Evaluation suite must contain between 1 and {MAX_EVAL_TASKS} tasks")
    input_root_value = suite.get("input_root", ".")
    if not isinstance(input_root_value, str) or not input_root_value or Path(input_root_value).is_absolute():
        raise ValueError("Evaluation suite input_root must be a relative path")
    input_root = (suite_path.parent / input_root_value).resolve()
    if input_root.is_symlink() or not input_root.is_dir():
        raise ValueError("Evaluation suite input_root must resolve to a regular directory")
    tasks: list[dict[str, Any]] = []
    for relative in suite["tasks"]:
        if not isinstance(relative, str) or Path(relative).is_absolute() or ".." in Path(relative).parts:
            raise ValueError("Evaluation task path is unsafe")
        task_path = suite_path.parent / relative
        task = load_bounded_json(task_path, max_bytes=256 * 1024, field="evaluation task")
        validate_artifact("eval-task", task)
        task["_input_payloads"] = _validate_task_inputs(task, input_root)
        tasks.append(task)
    if len({task["task_id"] for task in tasks}) != len(tasks):
        raise ValueError("Evaluation suite task IDs must be unique")
    return suite, tasks


def _load_private_holdout() -> list[dict[str, Any]]:
    configured = os.environ.get("GEOHUB_PRIVATE_EVAL_ROOT", "").strip()
    if not configured:
        return []
    root = Path(configured)
    try:
        mode = root.lstat().st_mode
    except OSError as exc:
        raise ValueError("GEOHUB_PRIVATE_EVAL_ROOT is unavailable") from exc
    if root.is_symlink() or not stat.S_ISDIR(mode):
        raise ValueError("GEOHUB_PRIVATE_EVAL_ROOT must be a regular directory")
    tasks = []
    for path in sorted(root.glob("*.json")):
        if path.is_symlink() or not path.is_file():
            raise ValueError("Private holdout entries must be regular JSON files")
        task = load_bounded_json(path, max_bytes=256 * 1024, field="private holdout task")
        validate_artifact("eval-task", task)
        task["_input_payloads"] = _validate_task_inputs(task, root)
        tasks.append(task)
        if len(tasks) > MAX_EVAL_TASKS:
            raise ValueError(f"Private holdout cannot exceed {MAX_EVAL_TASKS} tasks")
    if not tasks:
        raise ValueError("GEOHUB_PRIVATE_EVAL_ROOT contains no JSON tasks")
    return tasks


def _validate_task_inputs(task: dict[str, Any], base: Path) -> list[dict[str, str]]:
    payloads = []
    total_bytes = 0
    for relative in task["input_files"]:
        raw = read_bounded_regular_file(
            base / relative,
            max_bytes=task["limits"]["max_input_bytes"],
            field=f"evaluation input_files entry for {task['task_id']}",
        )
        total_bytes += len(raw)
        if total_bytes > task["limits"]["max_input_bytes"]:
            raise ValueError(f"evaluation inputs exceed task limit for {task['task_id']}")
        try:
            content = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError("evaluation inputs must be UTF-8 text") from exc
        payloads.append({"path": relative, "sha256": hashlib.sha256(raw).hexdigest(), "content": content})
    return payloads


def _public_task(task: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in task.items() if not key.startswith("_")}


def _sanitized_environment(python_path: Path | None = None) -> dict[str, str]:
    environment = {
        "PATH": os.environ.get("PATH", os.defpath),
        "LANG": os.environ.get("LANG", "C.UTF-8"),
        "LC_ALL": os.environ.get("LC_ALL", "C.UTF-8"),
        "PYTHONNOUSERSITE": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PIP_CONFIG_FILE": os.devnull,
        "PIP_DISABLE_PIP_VERSION_CHECK": "1",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_TERMINAL_PROMPT": "0",
    }
    if python_path is not None:
        environment["PYTHONPATH"] = str(python_path)
    for name in ("SYSTEMROOT", "WINDIR", "TMPDIR", "TEMP", "TMP"):
        if os.environ.get(name):
            environment[name] = os.environ[name]
    return environment


class EvalRunner(Protocol):
    def run(self, task: dict[str, Any], variant: str) -> dict[str, Any]: ...


class RecordedFixtureRunner:
    def run(self, task: dict[str, Any], variant: str) -> dict[str, Any]:
        return {
            "output": task["variants"][variant]["output"],
            "execution_kind": "recorded_fixture",
            "provider": None,
            "model": None,
            "usage": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
            "cost_usd": 0.0,
        }


class CommandRunner:
    def __init__(
        self,
        command: list[str],
        *,
        timeout_seconds: int = 120,
        environment: dict[str, str] | None = None,
    ):
        if not command or not all(isinstance(part, str) and part for part in command):
            raise ValueError("Runner command must be a non-empty JSON string list")
        self.command = command
        self.timeout_seconds = timeout_seconds
        self.environment = environment

    def run(self, task: dict[str, Any], variant: str) -> dict[str, Any]:
        request = {"protocol_version": "1.0.0", "task": task, "variant": variant}
        try:
            with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as stdout, tempfile.TemporaryFile(mode="w+", encoding="utf-8") as stderr:
                completed = subprocess.run(
                    self.command,
                    input=json.dumps(request, ensure_ascii=False, allow_nan=False),
                    stdout=stdout,
                    stderr=stderr,
                    text=True,
                    timeout=self.timeout_seconds,
                    check=False,
                    env=self.environment,
                )
                stdout_size = stdout.tell()
                stderr_size = stderr.tell()
                if stdout_size > MAX_RUNNER_OUTPUT_BYTES or stderr_size > MAX_RUNNER_OUTPUT_BYTES:
                    raise ValueError(f"Evaluation runner output exceeds {MAX_RUNNER_OUTPUT_BYTES} bytes")
                stdout.seek(0)
                stderr.seek(0)
                stdout_text = stdout.read()
                stderr_text = stderr.read()
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ValueError(f"Evaluation runner failed to execute: {exc}") from exc
        if completed.returncode != 0:
            detail = stderr_text.strip()[:1000]
            raise ValueError(f"Evaluation runner exited with {completed.returncode}: {detail}")
        try:
            response = strict_json_loads(stdout_text)
        except ValueError as exc:
            raise ValueError(f"Evaluation runner returned invalid JSON: {exc}") from exc
        return _normalize_runner_response(response, expected_kind="command")


class OpenAIProviderRunner:
    def __init__(self, api_key: str, model: str, *, input_usd_per_1m: float, output_usd_per_1m: float, timeout_seconds: int = 120):
        self.api_key = api_key
        self.model = model
        self.input_usd_per_1m = input_usd_per_1m
        self.output_usd_per_1m = output_usd_per_1m
        self.timeout_seconds = timeout_seconds

    @staticmethod
    def _instruction(variant: str) -> str:
        if variant == "baseline":
            return "Answer the user request directly as JSON."
        return (
            "Follow the GEOHub task contract and rubric. Return one JSON object with the requested "
            "answer, artifacts, claims, evidence status, and boundaries when applicable."
        )

    @staticmethod
    def _user_content(task: dict[str, Any]) -> str:
        return json.dumps(
            {"prompt": task["prompt"], "approved_inputs": task.get("_input_payloads", [])},
            ensure_ascii=False,
            sort_keys=True,
            allow_nan=False,
        )

    def estimate_max_cost(self, task: dict[str, Any], variant: str) -> float:
        input_upper_bound = len((self._instruction(variant) + self._user_content(task)).encode("utf-8"))
        return (
            input_upper_bound * self.input_usd_per_1m
            + task["limits"]["max_output_tokens"] * self.output_usd_per_1m
        ) / 1_000_000

    def run(self, task: dict[str, Any], variant: str) -> dict[str, Any]:
        instruction = self._instruction(variant)
        payload = {
            "model": self.model,
            "input": [
                {"role": "developer", "content": instruction},
                {"role": "user", "content": self._user_content(task)},
            ],
            "max_output_tokens": task["limits"]["max_output_tokens"],
        }
        request = urllib.request.Request(
            "https://api.openai.com/v1/responses",
            data=json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8"),
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                raw = response.read(4 * 1024 * 1024 + 1)
        except (OSError, urllib.error.URLError) as exc:
            raise ValueError(f"Provider evaluation request failed: {exc}") from exc
        if len(raw) > 4 * 1024 * 1024:
            raise ValueError("Provider evaluation response exceeds 4194304 bytes")
        try:
            provider_result = strict_json_loads(raw)
        except ValueError as exc:
            raise ValueError(f"Provider evaluation returned invalid JSON: {exc}") from exc
        output_text = provider_result.get("output_text")
        if not isinstance(output_text, str):
            text_parts = []
            for output_item in provider_result.get("output", []):
                if not isinstance(output_item, dict):
                    continue
                for content_item in output_item.get("content", []):
                    if (
                        isinstance(content_item, dict)
                        and content_item.get("type") == "output_text"
                        and isinstance(content_item.get("text"), str)
                    ):
                        text_parts.append(content_item["text"])
            output_text = "\n".join(text_parts) if text_parts else None
        if not isinstance(output_text, str):
            raise ValueError("Provider evaluation response is missing output_text")
        try:
            parsed_output = strict_json_loads(output_text)
        except ValueError:
            parsed_output = {"answer": output_text}
        if not isinstance(parsed_output, dict):
            parsed_output = {"answer": output_text}
        usage = provider_result.get("usage") or {}
        if int(usage.get("output_tokens", 0)) > task["limits"]["max_output_tokens"]:
            raise ValueError("Provider reported output usage above the task limit")
        result = {
            "output": parsed_output,
            "execution_kind": "model",
            "provider": "openai",
            "model": self.model,
            "usage": {
                "input_tokens": int(usage.get("input_tokens", 0)),
                "output_tokens": int(usage.get("output_tokens", 0)),
                "total_tokens": int(usage.get("total_tokens", 0)),
            },
            "cost_usd": round(
                (
                    int(usage.get("input_tokens", 0)) * self.input_usd_per_1m
                    + int(usage.get("output_tokens", 0)) * self.output_usd_per_1m
                )
                / 1_000_000,
                8,
            ),
        }
        return _normalize_runner_response(result, expected_kind="model")


def _normalize_runner_response(response: Any, *, expected_kind: str) -> dict[str, Any]:
    if not isinstance(response, dict) or not isinstance(response.get("output"), dict):
        raise ValueError("Evaluation runner response must contain an output object")
    execution_kind = response.get("execution_kind", expected_kind)
    if execution_kind not in {"recorded_fixture", "command", "model"}:
        raise ValueError("Evaluation runner returned an invalid execution_kind")
    provider = response.get("provider")
    model = response.get("model")
    if execution_kind == "model" and not (
        isinstance(provider, str) and provider.strip() and isinstance(model, str) and model.strip()
    ):
        execution_kind = "command"
        provider = None
        model = None
    usage = response.get("usage") or {}
    if any(isinstance(usage.get(name, 0), bool) for name in ("input_tokens", "output_tokens", "total_tokens")):
        raise ValueError("Evaluation usage values must be integers")
    normalized_usage = {name: int(usage.get(name, 0)) for name in ("input_tokens", "output_tokens", "total_tokens")}
    if min(normalized_usage.values()) < 0:
        raise ValueError("Evaluation usage values must be non-negative")
    cost_usd = float(response.get("cost_usd", 0.0))
    if not math.isfinite(cost_usd) or cost_usd < 0:
        raise ValueError("Evaluation cost must be non-negative")
    return {
        "output": response["output"],
        "execution_kind": execution_kind,
        "provider": provider,
        "model": model,
        "usage": normalized_usage,
        "cost_usd": cost_usd,
    }


def _missing_environment(label: str) -> dict[str, Any]:
    return {
        "label": label,
        "status": "missing-evidence",
        "wheel_sha256": None,
        "python_version": None,
        "platform": None,
        "dependency_digest": None,
    }


def _prepare_wheel_environment(
    label: str,
    wheel_path: Path,
) -> tuple[dict[str, Any], Path, tempfile.TemporaryDirectory[str], dict[str, str]]:
    if wheel_path.suffix != ".whl":
        raise ValueError(f"{label} wheel must use the .whl extension")
    wheel_bytes = read_bounded_regular_file(
        wheel_path,
        max_bytes=256 * 1024 * 1024,
        field=f"{label} wheel",
    )
    wheel_sha256 = hashlib.sha256(wheel_bytes).hexdigest()
    temporary = tempfile.TemporaryDirectory(prefix=f"geohub-{label}-wheel-")
    environment_root = Path(temporary.name) / "site-packages"
    try:
        environment_root.mkdir()
        python_path = Path(sys.executable)
        install_environment = _sanitized_environment()
        install = subprocess.run(
            [
                str(python_path),
                "-m",
                "pip",
                "install",
                "--no-deps",
                "--disable-pip-version-check",
                "--no-index",
                "--target",
                str(environment_root),
                str(wheel_path),
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=120,
            env=install_environment,
        )
        if install.returncode != 0:
            raise ValueError(f"Unable to install {label} wheel: {install.stderr.strip()[:1000]}")
        isolated_environment = _sanitized_environment(environment_root)
        probe = subprocess.run(
            [str(python_path), "-c", "import geo_seo_hub; print(geo_seo_hub.__file__)"],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
            cwd=temporary.name,
            env=isolated_environment,
        )
        imported_path = Path(probe.stdout.strip()).resolve() if probe.stdout.strip() else None
        if (
            probe.returncode != 0
            or imported_path is None
            or environment_root.resolve() not in imported_path.parents
        ):
            raise ValueError(f"Unable to import {label} wheel after installation")
        digest = hashlib.sha256()
        files = sorted(path for path in environment_root.rglob("*") if path.is_file() and not path.is_symlink())
        if not files:
            raise ValueError(f"Unable to inspect {label} wheel environment")
        for path in files:
            relative = path.relative_to(environment_root).as_posix()
            digest.update(relative.encode("utf-8"))
            digest.update(b"\0")
            digest.update(path.read_bytes())
            digest.update(b"\0")
        dependency_digest = digest.hexdigest()
        environment = {
            "label": label,
            "status": "verified",
            "wheel_sha256": wheel_sha256,
            "python_version": sys.version.split()[0],
            "platform": platform.platform(),
            "dependency_digest": dependency_digest,
        }
        return environment, python_path, temporary, isolated_environment
    except Exception:
        temporary.cleanup()
        raise


def _build_blind_pairs(
    suite_id: str,
    runs_by_task: dict[str, list[dict[str, dict[str, Any]]]],
    pair_repeats: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    pack_pairs = []
    key_pairs = []
    for task_id, comparisons in runs_by_task.items():
        for repeat in range(pair_repeats):
            variants = comparisons[repeat % len(comparisons)]
            with_skill_is_a = bool(secrets.randbits(1))
            pair_id = f"{task_id}-pair-{repeat + 1:02d}"
            baseline_output = variants["baseline"]["output"]
            with_skill_output = variants["with_skill"]["output"]
            pack_pairs.append(
                {
                    "pair_id": pair_id,
                    "task_id": task_id,
                    "variant_a": with_skill_output if with_skill_is_a else baseline_output,
                    "variant_b": baseline_output if with_skill_is_a else with_skill_output,
                    "rubric": variants["with_skill"]["rubric"],
                }
            )
            key_pairs.append(
                {
                    "pair_id": pair_id,
                    "task_id": task_id,
                    "with_skill_variant": "A" if with_skill_is_a else "B",
                }
            )
    return (
        {"protocol_version": "1.0.0", "suite_id": suite_id, "pairs": pack_pairs},
        {"protocol_version": "1.0.0", "suite_id": suite_id, "pairs": key_pairs},
    )


def _environment_number(name: str, *, default: float | None = None, allow_zero: bool = False) -> float:
    raw = os.environ.get(name, "").strip()
    if not raw and default is not None:
        return default
    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be a finite number") from exc
    if not math.isfinite(value) or value < 0 or (value == 0 and not allow_zero):
        raise ValueError(f"{name} must be {'non-negative' if allow_zero else 'positive'}")
    return value


def _private_provider_approval(private_tasks: list[dict[str, Any]]) -> str | None:
    if not private_tasks:
        return None
    consent = os.environ.get("GEOHUB_PRIVATE_PROVIDER_CONSENT", "").strip()
    classification = os.environ.get("GEOHUB_PRIVATE_DATA_CLASSIFICATION", "").strip()
    approved_provider = os.environ.get("GEOHUB_PRIVATE_APPROVED_PROVIDER", "").strip().casefold()
    if consent != "1" or not classification or approved_provider != "openai":
        raise ValueError(
            "Provider mode excludes private holdouts unless GEOHUB_PRIVATE_PROVIDER_CONSENT=1, "
            "GEOHUB_PRIVATE_DATA_CLASSIFICATION is set, and GEOHUB_PRIVATE_APPROVED_PROVIDER=openai"
        )
    return hashlib.sha256(f"{classification}\x1f{approved_provider}\x1f{len(private_tasks)}".encode("utf-8")).hexdigest()


def run_quality_lab(
    suite_path: Path,
    output: Path,
    *,
    execution_mode: str = "deterministic",
    runner_command_json: str | None = None,
    baseline_wheel: Path | None = None,
    candidate_wheel: Path | None = None,
) -> dict[str, Any]:
    runner_pairs: list[tuple[EvalRunner, EvalRunner]]
    temporary_environments: list[tempfile.TemporaryDirectory[str]] = []
    baseline_environment = _missing_environment("baseline")
    candidate_environment = _missing_environment("candidate")
    provider_max_cost: float | None = None
    provider_estimated_max_cost: float | None = None
    private_provider_approval_digest: str | None = None
    if execution_mode == "deterministic":
        runner = RecordedFixtureRunner()
        runner_pairs = [(runner, runner)]
    elif execution_mode == "command":
        if not runner_command_json:
            raise ValueError("--runner-command-json is required for command mode")
        command = strict_json_loads(runner_command_json)
        if not isinstance(command, list):
            raise ValueError("--runner-command-json must be a JSON string list")
        if baseline_wheel is None or candidate_wheel is None:
            raise ValueError("command mode requires --baseline-wheel and --candidate-wheel")
        baseline_environment, baseline_python, baseline_temporary, baseline_process_environment = _prepare_wheel_environment(
            "baseline", baseline_wheel
        )
        temporary_environments.append(baseline_temporary)
        try:
            candidate_environment, candidate_python, candidate_temporary, candidate_process_environment = _prepare_wheel_environment(
                "candidate", candidate_wheel
            )
        except Exception:
            for temporary in temporary_environments:
                temporary.cleanup()
            raise
        temporary_environments.append(candidate_temporary)
        baseline_command = [str(baseline_python) if part == "{python}" else part for part in command]
        candidate_command = [str(candidate_python) if part == "{python}" else part for part in command]
        runner_pairs = [
            (
                CommandRunner(baseline_command, environment=baseline_process_environment),
                CommandRunner(candidate_command, environment=candidate_process_environment),
            )
        ]
    elif execution_mode == "provider":
        api_key = os.environ.get("OPENAI_API_KEY", "").strip()
        if not api_key:
            raise ValueError("OPENAI_API_KEY is required for provider mode")
        model_a = os.environ.get("GEOHUB_GENERATOR_MODEL_A", "").strip()
        model_b = os.environ.get("GEOHUB_GENERATOR_MODEL_B", "").strip()
        if not model_a or not model_b:
            raise ValueError("GEOHUB_GENERATOR_MODEL_A and GEOHUB_GENERATOR_MODEL_B are required for provider mode")
        if model_a == model_b:
            raise ValueError("Provider mode requires two distinct generator models")
        runner_a = OpenAIProviderRunner(
            api_key,
            model_a,
            input_usd_per_1m=_environment_number("GEOHUB_MODEL_A_INPUT_USD_PER_1M", allow_zero=True),
            output_usd_per_1m=_environment_number("GEOHUB_MODEL_A_OUTPUT_USD_PER_1M", allow_zero=True),
        )
        runner_b = OpenAIProviderRunner(
            api_key,
            model_b,
            input_usd_per_1m=_environment_number("GEOHUB_MODEL_B_INPUT_USD_PER_1M", allow_zero=True),
            output_usd_per_1m=_environment_number("GEOHUB_MODEL_B_OUTPUT_USD_PER_1M", allow_zero=True),
        )
        provider_max_cost = _environment_number("GEOHUB_MAX_EVAL_COST_USD", default=DEFAULT_MAX_EVAL_COST_USD)
        if provider_max_cost > DEFAULT_MAX_EVAL_COST_USD and not os.environ.get("GEOHUB_EVAL_BUDGET_APPROVAL", "").strip():
            raise ValueError("An explicit GEOHUB_EVAL_BUDGET_APPROVAL is required above the default $25 budget")
        runner_pairs = [(runner_a, runner_a), (runner_b, runner_b)]
    else:
        raise ValueError(f"Unsupported execution mode: {execution_mode}")

    if (
        baseline_environment["wheel_sha256"] is not None
        and baseline_environment["wheel_sha256"] == candidate_environment["wheel_sha256"]
    ):
        raise ValueError("Baseline and candidate wheels must have distinct digests")
    suite, public_tasks = _load_suite(suite_path)
    private_tasks = _load_private_holdout()
    tasks = [*public_tasks, *private_tasks]
    if len(tasks) > MAX_EVAL_TASKS:
        raise ValueError(f"Combined public and private evaluation tasks cannot exceed {MAX_EVAL_TASKS}")
    if len({task["task_id"] for task in tasks}) != len(tasks):
        raise ValueError("Public and private evaluation task IDs must be unique")
    private_task_ids = {task["task_id"] for task in private_tasks}
    if execution_mode == "provider":
        private_provider_approval_digest = _private_provider_approval(private_tasks)
        provider_estimated_max_cost = math.fsum(
            runner.estimate_max_cost(task, variant)
            for task in tasks
            for baseline_runner, candidate_runner in runner_pairs
            for variant, runner in (("baseline", baseline_runner), ("with_skill", candidate_runner))
            if isinstance(runner, OpenAIProviderRunner)
        )
        if provider_max_cost is None or provider_estimated_max_cost > provider_max_cost:
            raise ValueError(
                f"Provider evaluation preflight estimate ${provider_estimated_max_cost:.6f} exceeds budget ${provider_max_cost:.6f}"
            )
    if output.exists() and any(output.iterdir()):
        raise ValueError(f"Output directory must be empty: {output}")
    output.mkdir(parents=True, exist_ok=True)
    suite_id = suite.get("suite_id", "quality-public-v1")
    pair_repeats = suite.get("pair_repeats", 4)
    if not isinstance(pair_repeats, int) or pair_repeats < 1 or pair_repeats > 20:
        raise ValueError("pair_repeats must be an integer between 1 and 20")

    runs = []
    runs_by_task: dict[str, list[dict[str, dict[str, Any]]]] = {}
    for task in tasks:
        comparisons = []
        for baseline_runner, candidate_runner in runner_pairs:
            variants: dict[str, dict[str, Any]] = {}
            for variant in ("baseline", "with_skill"):
                runner = baseline_runner if variant == "baseline" else candidate_runner
                started = time.monotonic()
                runner_result = runner.run(task, variant)
                latency_ms = max(0, round((time.monotonic() - started) * 1000))
                metrics = score_output(task, runner_result["output"])
                public_output = runner_result["output"]
                if task["task_id"] in private_task_ids:
                    output_digest = hashlib.sha256(
                        json.dumps(public_output, ensure_ascii=False, sort_keys=True, allow_nan=False).encode("utf-8")
                    ).hexdigest()
                    public_output = {"redacted": True, "semantic_digest": output_digest}
                run = {
                    "task_id": task["task_id"],
                    "variant": variant,
                    "execution_kind": runner_result["execution_kind"],
                    "provider": runner_result["provider"],
                    "model": runner_result["model"],
                    "output": public_output,
                    "metrics": metrics,
                    "latency_ms": latency_ms,
                    "usage": {**runner_result["usage"], "estimated": False},
                    "cost_usd": runner_result["cost_usd"],
                    "rubric": "[private rubric redacted]" if task["task_id"] in private_task_ids else task["rubric"],
                }
                runs.append(run)
                variants[variant] = run
                if provider_max_cost is not None and math.fsum(item["cost_usd"] for item in runs) > provider_max_cost:
                    raise ValueError("Provider evaluation actual cost exceeded the configured budget")
            comparisons.append(variants)
        runs_by_task[task["task_id"]] = comparisons

    baseline_runs = [run for run in runs if run["variant"] == "baseline"]
    with_skill_runs = [run for run in runs if run["variant"] == "with_skill"]
    baseline_rate = sum(run["metrics"]["passed"] for run in baseline_runs) / len(baseline_runs)
    with_skill_rate = sum(run["metrics"]["passed"] for run in with_skill_runs) / len(with_skill_runs)
    fabricated = sum(run["metrics"]["fabricated_citations"] for run in with_skill_runs)
    citation_support = sum(run["metrics"]["citation_support"] for run in with_skill_runs) / len(with_skill_runs)
    semantic_payload = {
        "suite_id": suite_id,
        "tasks": [task["task_id"] for task in tasks],
        "runs": [{key: run[key] for key in ("task_id", "variant", "output", "metrics")} for run in runs],
    }
    semantic_digest = hashlib.sha256(
        json.dumps(semantic_payload, sort_keys=True, ensure_ascii=False, allow_nan=False).encode("utf-8")
    ).hexdigest()

    pair_count = len(public_tasks) * pair_repeats
    result = {
        "protocol_version": "1.0.0",
        "suite_id": suite_id,
        "created_at": _utc_now(),
        "execution_mode": execution_mode,
        "environments": {
            "baseline": baseline_environment,
            "candidate": candidate_environment,
        },
        "budget": {
            "max_cost_usd": provider_max_cost,
            "estimated_max_cost_usd": round(provider_estimated_max_cost, 8) if provider_estimated_max_cost is not None else None,
            "actual_cost_usd": round(math.fsum(run["cost_usd"] for run in runs), 8),
            "planned_calls": len(tasks) * len(runner_pairs) * 2,
            "private_provider_approval_digest": private_provider_approval_digest,
        },
        "runs": runs,
        "summary": {
            "case_count": len(tasks),
            "private_holdout_case_count": len(private_tasks),
            "pair_count": pair_count,
            "baseline_pass_rate": baseline_rate,
            "with_skill_pass_rate": with_skill_rate,
            "absolute_delta": with_skill_rate - baseline_rate,
            "citation_support": citation_support,
            "fabricated_citations": fabricated,
            "semantic_digest": semantic_digest,
            "failure_taxonomy": {
                "route": 0,
                "contract": sum(not run["metrics"]["passed"] for run in with_skill_runs),
                "evidence": fabricated,
                "factuality": 0,
                "relevance": 0,
                "style": 0,
                "safety": 0,
                "runtime": 0,
            },
        },
        "human_review": {
            "status": "missing-evidence",
            "reviewed_pairs": 0,
            "pending_pairs": pair_count,
            "with_skill_win_rate": None,
            "second_reviewer_coverage": 0.0,
            "cohen_kappa": None,
        },
    }
    validate_artifact("eval-result", result)
    public_runs_by_task = {
        task_id: comparisons
        for task_id, comparisons in runs_by_task.items()
        if task_id not in private_task_ids
    }
    pack, answer_key = _build_blind_pairs(suite_id, public_runs_by_task, pair_repeats)
    _write_json(output / "eval-result.json", result)
    _write_json(output / "blind-review-pack.json", pack)
    _write_json(output / "blind-answer-key.json", answer_key)
    summary = {
        "status": "completed" if execution_mode != "deterministic" else "completed-with-missing-evidence",
        "output": str(output.resolve()),
        "case_count": len(tasks),
        "private_holdout_case_count": len(private_tasks),
        "pair_count": pair_count,
        "execution_kinds": sorted({run["execution_kind"] for run in runs}),
        "semantic_digest": semantic_digest,
    }
    for temporary in temporary_environments:
        temporary.cleanup()
    return summary
