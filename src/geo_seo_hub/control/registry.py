from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..registry import load_registry


@dataclass(frozen=True)
class RegistrySnapshot:
    protocol_version: str
    registry_version: str
    skills: tuple[dict[str, Any], ...]
    workflows: tuple[dict[str, Any], ...]

    @property
    def skills_by_id(self) -> dict[str, dict[str, Any]]:
        return {skill["id"]: skill for skill in self.skills}


def load_registry_snapshot(path: Path | None = None) -> RegistrySnapshot:
    registry = load_registry(path)
    return RegistrySnapshot(
        protocol_version=registry["protocol_version"],
        registry_version=registry["registry_version"],
        skills=tuple(dict(skill) for skill in registry["skills"]),
        workflows=tuple(dict(workflow) for workflow in registry["workflows"]),
    )
