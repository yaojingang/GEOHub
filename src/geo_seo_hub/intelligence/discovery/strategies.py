from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ProviderHypothesis:
    text: str
    provider: str
    model: str
    prompt_digest: str
    token_count: int
    cost_usd: float


@dataclass(frozen=True)
class DiscoveryCandidate:
    question: str
    intent: str
    seed: str
    audience: str
    scenario: str
    generator: str
    parent_query: str


def _parent(seed: str, audience: str, scenario: str) -> str:
    digest = hashlib.sha256(f"{seed}\x1f{audience}\x1f{scenario}".encode("utf-8")).hexdigest()[:12]
    return f"seed-{digest}"


def _template_questions(locale: str, seed: str, audience: str, scenario: str) -> list[tuple[str, str]]:
    if locale.casefold().startswith("zh"):
        templates = (
            ("learn", "{audience}在{scenario}场景下，应该如何理解“{seed}”？"),
            ("compare", "{audience}在{scenario}场景下比较“{seed}”时，应关注哪些差异？"),
            ("evaluate", "{audience}在{scenario}场景下评估“{seed}”时，需要哪些可验证证据？"),
            ("act", "{audience}要在{scenario}场景下推进“{seed}”，下一步应该怎么做？"),
        )
    else:
        templates = (
            ("learn", "How should {audience} understand {seed} in a {scenario} scenario?"),
            ("compare", "What differences should {audience} assess when comparing {seed} for {scenario}?"),
            ("evaluate", "What verifiable evidence should {audience} require when evaluating {seed} for {scenario}?"),
            ("act", "What should {audience} do next to move forward with {seed} for {scenario}?"),
        )
    return [
        (intent, template.format(audience=audience, scenario=scenario, seed=seed))
        for intent, template in templates
    ]


def _graph_questions(locale: str, seed: str, audience: str, scenario: str, competitors: list[str]) -> list[tuple[str, str]]:
    compared = "、".join(competitors[:3]) if competitors else "可选方案"
    if locale.casefold().startswith("zh"):
        return [
            ("learn", f"{audience}理解“{seed}”前，需要识别哪些核心实体、术语和关系？"),
            ("compare", f"{audience}在{scenario}中，应使用哪些统一标准比较“{seed}”与{compared}？"),
            ("evaluate", f"{audience}采用“{seed}”时，最常见的证据缺口、失败风险和反例是什么？"),
            ("act", f"{audience}在{scenario}中实施“{seed}”时，验证、试点和复盘顺序是什么？"),
        ]
    compared_en = ", ".join(competitors[:3]) if competitors else "available alternatives"
    return [
        ("learn", f"Which entities, terms, and relationships should {audience} identify before assessing {seed}?"),
        ("compare", f"Which consistent criteria should {audience} use to compare {seed} with {compared_en} for {scenario}?"),
        ("evaluate", f"Which evidence gaps, failure risks, and counterexamples matter when {audience} evaluates {seed}?"),
        ("act", f"Which validation, pilot, and review sequence should {audience} use to implement {seed} for {scenario}?"),
    ]


def _hypothesis_questions(locale: str, seed: str, audience: str, hypothesis: str) -> list[tuple[str, str]]:
    compact = " ".join(hypothesis.split())[:300]
    if locale.casefold().startswith("zh"):
        return [
            ("learn", f"围绕“{seed}”，如何核验这份假设性回答中的关键主张：{compact}"),
            ("evaluate", f"{audience}需要哪些来源来证实或反驳“{seed}”假设：{compact}"),
        ]
    return [
        ("learn", f"How can the central claims in this hypothetical answer about {seed} be verified: {compact}"),
        ("evaluate", f"Which sources should {audience} use to support or refute this {seed} hypothesis: {compact}"),
    ]


def _ordered(values: list[str] | None, fallback: str) -> list[str]:
    result = sorted({item.strip() for item in (values or []) if item.strip()}, key=lambda item: (item.casefold(), item))
    return result or [fallback]


def generate_discovery_candidates(
    brief: dict[str, Any],
    *,
    execution_mode: str,
    provider_hypothesis: ProviderHypothesis | None = None,
) -> list[DiscoveryCandidate]:
    if execution_mode not in {"legacy", "deterministic", "research", "provider"}:
        raise ValueError("unsupported discovery execution mode")
    locale = brief.get("locale", "zh-CN")
    chinese = locale.casefold().startswith("zh")
    audiences = _ordered(brief.get("audiences"), "通用用户" if chinese else "general user")[:3]
    scenarios = _ordered(brief.get("scenarios"), "调研" if chinese else "research")[:3]
    seeds = _ordered(brief.get("seed_queries"), "")[:20]
    competitors = _ordered(brief.get("competitors"), "") if brief.get("competitors") else []
    hypothesis = provider_hypothesis
    if execution_mode == "research" and brief.get("evidence"):
        hypothesis = ProviderHypothesis(
            text="；".join(item["claim"] for item in brief["evidence"]),
            provider="approved-input",
            model="none",
            prompt_digest=hashlib.sha256(brief["brief_id"].encode("utf-8")).hexdigest(),
            token_count=0,
            cost_usd=0.0,
        )
    candidates: list[DiscoveryCandidate] = []
    for seed in seeds:
        for audience in audiences:
            for scenario in scenarios:
                parent = _parent(seed, audience, scenario)
                for intent, question in _template_questions(locale, seed, audience, scenario):
                    candidates.append(DiscoveryCandidate(question, intent, seed, audience, scenario, "template_baseline", parent))
                if execution_mode != "legacy":
                    for intent, question in _graph_questions(locale, seed, audience, scenario, competitors):
                        candidates.append(DiscoveryCandidate(question, intent, seed, audience, scenario, "question_graph", parent))
                if hypothesis is not None and execution_mode in {"research", "provider"}:
                    for intent, question in _hypothesis_questions(locale, seed, audience, hypothesis.text):
                        candidates.append(DiscoveryCandidate(question, intent, seed, audience, scenario, "hypothetical_document", parent))
    return candidates
