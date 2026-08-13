import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from geo_seo_hub.data_retention import apply_retention_policy, purge_batch, recover_batch


NOW = datetime(2026, 8, 12, 12, 0, tzinfo=timezone.utc)


def _write_run(runs_root: Path, run_id: str, age_days: int, data_class: str = "L2") -> Path:
    run = runs_root / run_id
    run.mkdir(parents=True)
    created_at = (NOW - timedelta(days=age_days)).isoformat().replace("+00:00", "Z")
    (run / "run-manifest.json").write_text(
        json.dumps({"run_id": run_id, "created_at": created_at}),
        encoding="utf-8",
    )
    (run / "retention-policy.json").write_text(
        json.dumps({"data_class": data_class}),
        encoding="utf-8",
    )
    (run / "payload.txt").write_text("recoverable", encoding="utf-8")
    return run


def test_retention_defaults_to_dry_run_then_moves_to_recoverable_trash(tmp_path):
    runs_root = tmp_path / "runs"
    runs_root.mkdir()
    expired = _write_run(runs_root, "run-expired", 31)
    current = _write_run(runs_root, "run-current", 10)

    preview = apply_retention_policy(runs_root, now=NOW, confirm=False)
    assert preview["status"] == "dry-run"
    assert preview["targets"] == ["run-expired"]
    assert expired.is_dir() and current.is_dir()

    moved = apply_retention_policy(runs_root, now=NOW, confirm=True)
    assert moved["status"] == "moved-to-trash"
    assert moved["batch_id"]
    assert not expired.exists() and current.is_dir()
    batch = runs_root / ".geohub-trash" / moved["batch_id"]
    assert (batch / "runs/run-expired/payload.txt").read_text() == "recoverable"
    manifest = json.loads((batch / "recover-manifest.json").read_text())
    assert manifest["runs"] == ["run-expired"]

    recovered = recover_batch(runs_root, moved["batch_id"])
    assert recovered["status"] == "recovered"
    assert (runs_root / "run-expired/payload.txt").read_text() == "recoverable"
    assert not batch.exists()


def test_purge_requires_seven_day_grace_and_second_confirmation(tmp_path):
    runs_root = tmp_path / "runs"
    runs_root.mkdir()
    _write_run(runs_root, "run-expired", 31)
    moved = apply_retention_policy(runs_root, now=NOW, confirm=True)

    with pytest.raises(ValueError, match="7-day grace"):
        purge_batch(runs_root, moved["batch_id"], now=NOW + timedelta(days=6), confirm=True)
    with pytest.raises(ValueError, match="explicit confirmation"):
        purge_batch(runs_root, moved["batch_id"], now=NOW + timedelta(days=8), confirm=False)

    purged = purge_batch(runs_root, moved["batch_id"], now=NOW + timedelta(days=8), confirm=True)
    assert purged == {"status": "purged", "batch_id": moved["batch_id"], "run_count": 1}
    assert not (runs_root / ".geohub-trash" / moved["batch_id"]).exists()


def test_retention_rejects_symlink_run_and_broad_root(tmp_path):
    runs_root = tmp_path / "runs"
    runs_root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (runs_root / "run-link").symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match="symlink"):
        apply_retention_policy(runs_root, now=NOW, confirm=False)
    with pytest.raises(ValueError, match="broad"):
        apply_retention_policy(Path("/"), now=NOW, confirm=False)


def test_retention_recovers_crashed_staging_journal_before_next_scan(tmp_path):
    runs_root = tmp_path / "runs"
    runs_root.mkdir()
    run = _write_run(runs_root, "run-crashed", 31)
    batch_id = "batch-20260812T120000Z-1234abcd"
    staging = runs_root / ".geohub-trash" / f".{batch_id}.staging"
    (staging / "runs").mkdir(parents=True)
    manifest = {
        "protocol_version": "1.0.0",
        "batch_id": batch_id,
        "moved_at": "2026-08-12T12:00:00Z",
        "source": ".",
        "runs": ["run-crashed"],
    }
    (staging / "recover-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    run.rename(staging / "runs" / "run-crashed")

    preview = apply_retention_policy(runs_root, now=NOW, confirm=False)
    assert preview["targets"] == ["run-crashed"]
    assert (runs_root / "run-crashed/payload.txt").is_file()
    assert not staging.exists()


def test_recovery_resumes_after_crash_with_split_batch_state(tmp_path):
    runs_root = tmp_path / "runs"
    runs_root.mkdir()
    _write_run(runs_root, "run-one", 31)
    _write_run(runs_root, "run-two", 31)
    moved = apply_retention_policy(runs_root, now=NOW, confirm=True)
    batch = runs_root / ".geohub-trash" / moved["batch_id"]
    marker = {"protocol_version": "1.0.0", "batch_id": moved["batch_id"], "runs": ["run-one", "run-two"]}
    (batch / "recovery-in-progress.json").write_text(json.dumps(marker), encoding="utf-8")
    (batch / "runs" / "run-one").rename(runs_root / "run-one")

    rolled_back = recover_batch(runs_root, moved["batch_id"])
    assert rolled_back == {"status": "recovery-rolled-back", "batch_id": moved["batch_id"], "run_count": 2}
    assert not (runs_root / "run-one").exists()
    assert not (runs_root / "run-two").exists()
    result = recover_batch(runs_root, moved["batch_id"])
    assert result["run_count"] == 2
    assert (runs_root / "run-one").is_dir()
    assert (runs_root / "run-two").is_dir()
