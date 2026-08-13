from __future__ import annotations

import hashlib
import fcntl
import json
import os
import re
import shutil
import stat
import tempfile
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .validation import load_bounded_json


RETENTION_DAYS = {"L0": 365, "L1": 180, "L2": 30, "L3": 7}
TRASH_DIRECTORY = ".geohub-trash"
PURGE_GRACE_DAYS = 7
RETENTION_LOCK = ".geohub-retention.lock"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _safe_runs_root(runs_root: Path) -> Path:
    candidate = Path(runs_root)
    try:
        metadata = os.lstat(candidate)
    except OSError as exc:
        raise ValueError("runs root is unavailable") from exc
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
        raise ValueError("runs root must be a regular directory and cannot be a symlink")
    root = candidate.resolve()
    broad = {Path("/").resolve(), Path.home().resolve()}
    if root in broad or (root / ".git").exists() or (root / "pyproject.toml").exists():
        raise ValueError("refusing broad runs root")
    return root


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _durable_json(path: Path, payload: dict[str, Any]) -> None:
    descriptor, raw_temporary = tempfile.mkstemp(prefix=f".{path.name}.tmp-", dir=path.parent)
    temporary = Path(raw_temporary)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        _fsync_directory(path.parent)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


@contextmanager
def _retention_lock(root: Path):
    descriptor = os.open(root / RETENTION_LOCK, os.O_CREAT | os.O_RDWR | os.O_CLOEXEC | os.O_NOFOLLOW, 0o600)
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise ValueError("retention lock must be a regular file")
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


def _recover_incomplete_staging(root: Path) -> None:
    trash_root = root / TRASH_DIRECTORY
    if not trash_root.exists():
        return
    if trash_root.is_symlink() or not trash_root.is_dir():
        raise ValueError("trash root cannot be a symlink and must be a directory")
    for staging in sorted(trash_root.glob(".batch-*.staging")):
        if staging.is_symlink() or not staging.is_dir():
            raise ValueError("retention staging entry is unsafe")
        manifest_path = staging / "recover-manifest.json"
        staged_runs = staging / "runs"
        if not manifest_path.exists():
            if staged_runs.is_dir() and not any(staged_runs.iterdir()):
                staged_runs.rmdir()
                staging.rmdir()
                _fsync_directory(trash_root)
                continue
            raise ValueError(f"retention staging journal is missing: {staging.name}")
        manifest = load_bounded_json(manifest_path, max_bytes=1024 * 1024, field="staging recover manifest")
        expected = {"protocol_version", "batch_id", "moved_at", "source", "runs"}
        if set(manifest) != expected or staging.name != f".{manifest.get('batch_id')}.staging":
            raise ValueError("retention staging journal is invalid")
        for run_id in reversed(manifest["runs"]):
            source = root / run_id
            staged = staged_runs / run_id
            source_exists = source.exists()
            staged_exists = staged.exists()
            if source_exists and staged_exists:
                raise ValueError(f"retention staging has duplicate run state: {run_id}")
            if staged_exists:
                os.rename(staged, source)
                _fsync_directory(root)
                _fsync_directory(staged_runs)
            elif not source_exists:
                raise ValueError(f"retention staging lost run state: {run_id}")
        manifest_path.unlink()
        staged_runs.rmdir()
        staging.rmdir()
        _fsync_directory(trash_root)


def _safe_run_entries(root: Path) -> list[Path]:
    runs: list[Path] = []
    for entry in sorted(root.iterdir(), key=lambda path: path.name):
        if not entry.name.startswith("run-"):
            continue
        metadata = os.lstat(entry)
        if stat.S_ISLNK(metadata.st_mode):
            raise ValueError(f"run entry is a symlink: {entry.name}")
        if not stat.S_ISDIR(metadata.st_mode):
            raise ValueError(f"run entry must be a directory: {entry.name}")
        runs.append(entry)
    return runs


def _parse_timestamp(value: Any, field: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be an ISO timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field} must be an ISO timestamp") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{field} must include a timezone")
    return parsed.astimezone(timezone.utc)


def _run_policy(run: Path) -> tuple[str, int]:
    policy_path = run / "retention-policy.json"
    if not policy_path.exists():
        return "L2", RETENTION_DAYS["L2"]
    policy = load_bounded_json(policy_path, max_bytes=16 * 1024, field="retention policy")
    extra = set(policy) - {"data_class"}
    data_class = policy.get("data_class")
    if extra or data_class not in RETENTION_DAYS:
        raise ValueError(f"invalid retention policy for {run.name}")
    return data_class, RETENTION_DAYS[data_class]


def _expired_runs(root: Path, now: datetime) -> list[dict[str, Any]]:
    expired: list[dict[str, Any]] = []
    for run in _safe_run_entries(root):
        manifest = load_bounded_json(
            run / "run-manifest.json",
            max_bytes=1024 * 1024,
            field="run manifest",
        )
        if manifest.get("run_id") != run.name:
            raise ValueError(f"run manifest ID mismatch: {run.name}")
        created_at = _parse_timestamp(manifest.get("created_at"), "created_at")
        data_class, retention_days = _run_policy(run)
        if now - created_at >= timedelta(days=retention_days):
            expired.append(
                {
                    "run_id": run.name,
                    "data_class": data_class,
                    "created_at": created_at.isoformat().replace("+00:00", "Z"),
                    "retention_days": retention_days,
                }
            )
    return expired


def _batch_id(now: datetime, targets: list[str]) -> str:
    timestamp = now.strftime("%Y%m%dT%H%M%SZ")
    suffix = hashlib.sha256("\x1f".join(targets).encode("utf-8")).hexdigest()[:8]
    return f"batch-{timestamp}-{suffix}"


def apply_retention_policy(
    runs_root: Path,
    *,
    now: datetime | None = None,
    confirm: bool = False,
) -> dict[str, Any]:
    root = _safe_runs_root(runs_root)
    with _retention_lock(root):
        _recover_incomplete_staging(root)
        moment = (now or _utc_now()).astimezone(timezone.utc)
        candidates = _expired_runs(root, moment)
        targets = [item["run_id"] for item in candidates]
        if not confirm:
            return {"status": "dry-run", "targets": targets, "policies": candidates}
        if not targets:
            return {"status": "no-op", "targets": [], "batch_id": None, "run_count": 0}

        trash_root = root / TRASH_DIRECTORY
        trash_root.mkdir(mode=0o700, exist_ok=True)
        if trash_root.is_symlink():
            raise ValueError("trash root cannot be a symlink")
        batch_id = _batch_id(moment, targets)
        final_batch = trash_root / batch_id
        staging = trash_root / f".{batch_id}.staging"
        if final_batch.exists() or staging.exists():
            raise ValueError(f"retention batch already exists: {batch_id}")
        staged_runs = staging / "runs"
        staged_runs.mkdir(parents=True, mode=0o700)
        if os.stat(root).st_dev != os.stat(staging).st_dev:
            raise ValueError("retention trash must use the same filesystem as runs root")
        manifest = {
            "protocol_version": "1.0.0",
            "batch_id": batch_id,
            "moved_at": moment.isoformat().replace("+00:00", "Z"),
            "source": ".",
            "runs": targets,
        }
        _durable_json(staging / "recover-manifest.json", manifest)
        moved: list[str] = []
        try:
            for run_id in targets:
                source = root / run_id
                destination = staged_runs / run_id
                if destination.exists():
                    raise ValueError(f"trash destination exists: {run_id}")
                os.rename(source, destination)
                _fsync_directory(root)
                _fsync_directory(staged_runs)
                moved.append(run_id)
            os.rename(staging, final_batch)
            _fsync_directory(trash_root)
        except BaseException:
            for run_id in reversed(moved):
                source = staged_runs / run_id
                if source.exists() and not (root / run_id).exists():
                    os.rename(source, root / run_id)
            if staging.exists():
                shutil.rmtree(staging)
            raise
        return {
            "status": "moved-to-trash",
            "batch_id": batch_id,
            "targets": targets,
            "run_count": len(targets),
        }


def _load_batch(root: Path, batch_id: str) -> tuple[Path, dict[str, Any]]:
    if not re.fullmatch(r"batch-\d{8}T\d{6}Z-[0-9a-f]{8}", batch_id):
        raise ValueError("invalid retention batch ID")
    batch = root / TRASH_DIRECTORY / batch_id
    metadata = os.lstat(batch)
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
        raise ValueError("retention batch must be a regular directory")
    manifest = load_bounded_json(
        batch / "recover-manifest.json",
        max_bytes=1024 * 1024,
        field="recover manifest",
    )
    expected = {"protocol_version", "batch_id", "moved_at", "source", "runs"}
    if set(manifest) != expected or manifest["batch_id"] != batch_id or manifest["source"] != ".":
        raise ValueError("invalid recover manifest")
    if not isinstance(manifest["runs"], list) or not manifest["runs"]:
        raise ValueError("recover manifest has no runs")
    if any(not isinstance(item, str) or not re.fullmatch(r"run-[A-Za-z0-9._-]+", item) for item in manifest["runs"]):
        raise ValueError("recover manifest has an invalid run ID")
    if len(manifest["runs"]) != len(set(manifest["runs"])):
        raise ValueError("recover manifest has duplicate runs")
    return batch, manifest


def recover_batch(runs_root: Path, batch_id: str) -> dict[str, Any]:
    root = _safe_runs_root(runs_root)
    with _retention_lock(root):
        trash_root = root / TRASH_DIRECTORY
        batch_candidate = trash_root / batch_id
        recovery_marker = batch_candidate / "recovery-in-progress.json"
        if recovery_marker.exists():
            batch, manifest = _load_batch(root, batch_id)
            progress = load_bounded_json(recovery_marker, max_bytes=1024 * 1024, field="recovery progress")
            if progress != {"protocol_version": "1.0.0", "batch_id": batch_id, "runs": manifest["runs"]}:
                raise ValueError("recovery progress journal is invalid")
            for run_id in reversed(manifest["runs"]):
                staged = batch / "runs" / run_id
                destination = root / run_id
                if destination.exists() and staged.exists():
                    raise ValueError(f"recovery rollback has duplicate run state: {run_id}")
                if destination.exists():
                    os.rename(destination, staged)
                    _fsync_directory(root)
                    _fsync_directory(batch / "runs")
                elif not staged.exists():
                    raise ValueError(f"recovery rollback lost run state: {run_id}")
            recovery_marker.unlink()
            _fsync_directory(batch)
            return {"status": "recovery-rolled-back", "batch_id": batch_id, "run_count": len(manifest["runs"])}
        _recover_incomplete_staging(root)
        batch, manifest = _load_batch(root, batch_id)
        marker = batch / "recovery-in-progress.json"
        if not marker.exists():
            for run_id in manifest["runs"]:
                if (root / run_id).exists():
                    raise ValueError(f"recovery target already exists: {run_id}")
                source = batch / "runs" / run_id
                metadata = os.lstat(source)
                if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
                    raise ValueError(f"recovery source is unsafe: {run_id}")
            _durable_json(marker, {"protocol_version": "1.0.0", "batch_id": batch_id, "runs": manifest["runs"]})
        for run_id in manifest["runs"]:
            source = batch / "runs" / run_id
            destination = root / run_id
            if source.exists() and destination.exists():
                raise ValueError(f"recovery has duplicate run state: {run_id}")
            if source.exists():
                os.rename(source, destination)
                _fsync_directory(root)
                _fsync_directory(batch / "runs")
            elif not destination.exists():
                raise ValueError(f"recovery lost run state: {run_id}")
        marker.unlink()
        (batch / "recover-manifest.json").unlink()
        (batch / "runs").rmdir()
        batch.rmdir()
        _fsync_directory(root / TRASH_DIRECTORY)
        return {"status": "recovered", "batch_id": batch_id, "run_count": len(manifest["runs"])}


def _reject_symlinks(root: Path) -> None:
    for current, directories, files in os.walk(root, followlinks=False):
        for name in [*directories, *files]:
            path = Path(current) / name
            if stat.S_ISLNK(os.lstat(path).st_mode):
                raise ValueError(f"purge batch contains a symlink: {path.name}")


def purge_batch(
    runs_root: Path,
    batch_id: str,
    *,
    now: datetime | None = None,
    confirm: bool = False,
) -> dict[str, Any]:
    root = _safe_runs_root(runs_root)
    with _retention_lock(root):
        _recover_incomplete_staging(root)
        batch, manifest = _load_batch(root, batch_id)
        if (batch / "recovery-in-progress.json").exists():
            raise ValueError("purge cannot run while recovery is in progress")
        if not confirm:
            raise ValueError("purge requires explicit confirmation")
        moment = (now or _utc_now()).astimezone(timezone.utc)
        moved_at = _parse_timestamp(manifest["moved_at"], "moved_at")
        if moment - moved_at < timedelta(days=PURGE_GRACE_DAYS):
            raise ValueError("purge requires a 7-day grace period")
        if not getattr(shutil.rmtree, "avoids_symlink_attacks", False):
            raise ValueError("platform cannot provide symlink-safe purge")
        _reject_symlinks(batch)
        run_count = len(manifest["runs"])
        shutil.rmtree(batch)
        _fsync_directory(root / TRASH_DIRECTORY)
        return {"status": "purged", "batch_id": batch_id, "run_count": run_count}
