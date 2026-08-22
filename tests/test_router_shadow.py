from __future__ import annotations

from geo_seo_hub.control.routing import FastEmbedSemanticScorer, StaticSemanticScorer
from geo_seo_hub.registry import load_registry
from geo_seo_hub.router import route


def test_semantic_shadow_never_changes_production_route():
    scorer = StaticSemanticScorer(
        {"geo-content": 0.91, "geo-diagnose": 0.07},
        model_id="fixture-semantic-v1",
    )
    production = route("Audit this website")
    observed = route("Audit this website", semantic_scorer=scorer)

    assert {key: observed[key] for key in production} == production
    assert observed["shadow"]["production_skill_id"] == "geo-diagnose"
    assert observed["shadow"]["shadow_skill_id"] == "geo-content"
    assert observed["shadow"]["disagreed"] is True
    assert observed["shadow"]["decision_reason"]
    assert observed["shadow"]["threshold_version"] == "semantic-shadow-1.0.0"
    assert observed["shadow"]["model_id"] == "fixture-semantic-v1"


def test_shadow_candidates_expose_components_and_do_not_activate_planned_skill():
    scorer = StaticSemanticScorer({"geo-publish": 0.99, "geo-discover": 0.60})
    result = route("Discover questions", semantic_scorer=scorer)
    shadow = result["shadow"]

    planned = next(item for item in shadow["candidates"] if item["skill_id"] == "geo-publish")
    assert planned["status"] == "planned"
    assert planned["eligible"] is False
    assert planned["score_components"] == {"semantic": 0.99}
    assert shadow["shadow_skill_id"] == "geo-discover"
    assert result["skill_id"] == "geo-discover"


def test_below_threshold_shadow_records_missing_decision():
    result = route("GEO", semantic_scorer=StaticSemanticScorer({"geo-content": 0.44}))
    assert result["shadow"]["shadow_skill_id"] is None
    assert result["shadow"]["decision_reason"] == "No eligible active candidate met the semantic threshold."


def test_shadow_failure_never_blocks_lexical_production_route():
    class BrokenScorer:
        model_id = "broken"

        def score(self, _text, _candidate_skill_ids):
            raise RuntimeError("fixture failure")

    result = route("Audit this website", semantic_scorer=BrokenScorer())
    assert result["skill_id"] == "geo-diagnose"
    assert result["shadow"]["status"] == "unavailable"
    assert result["shadow"]["production_skill_id"] == "geo-diagnose"


def test_fastembed_semantic_scorer_uses_registry_examples_without_network():
    class FixtureEmbeddingModel:
        @staticmethod
        def embed(documents):
            for document in documents:
                normalized = document.casefold()
                if any(token in normalized for token in ("audit", "诊断", "检查", "障碍")):
                    yield [1.0, 0.0, 0.0]
                elif any(token in normalized for token in ("write", "draft", "文章", "页面")):
                    yield [0.0, 1.0, 0.0]
                else:
                    yield [0.0, 0.0, 1.0]

    scorer = FastEmbedSemanticScorer(
        load_registry(),
        embedding_model=FixtureEmbeddingModel(),
        model_name="fixture-multilingual",
    )

    scores = scorer.score("Audit this website for citation barriers", ["geo-diagnose", "geo-content"])

    assert scores["geo-diagnose"] > scores["geo-content"]
    assert all(0.0 <= value <= 1.0 for value in scores.values())
