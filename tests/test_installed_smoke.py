import json
import os
import site
import subprocess
import sys
from pathlib import Path

from geo_seo_hub.paths import repository_root


def _run(arguments, *, cwd, env):
    return subprocess.run(
        arguments,
        cwd=cwd,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )


def test_offline_wheel_install_runs_diagnose_outside_repository(tmp_path):
    root = repository_root()
    expected_version = (root / "VERSION").read_text(encoding="utf-8").strip()
    wheels = tmp_path / "wheels"
    wheels.mkdir()
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    environment["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"

    _run(
        [
            sys.executable,
            "-m",
            "pip",
            "wheel",
            ".",
            "--no-deps",
            "--no-build-isolation",
            "--no-index",
            "--wheel-dir",
            str(wheels),
        ],
        cwd=root,
        env=environment,
    )
    wheel = next(wheels.glob(f"geo_seo_hub-{expected_version}-*.whl"))
    virtualenv = tmp_path / "venv"
    _run(
        [sys.executable, "-m", "venv", "--system-site-packages", str(virtualenv)],
        cwd=tmp_path,
        env=environment,
    )
    python = virtualenv / "bin" / "python"
    console = virtualenv / "bin" / "geo-seo-hub"
    dependency_site = next(
        Path(candidate).resolve()
        for candidate in site.getsitepackages()
        if (Path(candidate) / "jsonschema").is_dir()
        and (Path(candidate) / "yaml").is_dir()
    )
    child_site = Path(
        _run(
            [str(python), "-c", "import site; print(site.getsitepackages()[0])"],
            cwd=tmp_path,
            env=environment,
        ).stdout.strip()
    )
    (child_site / "geo_seo_hub_test_dependencies.pth").write_text(
        f"{dependency_site}\n",
        encoding="utf-8",
    )
    _run(
        [
            str(python),
            "-m",
            "pip",
            "install",
            "--no-index",
            "--no-deps",
            "--ignore-installed",
            str(wheel),
        ],
        cwd=tmp_path,
        env=environment,
    )

    outside = tmp_path / "outside"
    outside.mkdir()
    data_check = _run(
        [
            str(python),
            "-c",
            (
                "import sys; from pathlib import Path; import geo_seo_hub; "
                "prefix=Path(sys.prefix).resolve(); "
                "assert Path(geo_seo_hub.__file__).resolve().is_relative_to(prefix); "
                "assert (prefix/'share/geo-seo-hub/registry/skills.yaml').is_file(); "
                "assert (prefix/'share/geo-seo-hub/skills/geo-diagnose/SKILL.md').is_file(); "
                "assert (prefix/'share/geo-seo-hub/skills/geo-content/SKILL.md').is_file(); "
                "assert (prefix/'share/geo-seo-hub/skills/geo-content/references/modes.md').is_file(); "
                "assert (prefix/'share/geo-seo-hub/skills/geo-measure/SKILL.md').is_file(); "
                "assert (prefix/'share/geo-seo-hub/skills/geo-measure/references/measurement-method.md').is_file(); "
                "print(prefix)"
            ),
        ],
        cwd=outside,
        env=environment,
    )
    assert data_check.stdout.strip() == str(virtualenv.resolve())

    version_payload = json.loads(
        _run([str(console), "--version"], cwd=outside, env=environment).stdout
    )
    assert version_payload == {
        "distribution": "geo-seo-hub",
        "name": "GEOHub",
        "version": expected_version,
    }

    runs_root = tmp_path / "installed-runs"
    completed = _run(
        [
            str(console),
            "diagnose",
            "--input",
            str(root / "tests" / "fixtures" / "diagnosis-page.json"),
            "--output",
            str(runs_root),
        ],
        cwd=outside,
        env=environment,
    )
    payload = json.loads(completed.stdout)
    run = Path(payload["output"])
    expected = {
        "input/diagnosis-brief.json",
        "input/sources/source-html-1.html",
            "diagnosis.json",
            "diagnosis-funnel.json",
            "report.md",
        "evidence-ledger.json",
        "query-map.json",
        "opportunity-map.json",
            "quality-report.json",
            "research-context.json",
            "run-manifest.json",
    }
    actual = {
        path.relative_to(run).as_posix()
        for path in run.rglob("*")
        if path.is_file()
    }
    assert actual == expected
    manifest = json.loads((run / "run-manifest.json").read_text(encoding="utf-8"))
    assert set(manifest["artifacts"]) == expected - {"run-manifest.json"}

    content_brief = outside / "content.json"
    content_brief.write_text(
        json.dumps({"mode": "explainer", "topic": "Installed content"}),
        encoding="utf-8",
    )
    content_completed = _run(
        [str(console), "content", "--input", str(content_brief), "--output", str(tmp_path / "content-runs")],
        cwd=outside,
        env=environment,
    )
    content_payload = json.loads(content_completed.stdout)
    content_run = Path(content_payload["output"])
    assert (content_run / "content.json").is_file()
    assert (content_run / "content.md").is_file()
    assert (content_run / "content.html").is_file()
    routed = json.loads(
        _run([str(console), "route", "--text", "Create an article-friendly draft"], cwd=outside, env=environment).stdout
    )
    assert routed["skill_id"] == "geo-content"

    measure_completed = _run(
        [
            str(console),
            "measure",
            "--input",
            str(root / "tests" / "fixtures" / "measurement-brief.json"),
            "--output",
            str(tmp_path / "measure-runs"),
        ],
        cwd=outside,
        env=environment,
    )
    measure_payload = json.loads(measure_completed.stdout)
    measure_run = Path(measure_payload["output"])
    assert (measure_run / "measurement-report.json").is_file()
    assert (measure_run / "research-context.json").is_file()
