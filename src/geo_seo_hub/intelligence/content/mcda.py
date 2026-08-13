from __future__ import annotations

import math
from typing import Any


MCDA_POLICY_VERSION = "1.0.0"


def _winner(rows: list[dict[str, Any]], *, tolerance: float = 1e-12) -> tuple[str | None, bool]:
    ranked = sorted(rows, key=lambda item: (-item["score"], item["entity"].casefold()))
    if len(ranked) > 1 and math.isclose(ranked[0]["score"], ranked[1]["score"], abs_tol=tolerance):
        return None, True
    return ranked[0]["entity"], False


def _weighted_rows(
    normalized: dict[str, dict[str, float]],
    weights: dict[str, float],
) -> list[dict[str, Any]]:
    rows = [
        {
            "entity": entity,
            "score": round(math.fsum(values[name] * weights[name] for name in weights), 12),
        }
        for entity, values in normalized.items()
    ]
    return sorted(rows, key=lambda item: (-item["score"], item["entity"].casefold()))


def evaluate_mcda(
    matrix: dict[str, dict[str, float | int | None]],
    criteria: list[dict[str, Any]],
    *,
    normalization: str = "min-max",
    weighting: str = "normalized-explicit",
    missing_value: str = "reject",
    tie_policy: str = "no-winner",
) -> dict[str, Any]:
    if not matrix or not criteria:
        raise ValueError("MCDA matrix and criteria are required")
    if normalization != "min-max" or weighting != "normalized-explicit":
        raise ValueError("unsupported MCDA normalization or weighting policy")
    if missing_value != "reject" or tie_policy != "no-winner":
        raise ValueError("unsupported MCDA missing-value or tie policy")
    names: list[str] = []
    raw_weights: dict[str, float] = {}
    polarities: dict[str, str] = {}
    for criterion in criteria:
        if set(criterion) != {"name", "weight", "polarity"}:
            raise ValueError("each MCDA criterion must declare name, weight, and polarity")
        name = criterion["name"]
        polarity = criterion["polarity"]
        weight = criterion["weight"]
        if not isinstance(name, str) or not name.strip() or name in names:
            raise ValueError("MCDA criterion names must be unique and non-blank")
        if polarity not in {"benefit", "cost"}:
            raise ValueError("MCDA criterion polarity must be benefit or cost")
        if isinstance(weight, bool) or not isinstance(weight, (int, float)) or not math.isfinite(weight) or weight <= 0:
            raise ValueError("MCDA weights must be positive and finite")
        names.append(name)
        polarities[name] = polarity
        raw_weights[name] = float(weight)
    for entity, values in matrix.items():
        if not isinstance(entity, str) or not entity.strip() or set(values) != set(names):
            raise ValueError("MCDA matrix rows must contain every declared criterion")
        for name, value in values.items():
            if value is None:
                raise ValueError(f"MCDA missing value for {entity} × {name}")
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError(f"MCDA value must be finite for {entity} × {name}")
    weight_total = math.fsum(raw_weights.values())
    weights = {name: round(raw_weights[name] / weight_total, 12) for name in names}
    normalized: dict[str, dict[str, float]] = {entity: {} for entity in matrix}
    for name in names:
        values = [float(row[name]) for row in matrix.values()]
        low, high = min(values), max(values)
        for entity, row in matrix.items():
            value = float(row[name])
            if math.isclose(low, high, abs_tol=1e-15):
                score = 0.5
            elif polarities[name] == "benefit":
                score = (value - low) / (high - low)
            else:
                score = (high - value) / (high - low)
            normalized[entity][name] = round(score, 12)

    weighted_sum = _weighted_rows(normalized, weights)
    winner, tie = _winner(weighted_sum)
    weighted_vectors = {
        entity: {name: normalized[entity][name] * weights[name] for name in names}
        for entity in matrix
    }
    ideal = {name: max(values[name] for values in weighted_vectors.values()) for name in names}
    anti_ideal = {name: min(values[name] for values in weighted_vectors.values()) for name in names}
    topsis = []
    for entity, values in weighted_vectors.items():
        distance_best = math.sqrt(math.fsum((values[name] - ideal[name]) ** 2 for name in names))
        distance_worst = math.sqrt(math.fsum((values[name] - anti_ideal[name]) ** 2 for name in names))
        total = distance_best + distance_worst
        closeness = 0.5 if math.isclose(total, 0.0, abs_tol=1e-15) else distance_worst / total
        topsis.append(
            {
                "entity": entity,
                "closeness": round(closeness, 12),
                "distance_best": round(distance_best, 12),
                "distance_worst": round(distance_worst, 12),
            }
        )
    topsis.sort(key=lambda item: (-item["closeness"], item["entity"].casefold()))

    scenarios = []
    observed_winners: set[str | None] = set()
    for name in names:
        for factor in (0.9, 1.1):
            varied_raw = {**raw_weights, name: raw_weights[name] * factor}
            varied_total = math.fsum(varied_raw.values())
            varied = {key: value / varied_total for key, value in varied_raw.items()}
            varied_rows = _weighted_rows(normalized, varied)
            varied_winner, varied_tie = _winner(varied_rows)
            observed_winners.add(varied_winner)
            scenarios.append(
                {
                    "criterion": name,
                    "factor": factor,
                    "winner": varied_winner,
                    "tie": varied_tie,
                }
            )
    sensitive = any(item != winner for item in observed_winners)
    return {
        "policy_version": MCDA_POLICY_VERSION,
        "normalization": normalization,
        "weighting": weighting,
        "missing_value_policy": missing_value,
        "tie_policy": tie_policy,
        "polarities": polarities,
        "raw_matrix": matrix,
        "normalized_matrix": normalized,
        "weights": weights,
        "weighted_sum": weighted_sum,
        "topsis": topsis,
        "winner": winner,
        "tie": tie,
        "sensitivity": {"range": 0.10, "sensitive": sensitive, "scenarios": scenarios},
    }
