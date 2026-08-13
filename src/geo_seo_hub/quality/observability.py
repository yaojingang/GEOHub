from __future__ import annotations

import os
import stat
from collections import Counter
from pathlib import Path

from ..validation import load_bounded_json, validate_artifact


def aggregate_adoption_drift(runs_root: Path) -> dict:
    """Aggregate allowlisted lineage counters without copying run payloads."""
    root = Path(runs_root)
    by_skill: Counter[str] = Counter()
    by_status: Counter[str] = Counter()
    errors: Counter[str] = Counter()
    gaps: list[str] = []
    run_count = 0
    if not root.is_dir() or root.is_symlink():
        raise ValueError("runs root must be a regular directory")
    for run in sorted(root.iterdir(), key=lambda path: path.name):
        try:
            metadata = os.lstat(run)
        except OSError:
            gaps.append(f"unreadable run entry: {run.name}")
            continue
        if not run.name.startswith("run-"):
            continue
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
            gaps.append(f"unsafe run entry: {run.name}")
            continue
        lineage_path = run / "run-lineage.json"
        try:
            lineage = load_bounded_json(lineage_path, max_bytes=1024 * 1024, field="run lineage")
            validate_artifact("run-lineage", lineage)
        except (OSError, ValueError) as exc:
            gaps.append(f"invalid lineage: {run.name}: {exc.__class__.__name__}")
            continue
        run_count += 1
        by_skill[lineage["skill_id"]] += 1
        for event in lineage["events"]:
            by_status[event["status"]] += 1
            if event["error_class"] is not None:
                errors[event["error_class"]] += 1
    return {
        "protocol_version": "1.0.0",
        "run_count": run_count,
        "by_skill": dict(sorted(by_skill.items())),
        "by_status": dict(sorted(by_status.items())),
        "errors": dict(sorted(errors.items())),
        "gaps": gaps,
    }
