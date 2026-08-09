import importlib
import json
import math
import os
import re
import zipfile
from pathlib import Path

import pytest

from geo_seo_hub.artifact_bus import ArtifactBus
from geo_seo_hub.cli import main
from geo_seo_hub.content import (
    MAX_INPUT_BYTES,
    UNSUPPORTED_TITLE_PATTERNS,
    content,
    validate_content_brief,
)

content_module = importlib.import_module("geo_seo_hub.content")


def _write(tmp_path: Path, payload: dict, name: str = "brief.json") -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def _run(tmp_path: Path, payload: dict, root: str = "runs") -> tuple[dict, Path]:
    result = content(_write(tmp_path, payload), tmp_path / root)
    return result, Path(result["output"])


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_title_candidates_are_pattern_varied_and_compliant(tmp_path):
    original_topic = "2026 最新最好 AI 搜索"
    _, run = _run(tmp_path, {"mode": "title", "topic": original_topic})
    artifact = _read(run / "content.json")
    candidates = artifact["mode_data"]["title_candidates"]
    assert len(candidates) >= 5
    assert len({item["pattern"] for item in candidates}) == len(candidates)
    rendered = " ".join(item["title"] for item in candidates).casefold()
    for forbidden in ("最好", "最新", "best", "latest", "2026"):
        assert forbidden not in rendered
    assert all(set(item["scores"]) == {"intent", "scenario", "evidence", "compliance"} for item in candidates)
    spec_title = _read(run / "content-spec.json")["title"]
    assert spec_title == candidates[0]["title"]
    assert spec_title != original_topic


@pytest.mark.parametrize(
    "topic",
    (
        "100%有效的终极方案",
        "100％有效的顶级首选",
        "完美唯一万能无敌方案",
        "行业领先且绝对有效",
        "The ultimate 100% guaranteed industry-leading first choice",
    ),
)
def test_title_candidates_remove_every_unsupported_compliance_pattern(tmp_path, topic):
    _, run = _run(tmp_path, {"mode": "title", "topic": topic})
    candidates = _read(run / "content.json")["mode_data"]["title_candidates"]
    for candidate in candidates:
        assert all(
            pattern.search(candidate["title"]) is None
            for pattern in UNSUPPORTED_TITLE_PATTERNS
        )
    spec_title = _read(run / "content-spec.json")["title"]
    assert spec_title == candidates[0]["title"]


def test_title_surface_is_canonical_across_core_and_renderer_inputs(tmp_path, monkeypatch):
    captured = {}

    def fake_docx(markdown):
        captured["docx"] = markdown
        return b"docx"

    def fake_pdf(html_document, markdown):
        captured["pdf_html"] = html_document
        captured["pdf_markdown"] = markdown
        return b"%PDF-test", [], [], []

    monkeypatch.setattr(content_module, "_render_docx", fake_docx)
    monkeypatch.setattr(content_module, "_render_pdf", fake_pdf)
    _, run = _run(
        tmp_path,
        {
            "mode": "title",
            "topic": "2026 100%有效终极标题",
            "desired_formats": ["docx", "pdf"],
        },
    )
    artifact = _read(run / "content.json")
    canonical = artifact["mode_data"]["title_candidates"][0]["title"]
    assert artifact["topic"] == canonical
    assert _read(run / "content-spec.json")["title"] == canonical
    html_document = (run / "content.html").read_text(encoding="utf-8")
    markdown = (run / "content.md").read_text(encoding="utf-8")
    assert f"<title>{canonical}</title>" in html_document
    assert canonical in html_document and canonical in markdown
    assert canonical in captured["docx"]
    assert canonical in captured["pdf_html"] and canonical in captured["pdf_markdown"]


def test_explainer_has_required_structure_and_lineage(tmp_path):
    _, run = _run(
        tmp_path,
        {
            "mode": "explainer",
            "topic": "证据血缘",
            "evidence": [{"label": "user-ref", "claim": "事实 A", "source_uri": "https://example.com/a"}],
        },
    )
    content_json = _read(run / "content.json")
    ledger = _read(run / "evidence-ledger.json")
    assert len(content_json["sections"]) >= 6
    assert content_json["factual_claims"][0]["evidence_ids"][0] == ledger["records"][0]["evidence_id"]
    assert ledger["records"][0]["evidence_id"] != "user-ref"
    normalized = _read(run / "input" / "content-brief.json")
    assert normalized["evidence"][0]["label"] == ledger["records"][0]["evidence_id"]


def test_comparison_blocks_without_evidence_and_stays_neutral_with_evidence(tmp_path):
    _, blocked_run = _run(tmp_path, {"mode": "comparison", "topic": "A 和 B", "entities": ["A", "B"]}, "blocked")
    blocked = _read(blocked_run / "content.json")
    assert blocked["status"] == "blocked-by-evidence"
    assert blocked["mode_data"]["comparison"]["verdict"] is None
    _, ready_run = _run(
        tmp_path,
        {
            "mode": "comparison",
            "topic": "A 和 B",
            "entities": ["A", "B"],
            "evidence": [
                {"label": "a", "claim": "A 有属性 X", "source_uri": "https://example.com/a", "entity": "A", "dimension": "X"},
                {"label": "b", "claim": "B 有属性 X", "source_uri": "https://example.com/b", "entity": "B", "dimension": "X"},
            ],
        },
        "ready",
    )
    ready = _read(ready_run / "content.json")
    assert ready["status"] == "ready"
    assert ready["mode_data"]["comparison"]["verdict"] is None


def test_comparison_blocks_missing_or_different_dimension_evidence(tmp_path):
    cases = (
        [
            {"label": "a", "claim": "A 有属性", "source_uri": "https://example.com/a", "entity": "A"},
            {"label": "b", "claim": "B 有属性", "source_uri": "https://example.com/b", "entity": "B"},
        ],
        [
            {"label": "a", "claim": "A 有质量证据", "source_uri": "https://example.com/a", "entity": "A", "dimension": "质量"},
            {"label": "b", "claim": "B 有价格证据", "source_uri": "https://example.com/b", "entity": "B", "dimension": "价格"},
        ],
    )
    for index, evidence in enumerate(cases):
        _, run = _run(
            tmp_path,
            {"mode": "comparison", "topic": "不同口径", "entities": ["A", "B"], "evidence": evidence},
            f"comparison-gap-{index}",
        )
        comparison = _read(run / "content.json")["mode_data"]["comparison"]
        assert _read(run / "content.json")["status"] == "blocked-by-evidence"
        assert comparison["dimensions"] == []
        assert comparison["verdict"] is None
        assert comparison["gap_plan"]
        assert all("×" in gap for gap in comparison["gap_plan"])


def test_comparison_blocks_any_union_gap_but_keeps_shared_matrix(tmp_path):
    _, run = _run(
        tmp_path,
        {
            "mode": "comparison",
            "topic": "部分共享矩阵",
            "entities": ["A", "B"],
            "evidence": [
                {"label": "aq", "claim": "A 质量", "source_uri": "https://example.com/aq", "entity": "A", "dimension": "质量"},
                {"label": "ap", "claim": "A 价格", "source_uri": "https://example.com/ap", "entity": "A", "dimension": "价格"},
                {"label": "bq", "claim": "B 质量", "source_uri": "https://example.com/bq", "entity": "B", "dimension": "质量"},
            ],
        },
    )
    artifact = _read(run / "content.json")
    comparison = artifact["mode_data"]["comparison"]
    assert artifact["status"] == "blocked-by-evidence"
    assert comparison["dimensions"] == ["质量"]
    assert all(row["evidence_ids"] for row in comparison["rows"])
    assert comparison["gap_plan"] == ["补充 B × 价格 的同口径证据"]


def test_entities_combine_across_fields_and_reject_cross_field_duplicates(tmp_path):
    evidence = [
        {"label": name, "claim": f"{name} 质量", "source_uri": f"https://example.com/{name}", "entity": name, "dimension": "质量"}
        for name in ("A", "B", "C")
    ]
    _, run = _run(
        tmp_path,
        {
            "mode": "comparison",
            "topic": "组合实体",
            "target_brand": "A",
            "competitors": ["B"],
            "entities": ["C"],
            "evidence": evidence,
        },
    )
    comparison = _read(run / "content.json")["mode_data"]["comparison"]
    assert comparison["entities"] == ["A", "B", "C"]
    assert len(comparison["rows"]) == 3
    duplicate = {
        "mode": "comparison",
        "topic": "重复实体",
        "target_brand": "A",
        "competitors": ["B"],
        "entities": ["a"],
    }
    with pytest.raises(ValueError, match="duplicate entities"):
        content(_write(tmp_path, duplicate, "duplicate.json"), tmp_path / "duplicate-runs")


def test_ranking_requires_method_and_evidence_backed_scores(tmp_path):
    _, blocked_run = _run(tmp_path, {"mode": "ranking", "topic": "工具榜单", "entities": ["A", "B"]}, "blocked")
    blocked = _read(blocked_run / "content.json")
    assert blocked["status"] == "blocked-by-evidence"
    assert blocked["mode_data"]["ranking"]["rows"] == []
    assert "TOP1" not in (blocked_run / "content.md").read_text(encoding="utf-8")

    _, ready_run = _run(
        tmp_path,
        {
            "mode": "ranking",
            "topic": "工具评估",
            "entities": ["A", "B"],
            "evaluation_method": {"name": "同口径评分", "criteria": [{"name": "质量", "weight": 2}]},
            "evidence": [
                {"label": "a", "claim": "A 质量得分 80", "source_uri": "https://example.com/a", "entity": "A", "dimension": "质量", "score": 80},
                {"label": "b", "claim": "B 质量得分 90", "source_uri": "https://example.com/b", "entity": "B", "dimension": "质量", "score": 90},
            ],
        },
        "ready",
    )
    rows = _read(ready_run / "content.json")["mode_data"]["ranking"]["rows"]
    assert [(row["rank"], row["entity"]) for row in rows] == [(1, "B"), (2, "A")]
    assert all(row["evidence_ids"] for row in rows)


def test_ranking_criteria_requires_complete_entity_dimension_matrix(tmp_path):
    _, run = _run(
        tmp_path,
        {
            "mode": "ranking",
            "topic": "完整矩阵",
            "entities": ["A", "B"],
            "evaluation_method": {
                "name": "质量价格评分",
                "criteria": [
                    {"name": "质量", "weight": 2},
                    {"name": "价格", "weight": 1},
                ],
            },
            "evidence": [
                {"label": "a-quality", "claim": "A 质量 80", "source_uri": "https://example.com/aq", "entity": "A", "dimension": "质量", "score": 80},
                {"label": "a-price", "claim": "A 价格 70", "source_uri": "https://example.com/ap", "entity": "A", "dimension": "价格", "score": 70},
                {"label": "b-quality", "claim": "B 质量 90", "source_uri": "https://example.com/bq", "entity": "B", "dimension": "质量", "score": 90},
            ],
        },
    )
    artifact = _read(run / "content.json")
    assert artifact["status"] == "blocked-by-evidence"
    assert artifact["mode_data"]["ranking"]["rows"] == []
    assert any("B × 价格" in item for item in artifact["supplement_requests"])
    assert "TOP1" not in (run / "content.md").read_text(encoding="utf-8")


def test_ranking_string_method_requires_identical_explicit_dimension_sets(tmp_path):
    _, run = _run(
        tmp_path,
        {
            "mode": "ranking",
            "topic": "字符串方法",
            "entities": ["A", "B"],
            "evaluation_method": "同口径平均分",
            "evidence": [
                {"label": "a-quality", "claim": "A 质量 80", "source_uri": "https://example.com/aq", "entity": "A", "dimension": "质量", "score": 80},
                {"label": "a-price", "claim": "A 价格 70", "source_uri": "https://example.com/ap", "entity": "A", "dimension": "价格", "score": 70},
                {"label": "b-quality", "claim": "B 质量 90", "source_uri": "https://example.com/bq", "entity": "B", "dimension": "质量", "score": 90},
            ],
        },
    )
    artifact = _read(run / "content.json")
    assert artifact["status"] == "blocked-by-evidence"
    assert artifact["mode_data"]["ranking"]["rows"] == []
    assert any("B × 价格" in item for item in artifact["supplement_requests"])


def test_ranking_rejects_conflicting_duplicate_entity_dimension_scores(tmp_path):
    brief = {
        "mode": "ranking",
        "topic": "冲突评分",
        "entities": ["A", "B"],
        "evaluation_method": "同口径平均分",
        "evidence": [
            {"label": "a-1", "claim": "A 质量 80", "source_uri": "https://example.com/a1", "entity": "A", "dimension": "质量", "score": 80},
            {"label": "a-2", "claim": "A 质量 70", "source_uri": "https://example.com/a2", "entity": "A", "dimension": "质量", "score": 70},
            {"label": "b", "claim": "B 质量 90", "source_uri": "https://example.com/b", "entity": "B", "dimension": "质量", "score": 90},
        ],
    }
    with pytest.raises(ValueError, match="conflicting duplicate scores"):
        content(_write(tmp_path, brief), tmp_path / "runs")


def test_ranking_rejects_nonfinite_intermediate_without_partial_run(tmp_path):
    brief = {
        "mode": "ranking",
        "topic": "overflow",
        "entities": ["A", "B"],
        "evaluation_method": {
            "name": "overflow-safe",
            "criteria": [{"name": "quality", "weight": 1e308}],
        },
        "evidence": [
            {"label": "a", "claim": "A score", "source_uri": "https://example.com/a", "entity": "A", "dimension": "quality", "score": 1e308},
            {"label": "b", "claim": "B score", "source_uri": "https://example.com/b", "entity": "B", "dimension": "quality", "score": 1e308},
        ],
    }
    runs = tmp_path / "runs"
    with pytest.raises(ValueError, match="ranking.*finite"):
        content(_write(tmp_path, brief), runs)
    assert not runs.exists() or list(runs.iterdir()) == []


@pytest.mark.parametrize("nonfinite", [math.nan, math.inf, -math.inf])
def test_artifact_bus_rejects_nested_nonfinite_json(nonfinite, tmp_path):
    bus = ArtifactBus(tmp_path / "artifacts")
    with pytest.raises(ValueError, match="non-finite"):
        bus.write_json("nested.json", {"outer": [{"value": nonfinite}]})
    assert list(bus.root.rglob("*")) == []


@pytest.mark.parametrize("literal", ("1e9999", "-1e9999"))
def test_artifact_bus_rejects_numeric_overflow_in_staged_manifest(literal, tmp_path):
    runs = tmp_path / "runs"
    with ArtifactBus.transaction(runs, "run-overflow") as bus:
        bus.write_text("payload.txt", "payload")
        bus.write_text(
            "run-manifest.json",
            f'{{"artifacts":["payload.txt"],"nested":{{"value":{literal}}}}}',
        )
        with pytest.raises(ValueError, match="non-finite JSON number"):
            bus.publish({"payload.txt", "run-manifest.json"})
    assert list(runs.iterdir()) == []


def test_evaluation_method_rejects_tie_breaker_in_v01():
    with pytest.raises(ValueError, match="unknown fields"):
        validate_content_brief(
            {
                "mode": "ranking",
                "topic": "tie",
                "evaluation_method": {"name": "method", "tie_breaker": "manual"},
            }
        )


def test_page_blueprint_contains_semantic_html_and_evidence_consistent_schema(tmp_path):
    _, run = _run(
        tmp_path,
        {"mode": "page-blueprint", "topic": "产品页", "evidence": [{"label": "x", "claim": "产品支持离线运行", "source_uri": "https://example.com/product"}]},
    )
    blueprint = _read(run / "content.json")["mode_data"]["page_blueprint"]
    assert blueprint["semantic_html_example"].startswith("<main>")
    assert blueprint["schema_candidates"][0]["claims"] == ["产品支持离线运行"]
    assert blueprint["cms_fields"] and blueprint["acceptance_checklist"]


def test_refine_requires_source_and_article_friendly_reuses_profile(tmp_path):
    with pytest.raises(ValueError, match="requires source_content"):
        validate_content_brief({"mode": "refine", "topic": "原文"})
    source = "核心主张保持不变。\n第二条内容可用于回答问题。"
    _, refine_run = _run(tmp_path, {"mode": "refine", "topic": "原文", "source_content": source}, "refine")
    refine = _read(refine_run / "content.json")["mode_data"]["refinement"]
    assert refine["profile"] == "refine"
    assert any("核心主张保持不变" in item["text"] for item in refine["source_claims"])
    assert refine["after_score"] > refine["before_score"]
    _, article_run = _run(tmp_path, {"mode": "article-friendly", "topic": "原文", "source_content": source}, "article")
    article = _read(article_run / "content.json")["mode_data"]["refinement"]
    assert article["profile"] == "article-friendly"
    assert article["source_claims"] == refine["source_claims"]
    assert any("证据补充" in note for note in article["change_notes"])


def test_refine_binds_each_source_claim_and_unrelated_evidence_cannot_unlock(tmp_path):
    source = "核心主张保持不变。\n第二条内容仍需补证。"
    _, run = _run(
        tmp_path,
        {
            "mode": "refine",
            "topic": "逐条绑定",
            "source_content": source,
            "evidence": [
                {"label": "related", "claim": "核心主张保持不变", "source_uri": "https://example.com/related"},
                {"label": "unrelated", "claim": "完全无关的外部事实", "source_uri": "https://example.com/unrelated"},
            ],
        },
    )
    artifact = _read(run / "content.json")
    claims = artifact["mode_data"]["refinement"]["source_claims"]
    ledger = _read(run / "evidence-ledger.json")
    related_id = next(item["evidence_id"] for item in ledger["records"] if "核心主张" in item["claim"])
    assert claims[0]["evidence_ids"] == [related_id]
    assert claims[0]["status"] == "provided"
    assert claims[1]["evidence_ids"] == []
    assert claims[1]["status"] == "unverified"
    assert artifact["status"] == "unverified"
    assert _read(run / "content-spec.json")["status"] == "draft"
    assert any("第二条内容仍需补证" in item for item in artifact["supplement_requests"])


def test_refine_all_exactly_matched_source_claims_can_be_ready(tmp_path):
    source = "第一条已核验主张。\n第二条已核验主张。"
    _, run = _run(
        tmp_path,
        {
            "mode": "article-friendly",
            "topic": "完整绑定",
            "source_content": source,
            "evidence": [
                {"label": "one", "claim": "第一条已核验主张", "source_uri": "https://example.com/one"},
                {"label": "two", "claim": "第二条已核验主张", "source_uri": "https://example.com/two"},
            ],
        },
    )
    artifact = _read(run / "content.json")
    claims = artifact["mode_data"]["refinement"]["source_claims"]
    assert artifact["status"] == "ready"
    assert _read(run / "content-spec.json")["status"] == "ready"
    assert all(claim["evidence_ids"] and claim["status"] == "provided" for claim in claims)


@pytest.mark.parametrize(
    ("source_claim", "evidence_claim"),
    (
        ("该功能已经正式取消并停止服务", "该功能已经正式取消并停止服务的传言不准确"),
        ("该功能目前仅限企业版客户使用", "该功能目前仅限企业版客户使用的限制已经解除"),
        ("该产品曾经支持本地离线导出功能", "该产品曾经支持本地离线导出功能的记录已被官方更正"),
    ),
)
def test_refine_rejects_high_overlap_semantically_different_evidence(
    tmp_path, source_claim, evidence_claim
):
    _, run = _run(
        tmp_path,
        {
            "mode": "refine",
            "topic": "严格事实匹配",
            "source_content": f"{source_claim}。",
            "evidence": [
                {
                    "label": "semantic-mismatch",
                    "claim": evidence_claim,
                    "source_uri": "https://example.com/semantic-mismatch",
                }
            ],
        },
    )
    artifact = _read(run / "content.json")
    claim = artifact["mode_data"]["refinement"]["source_claims"][0]
    assert claim["evidence_ids"] == []
    assert claim["status"] == "unverified"
    assert artifact["status"] == "unverified"
    assert _read(run / "content-spec.json")["status"] == "draft"


def test_refine_exact_match_normalizes_nfkc_case_whitespace_and_trailing_punctuation(tmp_path):
    _, run = _run(
        tmp_path,
        {
            "mode": "refine",
            "topic": "规范化严格相等",
            "source_content": "Ｆｅａｔｕｒｅ   IS\tAVAILABLE！",
            "evidence": [
                {
                    "label": "equivalent",
                    "claim": "feature is available.",
                    "source_uri": "https://example.com/equivalent",
                }
            ],
        },
    )
    artifact = _read(run / "content.json")
    claim = artifact["mode_data"]["refinement"]["source_claims"][0]
    ledger = _read(run / "evidence-ledger.json")
    assert claim["evidence_ids"] == [ledger["records"][0]["evidence_id"]]
    assert claim["status"] == "provided"
    assert artifact["status"] == "ready"
    assert _read(run / "content-spec.json")["status"] == "ready"


def test_source_snapshot_is_safe_and_replayable(tmp_path):
    source = tmp_path / "source.md"
    source.write_text("需要保留的核心 claim。", encoding="utf-8")
    brief = {"mode": "refine", "topic": "安全快照", "source_content": {"path": "source.md"}}
    result, run = _run(tmp_path, brief, "first")
    normalized = _read(run / "input" / "content-brief.json")
    assert normalized["source_content"]["path"] == "source.md"
    replay = content(run / "input" / "content-brief.json", tmp_path / "replay")
    assert replay["run_id"] == result["run_id"]
    assert (Path(replay["output"]) / "input" / "source.md").read_text(encoding="utf-8") == source.read_text(encoding="utf-8")

    outside = tmp_path.parent / f"{tmp_path.name}-outside.md"
    outside.write_text("secret", encoding="utf-8")
    with pytest.raises(ValueError, match="stay relative"):
        content(_write(tmp_path, {"mode": "refine", "topic": "escape", "source_content": {"path": f"../{outside.name}"}}, "escape.json"), tmp_path / "escape-runs")


def test_source_symlink_is_rejected(tmp_path):
    target = tmp_path / "target.md"
    target.write_text("claim", encoding="utf-8")
    (tmp_path / "link.md").symlink_to(target)
    brief = _write(tmp_path, {"mode": "refine", "topic": "link", "source_content": {"path": "link.md"}})
    with pytest.raises(ValueError, match="unsafe"):
        content(brief, tmp_path / "runs")


def test_brief_and_source_reject_fifo_and_brief_symlink(tmp_path):
    fifo_brief = tmp_path / "brief.fifo"
    os.mkfifo(fifo_brief)
    with pytest.raises(ValueError, match="regular file"):
        content(fifo_brief, tmp_path / "fifo-brief-runs")

    real_brief = _write(tmp_path, {"mode": "title", "topic": "real"}, "real.json")
    linked_brief = tmp_path / "linked.json"
    linked_brief.symlink_to(real_brief)
    with pytest.raises(ValueError, match="unsafe"):
        content(linked_brief, tmp_path / "linked-runs")

    real_parent = tmp_path / "real-parent"
    real_parent.mkdir()
    parent_brief = _write(real_parent, {"mode": "title", "topic": "parent link"})
    linked_parent = tmp_path / "linked-parent"
    linked_parent.symlink_to(real_parent, target_is_directory=True)
    with pytest.raises(ValueError, match="unsafe"):
        content(linked_parent / parent_brief.name, tmp_path / "linked-parent-runs")

    fifo_source = tmp_path / "source.fifo"
    os.mkfifo(fifo_source)
    source_brief = _write(
        tmp_path,
        {"mode": "refine", "topic": "fifo", "source_content": {"path": "source.fifo"}},
        "fifo-source.json",
    )
    with pytest.raises(ValueError, match="regular file"):
        content(source_brief, tmp_path / "fifo-source-runs")


def test_brief_read_uses_open_descriptor_when_path_is_replaced(tmp_path, monkeypatch):
    brief = _write(tmp_path, {"mode": "title", "topic": "original"})
    replacement = _write(tmp_path, {"mode": "title", "topic": "replacement"}, "replacement.json")
    real_open = os.open
    replaced = False

    def racing_open(path, flags, mode=0o777, *, dir_fd=None):
        nonlocal replaced
        descriptor = real_open(path, flags, mode, dir_fd=dir_fd)
        if not replaced and dir_fd is not None and path == brief.name:
            os.replace(replacement, brief)
            replaced = True
        return descriptor

    monkeypatch.setattr(content_module.os, "open", racing_open)
    result = content(brief, tmp_path / "runs")
    output = Path(result["output"])
    assert _read(output / "input" / "content-brief.json")["topic"] == "original"


def test_source_read_uses_open_descriptor_when_path_is_replaced(tmp_path, monkeypatch):
    source = tmp_path / "source.md"
    source.write_text("original source claim", encoding="utf-8")
    replacement = tmp_path / "replacement.md"
    replacement.write_text("replacement source claim", encoding="utf-8")
    brief = _write(
        tmp_path,
        {"mode": "refine", "topic": "source race", "source_content": {"path": "source.md"}},
    )
    real_open = os.open
    replaced = False

    def racing_open(path, flags, mode=0o777, *, dir_fd=None):
        nonlocal replaced
        descriptor = real_open(path, flags, mode, dir_fd=dir_fd)
        if not replaced and dir_fd is not None and path == "source.md":
            os.replace(replacement, source)
            replaced = True
        return descriptor

    monkeypatch.setattr(content_module.os, "open", racing_open)
    result = content(brief, tmp_path / "runs")
    output = Path(result["output"])
    assert (output / "input" / "source.md").read_text(encoding="utf-8") == "original source claim"


def test_brief_growth_after_fstat_is_rejected(tmp_path, monkeypatch):
    brief = _write(tmp_path, {"mode": "title", "topic": "growth"})
    real_read = os.read
    grew = False

    def growing_read(file_descriptor, count):
        nonlocal grew
        chunk = real_read(file_descriptor, count)
        if chunk and not grew:
            with brief.open("ab") as stream:
                stream.write(b" " * (MAX_INPUT_BYTES + 1))
            grew = True
        return chunk

    monkeypatch.setattr(content_module.os, "read", growing_read)
    with pytest.raises(ValueError, match="exceeds"):
        content(brief, tmp_path / "runs")


def test_source_commonmark_is_plain_text_and_cannot_create_structure(tmp_path):
    source = """Readable source
## injected heading
> injected quote
- injected list
setext heading
===
    indented code
```python
print('unsafe')
```
[link](https://example.com)
![image](https://example.com/x.png)
<script>alert(1)</script>"""
    _, run = _run(
        tmp_path,
        {"mode": "article-friendly", "topic": "Markdown 安全", "source_content": source},
    )
    markdown = (run / "content.md").read_text(encoding="utf-8")
    assert len(re.findall(r"^# ", markdown, re.MULTILINE)) == 2
    assert "\n## injected heading" not in markdown
    assert "\n> injected quote" not in markdown
    assert "\n- injected list" not in markdown
    assert "\n===" not in markdown
    assert "\n    indented code" not in markdown
    assert "```" not in markdown
    assert "[link](https://example.com)" not in markdown
    assert "![image](https://example.com/x.png)" not in markdown
    assert "<script>" not in markdown
    assert r"\#\# injected heading" in markdown
    assert r"\[link\]\(https://example\.com\)" in markdown
    assert "&lt;script&gt;" in markdown


def test_html_escapes_user_text_and_has_sticky_print_navigation(tmp_path):
    attack = '<script>alert("x")</script><img src=x onerror=alert(1)>\n# injected-heading'
    _, run = _run(tmp_path, {"mode": "title", "topic": attack})
    rendered = (run / "content.html").read_text(encoding="utf-8")
    assert attack not in rendered
    assert "&lt;script&gt;" in rendered
    assert "position:sticky" in rendered
    assert "@media print" in rendered
    assert "内容主体" in rendered and "补充说明与参考来源" in rendered
    assert "http://" not in rendered and "https://" not in rendered
    markdown = (run / "content.md").read_text(encoding="utf-8")
    assert markdown.count("\n# ") == 2


def test_optional_renderers_create_valid_files_when_available(tmp_path):
    pytest.importorskip("docx")
    if importlib.util.find_spec("weasyprint") is None and importlib.util.find_spec("reportlab") is None:
        pytest.skip("no PDF renderer")
    _, run = _run(tmp_path, {"mode": "title", "topic": "渲染", "desired_formats": ["docx", "pdf"]})
    assert zipfile.is_zipfile(run / "content.docx")
    assert (run / "content.pdf").read_bytes().startswith(b"%PDF")
    manifest = _read(run / "run-manifest.json")
    assert "content.docx" in manifest["artifacts"] and "content.pdf" in manifest["artifacts"]


def test_missing_optional_renderers_degrade_explicitly(tmp_path, monkeypatch):
    real_import = importlib.import_module

    def unavailable(name, package=None):
        if name in {"docx", "weasyprint", "reportlab.pdfgen.canvas"}:
            raise ModuleNotFoundError(name)
        return real_import(name, package)

    monkeypatch.setattr(importlib, "import_module", unavailable)
    _, run = _run(tmp_path, {"mode": "title", "topic": "降级", "desired_formats": ["docx", "pdf"]})
    assert not (run / "content.docx").exists() and not (run / "content.pdf").exists()
    quality = _read(run / "quality-report.json")
    assert quality["status"] == "passed-with-warnings"
    assert any("DOCX renderer" in item for item in quality["warnings"])
    assert any("PDF renderer" in item for item in quality["warnings"])
    manifest = _read(run / "run-manifest.json")
    assert manifest["status"] == "completed-with-warnings"
    assert manifest["degraded"] is True
    assert manifest["missing_dependencies"] == ["python-docx", "reportlab", "weasyprint"]


def test_pdf_fallback_records_only_missing_primary_dependency(tmp_path, monkeypatch):
    real_import = importlib.import_module

    class FakeCanvas:
        def __init__(self, buffer):
            self.buffer = buffer

        def drawString(self, *_args):
            return None

        def showPage(self):
            return None

        def save(self):
            self.buffer.write(b"%PDF-1.4\n% synthetic reportlab fixture\n")

    class FakeReportLab:
        Canvas = FakeCanvas

    def primary_missing(name, package=None):
        if name == "weasyprint":
            raise ModuleNotFoundError("No module named 'weasyprint'", name="weasyprint")
        if name == "reportlab.pdfgen.canvas":
            return FakeReportLab
        return real_import(name, package)

    monkeypatch.setattr(importlib, "import_module", primary_missing)
    _, run = _run(tmp_path, {"mode": "title", "topic": "fallback", "desired_formats": ["pdf"]})
    assert (run / "content.pdf").read_bytes().startswith(b"%PDF")
    manifest = _read(run / "run-manifest.json")
    assert manifest["degraded"] is True
    assert manifest["missing_dependencies"] == ["weasyprint"]
    assert manifest["renderer_errors"] == []


def test_pdf_fallback_separates_renderer_error_from_missing_dependency(tmp_path, monkeypatch):
    real_import = importlib.import_module

    class FakeCanvas:
        def __init__(self, buffer):
            self.buffer = buffer

        def drawString(self, *_args):
            return None

        def showPage(self):
            return None

        def save(self):
            self.buffer.write(b"%PDF-1.4\n% synthetic reportlab fixture\n")

    class FakeReportLab:
        Canvas = FakeCanvas

    class BrokenHTML:
        def __init__(self, **_kwargs):
            pass

        def write_pdf(self):
            raise RuntimeError("synthetic renderer failure")

    class BrokenWeasyPrint:
        HTML = BrokenHTML

    def primary_broken(name, package=None):
        if name == "weasyprint":
            return BrokenWeasyPrint
        if name == "reportlab.pdfgen.canvas":
            return FakeReportLab
        return real_import(name, package)

    monkeypatch.setattr(importlib, "import_module", primary_broken)
    _, run = _run(tmp_path, {"mode": "title", "topic": "renderer error", "desired_formats": ["pdf"]})
    assert (run / "content.pdf").read_bytes().startswith(b"%PDF")
    manifest = _read(run / "run-manifest.json")
    assert manifest["degraded"] is True
    assert manifest["missing_dependencies"] == []
    assert len(manifest["renderer_errors"]) == 1
    assert manifest["renderer_errors"][0].startswith("weasyprint:")


def test_artifact_bus_failure_does_not_publish_partial_run(tmp_path, monkeypatch):
    brief = _write(tmp_path, {"mode": "title", "topic": "atomic"})

    def fail_publish(self, expected_files):
        raise RuntimeError("simulated publish failure")

    monkeypatch.setattr(ArtifactBus, "publish", fail_publish)
    with pytest.raises(RuntimeError, match="simulated"):
        content(brief, tmp_path / "runs")
    assert list((tmp_path / "runs").iterdir()) == []


def test_core_artifacts_and_manifest_exact_file_set(tmp_path):
    result, run = _run(tmp_path, {"mode": "explainer", "topic": "产物"})
    expected = {
        "input/content-brief.json",
        "content-spec.json",
        "content.json",
        "content.md",
        "content.html",
        "evidence-ledger.json",
        "quality-report.json",
        "run-manifest.json",
    }
    actual = {path.relative_to(run).as_posix() for path in run.rglob("*") if path.is_file()}
    assert actual == expected
    manifest = _read(run / "run-manifest.json")
    assert set(manifest["artifacts"]) == expected - {"run-manifest.json"}
    assert run.parent.name == "runs" and run.name == result["run_id"]


def test_strict_contract_limits_and_cli_json_error(tmp_path, capsys):
    with pytest.raises(ValueError, match="unknown fields"):
        validate_content_brief({"mode": "title", "topic": "x", "unexpected": True})
    oversized = tmp_path / "oversized.json"
    oversized.write_bytes(b" " * (MAX_INPUT_BYTES + 1))
    with pytest.raises(ValueError, match="exceeds"):
        content(oversized, tmp_path / "runs")
    bad = _write(tmp_path, {"mode": "refine", "topic": "missing source"}, "bad.json")
    assert main(["content", "--input", str(bad), "--output", str(tmp_path / "cli-runs")]) == 2
    error = json.loads(capsys.readouterr().err)
    assert error["status"] == "error"
