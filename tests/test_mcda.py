from __future__ import annotations

import math

import pytest

from geo_seo_hub.intelligence.content.mcda import evaluate_mcda


CRITERIA = [
    {"name": "quality", "weight": 0.7, "polarity": "benefit"},
    {"name": "cost", "weight": 0.3, "polarity": "cost"},
]


def test_mcda_outputs_reconstructable_weighted_sum_topsis_and_sensitivity():
    matrix = {"A": {"quality": 90, "cost": 30}, "B": {"quality": 80, "cost": 20}}
    report = evaluate_mcda(matrix, CRITERIA)
    assert report["winner"] in {"A", "B"}
    assert set(report) >= {"raw_matrix", "normalized_matrix", "weights", "weighted_sum", "topsis", "sensitivity"}
    for row in report["weighted_sum"]:
        reconstructed = sum(
            report["normalized_matrix"][row["entity"]][criterion] * report["weights"][criterion]
            for criterion in report["weights"]
        )
        assert row["score"] == pytest.approx(reconstructed)


def test_mcda_is_scale_invariant_and_monotonic_for_benefit_criterion():
    base = {"A": {"quality": 9, "cost": 3}, "B": {"quality": 8, "cost": 2}}
    scaled = {entity: {key: value * 10 for key, value in values.items()} for entity, values in base.items()}
    assert evaluate_mcda(base, CRITERIA)["winner"] == evaluate_mcda(scaled, CRITERIA)["winner"]
    improved = {**base, "A": {"quality": 10, "cost": 3}}
    base_a = next(item["score"] for item in evaluate_mcda(base, CRITERIA)["weighted_sum"] if item["entity"] == "A")
    improved_a = next(item["score"] for item in evaluate_mcda(improved, CRITERIA)["weighted_sum"] if item["entity"] == "A")
    assert improved_a >= base_a


def test_mcda_tie_all_missing_and_non_finite_boundaries():
    tie = evaluate_mcda({"A": {"quality": 1, "cost": 1}, "B": {"quality": 1, "cost": 1}}, CRITERIA)
    assert tie["winner"] is None
    assert tie["tie"] is True
    with pytest.raises(ValueError, match="missing"):
        evaluate_mcda({"A": {"quality": None, "cost": None}, "B": {"quality": None, "cost": None}}, CRITERIA)
    with pytest.raises(ValueError, match="finite"):
        evaluate_mcda({"A": {"quality": math.inf, "cost": 1}, "B": {"quality": 1, "cost": 1}}, CRITERIA)
    with pytest.raises(ValueError, match="polarity"):
        evaluate_mcda({"A": {"quality": 1}}, [{"name": "quality", "weight": 1, "polarity": "unknown"}])

