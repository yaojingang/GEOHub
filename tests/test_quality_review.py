import json
from datetime import datetime, timezone

from geo_seo_hub.quality.review import adjudicate_review


def _review_artifacts():
    pack_pairs = []
    key_pairs = []
    decisions = []
    reviewed_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    for index in range(20):
        pair_id = f"pair-{index + 1:02d}"
        with_skill_variant = "A" if index % 2 == 0 else "B"
        pack_pairs.append(
            {
                "pair_id": pair_id,
                "task_id": f"task-{index % 5}",
                "variant_a": {"answer": "A"},
                "variant_b": {"answer": "B"},
                "rubric": "Prefer contract and evidence quality.",
            }
        )
        key_pairs.append(
            {
                "pair_id": pair_id,
                "task_id": f"task-{index % 5}",
                "with_skill_variant": with_skill_variant,
            }
        )
        decisions.append(
            {
                "pair_id": pair_id,
                "reviewer": "reviewer-primary",
                "reviewed_at": reviewed_at,
                "winner_variant": with_skill_variant,
                "confidence": 0.9,
                "reason": "The selected variant follows the evidence and output contract.",
            }
        )
        if index < 4:
            decisions.append(
                {
                    "pair_id": pair_id,
                    "reviewer": "reviewer-secondary",
                    "reviewed_at": reviewed_at,
                    "winner_variant": with_skill_variant,
                    "confidence": 0.8,
                    "reason": "Independent review reached the same rubric-based decision.",
                }
            )
    pack = {"protocol_version": "1.0.0", "suite_id": "suite-v1", "pairs": pack_pairs}
    key = {"protocol_version": "1.0.0", "suite_id": "suite-v1", "pairs": key_pairs}
    ledger = {"protocol_version": "1.0.0", "suite_id": "suite-v1", "decisions": decisions}
    return pack, key, ledger


def test_adjudication_counts_real_reviewers_and_second_reviewer_coverage(tmp_path):
    pack, key, decisions = _review_artifacts()
    eval_result = {
        "protocol_version": "1.0.0",
        "suite_id": "suite-v1",
        "human_review": {
            "status": "missing-evidence",
            "reviewed_pairs": 0,
            "pending_pairs": 20,
            "with_skill_win_rate": None,
            "second_reviewer_coverage": 0.0,
            "cohen_kappa": None,
        },
    }

    report = adjudicate_review(pack, key, decisions, eval_result=eval_result)

    assert report["status"] == "completed"
    assert report["reviewed_pairs"] == 20
    assert report["pending_pairs"] == 0
    assert report["with_skill_win_rate"] == 1.0
    assert report["second_reviewer_coverage"] == 0.2
    assert report["cohen_kappa"] == 1.0
    assert eval_result["human_review"] == {
        "status": "completed",
        "reviewed_pairs": 20,
        "pending_pairs": 0,
        "with_skill_win_rate": 1.0,
        "second_reviewer_coverage": 0.2,
        "cohen_kappa": 1.0,
    }


def test_adjudication_rejects_decision_without_rubric_reason():
    pack, key, decisions = _review_artifacts()
    decisions["decisions"][0]["reason"] = " "

    try:
        adjudicate_review(pack, key, decisions)
    except ValueError as exc:
        assert "reason" in str(exc)
    else:
        raise AssertionError("decision without reason must be rejected")


def test_single_reviewer_cannot_complete_independent_review_gate():
    pack, key, decisions = _review_artifacts()
    decisions["decisions"] = [item for item in decisions["decisions"] if item["reviewer"] == "reviewer-primary"]
    report = adjudicate_review(pack, key, decisions)
    assert report["reviewed_pairs"] == 20
    assert report["second_reviewer_coverage"] == 0.0
    assert report["cohen_kappa"] is None
    assert report["status"] == "warn"
