from __future__ import annotations

from copy import deepcopy
from typing import Any

from .paths import repository_root
from .validation import load_json, validate_artifact

PROTOCOL_VERSION = "1.0.0"


def load_research_registry() -> dict[str, Any]:
    registry = load_json(repository_root() / "registry" / "research-evidence.json")
    validate_research_registry(registry)
    return registry


def validate_research_registry(registry: dict[str, Any]) -> None:
    if not isinstance(registry, dict):
        raise ValueError("research evidence registry must be an object")
    principles = registry.get("principles")
    if not isinstance(principles, list):
        raise ValueError("research evidence registry principles must be an array")
    for principle in principles:
        if isinstance(principle, dict) and principle.get("allowed_use") == "effect-guarantee":
            raise ValueError("research principles must not authorize effect guarantees")
    validate_artifact("research-evidence-registry", registry)

    source_ids = registry["source_ids"]
    known_sources = set(source_ids)
    principle_ids: set[str] = set()
    referenced_sources: set[str] = set()
    for principle in principles:
        principle_id = principle["principle_id"]
        if principle_id in principle_ids:
            raise ValueError(f"duplicate research principle: {principle_id}")
        principle_ids.add(principle_id)
        unknown_sources = sorted(set(principle["source_ids"]) - known_sources)
        if unknown_sources:
            raise ValueError(f"unknown research source in {principle_id}: {unknown_sources}")
        referenced_sources.update(principle["source_ids"])
        if principle["causal_status"] == "causal-estimate" and "causal" not in principle["claim_classes"]:
            raise ValueError(f"causal research principle lacks a causal claim class: {principle_id}")
    uncovered = sorted(known_sources - referenced_sources)
    if uncovered:
        raise ValueError(f"research sources are not mapped to a principle: {uncovered}")


def build_research_context(
    run_id: str,
    surface: str,
    *,
    registry: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not isinstance(run_id, str) or not run_id.strip():
        raise ValueError("research context run_id must be a non-blank string")
    if not isinstance(surface, str) or not surface.strip():
        raise ValueError("research context surface must be a non-blank string")
    normalized_surface = surface.strip()
    source = registry or load_research_registry()
    validate_research_registry(source)
    principles = [
        deepcopy(principle)
        for principle in source["principles"]
        if any(
            declared == "all"
            or declared == normalized_surface
            or normalized_surface.startswith(f"{declared}:")
            for declared in principle["surfaces"]
        )
    ]
    if not principles:
        raise ValueError(f"research registry has no principles for surface: {surface}")
    applied_source_ids = sorted(
        {source_id for principle in principles for source_id in principle["source_ids"]},
        key=lambda value: (value[0], int(value[1:])),
    )
    limitations = sorted(
        {limitation for principle in principles for limitation in principle["limitations"]},
        key=lambda value: (value.casefold(), value),
    )
    context = {
        "protocol_version": PROTOCOL_VERSION,
        "run_id": run_id.strip(),
        "registry_version": source["registry_version"],
        "source_commit": source["source_commit"],
        "surface": normalized_surface,
        "effect_guarantee": False,
        "applied_source_ids": applied_source_ids,
        "principles": principles,
        "limitations": limitations,
    }
    validate_artifact("research-context", context)
    return context
