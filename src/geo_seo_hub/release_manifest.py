from __future__ import annotations

from pathlib import Path
from typing import Any

from .registry import load_registry


SOURCE_EXACT = frozenset(
    {
        "VERSION",
        "LICENSE",
        "LICENSE-SCOPE.md",
        "COMMERCIAL-LICENSING.md",
        "THIRD_PARTY_NOTICES.md",
        "README.md",
        "CHANGELOG.md",
        "SECURITY.md",
        "pyproject.toml",
        "requirements-ci.lock",
        "Makefile",
        "CONTRIBUTING.md",
        "CONTRIBUTOR-LICENSE-AGREEMENT.md",
        "TRADEMARKS.md",
        ".github/dependabot.yml",
        ".github/ISSUE_TEMPLATE/commercial-licensing.yml",
        ".github/workflows/ci.yml",
        ".github/workflows/release.yml",
    }
)
SOURCE_PREFIXES = ("src/", "schemas/", "registry/", "skills/", "scripts/", "docs/", "tests/", "evals/")
EXCLUDED_PARTS = frozenset({".git", "__pycache__", ".pytest_cache", "runs", "dist"})


def is_release_source(relative: Path) -> bool:
    raw = relative.as_posix()
    if "reports" in relative.parts and (not relative.parts or relative.parts[0] != "skills"):
        return False
    return not (set(relative.parts) & EXCLUDED_PARTS) and (raw in SOURCE_EXACT or raw.startswith(SOURCE_PREFIXES))


def expected_archive_names(version: str, active_skill_ids: tuple[str, ...]) -> frozenset[str]:
    return frozenset(
        {
            f"geo-seo-hub-source-{version}.zip",
            f"geo-seo-hub-unified-community-{version}.zip",
            *(f"{skill_id}-community-{version}.zip" for skill_id in active_skill_ids),
            f"geo-seo-hub-codex-community-{version}.zip",
            f"geo-seo-hub-claude-community-{version}.zip",
        }
    )


def build_release_manifest(root: Path) -> dict[str, Any]:
    root = Path(root)
    registry = load_registry(root / "registry" / "skills.yaml")
    active_skill_ids = tuple(skill["id"] for skill in registry["skills"] if skill["status"] == "active")
    version = (root / "VERSION").read_text(encoding="utf-8").strip()
    archive_names = expected_archive_names(version, active_skill_ids)
    return {
        "version": version,
        "active_skill_ids": active_skill_ids,
        "archive_names": archive_names,
        "archive_count": len(archive_names),
    }
