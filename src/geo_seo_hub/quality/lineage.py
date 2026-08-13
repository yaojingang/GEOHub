from __future__ import annotations

import hashlib
import os
import stat
from pathlib import Path
from typing import Iterable

from ..validation import validate_artifact


def _stable_identifier(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()[:16]
    return f"{prefix}-{digest}"


def _hash_regular_artifact(run_root: Path, relative: str) -> str:
    candidate = Path(relative)
    if candidate.is_absolute() or not candidate.parts or any(part in {"", ".", ".."} for part in candidate.parts):
        raise ValueError(f"lineage artifact path is unsafe: {relative}")
    target = run_root.joinpath(*candidate.parts)
    try:
        metadata = os.lstat(target)
    except OSError as exc:
        raise ValueError(f"lineage artifact is unavailable: {relative}") from exc
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
        raise ValueError(f"lineage artifact must be a regular file: {relative}")
    digest = hashlib.sha256()
    with target.open("rb") as stream:
        while chunk := stream.read(64 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def build_run_lineage(
    run_root: Path,
    *,
    run_id: str,
    skill_id: str,
    status: str,
    artifact_paths: Iterable[str],
    metric_names: Iterable[str] = (),
    data_class: str = "L2",
) -> dict:
    """Build metadata-only lineage for already staged run artifacts."""
    hashes = {
        relative: _hash_regular_artifact(run_root, relative)
        for relative in sorted(set(artifact_paths))
    }
    lineage = {
        "protocol_version": "1.0.0",
        "trace_id": _stable_identifier("trace", run_id, skill_id),
        "run_id": run_id,
        "skill_id": skill_id,
        "data_class": data_class,
        "events": [
            {
                "span_id": _stable_identifier("span", run_id, skill_id, "execute"),
                "parent_span_id": None,
                "stage": "execute",
                "status": status,
                "duration_ms": 0,
                "artifact_hashes": hashes,
                "metric_names": sorted(set(metric_names)),
                "token_count": 0,
                "cost_usd": 0.0,
                "error_class": None,
            }
        ],
    }
    validate_artifact("run-lineage", lineage)
    return lineage
