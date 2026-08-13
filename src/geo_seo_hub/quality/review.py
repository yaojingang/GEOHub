from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any


def _validate_decision(decision: dict[str, Any]) -> None:
    required_text = ("pair_id", "reviewer", "reviewed_at", "winner_variant", "reason")
    for field in required_text:
        if not isinstance(decision.get(field), str) or not decision[field].strip():
            raise ValueError(f"Review decision requires a non-empty {field}")
    if decision["winner_variant"] not in {"A", "B", "tie"}:
        raise ValueError("Review winner_variant must be A, B, or tie")
    confidence = decision.get("confidence")
    if confidence is not None and (
        not isinstance(confidence, (int, float))
        or isinstance(confidence, bool)
        or confidence < 0
        or confidence > 1
    ):
        raise ValueError("Review confidence must be between 0 and 1")


def _cohen_kappa(pairs: list[tuple[str, str]]) -> float | None:
    if not pairs:
        return None
    labels = ("A", "B", "tie")
    observed = sum(first == second for first, second in pairs) / len(pairs)
    first_counts = Counter(first for first, _ in pairs)
    second_counts = Counter(second for _, second in pairs)
    expected = sum(
        first_counts[label] / len(pairs) * second_counts[label] / len(pairs)
        for label in labels
    )
    if expected == 1.0:
        return 1.0 if observed == 1.0 else 0.0
    return (observed - expected) / (1.0 - expected)


def adjudicate_review(
    pack: dict[str, Any],
    answer_key: dict[str, Any],
    decision_ledger: dict[str, Any],
    *,
    eval_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    suite_ids = {pack.get("suite_id"), answer_key.get("suite_id"), decision_ledger.get("suite_id")}
    if len(suite_ids) != 1 or None in suite_ids:
        raise ValueError("Review pack, answer key, and decisions must use the same suite_id")
    pack_pairs = pack.get("pairs")
    key_pairs = answer_key.get("pairs")
    decisions = decision_ledger.get("decisions")
    if not isinstance(pack_pairs, list) or not isinstance(key_pairs, list) or not isinstance(decisions, list):
        raise ValueError("Review artifacts must contain pairs and decisions lists")
    pack_ids = [pair.get("pair_id") for pair in pack_pairs]
    if len(set(pack_ids)) != len(pack_ids) or any(not isinstance(pair_id, str) for pair_id in pack_ids):
        raise ValueError("Review pack pair IDs must be unique strings")
    key_by_pair = {pair.get("pair_id"): pair for pair in key_pairs}
    if set(key_by_pair) != set(pack_ids):
        raise ValueError("Blind answer key must exactly match review pack pairs")

    by_pair: dict[str, list[dict[str, Any]]] = defaultdict(list)
    seen_reviewers = set()
    for decision in decisions:
        if not isinstance(decision, dict):
            raise ValueError("Review decision must be an object")
        _validate_decision(decision)
        pair_id = decision["pair_id"]
        if pair_id not in key_by_pair:
            raise ValueError(f"Unknown review pair: {pair_id}")
        reviewer_key = (pair_id, decision["reviewer"])
        if reviewer_key in seen_reviewers:
            raise ValueError(f"Duplicate reviewer decision for {pair_id}")
        seen_reviewers.add(reviewer_key)
        by_pair[pair_id].append(decision)

    reviewed_pairs = [pair_id for pair_id in pack_ids if by_pair.get(pair_id)]
    with_skill_wins = 0
    agreement_pairs: list[tuple[str, str]] = []
    for pair_id in reviewed_pairs:
        pair_decisions = by_pair[pair_id]
        primary = pair_decisions[0]["winner_variant"]
        if primary == key_by_pair[pair_id]["with_skill_variant"]:
            with_skill_wins += 1
        if len(pair_decisions) >= 2:
            agreement_pairs.append((primary, pair_decisions[1]["winner_variant"]))

    reviewed_count = len(reviewed_pairs)
    total_pairs = len(pack_ids)
    second_coverage = len(agreement_pairs) / total_pairs if total_pairs else 0.0
    kappa = _cohen_kappa(agreement_pairs)
    completed = reviewed_count == total_pairs and total_pairs > 0
    independent_coverage_met = second_coverage >= 0.20
    status = "completed" if completed and independent_coverage_met and kappa is not None and kappa >= 0.60 else "warn" if reviewed_count else "missing-evidence"
    report = {
        "status": status,
        "reviewed_pairs": reviewed_count,
        "pending_pairs": total_pairs - reviewed_count,
        "with_skill_win_rate": with_skill_wins / reviewed_count if reviewed_count else None,
        "second_reviewer_coverage": second_coverage,
        "cohen_kappa": kappa,
        "reviewer_count": len({decision["reviewer"] for decision in decisions}),
    }
    if eval_result is not None:
        eval_result["human_review"] = {
            key: report[key]
            for key in (
                "status",
                "reviewed_pairs",
                "pending_pairs",
                "with_skill_win_rate",
                "second_reviewer_coverage",
                "cohen_kappa",
            )
        }
    return report
