#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "evals" / "router_natural_cases.json"

SKILLS = (
    ("geo-discover", "围绕{subject}挖掘用户在 AI 搜索里会问的问题", "Research buyer questions about {subject} for AI search"),
    ("geo-diagnose", "检查{subject}的网站为什么难被 AI 回答引用", "Audit the {subject} website for answer-engine citation gaps"),
    ("geo-content", "根据现有证据为{subject}写一篇可引用的解释文章", "Draft an evidence-backed explainer about {subject}"),
    ("geo-strategy", "为{subject}制定一轮有测量标准的 GEO 优化实验", "Plan a bounded GEO experiment roadmap for {subject}"),
    ("geo-knowledge", "把{subject}的品牌事实整理成保留冲突的知识图谱", "Build a governed entity graph for {subject}"),
    ("geo-measure", "计算{subject}在这批 AI 回答中的提及率和引用份额", "Measure mention rate and citation share for {subject}"),
)
SUBJECTS = (
    "企业协作软件",
    "智能家居品牌",
    "在线教育平台",
    "跨境支付产品",
    "工业机器人方案",
    "健康管理应用",
    "developer tools",
    "customer support software",
    "sustainable packaging",
    "travel planning services",
    "cybersecurity platforms",
    "cloud data products",
    "workflow automation",
    "research assistants",
    "marketing analytics",
    "HR technology",
    "video collaboration",
    "electric mobility",
    "financial education",
    "product design tools",
)
ZH_CONTEXTS = ("面向采购负责人", "面向产品团队", "面向市场团队", "用于季度复盘", "用于新品研究", "用于竞争分析")
EN_CONTEXTS = ("for procurement leaders", "for the product team", "for the marketing team", "for a quarterly review", "for launch research", "for competitive analysis")


def _split(index: int, family_count: int) -> str:
    if index < family_count * 3 // 5:
        return "calibration"
    if index < family_count * 4 // 5:
        return "public-test"
    return "private-holdout"


def _case(
    identifier: str,
    *,
    category: str,
    family_id: str,
    split: str,
    text: str,
    decision_type: str,
    skill_id: str | None = None,
    workflow_id: str | None = None,
) -> dict:
    return {
        "id": identifier,
        "category": category,
        "family_id": family_id,
        "split": split,
        "text": text,
        "expected": {
            "decision_type": decision_type,
            "skill_id": skill_id,
            "workflow_id": workflow_id,
        },
        "label_status": "proposed",
    }


def build_cases() -> list[dict]:
    cases: list[dict] = []
    serial = 1

    for family_index in range(120):
        skill_id, zh, en = SKILLS[family_index % len(SKILLS)]
        subject = SUBJECTS[family_index % len(SUBJECTS)]
        context_index = family_index // len(SUBJECTS)
        family_id = f"single-{family_index + 1:03d}"
        split = _split(family_index, 120)
        for text in (
            f"{zh.format(subject=subject)}，{ZH_CONTEXTS[context_index]}",
            f"{en.format(subject=subject)} {EN_CONTEXTS[context_index]}",
        ):
            cases.append(
                _case(
                    f"natural-{serial:04d}",
                    category="single-intent",
                    family_id=family_id,
                    split=split,
                    text=text,
                    decision_type="single_skill",
                    skill_id=skill_id,
                )
            )
            serial += 1

    neighbor_actions = (
        ("geo-discover", "不要扩展搜索问题", "只检查网站的引用障碍", "geo-diagnose"),
        ("geo-diagnose", "不要诊断网站", "只生成一篇解释文章", "geo-content"),
        ("geo-content", "不要生成任何内容", "只制定优化实验", "geo-strategy"),
        ("geo-strategy", "不要制定优化策略", "只整理实体关系", "geo-knowledge"),
        ("geo-knowledge", "不要更新知识图谱", "只统计 AI 可见度", "geo-measure"),
        ("geo-measure", "不要计算本轮效果", "只挖掘用户问题", "geo-discover"),
    )
    for family_index in range(60):
        skill_id, negative, neighbor, neighbor_id = neighbor_actions[family_index % len(neighbor_actions)]
        family_id = f"neighbor-{family_index + 1:03d}"
        split = _split(family_index, 60)
        suffix = f"，对象是{SUBJECTS[family_index % len(SUBJECTS)]}"
        cases.append(
            _case(
                f"natural-{serial:04d}",
                category="near-neighbor",
                family_id=family_id,
                split=split,
                text=negative + suffix,
                decision_type="abstain",
            )
        )
        serial += 1
        cases.append(
            _case(
                f"natural-{serial:04d}",
                category="near-neighbor",
                family_id=family_id,
                split=split,
                text=neighbor + suffix,
                decision_type="single_skill",
                skill_id=neighbor_id,
            )
        )
        serial += 1

    workflows = (
        ("先挖掘问题，再诊断网站", "Discover buyer questions, then audit the website", "brand-baseline-lite", "geo-discover", "workflow"),
        ("先拓展查询，再写一篇解释文章", "Research queries, then draft an explainer", "content-campaign", "geo-discover", "workflow"),
        ("先挖掘问题、诊断网站，再生成内容", "Discover questions, audit the site, then create content", "brand-baseline-content", "geo-discover", "workflow"),
        ("先制定 GEO 策略，再监测 AI 可见度", "Build a GEO strategy, then measure AI visibility", "strategy-observation-loop", "geo-strategy", "workflow"),
    )
    for family_index in range(40):
        zh, en, workflow_id, skill_id, decision_type = workflows[family_index % len(workflows)]
        family_id = f"workflow-{family_index + 1:03d}"
        split = _split(family_index, 40)
        subject = SUBJECTS[family_index % len(SUBJECTS)]
        context_index = family_index // len(SUBJECTS)
        for text in (
            f"{zh}，对象是{subject}，{ZH_CONTEXTS[context_index]}",
            f"{en} for {subject} {EN_CONTEXTS[context_index]}",
        ):
            cases.append(
                _case(
                    f"natural-{serial:04d}",
                    category="multi-intent",
                    family_id=family_id,
                    split=split,
                    text=text,
                    decision_type=decision_type,
                    skill_id=skill_id,
                    workflow_id=workflow_id,
                )
            )
            serial += 1

    ambiguous_pairs = (
        "帮我处理这个品牌的 GEO 内容问题",
        "看看这个网站接下来该做什么",
        "Improve this brand's AI search presence",
        "Help with the next GEO step for this page",
    )
    for family_index in range(40):
        family_id = f"ambiguous-{family_index + 1:03d}"
        split = _split(family_index, 40)
        subject = SUBJECTS[family_index % len(SUBJECTS)]
        context_index = family_index // len(SUBJECTS)
        for variant in range(2):
            base = ambiguous_pairs[(family_index + variant) % len(ambiguous_pairs)]
            cases.append(
                _case(
                    f"natural-{serial:04d}",
                    category="ambiguous",
                    family_id=family_id,
                    split=split,
                    text=f"{base}：{subject}，{ZH_CONTEXTS[context_index]}",
                    decision_type="clarify",
                )
            )
            serial += 1

    out_of_domain = (
        "查询明天的天气预报",
        "把这首诗翻译成英文",
        "帮我计算房贷月供",
        "推荐今晚适合看的电影",
        "What is the capital of Finland",
        "Summarize this restaurant invoice",
        "Write a birthday message for my friend",
        "How do I repair a bicycle tire",
    )
    for family_index in range(40):
        family_id = f"ood-{family_index + 1:03d}"
        split = _split(family_index, 40)
        for variant in range(2):
            text = f"{out_of_domain[(family_index + variant) % len(out_of_domain)]} #{family_index + 1}"
            cases.append(
                _case(
                    f"natural-{serial:04d}",
                    category="out-of-domain",
                    family_id=family_id,
                    split=split,
                    text=text,
                    decision_type="abstain",
                )
            )
            serial += 1

    if len(cases) != 600:
        raise AssertionError(f"expected 600 cases, got {len(cases)}")
    return cases


def main() -> int:
    cases = build_cases()
    payload = {
        "schema_version": "1.0.0",
        "dataset_id": "geohub-router-natural-v1",
        "label_policy": {
            "status": "pending-human-review",
            "double_label_target_fraction": 0.20,
            "required_cohen_kappa": 0.80,
            "note": "Generated labels are proposals and cannot unlock the production promotion gate until human adjudication is recorded.",
        },
        "split_counts": {
            "calibration": 360,
            "public-test": 120,
            "private-holdout": 120,
        },
        "cases": cases,
    }
    OUTPUT.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {len(cases)} cases to {OUTPUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
