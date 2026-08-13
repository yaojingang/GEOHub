from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

import pytest

from geo_seo_hub.quality.release import (
    build_production_readiness,
    build_provenance,
    build_sbom,
    verify_release_provenance,
)


ROOT = Path(__file__).resolve().parents[1]


def _clock():
    return datetime(2026, 8, 13, tzinfo=timezone.utc)


def test_local_provenance_binds_source_sbom_and_artifact_digests(tmp_path):
    artifact = tmp_path / "fixture.zip"
    artifact.write_bytes(b"release fixture")
    sbom = build_sbom(ROOT, clock=_clock)
    assert sbom["bomFormat"] == "CycloneDX"
    assert sbom["specVersion"] == "1.6"
    assert all(component["hashes"][0]["alg"] == "SHA-256" for component in sbom["components"])
    provenance = build_provenance(ROOT, [artifact], sbom, clock=_clock)
    result = verify_release_provenance(ROOT, provenance, sbom, artifact_root=tmp_path, expected_artifact_names={artifact.name})
    assert result["status"] == "pass"
    assert provenance["builder"] == {
        "identity": "local-unsigned",
        "trusted": False,
        "attestation_status": "missing evidence",
        "slsa_level_claim": None,
    }


def test_provenance_rejects_tampered_artifact_wrong_revision_and_forged_builder(tmp_path):
    artifact = tmp_path / "fixture.zip"
    artifact.write_bytes(b"release fixture")
    sbom = build_sbom(ROOT, clock=_clock)
    provenance = build_provenance(ROOT, [artifact], sbom, clock=_clock)

    artifact.write_bytes(b"tampered")
    with pytest.raises(ValueError, match="artifact digest"):
        verify_release_provenance(ROOT, provenance, sbom, artifact_root=tmp_path, expected_artifact_names={artifact.name})
    artifact.write_bytes(b"release fixture")

    wrong_revision = deepcopy(provenance)
    wrong_revision["source"]["revision"] = "0" * 40
    with pytest.raises(ValueError, match="source revision"):
        verify_release_provenance(ROOT, wrong_revision, sbom, artifact_root=tmp_path, expected_artifact_names={artifact.name})

    forged = deepcopy(provenance)
    forged["builder"]["trusted"] = True
    with pytest.raises(ValueError, match="trusted builder"):
        verify_release_provenance(ROOT, forged, sbom, artifact_root=tmp_path, expected_artifact_names={artifact.name})

    wrong_subject = deepcopy(provenance)
    wrong_subject["subject"]["version"] = "9.9.9"
    with pytest.raises(ValueError, match="subject identity"):
        verify_release_provenance(ROOT, wrong_subject, sbom, artifact_root=tmp_path, expected_artifact_names={artifact.name})


def test_provenance_rejects_missing_declared_dependency(tmp_path):
    artifact = tmp_path / "fixture.zip"
    artifact.write_bytes(b"release fixture")
    sbom = build_sbom(ROOT, clock=_clock)
    provenance = build_provenance(ROOT, [artifact], sbom, clock=_clock)
    incomplete = deepcopy(sbom)
    incomplete["components"] = incomplete["components"][:-1]
    with pytest.raises(ValueError, match="dependency inventory"):
        verify_release_provenance(ROOT, provenance, incomplete, artifact_root=tmp_path, expected_artifact_names={artifact.name})


def test_provenance_rejects_forged_sbom_facts_even_when_digest_is_resynchronized(tmp_path):
    artifact = tmp_path / "fixture.zip"
    artifact.write_bytes(b"release fixture")
    sbom = build_sbom(ROOT, clock=_clock)
    provenance = build_provenance(ROOT, [artifact], sbom, clock=_clock)
    forged = deepcopy(sbom)
    forged["components"][0]["version"] = "999.0-forged"
    forged["components"][0]["hashes"][0]["content"] = "0" * 64
    import hashlib
    import json

    provenance["sbom_sha256"] = hashlib.sha256(
        json.dumps(forged, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()
    with pytest.raises(ValueError, match="component facts"):
        verify_release_provenance(
            ROOT,
            provenance,
            forged,
            artifact_root=tmp_path,
            expected_artifact_names={artifact.name},
        )


def test_readiness_blocks_production_when_external_evidence_is_missing():
    readiness = build_production_readiness(
        deterministic_statuses={
            "output-eval": "pass",
            "package": "pass",
            "install": "pass",
            "provenance": "pass",
        },
        external_statuses={
            "human-blind-review": "missing evidence",
            "real-platform-benchmark": "missing evidence",
        },
        clock=_clock,
    )
    assert readiness["production_decision"] == "blocked"
    assert readiness["experimental_release_decision"] == "eligible"
    assert all({"owner", "evidence", "verification_command", "source_fix"} <= set(gate) for gate in readiness["gates"] if gate["status"] != "pass")
