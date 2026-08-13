#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import stat
import subprocess
import sys
import zipfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from geo_seo_hub.release_manifest import build_release_manifest, is_release_source  # noqa: E402

RELEASE = build_release_manifest(ROOT)
VERSION = RELEASE["version"]
DIST = ROOT / "dist"
SKILLS = RELEASE["active_skill_ids"]
LEGAL = ("VERSION", "LICENSE", "LICENSE-SCOPE.md", "COMMERCIAL-LICENSING.md", "THIRD_PARTY_NOTICES.md")


def source_allowed(relative: Path) -> bool:
    return is_release_source(relative)


def tracked_files() -> list[Path]:
    if ROOT.is_symlink() or not stat.S_ISDIR(ROOT.lstat().st_mode):
        raise ValueError(f"package root must be a regular directory: {ROOT}")
    result = subprocess.run(["git", "ls-files", "-z", "--cached"], cwd=ROOT, check=True, capture_output=True)
    dirty_result = subprocess.run(["git", "diff", "--name-only", "-z"], cwd=ROOT, check=True, capture_output=True)
    dirty_allowed = [Path(os.fsdecode(raw)) for raw in dirty_result.stdout.split(b"\0") if raw and source_allowed(Path(os.fsdecode(raw)))]
    if dirty_allowed:
        raise ValueError(f"allowlisted package files have unstaged changes: {[path.as_posix() for path in dirty_allowed]}")
    files = []
    root_resolved = ROOT.resolve()
    for raw in result.stdout.split(b"\0"):
        if not raw:
            continue
        relative = Path(os.fsdecode(raw))
        if relative.is_absolute() or ".." in relative.parts:
            continue
        if not source_allowed(relative):
            continue
        current = ROOT
        for part in relative.parts:
            current = current / part
            mode = current.lstat().st_mode
            if stat.S_ISLNK(mode):
                raise ValueError(f"symlink is forbidden: {relative}")
        if not stat.S_ISREG((ROOT / relative).lstat().st_mode):
            raise ValueError(f"non-file package entry: {relative}")
        if root_resolved not in (ROOT / relative).resolve().parents:
            raise ValueError(f"package path escapes root: {relative}")
        files.append(relative)
    return sorted(files, key=lambda item: item.as_posix())


def common_runtime(files: list[Path]) -> dict[str, bytes]:
    allowed = set(LEGAL)
    prefixes = ("src/", "schemas/")
    return {path.as_posix(): (ROOT / path).read_bytes() for path in files if path.as_posix() in allowed or path.as_posix().startswith(prefixes)}


def packaged_skill(skill_id: str, *, nested: bool = False) -> bytes:
    text = (ROOT / "skills" / skill_id / "SKILL.md").read_text(encoding="utf-8")
    if nested:
        text = re.sub(r"references/([A-Za-z0-9_.\-/]+)", rf"references/providers/{skill_id}/\1", text)
        text = text.replace("`../RESOLVER.md`", "`references/providers/geo/RESOLVER.md`")
    else:
        text = text.replace("`../RESOLVER.md`", "`references/RESOLVER.md`")
    return text.encode()


def packaged_registry(root_skill_id: str) -> bytes:
    registry = yaml.safe_load((ROOT / "registry" / "skills.yaml").read_text(encoding="utf-8"))
    for skill in registry["skills"]:
        if skill["status"] != "active":
            continue
        skill["entry"] = "SKILL.md" if skill["id"] == root_skill_id else f"references/providers/{skill['id']}.md"
    return yaml.safe_dump(registry, allow_unicode=True, sort_keys=False).encode()


def packaged_pyproject(entries: dict[str, bytes]) -> bytes:
    source = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    base = source.split("[tool.setuptools.data-files]", 1)[0].replace('readme = "README.md"', 'readme = "SKILL.md"')
    runtime_roots = {"SKILL.md", "PACKAGE-METADATA.json", "TARGET.md"}
    runtime_prefixes = ("registry/", "schemas/", "references/", "scripts/", "agents/", "manifests/")
    groups: dict[str, list[str]] = {}
    for name in sorted(entries):
        if name not in runtime_roots and not name.startswith(runtime_prefixes):
            continue
        parent = Path(name).parent.as_posix()
        destination = "share/geo-seo-hub" if parent == "." else f"share/geo-seo-hub/{parent}"
        groups.setdefault(destination, []).append(name)
    lines = [base.rstrip(), "", "[tool.setuptools.data-files]"]
    for destination, sources in groups.items():
        if sources:
            lines.append(f'"{destination}" = {json.dumps(sources, allow_nan=False)}')
    return ("\n".join(lines) + "\n").encode()


def adapter_runtime(files: list[Path], root_skill_id: str) -> dict[str, bytes]:
    entries = common_runtime(files)
    entries["SKILL.md"] = packaged_skill(root_skill_id)
    entries["registry/skills.yaml"] = packaged_registry(root_skill_id)
    entries["registry/skills.schema.json"] = (ROOT / "registry" / "skills.schema.json").read_bytes()
    for skill_id in SKILLS:
        entries[f"references/providers/{skill_id}.md"] = packaged_skill(skill_id, nested=True)
        source_prefix = f"skills/{skill_id}/references/"
        for path in files:
            raw = path.as_posix()
            if raw.startswith(source_prefix):
                entries[f"references/providers/{skill_id}/{raw[len(source_prefix):]}"] = (ROOT / path).read_bytes()
        wrapper = "route" if skill_id == "geo" else skill_id.removeprefix("geo-")
        entries[f"scripts/run_{wrapper}.py"] = (ROOT / "skills" / skill_id / "scripts" / f"run_{wrapper}.py").read_bytes()
    entries["references/providers/geo/RESOLVER.md"] = (ROOT / "skills" / "RESOLVER.md").read_bytes()
    return entries


def zip_write(output: Path, entries: dict[str, bytes], prefix: str = "") -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, payload in sorted(entries.items()):
            safe = Path(name)
            if safe.is_absolute() or ".." in safe.parts:
                raise ValueError(f"unsafe archive path: {name}")
            info = zipfile.ZipInfo(f"{prefix}{name}", date_time=(2026, 8, 8, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, payload)


def source_package(files: list[Path]) -> Path:
    output = DIST / f"geo-seo-hub-source-{VERSION}.zip"
    entries = {path.as_posix(): (ROOT / path).read_bytes() for path in files}
    zip_write(output, entries, prefix=f"geo-seo-hub-{VERSION}/")
    return output


def unified_package(files: list[Path]) -> Path:
    entries = adapter_runtime(files, "geo")
    entries["agents/interface.yaml"] = (ROOT / "skills" / "geo" / "agents" / "interface.yaml").read_bytes()
    entries["references/RESOLVER.md"] = (ROOT / "skills" / "RESOLVER.md").read_bytes()
    entries["references/routing-contract.md"] = (ROOT / "skills" / "geo" / "references" / "routing-contract.md").read_bytes()
    for skill_id in SKILLS:
        skill_root = ROOT / "skills" / skill_id
        entries[f"manifests/{skill_id}.json"] = (skill_root / "manifest.json").read_bytes()
    entries["PACKAGE-METADATA.json"] = json.dumps({"channel": "community", "license": "AGPL-3.0-only", "commercial_license_status": "inquiry_only", "kind": "unified"}, indent=2, allow_nan=False).encode() + b"\n"
    entries["pyproject.toml"] = packaged_pyproject(entries)
    output = DIST / f"geo-seo-hub-unified-community-{VERSION}.zip"
    zip_write(output, entries)
    return output


def provider_package(files: list[Path], skill_id: str) -> Path:
    entries = adapter_runtime(files, skill_id)
    skill_root = ROOT / "skills" / skill_id
    entries["agents/interface.yaml"] = (skill_root / "agents" / "interface.yaml").read_bytes()
    entries["manifest.json"] = (skill_root / "manifest.json").read_bytes()
    for path in files:
        prefix = f"skills/{skill_id}/"
        raw = path.as_posix()
        if raw.startswith(prefix + "references/") or raw.startswith(prefix + "scripts/"):
            entries[raw[len(prefix):]] = (ROOT / path).read_bytes()
    if skill_id == "geo":
        entries["references/RESOLVER.md"] = (ROOT / "skills" / "RESOLVER.md").read_bytes()
    entries["PACKAGE-METADATA.json"] = json.dumps({"channel": "community", "license": "AGPL-3.0-only", "commercial_license_status": "inquiry_only", "kind": "provider", "skill_id": skill_id}, indent=2, allow_nan=False).encode() + b"\n"
    entries["pyproject.toml"] = packaged_pyproject(entries)
    output = DIST / f"{skill_id}-community-{VERSION}.zip"
    zip_write(output, entries)
    return output


def target_package(files: list[Path], target: str) -> Path:
    entries = adapter_runtime(files, "geo")
    entries["agents/interface.yaml"] = (ROOT / "skills" / "geo" / "agents" / "interface.yaml").read_bytes()
    entries["references/RESOLVER.md"] = (ROOT / "skills" / "RESOLVER.md").read_bytes()
    entries["references/routing-contract.md"] = (ROOT / "skills" / "geo" / "references" / "routing-contract.md").read_bytes()
    for skill_id in SKILLS:
        entries[f"manifests/{skill_id}.json"] = (ROOT / "skills" / skill_id / "manifest.json").read_bytes()
    entries["TARGET.md"] = f"# {target.title()} adapter\n\nInstall this directory as one GEO SEO Hub skill. Runtime contracts remain protocol 1.0.0.\n".encode()
    entries["PACKAGE-METADATA.json"] = json.dumps({"channel": "community", "license": "AGPL-3.0-only", "commercial_license_status": "inquiry_only", "kind": "target", "target": target}, indent=2, allow_nan=False).encode() + b"\n"
    entries["pyproject.toml"] = packaged_pyproject(entries)
    output = DIST / f"geo-seo-hub-{target}-community-{VERSION}.zip"
    zip_write(output, entries)
    return output


def build(target: str) -> list[Path]:
    files = tracked_files()
    outputs = []
    if target in {"generic", "all"}:
        outputs.extend([source_package(files), unified_package(files)])
        outputs.extend(provider_package(files, skill_id) for skill_id in SKILLS)
    if target in {"codex", "all"}:
        outputs.append(target_package(files, "codex"))
    if target in {"claude", "all"}:
        outputs.append(target_package(files, "claude"))
    return outputs


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", choices=("generic", "codex", "claude", "all"), default="all")
    parser.add_argument("--channel", choices=("community",), default="community")
    args = parser.parse_args()
    for path in build(args.target):
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
