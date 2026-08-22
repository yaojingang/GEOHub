from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Protocol, Sequence


SHADOW_THRESHOLD = 0.55
SHADOW_THRESHOLD_VERSION = "semantic-shadow-1.0.0"
FASTEMBED_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


class SemanticScorer(Protocol):
    model_id: str

    def score(self, text: str, candidate_skill_ids: Sequence[str]) -> Mapping[str, float]: ...


@dataclass(frozen=True)
class StaticSemanticScorer:
    scores: Mapping[str, float]
    model_id: str = "static-fixture-v1"

    def score(self, _text: str, candidate_skill_ids: Sequence[str]) -> Mapping[str, float]:
        return {
            skill_id: self.scores.get(skill_id, 0.0)
            for skill_id in candidate_skill_ids
        }


def _cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    if len(left) != len(right) or not left:
        raise ValueError("semantic vectors must have equal non-zero dimensions")
    dot = sum(float(a) * float(b) for a, b in zip(left, right))
    left_norm = math.sqrt(sum(float(value) ** 2 for value in left))
    right_norm = math.sqrt(sum(float(value) ** 2 for value in right))
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    return max(0.0, min(1.0, dot / (left_norm * right_norm)))


class FastEmbedSemanticScorer:
    """Offline semantic scorer backed by registry examples and a cached embedder."""

    def __init__(
        self,
        registry: dict[str, Any],
        *,
        cache_dir: Path | None = None,
        embedding_model: Any | None = None,
        model_name: str = FASTEMBED_MODEL,
    ) -> None:
        self.model_id = f"fastembed:{model_name}"
        self._examples = {
            skill["id"]: tuple(skill["positive_examples"])
            for skill in registry["skills"]
        }
        self._anchor_vectors: dict[str, tuple[tuple[float, ...], ...]] | None = None
        if embedding_model is None:
            try:
                from fastembed import TextEmbedding
            except ImportError as exc:
                raise RuntimeError(
                    "FastEmbed is unavailable; install the semantic optional dependency"
                ) from exc
            embedding_model = TextEmbedding(
                model_name=model_name,
                cache_dir=str(cache_dir) if cache_dir is not None else None,
                local_files_only=True,
            )
        self._embedding_model = embedding_model

    def _load_anchor_vectors(self) -> dict[str, tuple[tuple[float, ...], ...]]:
        if self._anchor_vectors is not None:
            return self._anchor_vectors
        identifiers: list[str] = []
        documents: list[str] = []
        for skill_id, examples in self._examples.items():
            for example in examples:
                identifiers.append(skill_id)
                documents.append(example)
        embedded = [tuple(float(value) for value in vector) for vector in self._embedding_model.embed(documents)]
        if len(embedded) != len(documents):
            raise ValueError("semantic embedder returned an unexpected vector count")
        grouped: dict[str, list[tuple[float, ...]]] = {
            skill_id: [] for skill_id in self._examples
        }
        for skill_id, vector in zip(identifiers, embedded):
            grouped[skill_id].append(vector)
        self._anchor_vectors = {
            skill_id: tuple(vectors) for skill_id, vectors in grouped.items()
        }
        return self._anchor_vectors

    def score(
        self,
        text: str,
        candidate_skill_ids: Sequence[str],
    ) -> Mapping[str, float]:
        unknown = sorted(set(candidate_skill_ids) - set(self._examples))
        if unknown:
            raise ValueError(f"unknown semantic candidate Skill IDs: {unknown}")
        query_vectors = list(self._embedding_model.embed([text]))
        if len(query_vectors) != 1:
            raise ValueError("semantic embedder must return exactly one query vector")
        query = tuple(float(value) for value in query_vectors[0])
        anchors = self._load_anchor_vectors()
        scores: dict[str, float] = {}
        for skill_id in candidate_skill_ids:
            ranked = sorted(
                (_cosine_similarity(query, vector) for vector in anchors[skill_id]),
                reverse=True,
            )
            selected = ranked[:3]
            scores[skill_id] = sum(selected) / len(selected) if selected else 0.0
        return scores


def build_shadow_assessment(
    text: str,
    registry: dict[str, Any],
    production: dict[str, Any],
    scorer: SemanticScorer,
    *,
    threshold: float = SHADOW_THRESHOLD,
) -> dict[str, Any]:
    """Score a route in shadow mode while preserving the lexical decision."""
    if not 0.0 <= threshold <= 1.0:
        raise ValueError("semantic threshold must be between zero and one")
    identifiers = [skill["id"] for skill in registry["skills"]]
    raw = scorer.score(text, identifiers)
    unknown = sorted(set(raw) - set(identifiers))
    if unknown:
        raise ValueError(f"semantic scorer returned unknown Skill IDs: {unknown}")
    candidates = []
    for index, skill in enumerate(registry["skills"]):
        value = raw.get(skill["id"], 0.0)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError(f"semantic score is invalid for {skill['id']}")
        score = float(value)
        if not 0.0 <= score <= 1.0:
            raise ValueError(f"semantic score is outside [0, 1] for {skill['id']}")
        eligible = skill["status"] == "active" and bool(skill["entry"])
        candidates.append(
            {
                "skill_id": skill["id"],
                "status": skill["status"],
                "eligible": eligible,
                "score_components": {"semantic": score},
                "total_score": score,
                "registry_order": index,
            }
        )
    ranked = sorted(
        (item for item in candidates if item["eligible"] and item["total_score"] >= threshold),
        key=lambda item: (-item["total_score"], item["registry_order"]),
    )
    shadow_skill_id = ranked[0]["skill_id"] if ranked else None
    disagreed = shadow_skill_id is not None and shadow_skill_id != production["skill_id"]
    if shadow_skill_id is None:
        reason = "No eligible active candidate met the semantic threshold."
    elif disagreed:
        reason = (
            f"Shadow candidate {shadow_skill_id} differs from lexical production route "
            f"{production['skill_id']}; production remains unchanged."
        )
    else:
        reason = f"Shadow candidate agrees with lexical production route {production['skill_id']}."
    return {
        "mode": "shadow",
        "threshold": threshold,
        "threshold_version": SHADOW_THRESHOLD_VERSION,
        "model_id": scorer.model_id,
        "production_skill_id": production["skill_id"],
        "shadow_skill_id": shadow_skill_id,
        "disagreed": disagreed,
        "decision_reason": reason,
        "candidates": candidates,
    }
