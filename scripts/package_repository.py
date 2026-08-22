#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import os
import stat
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
OUTPUT = ROOT / "dist" / f"geo-seo-hub-source-{VERSION}.zip"


def isolated_git_environment(root: Path) -> dict[str, str]:
    environment = os.environ.copy()
    for name in (
        "GIT_ALTERNATE_OBJECT_DIRECTORIES",
        "GIT_COMMON_DIR",
        "GIT_DIR",
        "GIT_OBJECT_DIRECTORY",
        "GIT_WORK_TREE",
    ):
        environment.pop(name, None)
    if root.resolve() != ROOT.resolve():
        environment.pop("GIT_INDEX_FILE", None)
    return environment


def load_current_packager():
    spec = importlib.util.spec_from_file_location("geo_seo_hub_current_packager", ROOT / "scripts" / "package.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


def trusted_files(root: Path) -> list[Path]:
    root_mode = root.lstat().st_mode
    if root.is_symlink() or not stat.S_ISDIR(root_mode):
        raise ValueError(f"package root must be a regular directory: {root}")
    root_resolved = root.resolve()
    result = subprocess.run(
        ["git", "ls-files", "-z", "--cached"],
        cwd=root,
        env=isolated_git_environment(root),
        check=True,
        capture_output=True,
    )
    files: list[Path] = []
    for raw_path in result.stdout.split(b"\0"):
        if not raw_path:
            continue
        relative = Path(os.fsdecode(raw_path))
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError(f"unsafe tracked path: {relative}")
        for parent in reversed(relative.parents):
            if parent == Path("."):
                continue
            parent_path = root / parent
            parent_mode = parent_path.lstat().st_mode
            if parent_path.is_symlink() or not stat.S_ISDIR(parent_mode):
                raise ValueError(f"tracked package parent must be a regular directory: {parent}")
        path = root / relative
        mode = path.lstat().st_mode
        if path.is_symlink() or not stat.S_ISREG(mode):
            raise ValueError(f"tracked package entry must be a regular file: {relative}")
        resolved = path.resolve()
        if root_resolved not in resolved.parents:
            raise ValueError(f"tracked package entry escapes package root: {relative}")
        files.append(relative)
    files = sorted(files, key=lambda path: path.as_posix())
    if root.resolve() == ROOT.resolve():
        allowed = set(load_current_packager().tracked_files())
        files = [path for path in files if path in allowed]
    return files


def build_archive(root: Path, output: Path) -> list[Path]:
    files = trusted_files(root)
    output.parent.mkdir(parents=True, exist_ok=True)
    version = (root / "VERSION").read_text(encoding="utf-8").strip()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for relative in files:
            path = root / relative
            info = zipfile.ZipInfo(
                f"geo-seo-hub-{version}/{relative.as_posix()}",
                date_time=(2026, 8, 8, 0, 0, 0),
            )
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, path.read_bytes())
    return files


def main() -> int:
    subprocess.run([sys.executable, "scripts/verify_repository.py"], cwd=ROOT, check=True)
    build_archive(ROOT, OUTPUT)
    print(OUTPUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
