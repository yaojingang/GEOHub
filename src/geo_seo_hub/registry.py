from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator

from .paths import repository_root
from .validation import ArtifactValidationError, load_json


class RegistryError(ValueError):
    """Raised when the skill registry is invalid."""


def load_registry(path: Path | None = None) -> dict[str, Any]:
    registry_path = path or repository_root() / "registry" / "skills.yaml"
    schema_path = registry_path.with_name("skills.schema.json")
    try:
        data = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
        schema = load_json(schema_path)
    except (OSError, yaml.YAMLError, ArtifactValidationError) as exc:
        raise RegistryError(f"Unable to load registry: {exc}") from exc

    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(data), key=lambda item: list(item.path))
    if errors:
        details = "; ".join(error.message for error in errors)
        raise RegistryError(f"Invalid registry: {details}")

    skills = data["skills"]
    identifiers = [skill["id"] for skill in skills]
    if len(identifiers) != len(set(identifiers)):
        raise RegistryError("Invalid registry: duplicate skill IDs")

    root = registry_path.parent.parent
    root_resolved = root.resolve()
    for skill in skills:
        entry = skill["entry"]
        if not entry:
            continue
        relative = Path(entry)
        expected = Path("skills") / skill["id"] / "SKILL.md"
        packaged = Path("references") / "providers" / f"{skill['id']}.md"
        allowed = {expected, packaged, Path("SKILL.md")}
        if relative.is_absolute() or ".." in relative.parts or relative not in allowed:
            raise RegistryError(
                f"Invalid registry: entry for {skill['id']} must be {expected.as_posix()} or a packaged entry"
            )
        resolved = (root / relative).resolve()
        if root_resolved not in resolved.parents or not resolved.is_file():
            raise RegistryError(f"Invalid registry: unsafe or missing entry for {skill['id']}: {entry}")
        if relative != expected:
            try:
                parts = resolved.read_text(encoding="utf-8").split("---", 2)
                frontmatter = yaml.safe_load(parts[1]) if len(parts) == 3 else None
            except (OSError, yaml.YAMLError) as exc:
                raise RegistryError(f"Invalid registry: unreadable packaged entry for {skill['id']}") from exc
            if not isinstance(frontmatter, dict) or frontmatter.get("name") != skill["id"]:
                raise RegistryError(f"Invalid registry: packaged entry identity mismatch for {skill['id']}")

    geo_routes = [skill for skill in skills if skill["id"] == "geo"]
    if len(geo_routes) != 1 or geo_routes[0]["status"] != "active" or not geo_routes[0]["entry"]:
        raise RegistryError("Invalid registry: exactly one active runnable geo route is required")
    suggestions = [skill for skill in skills if skill["id"] == "geo-discover"]
    if len(suggestions) != 1 or suggestions[0]["status"] != "active" or not suggestions[0]["entry"]:
        raise RegistryError("Invalid registry: geo-discover suggestion must exist and be runnable")
    by_id = {skill["id"]: skill for skill in skills}
    for skill in skills:
        suggestion = skill.get("nearest_active")
        if suggestion and (suggestion not in by_id or by_id[suggestion]["status"] != "active" or not by_id[suggestion]["entry"]):
            raise RegistryError(f"Invalid registry: nearest active suggestion for {skill['id']} is not runnable")
    workflow_ids: set[str] = set()
    for workflow in data["workflows"]:
        if workflow["id"] in workflow_ids:
            raise RegistryError("Invalid registry: duplicate workflow IDs")
        workflow_ids.add(workflow["id"])
        step_ids: set[str] = set()
        step_skills = []
        for step in workflow["steps"]:
            if step["id"] in step_ids or any(dep not in step_ids for dep in step["depends_on"]):
                raise RegistryError(f"Invalid registry: workflow {workflow['id']} is not a stable DAG")
            if step["skill_id"] not in by_id or by_id[step["skill_id"]]["status"] != "active":
                raise RegistryError(f"Invalid registry: workflow {workflow['id']} references an inactive skill")
            step_ids.add(step["id"])
            step_skills.append(step["skill_id"])
        if step_skills != workflow["required_skills"]:
            raise RegistryError(f"Invalid registry: workflow {workflow['id']} required_skills must match step order")
    return data
