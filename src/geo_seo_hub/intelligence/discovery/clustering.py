from __future__ import annotations

import re
from typing import Iterable

from .strategies import DiscoveryCandidate


def _tokens(value: str) -> set[str]:
    normalized = value.casefold().replace("-", " ")
    ascii_tokens = set(re.findall(r"[a-z0-9]+", normalized))
    chinese = "".join(re.findall(r"[\u3400-\u9fff]", normalized))
    grams = {chinese[index : index + 2] for index in range(max(0, len(chinese) - 1))}
    if len(chinese) == 1:
        grams.add(chinese)
    return ascii_tokens | grams


def normalized_similarity(left: str, right: str) -> float:
    left_tokens = _tokens(left)
    right_tokens = _tokens(right)
    if not left_tokens and not right_tokens:
        return 1.0
    union = left_tokens | right_tokens
    return len(left_tokens & right_tokens) / len(union) if union else 0.0


def cluster_and_prune(
    candidates: Iterable[DiscoveryCandidate],
    *,
    threshold: float = 0.92,
) -> list[DiscoveryCandidate]:
    if not 0.0 <= threshold <= 1.0:
        raise ValueError("clustering threshold must be between zero and one")
    retained: list[DiscoveryCandidate] = []
    exact: set[str] = set()
    for candidate in candidates:
        normalized = "".join(candidate.question.casefold().split())
        if normalized in exact:
            continue
        peers = (
            item
            for item in retained
            if item.intent == candidate.intent
            and item.audience.casefold() == candidate.audience.casefold()
            and item.scenario.casefold() == candidate.scenario.casefold()
        )
        if any(normalized_similarity(candidate.question, item.question) >= threshold for item in peers):
            continue
        exact.add(normalized)
        retained.append(candidate)
    return retained
