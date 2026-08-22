from __future__ import annotations

import hashlib
import importlib.metadata
import json
import re
import stat
import subprocess
import tomllib
import zipfile
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable

from ..version import package_version
from ..release_manifest import is_release_source


Clock = Callable[[], datetime]
def _canonical_bytes(payload: object) -> bytes:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(64 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def release_source_inventory(root: Path) -> dict[str, str]:
    result = subprocess.run(["git", "ls-files", "-z", "--cached"], cwd=root, check=True, capture_output=True)
    inventory: dict[str, str] = {}
    for raw in result.stdout.split(b"\0"):
        if not raw:
            continue
        relative = Path(raw.decode())
        if not is_release_source(relative):
            continue
        staged = subprocess.run(
            ["git", "show", f":{relative.as_posix()}"],
            cwd=root,
            check=True,
            capture_output=True,
        ).stdout
        inventory[relative.as_posix()] = hashlib.sha256(staged).hexdigest()
    return inventory


def _generated_at(clock: Clock | None) -> str:
    now = (clock or (lambda: datetime.now(timezone.utc)))()
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    return now.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _declared_dependencies(root: Path) -> list[tuple[str, str]]:
    project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    dependencies = []
    for requirement in project.get("dependencies", []):
        match = re.match(r"\s*([A-Za-z0-9_.-]+)\s*(.*)", requirement)
        if match is None:
            raise ValueError(f"unsupported dependency expression: {requirement}")
        dependencies.append((match.group(1), match.group(2)))
    return dependencies


def _distribution_digest(distribution: importlib.metadata.Distribution) -> str:
    digest = hashlib.sha256()
    files = sorted(
        (
            item for item in (distribution.files or ())
            if "__pycache__" not in item.parts and item.suffix != ".pyc"
        ),
        key=lambda item: item.as_posix(),
    )
    if not files:
        raise ValueError(f"installed dependency has no verifiable files: {distribution.metadata.get('Name', 'unknown')}")
    for relative in files:
        path = Path(distribution.locate_file(relative))
        if not path.is_file():
            continue
        digest.update(relative.as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def build_sbom(root: Path, *, clock: Clock | None = None) -> dict:
    components = []
    for declared_name, constraint in _declared_dependencies(root):
        try:
            distribution = importlib.metadata.distribution(declared_name)
        except importlib.metadata.PackageNotFoundError as exc:
            raise ValueError(f"declared dependency is not installed: {declared_name}") from exc
        metadata = distribution.metadata
        canonical_name = metadata.get("Name", declared_name)
        license_expression = metadata.get("License-Expression") or metadata.get("License") or "NOASSERTION"
        purl = f"pkg:pypi/{canonical_name.casefold().replace('_', '-')}@{distribution.version}"
        components.append(
            {
                "type": "library",
                "bom-ref": purl,
                "name": canonical_name,
                "version": distribution.version,
                "purl": purl,
                "licenses": [{"license": {"name": license_expression}}],
                "hashes": [{"alg": "SHA-256", "content": _distribution_digest(distribution)}],
                "properties": [
                    {"name": "geohub:declared-constraint", "value": constraint},
                    {"name": "geohub:hash-scope", "value": "installed distribution file set"},
                ],
            }
        )
    root_ref = f"pkg:pypi/geo-seo-hub@{package_version()}"
    serial_seed = hashlib.sha256(_canonical_bytes([(item["name"], item["version"]) for item in components])).hexdigest()
    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.6",
        "serialNumber": f"urn:uuid:{serial_seed[:8]}-{serial_seed[8:12]}-4{serial_seed[13:16]}-a{serial_seed[17:20]}-{serial_seed[20:32]}",
        "version": 1,
        "metadata": {
            "timestamp": _generated_at(clock),
            "tools": {"components": [{"type": "application", "name": "geo-seo-hub release tooling", "version": package_version()}]},
            "component": {"type": "application", "bom-ref": root_ref, "name": "geo-seo-hub", "version": package_version(), "licenses": [{"license": {"id": "AGPL-3.0-only"}}]},
        },
        "components": sorted(components, key=lambda item: item["name"].casefold()),
        "dependencies": [{"ref": root_ref, "dependsOn": sorted(item["bom-ref"] for item in components)}],
        "properties": [{"name": "geohub:dependency-resolution", "value": "current verified build environment"}],
    }


def release_source_digest(root: Path) -> str:
    inventory = release_source_inventory(root)
    digest = hashlib.sha256()
    for relative, file_digest in sorted(inventory.items()):
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(file_digest.encode("ascii"))
        digest.update(b"\0")
    return digest.hexdigest()


def _verify_source_archive(root: Path, artifact_root: Path, expected_names: set[str]) -> None:
    version = package_version()
    name = f"geo-seo-hub-source-{version}.zip"
    if name not in expected_names:
        return
    expected_inventory = release_source_inventory(root)
    prefix = f"geo-seo-hub-{version}/"
    try:
        with zipfile.ZipFile(artifact_root / name) as archive:
            members = {
                info.filename.removeprefix(prefix): hashlib.sha256(archive.read(info)).hexdigest()
                for info in archive.infolist()
                if not info.is_dir() and info.filename.startswith(prefix)
            }
    except (OSError, zipfile.BadZipFile) as exc:
        raise ValueError("source archive cannot be verified") from exc
    if members != expected_inventory:
        raise ValueError("source archive inventory does not match the staged source snapshot")


def source_revision(root: Path) -> str:
    source_paths = sorted(release_source_inventory(root))
    if not source_paths:
        raise ValueError("release source inventory is empty")
    return subprocess.run(
        ["git", "log", "-1", "--format=%H", "--", *source_paths],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def source_snapshot_state(root: Path) -> str:
    staged = subprocess.run(
        ["git", "diff", "--cached", "--quiet"],
        cwd=root,
        check=False,
    )
    if staged.returncode not in {0, 1}:
        raise ValueError("unable to determine staged source state")
    return "committed release source snapshot" if staged.returncode == 0 else "staged release candidate snapshot"


def build_provenance(
    root: Path,
    artifacts: Iterable[Path],
    sbom: dict,
    *,
    clock: Clock | None = None,
) -> dict:
    artifact_records = [
        {"name": path.name, "sha256": sha256_file(path), "size_bytes": path.stat().st_size}
        for path in sorted((Path(item) for item in artifacts), key=lambda item: item.name)
    ]
    if not artifact_records:
        raise ValueError("provenance requires at least one release artifact")
    return {
        "schema_version": "1.0.0",
        "generated_at": _generated_at(clock),
        "subject": {"name": "geo-seo-hub", "version": package_version(), "artifacts": artifact_records},
        "source": {
            "revision": source_revision(root),
            "source_digest": release_source_digest(root),
            "state": source_snapshot_state(root),
        },
        "builder": {
            "identity": "local-unsigned",
            "trusted": False,
            "attestation_status": "missing evidence",
            "slsa_level_claim": None,
        },
        "build": {
            "command": ["python", "scripts/package.py", "--target", "all", "--channel", "community"],
            "package_count": len(artifact_records),
            "network_requirement": "dependency installation only; package build is offline",
        },
        "sbom_sha256": hashlib.sha256(_canonical_bytes(sbom)).hexdigest(),
        "verification": {"command": ["python", "scripts/verify_provenance.py"], "status": "pending independent verification"},
    }


def verify_release_provenance(
    root: Path,
    provenance: dict,
    sbom: dict,
    *,
    artifact_root: Path,
    expected_artifact_names: set[str] | frozenset[str],
) -> dict:
    if provenance.get("schema_version") != "1.0.0":
        raise ValueError("provenance schema version mismatch")
    builder = provenance.get("builder", {})
    if builder.get("trusted") is not False or builder.get("identity") != "local-unsigned":
        raise ValueError("trusted builder claim lacks a verifiable CI attestation")
    declared = {name.casefold().replace("_", "-") for name, _ in _declared_dependencies(root)}
    observed = {str(item.get("name", "")).casefold().replace("_", "-") for item in sbom.get("components", [])}
    if declared != observed:
        raise ValueError(f"dependency inventory mismatch: declared={sorted(declared)}, observed={sorted(observed)}")
    if sbom.get("bomFormat") != "CycloneDX" or sbom.get("specVersion") != "1.6":
        raise ValueError("SBOM format mismatch")
    expected_sbom = build_sbom(root)
    supplied_semantic = deepcopy(sbom)
    expected_semantic = deepcopy(expected_sbom)
    supplied_semantic.get("metadata", {}).pop("timestamp", None)
    expected_semantic.get("metadata", {}).pop("timestamp", None)
    if supplied_semantic != expected_semantic:
        raise ValueError("SBOM component facts do not match the verified build environment")
    current_version = package_version()
    if sbom.get("metadata", {}).get("component", {}).get("version") != current_version:
        raise ValueError("SBOM component version mismatch")
    expected_sbom_digest = hashlib.sha256(_canonical_bytes(sbom)).hexdigest()
    if provenance.get("sbom_sha256") != expected_sbom_digest:
        raise ValueError("SBOM digest mismatch")
    current_revision = source_revision(root)
    if provenance.get("source", {}).get("revision") != current_revision:
        raise ValueError("source revision mismatch")
    if provenance.get("source", {}).get("source_digest") != release_source_digest(root):
        raise ValueError("source digest mismatch")
    artifact_records = provenance.get("subject", {}).get("artifacts", [])
    if not artifact_records:
        raise ValueError("artifact inventory is empty")
    if provenance.get("subject", {}).get("name") != "geo-seo-hub" or provenance.get("subject", {}).get("version") != current_version:
        raise ValueError("provenance subject identity mismatch")
    expected_names = set(expected_artifact_names)
    if not expected_names:
        raise ValueError("expected artifact inventory is empty")
    if len(artifact_records) != len(expected_names):
        raise ValueError(f"artifact inventory count mismatch: expected {len(expected_names)}, found {len(artifact_records)}")
    if provenance.get("build", {}).get("package_count") != len(artifact_records):
        raise ValueError("provenance build package count mismatch")
    artifact_names = [record.get("name") for record in artifact_records]
    if len(artifact_names) != len(set(artifact_names)):
        raise ValueError("artifact inventory contains duplicate names")
    disk_names = {path.name for path in artifact_root.glob("*.zip") if path.is_file() and not path.is_symlink()}
    if set(artifact_names) != expected_names or disk_names != expected_names:
        raise ValueError("artifact inventory name set mismatch")
    _verify_source_archive(root, artifact_root, expected_names)
    for record in artifact_records:
        name = record.get("name")
        if (
            not isinstance(name, str)
            or Path(name).name != name
            or re.fullmatch(r"[0-9a-f]{64}", str(record.get("sha256", ""))) is None
            or isinstance(record.get("size_bytes"), bool)
            or not isinstance(record.get("size_bytes"), int)
            or record["size_bytes"] < 1
        ):
            raise ValueError("artifact name is unsafe")
        path = artifact_root / name
        try:
            metadata = path.lstat()
        except OSError as exc:
            raise ValueError(f"artifact digest mismatch: {name}") from exc
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode) or sha256_file(path) != record.get("sha256"):
            raise ValueError(f"artifact digest mismatch: {name}")
        if path.stat().st_size != record.get("size_bytes"):
            raise ValueError(f"artifact size mismatch: {name}")
    return {
        "status": "pass",
        "artifact_count": len(artifact_records),
        "source_revision": current_revision,
        "builder_trust": "local-unsigned",
        "slsa_level_claim": None,
    }


_GATE_GUIDANCE = {
    "output-eval": ("evaluation owner", "reports/eval-summary.json", "python scripts/run_evals.py", "Restore all output and router gates."),
    "package": ("release owner", "reports/package-verification.json", "python scripts/verify_packages.py", "Rebuild and verify all eleven archives."),
    "install": ("release owner", "reports/install-simulation.json", "python scripts/install_simulation.py --target all", "Restore fresh-install and provider wrapper smokes."),
    "provenance": ("release owner", "reports/release-provenance-verification.json", "python scripts/verify_provenance.py", "Regenerate source, SBOM, and artifact provenance."),
    "sbom": ("release owner", "reports/release-sbom.json", "python scripts/generate_sbom.py", "Restore the complete declared dependency inventory."),
    "trust-and-permissions": ("security owner", "reports/yao-meta-gates.json", "python scripts/run_yao_meta_gates.py --verify-existing", "Resolve trust, permission, or unclassified review gates."),
    "ci-attestation": ("release owner", "GitHub artifact attestation", "gh attestation verify <artifact> -R yaojingang/geo-seo-hub", "Run the attested release workflow and preserve external verification evidence."),
    "human-blind-review": ("evaluation owner", "reports/output-blind-pack.json", "python scripts/adjudicate_output_review.py", "Collect independent reviewer decisions."),
    "real-platform-benchmark": ("GEO measurement owner", "approved live observation bundle", "python scripts/run_quality_lab.py --execution-mode provider", "Run an approved multi-engine benchmark."),
    "adoption-evidence": ("operations owner", "privacy-approved aggregate", "python scripts/aggregate_adoption_drift.py", "Collect governed real-usage metadata."),
    "commercial-legal-review": ("repository owner", "qualified legal decision", "python scripts/verify_repository.py", "Complete legal review before enabling external contributions or commercial terms."),
    "strategy-external-effect": ("strategy owner", "verified publication and post-window measurement", "geo-seo-hub measure --input <bundle> --output <runs>", "Run a governed external intervention observation."),
    "knowledge-production-eval": ("knowledge owner", "reviewed production graph task set", "python -m pytest tests/test_knowledge.py", "Evaluate real graph tasks with human-reviewed labels."),
}


def build_production_readiness(
    *,
    deterministic_statuses: dict[str, str],
    external_statuses: dict[str, str],
    clock: Clock | None = None,
) -> dict:
    gates = []
    for name, status in sorted({**deterministic_statuses, **external_statuses}.items()):
        owner, evidence, command, fix = _GATE_GUIDANCE.get(
            name,
            ("release owner", f"reports/{name}.json", "python scripts/verify_all.py", f"Resolve the {name} gate and regenerate evidence."),
        )
        gates.append(
            {
                "name": name,
                "status": status,
                "owner": owner,
                "evidence": evidence,
                "verification_command": command,
                "source_fix": "none; deterministic gate passed" if status == "pass" else fix,
            }
        )
    deterministic_pass = bool(deterministic_statuses) and all(status == "pass" for status in deterministic_statuses.values())
    production_pass = deterministic_pass and bool(external_statuses) and all(status == "pass" for status in external_statuses.values())
    return {
        "schema_version": "1.0.0",
        "generated_at": _generated_at(clock),
        "product": {"name": "GEO SEO Hub", "version": package_version(), "maturity": "Experimental"},
        "production_decision": "pass" if production_pass else "blocked",
        "experimental_release_decision": "eligible" if deterministic_pass else "blocked",
        "gates": gates,
        "summary": {
            "pass": sum(item["status"] == "pass" for item in gates),
            "missing_evidence": sum(item["status"] == "missing evidence" for item in gates),
            "blocked": sum(item["status"] not in {"pass", "missing evidence"} for item in gates),
        },
        "claims": {
            "trusted_builder": False,
            "slsa_level": None,
            "external_effect": "missing evidence",
        },
    }
