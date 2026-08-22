from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

import yaml

from ..registry import load_registry
from ..validation import load_json


def _normal(value: str) -> str:
    return " ".join(value.casefold().split())


def _artifact_schema_errors(root: Path, skill: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for field in ("input_artifacts", "output_artifacts"):
        for artifact in skill[field]:
            schema_name = artifact["schema"]
            if schema_name is None:
                continue
            schema_path = root / "schemas" / f"{schema_name}.schema.json"
            if not schema_path.is_file():
                errors.append(
                    f"{skill['id']}: {field} references missing schema {schema_name}"
                )
    return errors


def verify_capability_contracts(
    root: Path,
    *,
    registry: dict[str, Any] | None = None,
    skill_ids: Iterable[str] | None = None,
) -> dict[str, Any]:
    root = Path(root)
    registry = registry or load_registry(root / "registry" / "skills.yaml")
    requested = set(skill_ids) if skill_ids is not None else None
    selected = sorted(
        (
            skill
            for skill in registry["skills"]
            if skill["entry"] and (requested is None or skill["id"] in requested)
        ),
        key=lambda item: item["id"],
    )
    errors: list[str] = []
    for skill in selected:
        skill_id = skill["id"]
        positives = {_normal(item) for item in skill["positive_examples"]}
        negatives = {_normal(item) for item in skill["negative_examples"]}
        if positives & negatives:
            errors.append(f"{skill_id}: positive and negative examples overlap")
        errors.extend(_artifact_schema_errors(root, skill))
        required_inputs = [item for item in skill["input_artifacts"] if item["required"]]
        if (
            skill["status"] == "active"
            and skill["execution"]["executor"] not in {None, "route"}
            and len(required_inputs) != 1
        ):
            errors.append(
                f"{skill_id}: local CLI executor requires exactly one required input artifact"
            )

        manifest_path = root / "skills" / skill_id / "manifest.json"
        interface_path = root / "skills" / skill_id / "agents" / "interface.yaml"
        if not manifest_path.is_file():
            errors.append(f"{skill_id}: manifest.json is missing")
            continue
        manifest = load_json(manifest_path)
        expected_manifest = {
            "name": skill_id,
            "availability": skill["status"],
            "entrypoint": Path(skill["entry"]).name,
        }
        for field, expected in expected_manifest.items():
            if manifest.get(field) != expected:
                errors.append(
                    f"{skill_id}: manifest {field} is {manifest.get(field)!r}, expected {expected!r}"
                )
        manifest_permissions = manifest.get("permission_profile")
        registry_permissions = {
            key: skill["permissions"][key]
            for key in ("filesystem", "network", "shell")
        }
        if manifest_permissions != registry_permissions:
            errors.append(f"{skill_id}: manifest permission_profile drifted from registry")

        if not interface_path.is_file():
            errors.append(f"{skill_id}: agents/interface.yaml is missing")
            continue
        try:
            interface = yaml.safe_load(interface_path.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as exc:
            errors.append(f"{skill_id}: interface cannot be read: {type(exc).__name__}")
            continue
        surface = interface.get("interface") if isinstance(interface, dict) else None
        permissions = surface.get("permission_contract") if isinstance(surface, dict) else None
        if not isinstance(permissions, dict):
            errors.append(f"{skill_id}: interface permission_contract is missing")
        elif skill["permissions"]["network"] == "forbid" and permissions.get("network") != "forbid":
            errors.append(f"{skill_id}: interface network permission is broader than registry")

    return {
        "status": "pass" if not errors else "fail",
        "registry_version": registry["registry_version"],
        "checked_skill_ids": [skill["id"] for skill in selected],
        "errors": errors,
    }
