from __future__ import annotations

import hashlib
import html
import importlib
import io
import json
import math
import os
import re
import stat
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlsplit

from .artifact_bus import ArtifactBus
from .quality.lineage import build_run_lineage
from .intelligence.content import build_claim_map, build_content_pipeline, evaluate_mcda
from .validation import read_bounded_regular_file, strict_json_loads, validate_artifact
from .version import package_version

PROTOCOL_VERSION = "1.0.0"
GENERATOR_VERSION = package_version()
MAX_INPUT_BYTES = 1024 * 1024
MAX_SOURCE_BYTES = 2 * 1024 * 1024
MODES = {
    "title",
    "explainer",
    "comparison",
    "ranking",
    "page-blueprint",
    "refine",
    "article-friendly",
}
FORMATS = {"markdown", "json", "html", "docx", "pdf"}
DEFAULT_FORMATS = ["markdown", "json", "html"]
UNSUPPORTED_TITLE_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"(?:19|20)\d{2}年?",
        r"100\s*[%％]\s*(?:有效)?",
        r"今年|今日|当下|当前|实时|刚刚",
        r"绝对有效|终极|顶级|完美|唯一|万能|无敌|首选|行业领先",
        r"最好|第一|最新|最强|权威|保证",
        r"\b(?:today|now|real[ -]?time|up[ -]?to[ -]?date)\b",
        r"\b(?:absolute(?:ly)? effective|ultimate|top(?:\s*1|[ -]?tier)?|perfect|unique|only)\b",
        r"\b(?:universal|all[ -]?purpose|unbeatable|invincible|preferred)\b",
        r"\b(?:first choice|industry[ -]?leading)\b",
        r"\b(?:best|first|latest|newest|most recent|authoritative|guarantee(?:s|d)?)\b",
        r"(?:#\s*1|\btop\s*1\b|\bno\.\s*1\b)",
    )
)
Clock = Callable[[], datetime]
TypedBlock = tuple[str, str]


class RendererFailure(RuntimeError):
    def __init__(self, message: str, *, missing_dependencies: list[str], renderer_errors: list[str], warnings: list[str]):
        super().__init__(message)
        self.missing_dependencies = missing_dependencies
        self.renderer_errors = renderer_errors
        self.warnings = warnings


def _stable_id(prefix: str, *parts: str) -> str:
    canonical = "\x1f".join(parts).encode("utf-8")
    return f"{prefix}-{hashlib.sha256(canonical).hexdigest()[:12]}"


def _require_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-blank string")
    return value.strip()


def _string_list(value: Any, field: str, *, unique: bool = True) -> list[str]:
    if not isinstance(value, list):
        raise ValueError(f"{field} must be an array")
    cleaned = [_require_text(item, f"{field}[{index}]") for index, item in enumerate(value)]
    if unique and len({item.casefold() for item in cleaned}) != len(cleaned):
        raise ValueError(f"{field} must contain unique values")
    return cleaned


def _source_uri(value: Any, field: str) -> str:
    uri = _require_text(value, field)
    if not urlsplit(uri).scheme or re.search(r"\s", uri):
        raise ValueError(f"{field} must be an absolute URI")
    return uri


def _open_flags(*, directory: bool = False) -> int:
    flags = os.O_RDONLY
    for name in ("O_NOFOLLOW", "O_NONBLOCK", "O_CLOEXEC"):
        flags |= getattr(os, name, 0)
    if directory:
        flags |= getattr(os, "O_DIRECTORY", 0)
    return flags


def _read_regular_fd(file_descriptor: int, max_bytes: int, field: str) -> bytes:
    file_stat = os.fstat(file_descriptor)
    if not stat.S_ISREG(file_stat.st_mode):
        raise ValueError(f"{field} must be a regular file")
    if file_stat.st_size > max_bytes:
        raise ValueError(f"{field} exceeds {max_bytes} bytes")
    chunks: list[bytes] = []
    count = 0
    while True:
        chunk = os.read(file_descriptor, min(64 * 1024, max_bytes + 1 - count))
        if not chunk:
            break
        chunks.append(chunk)
        count += len(chunk)
        if count > max_bytes:
            raise ValueError(f"{field} exceeds {max_bytes} bytes")
    return b"".join(chunks)


def _load_content_brief(path: Path) -> dict[str, Any]:
    try:
        raw = read_bounded_regular_file(
            path,
            max_bytes=MAX_INPUT_BYTES,
            field="content brief",
        ).decode("utf-8")
        value = strict_json_loads(raw)
    except (UnicodeDecodeError, ValueError) as exc:
        raise ValueError(f"content brief is not valid UTF-8 JSON: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError("content brief must be a JSON object")
    return value


def _validate_evaluation_method(value: Any) -> str | dict[str, Any]:
    if isinstance(value, str):
        return _require_text(value, "evaluation_method")
    if not isinstance(value, dict):
        raise ValueError("evaluation_method must be a non-blank string or an object")
    allowed = {"name", "criteria", "score_scale", "normalization", "weighting", "missing_value", "tie_policy"}
    extra = sorted(set(value) - allowed)
    if extra:
        raise ValueError(f"evaluation_method has unknown fields: {', '.join(extra)}")
    normalized: dict[str, Any] = {"name": _require_text(value.get("name"), "evaluation_method.name")}
    if "criteria" in value:
        criteria = value["criteria"]
        if not isinstance(criteria, list) or not criteria:
            raise ValueError("evaluation_method.criteria must be a non-empty array")
        seen: set[str] = set()
        normalized_criteria = []
        for index, criterion in enumerate(criteria):
            if not isinstance(criterion, dict) or set(criterion) - {"name", "weight", "polarity"} or "name" not in criterion:
                raise ValueError(f"evaluation_method.criteria[{index}] has invalid fields")
            name = _require_text(criterion["name"], f"evaluation_method.criteria[{index}].name")
            if name.casefold() in seen:
                raise ValueError("evaluation_method criteria names must be unique")
            seen.add(name.casefold())
            weight = criterion.get("weight", 1.0)
            if not isinstance(weight, (int, float)) or isinstance(weight, bool) or not math.isfinite(weight) or weight <= 0:
                raise ValueError(f"evaluation_method.criteria[{index}].weight must be positive")
            normalized_criterion = {"name": name, "weight": float(weight)}
            if "polarity" in criterion:
                if criterion["polarity"] not in {"benefit", "cost"}:
                    raise ValueError(f"evaluation_method.criteria[{index}].polarity must be benefit or cost")
                normalized_criterion["polarity"] = criterion["polarity"]
            normalized_criteria.append(normalized_criterion)
        normalized["criteria"] = normalized_criteria
    for field in ("score_scale", "normalization", "weighting", "missing_value", "tie_policy"):
        if field in value:
            normalized[field] = _require_text(value[field], f"evaluation_method.{field}")
    return normalized


def validate_content_brief(value: Any) -> dict[str, Any]:
    """Validate a strict content brief without accepting undeclared extension fields."""
    if not isinstance(value, dict):
        raise ValueError("content brief must be a JSON object")
    allowed = {
        "mode",
        "topic",
        "locale",
        "audience",
        "goal",
        "target_brand",
        "competitors",
        "entities",
        "query_ids",
        "evidence",
        "source_content",
        "desired_formats",
        "compliance_notes",
        "page_type",
        "evaluation_method",
    }
    extra = sorted(set(value) - allowed)
    if extra:
        raise ValueError(f"content brief has unknown fields: {', '.join(extra)}")
    mode = value.get("mode")
    if mode not in MODES:
        raise ValueError(f"mode must be one of: {', '.join(sorted(MODES))}")
    _require_text(value.get("topic"), "topic")
    for field in ("locale", "audience", "goal", "target_brand", "page_type"):
        if field in value:
            _require_text(value[field], field)
    for field in ("competitors", "entities", "query_ids", "compliance_notes"):
        if field in value:
            _string_list(value[field], field)
    formats = value.get("desired_formats", DEFAULT_FORMATS)
    cleaned_formats = _string_list(formats, "desired_formats")
    invalid_formats = sorted(set(cleaned_formats) - FORMATS)
    if invalid_formats:
        raise ValueError(f"desired_formats has unsupported values: {', '.join(invalid_formats)}")

    evidence = value.get("evidence", [])
    if not isinstance(evidence, list):
        raise ValueError("evidence must be an array")
    labels: list[str] = []
    for index, record in enumerate(evidence):
        allowed_evidence = {"label", "claim", "source_uri", "entity", "dimension", "score"}
        if not isinstance(record, dict) or set(record) - allowed_evidence:
            raise ValueError(f"evidence[{index}] has invalid fields")
        if not {"label", "claim", "source_uri"} <= set(record):
            raise ValueError(f"evidence[{index}] requires label, claim, and source_uri")
        labels.append(_require_text(record["label"], f"evidence[{index}].label"))
        _require_text(record["claim"], f"evidence[{index}].claim")
        _source_uri(record["source_uri"], f"evidence[{index}].source_uri")
        for field in ("entity", "dimension"):
            if field in record:
                _require_text(record[field], f"evidence[{index}].{field}")
        if "score" in record and (
            not isinstance(record["score"], (int, float)) or isinstance(record["score"], bool)
            or not math.isfinite(record["score"])
        ):
            raise ValueError(f"evidence[{index}].score must be numeric")
    if len({label.casefold() for label in labels}) != len(labels):
        raise ValueError("content brief evidence labels must be unique")

    source = value.get("source_content")
    if source is not None:
        if isinstance(source, str):
            if not source.strip():
                raise ValueError("source_content must not be blank")
            if len(source.encode("utf-8")) > MAX_SOURCE_BYTES:
                raise ValueError(f"source_content exceeds {MAX_SOURCE_BYTES} bytes")
        elif isinstance(source, dict):
            if set(source) - {"path", "sha256", "source_uri"} or "path" not in source:
                raise ValueError("source_content file object has invalid fields")
            _require_text(source["path"], "source_content.path")
            if "sha256" in source and not re.fullmatch(r"[0-9a-f]{64}", _require_text(source["sha256"], "source_content.sha256")):
                raise ValueError("source_content.sha256 must be a lowercase SHA-256 digest")
            if "source_uri" in source:
                _source_uri(source["source_uri"], "source_content.source_uri")
        else:
            raise ValueError("source_content must be inline text or a file object")
    if mode in {"refine", "article-friendly"} and source is None:
        raise ValueError(f"{mode} mode requires source_content")
    if "evaluation_method" in value:
        _validate_evaluation_method(value["evaluation_method"])
    return value


def _read_relative_source(source: dict[str, Any], input_path: Path) -> tuple[str, str]:
    path = Path(source["path"].strip())
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise ValueError("source_content path must stay relative to the brief directory")
    opened: list[int] = []
    try:
        current = os.open(input_path.parent, _open_flags(directory=True))
        opened.append(current)
        for component in path.parts[:-1]:
            current = os.open(component, _open_flags(directory=True), dir_fd=current)
            opened.append(current)
        file_descriptor = os.open(
            path.parts[-1],
            _open_flags(),
            dir_fd=current,
        )
        opened.append(file_descriptor)
        body = _read_regular_fd(
            file_descriptor, MAX_SOURCE_BYTES, "source_content"
        ).decode("utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise ValueError(f"source_content is unavailable, unsafe, or not UTF-8: {path}") from exc
    finally:
        for descriptor in reversed(opened):
            try:
                os.close(descriptor)
            except OSError:
                pass
    digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
    if source.get("sha256") and source["sha256"] != digest:
        raise ValueError("source_content digest does not match its file snapshot")
    return body, source.get("source_uri", "urn:geo-seo-hub:input:source-content")


def _normalize_brief(brief: dict[str, Any], input_path: Path) -> tuple[dict[str, Any], str | None]:
    normalized: dict[str, Any] = {"mode": brief["mode"], "topic": brief["topic"].strip()}
    for field in ("locale", "audience", "goal", "target_brand", "page_type"):
        if field in brief:
            normalized[field] = brief[field].strip()
    for field in ("competitors", "entities", "query_ids", "compliance_notes"):
        if field in brief:
            normalized[field] = _string_list(brief[field], field)
    normalized["desired_formats"] = _string_list(brief.get("desired_formats", DEFAULT_FORMATS), "desired_formats")
    if "evaluation_method" in brief:
        normalized["evaluation_method"] = _validate_evaluation_method(brief["evaluation_method"])

    records = []
    for record in brief.get("evidence", []):
        claim = record["claim"].strip()
        uri = _source_uri(record["source_uri"], "evidence.source_uri")
        item: dict[str, Any] = {"label": _stable_id("ev", claim, uri), "claim": claim, "source_uri": uri}
        for field in ("entity", "dimension"):
            if field in record:
                item[field] = record[field].strip()
        if "score" in record:
            item["score"] = float(record["score"])
        records.append(item)
    records.sort(key=lambda item: item["label"])
    if len({record["label"] for record in records}) != len(records):
        raise ValueError("content brief contains duplicate normalized evidence records")
    if records:
        normalized["evidence"] = records

    source_text: str | None = None
    if "source_content" in brief:
        source = brief["source_content"]
        if isinstance(source, str):
            source_text = source
            source_uri = "urn:geo-seo-hub:input:source-content"
        else:
            source_text, source_uri = _read_relative_source(source, input_path)
        digest = hashlib.sha256(source_text.encode("utf-8")).hexdigest()
        normalized["source_content"] = {
            "path": "source.md",
            "sha256": digest,
            "source_uri": source_uri,
        }
    return normalized, source_text


def _entities(brief: dict[str, Any]) -> list[str]:
    values = [
        brief.get("target_brand", ""),
        *brief.get("competitors", []),
        *brief.get("entities", []),
    ]
    entities: list[str] = []
    seen: set[str] = set()
    for value in values:
        if not value:
            continue
        key = value.casefold()
        if key in seen:
            raise ValueError(
                "target_brand, competitors, and entities must not contain duplicate entities"
            )
        seen.add(key)
        entities.append(value)
    return entities


def _sections_for_mode(mode: str) -> list[dict[str, str]]:
    headings = {
        "title": ["候选标题", "意图与场景", "证据与合规", "文章结构映射"],
        "explainer": ["核心摘要", "定义与边界", "原理与原因", "实践步骤", "选择标准", "常见误区", "常见问题", "来源说明"],
        "comparison": ["比较范围", "证据维度", "中立对照", "信息缺口", "补证计划", "限制与来源"],
        "ranking": ["评估方法", "权重与分数", "排序结果", "限制", "来源说明", "复核清单"],
        "page-blueprint": ["页面目标", "信息架构", "可抽取摘要与问答", "表格模块", "语义 HTML", "Schema 候选", "CMS 字段", "验收清单"],
        "refine": ["优化后摘要", "优化后正文", "术语与结构", "可回答问题", "改动说明", "证据缺口"],
        "article-friendly": ["发布摘要", "发布友好正文", "术语与结构", "可回答问题", "证据补充标记", "风险说明"],
    }[mode]
    return [{"heading": heading, "purpose": f"提供{heading}所需的结构、边界与证据状态。"} for heading in headings]


def _evidence_ledger(brief: dict[str, Any], run_id: str) -> dict[str, Any]:
    records = [
        {
            "evidence_id": item["label"],
            "claim": item["claim"],
            "source_uri": item["source_uri"],
            "status": "provided",
        }
        for item in brief.get("evidence", [])
    ]
    missing = [] if records else ["source_gap: provide evidence for factual claims before publication"]
    return {"protocol_version": PROTOCOL_VERSION, "run_id": run_id, "records": records, "missing_evidence": missing}


def _factual_claims(brief: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "claim_id": _stable_id("claim", item["claim"], item["label"]),
            "text": item["claim"],
            "evidence_ids": [item["label"]],
            "status": "provided",
        }
        for item in brief.get("evidence", [])
    ]


def _clean_title_topic(topic: str) -> str:
    cleaned = topic
    for pattern in UNSUPPORTED_TITLE_PATTERNS:
        cleaned = pattern.sub("", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip(" ：:-") or "主题"


def _validate_title_candidate(title: str) -> None:
    for pattern in UNSUPPORTED_TITLE_PATTERNS:
        if pattern.search(title):
            raise ValueError(
                f"generated title contains an unsupported compliance pattern: {pattern.pattern}"
            )


def _title_candidates(brief: dict[str, Any]) -> list[dict[str, Any]]:
    topic = _clean_title_topic(brief["topic"])
    audience = _clean_title_topic(brief.get("audience", "目标读者"))
    patterns = [
        (f"{topic}：面向{audience}的核心问题与证据线索", "问题—证据", "研究", "信息核验"),
        (f"如何理解{topic}：定义、边界与实践路径", "解释—路径", "学习", "入门理解"),
        (f"{topic}对比指南：维度、证据与选择方法", "维度—选择", "比较", "方案选择"),
        (f"从问题到行动：{topic}的场景化解读", "场景—行动", "行动", "实践落地"),
        (f"{topic}常见误区与核验清单", "误区—清单", "核验", "发布前检查"),
    ]
    evidence_score = 100 if brief.get("evidence") else 40
    compliance_score = 95 if brief.get("compliance_notes") else 100
    candidates = [
        {
            "title": title,
            "pattern": pattern,
            "intent": intent,
            "scenario": scenario,
            "scores": {"intent": 90 - index * 3, "scenario": 86 - index * 2, "evidence": evidence_score, "compliance": compliance_score},
            "structure_mapping": ["核心摘要", "主体论证", "证据与限制", "常见问题"],
        }
        for index, (title, pattern, intent, scenario) in enumerate(patterns)
    ]
    for candidate in candidates:
        _validate_title_candidate(candidate["title"])
    return candidates


def _normalize_claim_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized.rstrip("。！？.!?；;：:'\"“”‘’（）()[]【】")


def _claim_text_matches(source_claim: str, evidence_claim: str) -> bool:
    source = _normalize_claim_text(source_claim)
    evidence = _normalize_claim_text(evidence_claim)
    return bool(source) and source == evidence


def _source_claims(
    source_text: str | None, evidence: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    if not source_text:
        return []
    candidates = [part.strip() for part in re.split(r"(?<=[。！？.!?])\s+|\n+", source_text) if part.strip()]
    claims = []
    for part in candidates[:20]:
        evidence_ids = sorted(
            item["label"]
            for item in evidence
            if _claim_text_matches(part, item["claim"])
        )
        claims.append(
            {
                "text": part,
                "status": "provided" if evidence_ids else "unverified",
                "evidence_ids": evidence_ids,
            }
        )
    return claims


def _ranking_score_cells(
    brief: dict[str, Any], entities: list[str]
) -> tuple[dict[tuple[str, str], list[dict[str, Any]]], set[str]]:
    entity_names = {entity.casefold() for entity in entities}
    cells: dict[tuple[str, str], list[dict[str, Any]]] = {}
    missing_dimension_entities: set[str] = set()
    for item in brief.get("evidence", []):
        entity = item.get("entity", "").casefold()
        if entity not in entity_names or "score" not in item:
            continue
        if "dimension" not in item:
            missing_dimension_entities.add(entity)
            continue
        key = (entity, item["dimension"].casefold())
        cells.setdefault(key, []).append(item)
    for (entity, dimension), records in cells.items():
        scores = {float(item["score"]) for item in records}
        if any(not math.isfinite(score) for score in scores):
            raise ValueError(f"ranking score must be finite for {entity} × {dimension}")
        if len(scores) > 1:
            raise ValueError(
                f"ranking has conflicting duplicate scores for {entity} × {dimension}"
            )
    return cells, missing_dimension_entities


def _ranking_rows(
    entities: list[str],
    dimensions: list[tuple[str, float]],
    cells: dict[tuple[str, str], list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    rows = []
    for entity in entities:
        weighted: list[tuple[float, float]] = []
        evidence_ids: list[str] = []
        for dimension, weight in dimensions:
            records = cells[(entity.casefold(), dimension.casefold())]
            value = float(records[0]["score"])
            product = value * weight
            if not all(math.isfinite(number) for number in (value, weight, product)):
                raise ValueError(f"ranking weighted product must be finite for {entity} × {dimension}")
            weighted.append((value, weight))
            evidence_ids.extend(item["label"] for item in records)
        try:
            numerator = math.fsum(value * weight for value, weight in weighted)
            denominator = math.fsum(weight for _, weight in weighted)
        except OverflowError as exc:
            raise ValueError(f"ranking aggregate must be finite for {entity}") from exc
        if not all(math.isfinite(number) for number in (numerator, denominator)) or denominator <= 0:
            raise ValueError(f"ranking aggregate must be finite for {entity}")
        score = numerator / denominator
        if not math.isfinite(score):
            raise ValueError(f"ranking result must be finite for {entity}")
        rows.append(
            {
                "entity": entity,
                "score": round(score, 4),
                "evidence_ids": sorted(evidence_ids),
            }
        )
    rows.sort(key=lambda item: (-item["score"], item["entity"].casefold()))
    for index, row in enumerate(rows):
        row["rank"] = index + 1
    return rows


def _build_content(
    brief: dict[str, Any],
    run_id: str,
    source_text: str | None,
    *,
    execution_mode: str = "legacy",
) -> dict[str, Any]:
    mode = brief["mode"]
    entities = _entities(brief)
    evidence_by_entity = {
        entity: [item for item in brief.get("evidence", []) if item.get("entity", "").casefold() == entity.casefold()]
        for entity in entities
    }
    status = "ready" if brief.get("evidence") else "unverified"
    supplement_requests: list[str] = []
    mode_data: dict[str, Any]
    guidance = ["guidance: validate claims, audience fit, and compliance notes before publication"]

    if mode == "title":
        mode_data = {"title_candidates": _title_candidates(brief)}
    elif mode == "explainer":
        mode_data = {
            "explainer": {
                "core_summary": f"围绕“{brief['topic']}”建立可核验的解释框架。",
                "definition_boundary": "说明术语适用范围、排除项与证据边界。",
                "why": "从机制、条件和影响路径解释原因。",
                "how_to": ["确认读者问题", "匹配证据", "按步骤展开", "复核限制"],
                "selection_criteria": ["相关性", "可验证性", "时效范围", "适用条件"],
                "misconceptions": ["把通用建议写成事实", "忽略来源的适用范围"],
                "faq": [f"什么是{brief['topic']}？", f"如何核验{brief['topic']}相关说法？"],
                "source_note": "事实仅来自 evidence ledger；其余内容属于 guidance。",
            }
        }
    elif mode == "comparison":
        if len(entities) < 2:
            raise ValueError("comparison mode requires at least two entities")
        missing_dimension_entities = [
            entity
            for entity in entities
            if any("dimension" not in item for item in evidence_by_entity[entity])
        ]
        dimension_sets = [
            {item["dimension"] for item in evidence_by_entity[entity] if "dimension" in item}
            for entity in entities
        ]
        comparable_dimensions = set.intersection(*dimension_sets) if dimension_sets else set()
        all_dimensions = set.union(*dimension_sets) if dimension_sets else set()
        comparison_gaps = [
            f"补充 {entity} × {dimension} 的同口径证据"
            for dimension in sorted(all_dimensions)
            for entity, dimensions in zip(entities, dimension_sets)
            if dimension not in dimensions
        ]
        comparison_gaps.extend(
            f"补充 {entity} × <明确 dimension> 的证据标注"
            for entity in missing_dimension_entities
        )
        if not all_dimensions:
            comparison_gaps.extend(
                f"补充 {entity} × <共同 dimension> 的同口径证据"
                for entity, dimensions in zip(entities, dimension_sets)
                if not dimensions and entity not in missing_dimension_entities
            )
        comparison_blocked = (
            not comparable_dimensions
            or bool(missing_dimension_entities)
            or bool(comparison_gaps)
        )
        if comparison_blocked:
            status = "blocked-by-evidence"
            supplement_requests.extend(comparison_gaps)
        dimensions = sorted(comparable_dimensions)
        mode_data = {
            "comparison": {
                "entities": entities,
                "dimensions": dimensions,
                "rows": [
                    {
                        "entity": entity,
                        "evidence_ids": [
                            item["label"]
                            for item in evidence_by_entity[entity]
                            if item.get("dimension") in comparable_dimensions
                        ],
                    }
                    for entity in entities
                ],
                "verdict": None,
                "gap_plan": comparison_gaps if comparison_blocked else [],
                "neutrality": "No winner is declared; compare only evidence-backed dimensions.",
            }
        }
    elif mode == "ranking":
        if len(entities) < 2:
            raise ValueError("ranking mode requires at least two entities")
        method = brief.get("evaluation_method")
        score_cells, missing_dimension_entities = _ranking_score_cells(brief, entities)
        ranking_gaps: list[str] = []
        dimensions: list[tuple[str, float]] = []
        if isinstance(method, dict):
            dimensions = [
                (item["name"], float(item["weight"]))
                for item in method.get("criteria", [])
            ]
            if not dimensions:
                ranking_gaps.append("补充 evaluation_method.criteria 及明确权重")
            for dimension, _weight in dimensions:
                for entity in entities:
                    if (entity.casefold(), dimension.casefold()) not in score_cells:
                        ranking_gaps.append(
                            f"补充 {entity} × {dimension} 的 evidence-backed numeric score"
                        )
        elif isinstance(method, str):
            dimension_sets = [
                {
                    dimension
                    for entity_name, dimension in score_cells
                    if entity_name == entity.casefold()
                }
                for entity in entities
            ]
            all_dimensions = set.union(*dimension_sets) if dimension_sets else set()
            if not all_dimensions:
                ranking_gaps.append("补充至少一个所有实体共有的非空 dimension 评分")
            for dimension in sorted(all_dimensions):
                for entity, entity_dimensions in zip(entities, dimension_sets):
                    if dimension not in entity_dimensions:
                        ranking_gaps.append(
                            f"补充 {entity} × {dimension} 的 evidence-backed numeric score"
                        )
            if dimension_sets and all(
                entity_dimensions == dimension_sets[0]
                for entity_dimensions in dimension_sets[1:]
            ) and dimension_sets[0]:
                display_dimensions = {
                    item["dimension"].casefold(): item["dimension"]
                    for item in brief.get("evidence", [])
                    if "dimension" in item and "score" in item
                }
                dimensions = [
                    (display_dimensions[dimension], 1.0)
                    for dimension in sorted(dimension_sets[0])
                ]
        else:
            ranking_gaps.append("补充明确的 evaluation_method、权重或评分口径")
        ranking_gaps.extend(
            f"补充 {entity} × <明确 dimension> 的评分标注"
            for entity in entities
            if entity.casefold() in missing_dimension_entities
        )
        if execution_mode != "legacy":
            if not isinstance(method, dict):
                ranking_gaps.append("MCDA requires a structured evaluation_method object")
            elif any(item.get("polarity") not in {"benefit", "cost"} for item in method.get("criteria", [])):
                ranking_gaps.append("MCDA requires benefit or cost polarity for every criterion")
            for field, expected in (
                ("normalization", "min-max"),
                ("weighting", "normalized-explicit"),
                ("missing_value", "reject"),
                ("tie_policy", "no-winner"),
            ):
                if isinstance(method, dict) and method.get(field, expected) != expected:
                    ranking_gaps.append(f"MCDA {field} must be {expected}")
        eligible = bool(method) and bool(dimensions) and not ranking_gaps
        mcda = None
        if eligible:
            rows = _ranking_rows(entities, dimensions, score_cells)
            if execution_mode != "legacy":
                matrix = {
                    entity: {
                        dimension: float(score_cells[(entity.casefold(), dimension.casefold())][0]["score"])
                        for dimension, _weight in dimensions
                    }
                    for entity in entities
                }
                criteria = [
                    {
                        "name": item["name"],
                        "weight": item["weight"],
                        "polarity": item["polarity"],
                    }
                    for item in method["criteria"]
                ]
                mcda = evaluate_mcda(
                    matrix,
                    criteria,
                    normalization=method.get("normalization", "min-max"),
                    weighting=method.get("weighting", "normalized-explicit"),
                    missing_value=method.get("missing_value", "reject"),
                    tie_policy=method.get("tie_policy", "no-winner"),
                )
        else:
            status = "blocked-by-evidence"
            rows = []
            supplement_requests.extend(ranking_gaps)
        ranking_data = {
            "evaluation_method": method,
            "rows": rows,
            "limitations": ["排序只覆盖输入证据与明确方法；同分时内部使用稳定的实体名称顺序。"],
            "source_evidence_ids": [item["label"] for item in brief.get("evidence", [])],
        }
        if execution_mode != "legacy":
            ranking_data["mcda"] = mcda
        mode_data = {"ranking": ranking_data}
    elif mode == "page-blueprint":
        factual_text = [item["claim"] for item in brief.get("evidence", [])]
        mode_data = {
            "page_blueprint": {
                "modules": ["Hero 摘要", "定义与边界", "证据表格", "FAQ", "来源与限制"],
                "information_architecture": ["summary", "main", "evidence", "faq", "references"],
                "extractable_summary": factual_text[:2] or ["guidance: 待证据补齐后生成事实摘要"],
                "faq": [f"{brief['topic']}适用于哪些场景？", "哪些结论仍需补证？"],
                "table": {"columns": ["维度", "结论", "证据 ID", "限制"]},
                "semantic_html_example": "<main><article><header></header><section></section><aside></aside></article></main>",
                "schema_candidates": ([{"type": "Article", "claims": factual_text}, {"type": "FAQPage", "claims": factual_text}] if factual_text else []),
                "cms_fields": ["title", "summary", "body", "evidence_ids", "limitations", "reviewed_at"],
                "acceptance_checklist": ["摘要可独立抽取", "FAQ 与正文事实一致", "证据 ID 可解析", "无外部运行资源"],
            }
        }
    else:
        claims = _source_claims(source_text, brief.get("evidence", []))
        profile = "article-friendly" if mode == "article-friendly" else "refine"
        before = 45 + min(20, len(claims))
        after = min(100, before + 25)
        notes = ["增加摘要与分层标题", "统一术语", "保留原始核心 claim", "FAQ 仅使用源内容可回答的问题"]
        if profile == "article-friendly":
            notes.extend(["整理为发布友好 Markdown", "增加证据补充标记与风险说明"])
        mode_data = {
            "refinement": {
                "profile": profile,
                "source_claims": claims,
                "refined_content": source_text.strip() if source_text else "",
                "summary": claims[0]["text"] if claims else "",
                "before_score": before,
                "after_score": after,
                "change_notes": notes,
                "faq": (
                    [
                        {
                            "question": f"源内容关于“{brief['topic']}”的核心表述是什么？",
                            "answer": claims[0]["text"],
                            "status": claims[0]["status"],
                            "evidence_ids": claims[0]["evidence_ids"],
                        }
                    ]
                    if claims
                    else []
                ),
                "risk_notes": ["source claims remain unverified unless linked to evidence IDs"],
            }
        }
        unverified_claims = [claim for claim in claims if not claim["evidence_ids"]]
        if unverified_claims:
            status = "unverified"
            supplement_requests.extend(
                f"为未验证 source claim 补充可解析证据：{claim['text']}"
                for claim in unverified_claims
            )

    content_topic = brief["topic"]
    if mode == "title":
        content_topic = mode_data["title_candidates"][0]["title"]
        _validate_title_candidate(content_topic)
    content = {
        "protocol_version": PROTOCOL_VERSION,
        "run_id": run_id,
        "mode": mode,
        "profile": "article-friendly" if mode == "article-friendly" else mode,
        "topic": content_topic,
        "status": status,
        "sections": _sections_for_mode(mode),
        "factual_claims": _factual_claims(brief),
        "guidance": guidance,
        "supplement_requests": supplement_requests,
        "mode_data": mode_data,
    }
    _validate_content(content, {item["label"] for item in brief.get("evidence", [])})
    return content


def _validate_content(content: dict[str, Any], evidence_ids: set[str]) -> None:
    expected = {"protocol_version", "run_id", "mode", "profile", "topic", "status", "sections", "factual_claims", "guidance", "supplement_requests", "mode_data"}
    if set(content) != expected:
        raise ValueError("content.json fields do not match the output contract")
    if content["mode"] not in MODES or content["status"] not in {"ready", "unverified", "source_gap", "blocked-by-evidence"}:
        raise ValueError("content.json mode or status is invalid")
    for claim in content["factual_claims"]:
        if set(claim) != {"claim_id", "text", "evidence_ids", "status"} or not claim["evidence_ids"]:
            raise ValueError("every factual claim must carry evidence_ids")
        if not set(claim["evidence_ids"]) <= evidence_ids:
            raise ValueError("factual claim evidence_ids must resolve in the evidence ledger")
    refinement = content["mode_data"].get("refinement")
    if refinement:
        for claim in refinement["source_claims"]:
            if set(claim) != {"text", "status", "evidence_ids"}:
                raise ValueError("source claim fields do not match the output contract")
            if not set(claim["evidence_ids"]) <= evidence_ids:
                raise ValueError("source claim evidence_ids must resolve in the evidence ledger")
            expected_status = "provided" if claim["evidence_ids"] else "unverified"
            if claim["status"] != expected_status:
                raise ValueError("source claim status does not match its evidence_ids")


def _content_spec(brief: dict[str, Any], content: dict[str, Any]) -> dict[str, Any]:
    query_ids = brief.get("query_ids") or [_stable_id("qry", brief["topic"], brief["mode"])]
    spec_status = "blocked-by-evidence" if content["status"] == "blocked-by-evidence" else ("ready" if content["status"] == "ready" else "draft")
    spec_title = brief["topic"]
    if brief["mode"] == "title":
        spec_title = content["mode_data"]["title_candidates"][0]["title"]
        _validate_title_candidate(spec_title)
    return {
        "protocol_version": PROTOCOL_VERSION,
        "spec_id": _stable_id("spec", content["run_id"], brief["mode"]),
        "title": spec_title,
        "target_query_ids": query_ids,
        "required_evidence_ids": [item["label"] for item in brief.get("evidence", [])],
        "sections": content["sections"],
        "status": spec_status,
    }


def _surface_title(content: dict[str, Any]) -> str:
    if content["mode"] == "title":
        title = content["mode_data"]["title_candidates"][0]["title"]
        _validate_title_candidate(title)
        return title
    return content["topic"]


def _commonmark_escape(value: str) -> str:
    escaped = html.escape(value.replace("\r\n", "\n").replace("\r", "\n"), quote=False)
    escaped = re.sub(r"([\\`*{}\[\]()#+\-.!_>~|=])", r"\\\1", escaped)
    return "\n".join(
        f"&#8203;{line}" if re.match(r"^(?: {4}|\t)", line) else line
        for line in escaped.split("\n")
    )


def _body_blocks(content: dict[str, Any]) -> list[TypedBlock]:
    mode_data = content["mode_data"]
    blocks: list[TypedBlock] = []
    if "title_candidates" in mode_data:
        for item in mode_data["title_candidates"]:
            blocks.extend(
                [
                    ("heading", item["title"]),
                    ("bullet", f"模式：{item['pattern']}"),
                    ("bullet", f"意图：{item['intent']}；场景：{item['scenario']}"),
                    ("bullet", f"评分：{json.dumps(item['scores'], ensure_ascii=False, sort_keys=True, allow_nan=False)}"),
                ]
            )
    elif "explainer" in mode_data:
        data = mode_data["explainer"]
        for heading, key in zip((item["heading"] for item in content["sections"]), data):
            value = data[key]
            blocks.extend(
                [
                    ("heading", heading),
                    ("paragraph", json.dumps(value, ensure_ascii=False, allow_nan=False) if not isinstance(value, str) else value),
                ]
            )
    elif "comparison" in mode_data:
        data = mode_data["comparison"]
        blocks.extend(
            [
                ("heading", "中立对照"),
                ("paragraph", f"实体：{', '.join(data['entities'])}"),
                ("paragraph", f"维度：{', '.join(data['dimensions']) or '待补证'}"),
                ("paragraph", data["neutrality"]),
            ]
        )
        for row in data["rows"]:
            blocks.append(("bullet", f"{row['entity']}：证据 {', '.join(row['evidence_ids']) or 'source_gap'}"))
    elif "ranking" in mode_data:
        data = mode_data["ranking"]
        blocks.extend(
            [
                ("heading", "评估方法"),
                ("paragraph", json.dumps(data["evaluation_method"], ensure_ascii=False, allow_nan=False)),
                ("heading", "排序结果"),
            ]
        )
        if data["rows"]:
            blocks.extend(
                ("ordered", f"{row['entity']} — {row['score']}（{', '.join(row['evidence_ids'])}）")
                for row in data["rows"]
            )
        else:
            blocks.append(("paragraph", "blocked-by-evidence：当前输入不生成排名。"))
    elif "page_blueprint" in mode_data:
        for key, value in mode_data["page_blueprint"].items():
            blocks.extend(
                [
                    ("heading", key.replace("_", " ").title()),
                    ("paragraph", json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)),
                ]
            )
    else:
        data = mode_data["refinement"]
        blocks.extend(
            [
                ("heading", "优化摘要"),
                ("paragraph", f"Profile: {data['profile']}；评分 {data['before_score']} → {data['after_score']}"),
                ("source", data["summary"]),
                ("heading", "优化后正文"),
                ("source", data["refined_content"]),
                ("heading", "保留的核心 Claim"),
            ]
        )
        blocks.extend(
            ("source-bullet", f"[{item['status']}] {item['text']}")
            for item in data["source_claims"]
        )
        blocks.append(("heading", "改动说明"))
        blocks.extend(("bullet", item) for item in data["change_notes"])
    return blocks


def _markdown(content: dict[str, Any], ledger: dict[str, Any]) -> str:
    title = _surface_title(content)
    safe_body: list[str] = []
    ordered_index = 0
    for block_type, value in _body_blocks(content):
        escaped = _commonmark_escape(value)
        if block_type == "heading":
            safe_body.extend([f"## {escaped}", ""])
        elif block_type in {"bullet", "source-bullet"}:
            safe_body.append(f"- {escaped}")
        elif block_type == "ordered":
            ordered_index += 1
            safe_body.append(f"{ordered_index}. {escaped}")
        else:
            safe_body.extend([escaped, ""])
    lines = [
        f"> 标题：{_commonmark_escape(title)} · 模式：`{content['mode']}` · 状态：`{content['status']}`",
        "",
        "# 内容主体",
        "",
        *safe_body,
        "# 补充说明与参考来源",
        "",
    ]
    lines.extend(
        f"- `{record['evidence_id']}` {_commonmark_escape(' '.join(record['claim'].split()))} — {_commonmark_escape(record['source_uri'])}"
        for record in ledger["records"]
    )
    if not ledger["records"]:
        lines.append("- source_gap：事实证据尚未提供；当前建议均按 guidance 使用。")
    lines.extend(
        f"- {_commonmark_escape(' '.join(item.split()))}"
        for item in content["supplement_requests"]
    )
    return "\n".join(lines).rstrip() + "\n"


def _html_document(content: dict[str, Any], ledger: dict[str, Any]) -> str:
    rendered = []
    ordered_index = 0
    for block_type, value in _body_blocks(content):
        escaped = html.escape(value)
        if block_type == "heading":
            rendered.append(f"<h2>{escaped}</h2>")
        elif block_type in {"bullet", "source-bullet"}:
            rendered.append(f"<p>• {escaped}</p>")
        elif block_type == "ordered":
            ordered_index += 1
            rendered.append(f"<p>{ordered_index}. {escaped}</p>")
        elif block_type == "source":
            rendered.append(f'<p class="source">{escaped}</p>')
        else:
            rendered.append(f"<p>{escaped}</p>")
    refs = [f"<li><code>{html.escape(item['evidence_id'])}</code> {html.escape(item['claim'])} — {html.escape(item['source_uri'])}</li>" for item in ledger["records"]]
    if not refs:
        refs = ["<li>source_gap：事实证据尚未提供；当前建议均按 guidance 使用。</li>"]
    supplements = [
        f"<li>{html.escape(item)}</li>" for item in content["supplement_requests"]
    ]
    title = html.escape(_surface_title(content))
    status = html.escape(content["status"])
    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title><style>
:root{{--ink:#17202a;--muted:#52606d;--line:#d8dee4;--paper:#fff;--accent:#2457d6}}*{{box-sizing:border-box}}html,body{{max-width:100%;overflow-x:hidden}}body{{margin:0;color:var(--ink);background:var(--paper);font:16px/1.7 system-ui,sans-serif;overflow-wrap:anywhere}}nav{{position:sticky;top:0;background:#fffffff2;border-bottom:1px solid var(--line);padding:.8rem 5vw;backdrop-filter:blur(8px)}}nav a{{color:var(--accent);margin-right:1rem}}a:focus-visible,button:focus-visible{{outline:3px solid var(--accent);outline-offset:3px}}main{{max-width:880px;margin:auto;padding:2rem 5vw 5rem}}h1{{margin-top:2.5rem}}h2{{margin-top:1.8rem}}code{{overflow-wrap:anywhere}}.status{{color:var(--muted)}}.source{{white-space:pre-wrap}}.table-scroll{{max-width:100%;overflow-x:auto}}@media print{{nav{{display:none}}main{{max-width:none;padding:0}}a{{color:inherit;text-decoration:none}}}}
</style></head><body><nav aria-label="内容导航"><a href="#main-content">内容主体</a><a href="#references">补充说明与参考来源</a></nav><main><p class="status">标题：{title} · 模式：{html.escape(content['mode'])} · 状态：{status}</p><section id="main-content"><h1>内容主体</h1>{''.join(rendered)}</section><section id="references"><h1>补充说明与参考来源</h1><ul>{''.join(refs)}</ul><h2>补证与风险说明</h2><ul>{''.join(supplements) or '<li>当前无额外补证请求。</li>'}</ul></section></main></body></html>"""


def _render_docx(markdown: str) -> bytes:
    document_module = importlib.import_module("docx")
    document = document_module.Document()
    for line in markdown.splitlines():
        if line.startswith("# "):
            document.add_heading(line[2:], level=1)
        elif line.startswith("## "):
            document.add_heading(line[3:], level=2)
        elif line.startswith("- "):
            document.add_paragraph(line[2:], style="List Bullet")
        elif line:
            document.add_paragraph(line)
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def _is_missing_module(exc: BaseException, module: str) -> bool:
    if not isinstance(exc, ModuleNotFoundError):
        return False
    root = module.split(".", 1)[0]
    missing_name = getattr(exc, "name", None)
    return missing_name in {module, root} or (missing_name is None and (str(exc) == module or module in str(exc)))


def _render_pdf(html_document: str, markdown: str) -> tuple[bytes, list[str], list[str], list[str]]:
    warnings: list[str] = []
    missing_dependencies: list[str] = []
    renderer_errors: list[str] = []
    try:
        weasyprint = importlib.import_module("weasyprint")
        rendered = weasyprint.HTML(string=html_document).write_pdf()
        if not rendered.startswith(b"%PDF"):
            raise ValueError("WeasyPrint returned an invalid PDF")
        return rendered, warnings, missing_dependencies, renderer_errors
    except Exception as primary_exc:
        if _is_missing_module(primary_exc, "weasyprint"):
            missing_dependencies.append("weasyprint")
            warnings.append("degraded: WeasyPrint dependency is missing; ReportLab fallback used")
        else:
            renderer_errors.append(f"weasyprint: {primary_exc}")
            warnings.append(f"degraded: WeasyPrint renderer failed; ReportLab fallback used: {primary_exc}")
    try:
        canvas_module = importlib.import_module("reportlab.pdfgen.canvas")
        buffer = io.BytesIO()
        canvas = canvas_module.Canvas(buffer)
        y = 800
        for line in markdown.splitlines():
            canvas.drawString(40, y, line[:100])
            y -= 14
            if y < 40:
                canvas.showPage()
                y = 800
        canvas.save()
        rendered = buffer.getvalue()
        if not rendered.startswith(b"%PDF"):
            raise ValueError("ReportLab returned an invalid PDF")
        return rendered, warnings, missing_dependencies, renderer_errors
    except Exception as fallback_exc:
        if _is_missing_module(fallback_exc, "reportlab.pdfgen.canvas"):
            missing_dependencies.append("reportlab")
        else:
            renderer_errors.append(f"reportlab: {fallback_exc}")
        raise RendererFailure(
            f"WeasyPrint and ReportLab renderers failed: {fallback_exc}",
            missing_dependencies=sorted(set(missing_dependencies)),
            renderer_errors=sorted(set(renderer_errors)),
            warnings=warnings,
        ) from fallback_exc


def content(
    input_path: Path,
    output_path: Path,
    *,
    clock: Clock | None = None,
    execution_mode: str = "legacy",
) -> dict[str, Any]:
    """Create one offline, evidence-lined geo-content Artifact Bus run."""
    if execution_mode not in {"legacy", "deterministic", "research", "provider"}:
        raise ValueError("execution mode must be legacy, deterministic, research, or provider")
    execution_failures = (
        ["provider mode has no configured drafting adapter; deterministic pipeline completed"]
        if execution_mode == "provider"
        else []
    )
    brief = validate_content_brief(_load_content_brief(input_path))
    normalized, source_text = _normalize_brief(brief, input_path)
    validate_content_brief(normalized)
    identity = (
        normalized
        if execution_mode == "legacy"
        else {"brief": normalized, "execution_mode": execution_mode}
    )
    canonical = json.dumps(
        identity,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    run_id = _stable_id("run", canonical)
    now = (clock or (lambda: datetime.now(timezone.utc)))()
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    created_at = now.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

    ledger = _evidence_ledger(normalized, run_id)
    generated_content = _build_content(
        normalized,
        run_id,
        source_text,
        execution_mode=execution_mode,
    )
    spec = _content_spec(normalized, generated_content)
    claim_map = None
    pipeline = None
    semantic_digest: str | None = None
    if execution_mode != "legacy":
        claim_map = build_claim_map(generated_content, ledger)
        validate_artifact("claim-map", claim_map)
        pipeline = build_content_pipeline(
            normalized,
            source_text,
            generated_content,
            claim_map,
            execution_mode=execution_mode,
            failures=execution_failures,
        )
        validate_artifact("content-pipeline", pipeline)
        semantic_digest = pipeline["semantic_digest"]
    markdown = _markdown(generated_content, ledger)
    html_document = _html_document(generated_content, ledger)
    validate_artifact("evidence-ledger", ledger)
    validate_artifact("content-spec", spec)

    requested = set(normalized["desired_formats"])
    warnings: list[str] = []
    warnings.extend(execution_failures)
    missing_dependencies: set[str] = set()
    renderer_errors: set[str] = set()
    binary_artifacts: dict[str, bytes] = {}
    if "docx" in requested:
        try:
            binary_artifacts["content.docx"] = _render_docx(markdown)
        except Exception as exc:
            if _is_missing_module(exc, "docx"):
                missing_dependencies.add("python-docx")
            else:
                renderer_errors.add(f"python-docx: {exc}")
            warnings.append(f"degraded: DOCX renderer unavailable or failed; core artifacts succeeded: {exc}")
    if "pdf" in requested:
        try:
            binary_artifacts["content.pdf"], pdf_warnings, pdf_missing, pdf_errors = _render_pdf(html_document, markdown)
            warnings.extend(pdf_warnings)
            missing_dependencies.update(pdf_missing)
            renderer_errors.update(pdf_errors)
        except RendererFailure as exc:
            warnings.extend(exc.warnings)
            missing_dependencies.update(exc.missing_dependencies)
            renderer_errors.update(exc.renderer_errors)
            warnings.append(f"degraded: PDF renderer unavailable or failed; core artifacts succeeded: {exc}")
        except Exception as exc:
            renderer_errors.add(f"pdf: {exc}")
            warnings.append(f"degraded: PDF renderer failed; core artifacts succeeded: {exc}")
    if generated_content["status"] != "ready":
        warnings.append(f"content status is {generated_content['status']}; review evidence and supplement requests")
    if claim_map is not None and claim_map["summary"]["support_rate"] < 0.95:
        warnings.append("claim support rate is below 0.95; repair unsupported claims before publication")

    quality = {
        "protocol_version": PROTOCOL_VERSION,
        "run_id": run_id,
        "passed_checks": [
            "content brief contract valid",
            "factual claim evidence lineage resolved",
            "HTML generated locally with escaped user text",
            "Artifact Bus file set prepared atomically",
            f"execution mode recorded: {execution_mode}",
        ],
        "warnings": sorted(set(warnings)),
        "failed_checks": [],
        "status": "passed-with-warnings" if warnings else "passed",
    }
    validate_artifact("quality-report", quality)

    lineage_inputs = [
        "input/content-brief.json",
        *( ["input/source.md"] if source_text is not None else [] ),
        "content-spec.json",
        "content.json",
        "content.md",
        "content.html",
        "evidence-ledger.json",
        "quality-report.json",
        *(["claim-map.json", "content-pipeline.json"] if execution_mode != "legacy" else []),
        *sorted(binary_artifacts),
    ]
    artifacts = [*lineage_inputs, "run-lineage.json"]
    manifest = {
        "protocol_version": PROTOCOL_VERSION,
        "run_id": run_id,
        "created_at": created_at,
        "generator": {"name": "geo-seo-hub-content", "version": GENERATOR_VERSION},
        "input_artifact": "input/content-brief.json",
        "artifacts": artifacts,
        "status": "completed-with-warnings" if warnings else "completed",
        "degraded": bool(missing_dependencies or renderer_errors or execution_failures),
        "missing_dependencies": sorted(missing_dependencies),
        "renderer_errors": sorted(renderer_errors),
    }
    validate_artifact("run-manifest", manifest)
    run_path = output_path / run_id
    with ArtifactBus.transaction(output_path, run_id) as bus:
        bus.write_json("input/content-brief.json", normalized)
        if source_text is not None:
            bus.write_text("input/source.md", source_text)
        bus.write_json("content-spec.json", spec, "content-spec")
        bus.write_json("content.json", generated_content)
        bus.write_text("content.md", markdown)
        bus.write_text("content.html", html_document)
        bus.write_json("evidence-ledger.json", ledger, "evidence-ledger")
        bus.write_json("quality-report.json", quality, "quality-report")
        if claim_map is not None and pipeline is not None:
            bus.write_json("claim-map.json", claim_map, "claim-map")
            bus.write_json("content-pipeline.json", pipeline, "content-pipeline")
        for relative, payload in binary_artifacts.items():
            bus.write_bytes(relative, payload)
        lineage = build_run_lineage(
            bus.root,
            run_id=run_id,
            skill_id="geo-content",
            status=manifest["status"],
            artifact_paths=lineage_inputs,
            metric_names=("warning-count",),
        )
        bus.write_json("run-lineage.json", lineage, "run-lineage")
        bus.write_json("run-manifest.json", manifest, "run-manifest")
        bus.publish(set(artifacts) | {"run-manifest.json"})
    result = {
        "run_id": run_id,
        "status": manifest["status"],
        "content_status": generated_content["status"],
        "output": str(run_path.resolve()),
        "artifacts": artifacts,
        "warning_count": len(quality["warnings"]),
        "execution_mode": execution_mode,
    }
    if semantic_digest is not None:
        result["semantic_digest"] = semantic_digest
    return result
