#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
REPORTS = ROOT / "reports"
VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
MAX_ARCHIVE_MEMBERS = 4096
MAX_ARCHIVE_BYTES = 256 * 1024 * 1024


def safe_extract(archive_path: Path, destination: Path) -> None:
    with zipfile.ZipFile(archive_path) as archive:
        infos = archive.infolist()
        if len(infos) > MAX_ARCHIVE_MEMBERS or sum(info.file_size for info in infos) > MAX_ARCHIVE_BYTES:
            raise ValueError("archive exceeds safe extraction limits")
        for info in infos:
            member = PurePosixPath(info.filename)
            if member.is_absolute() or ".." in member.parts or "\\" in info.filename:
                raise ValueError(f"unsafe archive member: {info.filename}")
            mode = info.external_attr >> 16
            if mode and (mode & 0o170000) == 0o120000:
                raise ValueError(f"symlink archive member: {info.filename}")
        archive.extractall(destination)


def run(command: list[str], cwd: Path, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(command, cwd=cwd, env=env, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(f"command failed ({result.returncode}): {' '.join(command)}\nstdout: {result.stdout}\nstderr: {result.stderr}")
    return result


def prepare_wheelhouse(wheelhouse: Path, clean_env: dict[str, str]) -> None:
    wheelhouse.mkdir()
    run(
        [
            sys.executable,
            "-m",
            "pip",
            "wheel",
            "-w",
            str(wheelhouse),
            "jsonschema>=4.21,<5",
            "PyYAML>=6.0,<7",
            "setuptools>=68",
            "wheel",
        ],
        ROOT,
        clean_env,
    )


def install_extracted(source_root: Path, venv: Path, wheelhouse: Path, clean_env: dict[str, str]) -> Path:
    run([sys.executable, "-m", "venv", str(venv)], source_root, clean_env)
    python = venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    run([str(python), "-m", "pip", "install", "--no-index", "--find-links", str(wheelhouse), "."], source_root, clean_env)
    run([str(python), "-c", "from pathlib import Path; import sys, geo_seo_hub; assert Path(geo_seo_hub.__file__).resolve().is_relative_to(Path(sys.prefix).resolve())"], source_root, clean_env)
    return python


def source_smoke(source_zip: Path, temp_root: Path, wheelhouse: Path) -> dict:
    extracted = temp_root / "source"
    extracted.mkdir()
    safe_extract(source_zip, extracted)
    source_root = next(extracted.iterdir())
    clean_env = os.environ.copy()
    clean_env.pop("PYTHONPATH", None)
    clean_env["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
    venv = temp_root / "venv"
    python = install_extracted(source_root, venv, wheelhouse, clean_env)
    fixtures = temp_root / "fixtures"
    fixtures.mkdir()
    brief = fixtures / "brief.json"
    brief.write_text(json.dumps({"protocol_version":"1.0.0","brief_id":"synthetic-install","subject":"Synthetic knowledge base","locale":"en","seed_queries":["synthetic query"],"audiences":["tester"],"scenarios":["test"],"competitors":[],"evidence":[]}, allow_nan=False), encoding="utf-8")
    diagnosis = fixtures / "diagnosis.json"
    diagnosis.write_text(json.dumps({"subject":"Synthetic brand","scope":"brand","evidence":[{"evidence_id":"synthetic","claim":"Synthetic brand has a documented page.","source_uri":"https://example.invalid/synthetic"}]}, allow_nan=False), encoding="utf-8")
    content = fixtures / "content.json"
    content.write_text(json.dumps({"mode":"explainer","topic":"Synthetic GEO topic","evidence":[],"desired_formats":["markdown","json","html"]}, allow_nan=False), encoding="utf-8")
    runs = temp_root / "runs"
    commands = [
        [str(python), "-m", "geo_seo_hub", "--version"],
        [str(python), "-m", "geo_seo_hub", "route", "--text", "Discover AI search questions"],
        [str(python), "-m", "geo_seo_hub", "discover", "--input", str(brief), "--output", str(runs)],
        [str(python), "-m", "geo_seo_hub", "diagnose", "--input", str(diagnosis), "--output", str(runs)],
        [str(python), "-m", "geo_seo_hub", "content", "--input", str(content), "--output", str(runs)],
    ]
    results = [run(command, temp_root, clean_env) for command in commands]
    version_payload = json.loads(results[0].stdout)
    if version_payload != {
        "distribution": "geo-seo-hub",
        "name": "GEO SEO Hub",
        "version": VERSION,
    }:
        raise ValueError(f"installed CLI version mismatch: {version_payload}")
    return {
        "package": source_zip.name,
        "installed_from": ".",
        "cli_smokes": ["version", "route", "discover", "diagnose", "content"],
        "status": "pass",
    }


def structural_smoke(path: Path, temp_root: Path, wheelhouse: Path) -> dict:
    destination = temp_root / path.stem
    destination.mkdir()
    safe_extract(path, destination)
    skill_files = list(destination.rglob("SKILL.md"))
    registry = list(destination.rglob("registry/skills.yaml"))
    schemas = list(destination.rglob("schemas/*.schema.json"))
    if len(skill_files) != 1 or not registry or not schemas:
        raise ValueError(f"structure smoke failed for {path.name}")
    skill_text = skill_files[0].read_text(encoding="utf-8")
    referenced = set(re.findall(r"(?:scripts|references)/[A-Za-z0-9_.\-/]+", skill_text))
    missing = [relative for relative in sorted(referenced) if not (skill_files[0].parent / relative).is_file()]
    if missing:
        raise ValueError(f"entry references missing packaged files for {path.name}: {missing}")
    wrappers = {wrapper.name: wrapper for wrapper in destination.glob("scripts/run_*.py")}
    expected_wrappers = {"run_route.py", "run_discover.py", "run_diagnose.py", "run_content.py"}
    if set(wrappers) != expected_wrappers:
        raise ValueError(f"expected provider wrappers in {path.name}; found {sorted(wrappers)}")
    clean_env = os.environ.copy()
    clean_env.pop("PYTHONPATH", None)
    clean_env["PYTHONNOUSERSITE"] = "1"
    venv = temp_root / "package-venvs" / path.stem
    venv.parent.mkdir(exist_ok=True)
    python = install_extracted(destination, venv, wheelhouse, clean_env)
    prefix_run = run([str(python), "-c", "import sys; print(sys.prefix)"], destination, clean_env)
    installed_root = Path(prefix_run.stdout.strip()) / "share" / "geo-seo-hub"
    installed_registry = installed_root / "registry" / "skills.yaml"
    installed_skill = installed_root / "SKILL.md"
    if not installed_registry.is_file() or not installed_skill.is_file():
        raise ValueError(f"installed runtime data is missing for {path.name}: {installed_root}")
    wrappers = {wrapper.name: wrapper for wrapper in installed_root.glob("scripts/run_*.py")}
    if set(wrappers) != expected_wrappers:
        raise ValueError(f"installed provider wrappers missing in {path.name}: {sorted(wrappers)}")
    fixtures = {
        "geo-discover": destination / "install-discover.json",
        "geo-diagnose": destination / "install-diagnose.json",
        "geo-content": destination / "install-content.json",
    }
    fixtures["geo-discover"].write_text(json.dumps({"protocol_version":"1.0.0","brief_id":"zip-install","subject":"Synthetic ZIP install","locale":"zh-CN","seed_queries":["拓词"],"audiences":["tester"],"scenarios":["install"],"competitors":[],"evidence":[]}, allow_nan=False), encoding="utf-8")
    fixtures["geo-diagnose"].write_text(json.dumps({"subject":"Synthetic ZIP install","scope":"brand","evidence":[{"evidence_id":"zip-install","claim":"Synthetic evidence for install smoke.","source_uri":"https://example.invalid/install"}]}, allow_nan=False), encoding="utf-8")
    fixtures["geo-content"].write_text(json.dumps({"mode":"explainer","topic":"Synthetic ZIP install","evidence":[],"desired_formats":["markdown","json","html"]}, allow_nan=False), encoding="utf-8")
    runs = destination / "install-runs"
    routed = {
        "geo-discover": ("Discover AI search questions", "run_discover.py"),
        "geo-diagnose": ("Audit this website", "run_diagnose.py"),
        "geo-content": ("Write an explainer", "run_content.py"),
    }
    resolved_entries = []
    provider_executions = []
    for skill_id, (route_text, wrapper_name) in routed.items():
        route_run = run([str(python), str(wrappers["run_route.py"]), "--text", route_text], destination, clean_env)
        route_result = json.loads(route_run.stdout)
        entry = installed_root / route_result["entry"]
        if route_result["skill_id"] != skill_id or not entry.is_file():
            raise ValueError(f"route entry resolution failed for {path.name}: {route_result}")
        entry_text = entry.read_text(encoding="utf-8")
        entry_references = set(re.findall(r"(?:references|scripts)/[A-Za-z0-9_.\-/]+", entry_text))
        missing_entry_references = sorted(relative for relative in entry_references if not (installed_root / relative).is_file())
        if missing_entry_references:
            raise ValueError(f"routed entry references missing resources for {path.name}: {missing_entry_references}")
        provider_run = run([str(python), str(wrappers[wrapper_name]), "--input", str(fixtures[skill_id]), "--output", str(runs)], destination, clean_env)
        provider_result = json.loads(provider_run.stdout)
        if provider_result.get("status") not in {"completed", "completed-with-warnings"}:
            raise ValueError(f"provider wrapper execution failed for {path.name}: {provider_result}")
        resolved_entries.append(route_result["entry"])
        provider_executions.append(skill_id)
    return {"package": path.name, "installed_from": ".", "entries": resolved_entries, "resolved_entry": True, "installed_share_resolved": True, "provider_executions": provider_executions, "runtime_data": True, "status": "pass"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", choices=("all",), default="all")
    parser.parse_args()
    source = DIST / f"geo-seo-hub-source-{VERSION}.zip"
    packages = sorted(path for path in DIST.glob("*.zip") if path.name != source.name)
    with tempfile.TemporaryDirectory(prefix="geo-seo-hub-install-") as raw:
        temp_root = Path(raw)
        clean_env = os.environ.copy()
        clean_env.pop("PYTHONPATH", None)
        clean_env["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
        wheelhouse = temp_root / "wheelhouse"
        prepare_wheelhouse(wheelhouse, clean_env)
        source_result = source_smoke(source, temp_root, wheelhouse)
        structural = [structural_smoke(path, temp_root, wheelhouse) for path in packages]
    report = {"status": "pass", "target": "all", "source": source_result, "structural_packages": structural, "scratch_retained": False}
    REPORTS.mkdir(exist_ok=True)
    (REPORTS / "install-simulation.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    lines = ["# Install Simulation", "", "Status: **pass**", "", f"Fresh source install and CLI smokes: {', '.join(source_result['cli_smokes'])}.", f"Fresh per-ZIP `pip install .`, route-entry resolution, and provider executions: {len(structural)}.", "Temporary install roots were removed."]
    (REPORTS / "install-simulation.md").write_text("\n\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"status": "pass", "source_cli_smokes": len(source_result["cli_smokes"]), "structural_packages": len(structural)}, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
