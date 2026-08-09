from __future__ import annotations

import json
import os
import re
import shutil
import stat
import tempfile
from pathlib import Path
from typing import Any

from .validation import strict_json_loads, validate_artifact


class ArtifactBus:
    """Write validated protocol artifacts inside one bounded run directory."""

    def __init__(self, root: Path):
        self.root = root.resolve()
        self.final_root: Path | None = None
        self._published = False
        if self.root.exists() and any(self.root.iterdir()):
            raise ValueError(f"Output directory must be empty: {self.root}")
        self.root.mkdir(parents=True, exist_ok=True)

    @classmethod
    def transaction(cls, runs_root: Path, run_id: str) -> "ArtifactBus":
        if not re.fullmatch(r"run-[A-Za-z0-9._-]+", run_id):
            raise ValueError(f"Invalid run ID: {run_id}")
        resolved_runs_root = runs_root.resolve()
        resolved_runs_root.mkdir(parents=True, exist_ok=True)
        final_root = resolved_runs_root / run_id
        if final_root.exists():
            raise ValueError(f"Run directory already exists: {final_root}")
        staging = Path(
            tempfile.mkdtemp(
                prefix=f".{run_id}.staging-",
                dir=resolved_runs_root,
            )
        )
        bus = cls.__new__(cls)
        bus.root = staging
        bus.final_root = final_root
        bus._published = False
        return bus

    def __enter__(self) -> "ArtifactBus":
        return self

    def __exit__(self, _exc_type, _exc, _traceback) -> None:
        if self.final_root is not None and not self._published and self.root.exists():
            shutil.rmtree(self.root)

    def _resolve(self, relative_path: str) -> Path:
        target = (self.root / relative_path).resolve()
        if target != self.root and self.root not in target.parents:
            raise ValueError(f"Artifact path escapes run directory: {relative_path}")
        return target

    def write_json(
        self,
        relative_path: str,
        artifact: dict[str, Any],
        schema_name: str | None = None,
    ) -> Path:
        if schema_name:
            validate_artifact(schema_name, artifact)
        target = self._resolve(relative_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(target.suffix + ".tmp")
        try:
            serialized = json.dumps(
                artifact,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
                allow_nan=False,
            )
        except ValueError as exc:
            raise ValueError(f"Artifact JSON contains a non-finite number: {relative_path}") from exc
        temporary.write_text(serialized + "\n", encoding="utf-8")
        temporary.replace(target)
        return target

    def write_text(self, relative_path: str, content: str) -> Path:
        target = self._resolve(relative_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(target.suffix + ".tmp")
        temporary.write_text(content, encoding="utf-8")
        temporary.replace(target)
        return target

    def write_bytes(self, relative_path: str, content: bytes) -> Path:
        """Atomically stage a binary artifact inside the bounded run directory."""
        target = self._resolve(relative_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(target.suffix + ".tmp")
        temporary.write_bytes(content)
        temporary.replace(target)
        return target

    def publish(self, expected_files: set[str]) -> Path:
        if self.final_root is None:
            raise ValueError("Direct ArtifactBus instances cannot be published")
        actual_files: set[str] = set()
        for path in self.root.rglob("*"):
            if path.is_dir():
                continue
            mode = path.lstat().st_mode
            if path.is_symlink() or not stat.S_ISREG(mode):
                raise ValueError(f"Artifact Bus contains a non-regular file: {path}")
            actual_files.add(path.relative_to(self.root).as_posix())
        if actual_files != expected_files:
            missing = sorted(expected_files - actual_files)
            extra = sorted(actual_files - expected_files)
            raise ValueError(
                f"Artifact Bus file set mismatch; missing={missing}, extra={extra}"
            )
        manifest_path = self.root / "run-manifest.json"
        try:
            manifest = strict_json_loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise ValueError(f"Unable to validate staged run manifest: {exc}") from exc
        declared = set(manifest.get("artifacts", []))
        expected_declared = expected_files - {"run-manifest.json"}
        if declared != expected_declared:
            raise ValueError(
                "Run manifest artifacts do not match the staged Artifact Bus files"
            )
        if self.final_root.exists():
            raise ValueError(f"Run directory already exists: {self.final_root}")
        try:
            os.rename(self.root, self.final_root)
        except OSError as exc:
            if self.final_root.exists():
                raise ValueError(f"Run directory already exists: {self.final_root}") from exc
            raise
        self._published = True
        self.root = self.final_root
        return self.final_root
