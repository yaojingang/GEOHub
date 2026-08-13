from __future__ import annotations

from geo_seo_hub.intelligence.discovery.clustering import cluster_and_prune, normalized_similarity
from geo_seo_hub.intelligence.discovery.strategies import (
    ProviderHypothesis,
    generate_discovery_candidates,
)


BRIEF = {
    "protocol_version": "1.0.0",
    "brief_id": "fixture",
    "subject": "团队知识库",
    "brand": "Example",
    "seed_queries": ["知识库选型"],
    "audiences": ["运营负责人"],
    "scenarios": ["工具选型"],
    "competitors": ["Alpha", "Beta"],
    "evidence": [],
    "locale": "zh-CN",
}


def test_question_graph_expands_beyond_template_baseline_deterministically():
    legacy = generate_discovery_candidates(BRIEF, execution_mode="legacy")
    first = generate_discovery_candidates(BRIEF, execution_mode="deterministic")
    second = generate_discovery_candidates(BRIEF, execution_mode="deterministic")

    assert first == second
    assert len(first) >= len(legacy) * 1.5
    assert {item.generator for item in first} >= {"template_baseline", "question_graph"}
    assert all(item.parent_query for item in first)


def test_research_uses_approved_evidence_as_hypothesis_source():
    brief = {**BRIEF, "evidence": [{"evidence_id": "ev-1", "claim": "支持权限和版本历史", "source_uri": "https://example.invalid/evidence"}]}
    candidates = generate_discovery_candidates(brief, execution_mode="research")
    assert "hypothetical_document" in {item.generator for item in candidates}
    assert any("权限和版本历史" in item.question for item in candidates)


def test_provider_hypothesis_is_bounded_and_file_contract_ready():
    hypothesis = ProviderHypothesis(
        text="理想知识库回答应说明权限、版本历史和迁移边界。",
        provider="fixture",
        model="fixture-v1",
        prompt_digest="a" * 64,
        token_count=42,
        cost_usd=0.001,
    )
    candidates = generate_discovery_candidates(
        BRIEF,
        execution_mode="provider",
        provider_hypothesis=hypothesis,
    )
    assert any(item.generator == "hypothetical_document" for item in candidates)


def test_cluster_and_prune_removes_normalized_duplicates():
    candidates = generate_discovery_candidates(BRIEF, execution_mode="legacy")
    duplicated = [*candidates, candidates[0]]
    pruned = cluster_and_prune(duplicated)
    assert len(pruned) == len(candidates)
    assert normalized_similarity("Knowledge-base choice", "knowledge base choice") > 0.8

