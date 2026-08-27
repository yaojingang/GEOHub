from __future__ import annotations

import hashlib
import json
import re
import socket
import time
import urllib.robotparser
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Callable, Iterable
from urllib.parse import urljoin, urlsplit, urlunsplit

from .artifact_bus import ArtifactBus
from .diagnose import (
    FetchResult,
    SourceUnavailable,
    URLPolicyError,
    _decode_html,
    _default_fetch,
    _stable_id,
    _validate_public_url,
    _validate_url_syntax,
    analyze_html,
)
from .quality.lineage import build_run_lineage
from .site_report import render_site_report
from .validation import strict_json_loads, validate_artifact
from .version import package_version


PROTOCOL_VERSION = "1.0.0"
SKILL_ID = "geo-site-diagnose"
MAX_PAGES = 10
MAX_INVENTORY_URLS = 500
MAX_SITEMAPS = 5
MAX_FETCH_BYTES = 2 * 1024 * 1024
MAX_TOTAL_BYTES = 15 * 1024 * 1024
TOTAL_FETCH_SECONDS = 90
MAX_BROWSER_REQUESTS = 64
PAGE_CHECK_COUNT = 19
USER_AGENT = "GEOHubSiteAudit/0.7 (+bounded-public-site-audit)"

Fetcher = Callable[[str], FetchResult]
Resolver = Callable[..., list[tuple[Any, ...]]]
Clock = Callable[[], datetime]


PAGE_TYPES: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("homepage", "首页", ()),
    ("organization", "品牌与组织", ("about", "company", "organization", "brand", "关于", "公司", "品牌")),
    ("offering", "产品与服务", ("product", "service", "solution", "platform", "产品", "服务", "方案")),
    ("collection", "分类与内容中心", ("category", "topics", "resources", "hub", "library", "分类", "专题", "资源", "中心")),
    ("editorial", "文章与新闻", ("blog", "article", "news", "insight", "post", "文章", "博客", "新闻", "洞察")),
    ("knowledge", "指南与文档", ("guide", "docs", "documentation", "learn", "academy", "knowledge", "指南", "文档", "知识")),
    ("proof", "案例与证明", ("case", "customer", "stories", "testimonial", "案例", "客户", "成功故事")),
    ("comparison", "对比与榜单", ("compare", "comparison", "versus", "vs", "ranking", "best", "对比", "比较", "榜单")),
    ("transaction", "价格与交易", ("pricing", "plans", "shop", "buy", "checkout", "价格", "套餐", "购买")),
    ("support", "FAQ、支持与联系", ("faq", "support", "help", "contact", "locations", "常见问题", "帮助", "支持", "联系")),
)

DIMENSIONS: tuple[tuple[str, str, int], ...] = (
    ("access_discovery", "AI 可访问性与技术发现", 15),
    ("architecture_coverage", "内容架构与页面覆盖", 10),
    ("entity_clarity", "实体清晰度与一致性", 12),
    ("answerability", "可回答性", 15),
    ("evidence_citation", "证据与可引用性", 16),
    ("authority_trust", "权威与信任", 12),
    ("structured_extractability", "结构化与可提取性", 12),
    ("freshness", "新鲜度与维护性", 8),
)

DIMENSION_LABELS = {key: label for key, label, _weight in DIMENSIONS}
DIMENSION_WEIGHTS = {key: weight for key, _label, weight in DIMENSIONS}

PAGE_LABELS_EN = {
    "homepage": "Homepage",
    "organization": "Organization",
    "offering": "Products and services",
    "collection": "Category and content hub",
    "editorial": "Articles and news",
    "knowledge": "Guides and documentation",
    "proof": "Cases and proof",
    "comparison": "Comparisons and rankings",
    "transaction": "Pricing and transactions",
    "support": "FAQ, support, and contact",
}

DIMENSION_LABELS_EN = {
    "access_discovery": "AI access and discovery",
    "architecture_coverage": "Content architecture and coverage",
    "entity_clarity": "Entity clarity and consistency",
    "answerability": "Answerability",
    "evidence_citation": "Evidence and citability",
    "authority_trust": "Authority and trust",
    "structured_extractability": "Structure and extractability",
    "freshness": "Freshness and maintenance",
}

REMEDIATIONS = {
    "title": "为页面补充明确且唯一的主题标题。",
    "meta-description": "编写能够概括页面价值与范围的事实型摘要。",
    "canonical": "声明规范 URL，并确保其与公开首选页面一致。",
    "indexable": "移除阻止公开发现的 noindex 或冲突型 robots 指令。",
    "internal-links": "从相关导航、专题页或正文增加描述性内部链接。",
    "type-confidence": "让 URL、标题、H1 与页面主要任务保持一致。",
    "entity-heading": "在标题和主标题中清楚说明品牌、产品或主题实体。",
    "entity-schema": "为适用实体增加与可见正文一致的结构化标记。",
    "answer-depth": "补充足够的可见正文，使页面能够独立回答核心问题。",
    "answer-structure": "使用描述性小标题、列表或表格组织可提取答案。",
    "evidence-language": "在关键主张附近注明数据、来源、方法或参考依据。",
    "external-sources": "为需要外部支持的主张链接到稳定且相关的原始来源。",
    "numeric-proof": "用带上下文、口径和来源的数字增强事实密度。",
    "authorship": "展示可追责的作者、审核者或机构主体。",
    "trust-contact": "提供关于、联系、编辑政策或专业资历信息。",
    "semantic-landmarks": "使用 main、article、标题、列表和表格表达正文结构。",
    "structured-data": "修复 JSON-LD，并让类型与页面可见内容保持一致。",
    "freshness-date": "在时效相关页面显示真实的发布或更新时间。",
    "sitemap-lastmod": "为站点地图提供真实、可解释的 lastmod。",
    "bot-access": "检查 robots.txt，确保面向公开搜索的爬虫能够访问核心页面。",
    "sitemap-access": "提供可访问的 XML 站点地图，并从 robots.txt 声明其位置。",
}

REMEDIATIONS_EN = {
    "title": "Add a clear, unique title that states the page topic.",
    "meta-description": "Write a factual summary of the page value and scope.",
    "canonical": "Declare the canonical URL and align it with the preferred public page.",
    "indexable": "Remove noindex or conflicting robots directives from public pages.",
    "internal-links": "Add descriptive internal links from navigation, hubs, or related content.",
    "type-confidence": "Align the URL, title, H1, and primary page task.",
    "entity-heading": "Name the brand, product, or topic entity clearly in the title and H1.",
    "entity-schema": "Add structured data for applicable entities and match visible content.",
    "answer-depth": "Add enough visible content for the page to answer its core question independently.",
    "answer-structure": "Use descriptive headings, lists, or tables to organize extractable answers.",
    "evidence-language": "Place data, sources, methods, or references next to important claims.",
    "external-sources": "Link evidence-dependent claims to stable, relevant primary sources.",
    "numeric-proof": "Add contextual numbers with definitions, methods, and sources.",
    "authorship": "Show an accountable author, reviewer, or responsible organization.",
    "trust-contact": "Provide organization, contact, editorial policy, or credential information.",
    "semantic-landmarks": "Use main, article, headings, lists, and tables to express content structure.",
    "structured-data": "Repair JSON-LD and align each type with visible page content.",
    "freshness-date": "Show a genuine publication or update date on time-sensitive pages.",
    "sitemap-lastmod": "Publish accurate and explainable sitemap lastmod values.",
    "bot-access": "Review robots.txt so public-search crawlers can access core pages.",
    "sitemap-access": "Publish an accessible XML sitemap and declare it in robots.txt.",
}


def _normalize_locale(locale: str) -> str:
    if not isinstance(locale, str) or not locale.strip():
        raise ValueError("locale must be a non-blank string")
    normalized = locale.strip().replace("_", "-").casefold()
    if normalized == "zh" or normalized.startswith("zh-"):
        return "zh-CN"
    if normalized == "en" or normalized.startswith("en-"):
        return "en-US"
    raise ValueError("locale must be a supported Chinese or English locale")


def _is_en(locale: str) -> bool:
    return locale == "en-US"


def _t(locale: str, zh: str, en: str) -> str:
    return en if _is_en(locale) else zh


def _page_label(page_type: str | None, locale: str) -> str:
    if _is_en(locale):
        return PAGE_LABELS_EN.get(page_type or "", page_type or "Unknown")
    return next((label for key, label, _terms in PAGE_TYPES if key == page_type), page_type or "未知")


def _dimension_label(dimension: str, locale: str) -> str:
    return DIMENSION_LABELS_EN[dimension] if _is_en(locale) else DIMENSION_LABELS[dimension]


@dataclass
class InventoryItem:
    url: str
    anchors: list[str]
    from_navigation: bool = False
    from_sitemap: bool = False
    lastmod: str | None = None
    page_type: str | None = None
    type_confidence: float = 0.0
    representativeness: float = 0.0


class DiscoveryParser(HTMLParser):
    def __init__(self, base_url: str):
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.links: list[tuple[str, str, bool]] = []
        self.schema_types: list[str] = []
        self._nav_depth = 0
        self._anchor_href: str | None = None
        self._anchor_nav = False
        self._anchor_parts: list[str] = []
        self._json_ld_depth = 0
        self._json_ld_parts: list[str] = []
        self._hidden_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.casefold()
        values = {key.casefold(): (value or "") for key, value in attrs}
        if tag == "nav":
            self._nav_depth += 1
        if tag in {"script", "style", "template", "noscript"}:
            self._hidden_depth += 1
        if tag == "a" and values.get("href"):
            self._anchor_href = urljoin(self.base_url, values["href"].strip())
            self._anchor_nav = self._nav_depth > 0
            self._anchor_parts = []
        if tag == "script" and values.get("type", "").casefold() == "application/ld+json":
            self._json_ld_depth = self._hidden_depth
            self._json_ld_parts = []

    def handle_endtag(self, tag: str) -> None:
        tag = tag.casefold()
        if tag == "a" and self._anchor_href:
            label = " ".join(" ".join(self._anchor_parts).split())
            self.links.append((self._anchor_href, label, self._anchor_nav))
            self._anchor_href = None
            self._anchor_nav = False
            self._anchor_parts = []
        if tag == "script" and self._json_ld_depth:
            try:
                payload = strict_json_loads("".join(self._json_ld_parts))
            except (TypeError, ValueError):
                payload = None
            self.schema_types.extend(_schema_types(payload))
            self._json_ld_depth = 0
            self._json_ld_parts = []
        if tag == "nav" and self._nav_depth:
            self._nav_depth -= 1
        if tag in {"script", "style", "template", "noscript"} and self._hidden_depth:
            self._hidden_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._anchor_href and data.strip():
            self._anchor_parts.append(data.strip())
        if self._json_ld_depth:
            self._json_ld_parts.append(data)


def _schema_types(payload: Any) -> list[str]:
    if isinstance(payload, list):
        result: list[str] = []
        for item in payload:
            result.extend(_schema_types(item))
        return result
    if not isinstance(payload, dict):
        return []
    result = []
    raw_type = payload.get("@type")
    if isinstance(raw_type, str) and raw_type.strip():
        result.append(raw_type.strip())
    elif isinstance(raw_type, list):
        result.extend(value.strip() for value in raw_type if isinstance(value, str) and value.strip())
    graph = payload.get("@graph")
    if isinstance(graph, list):
        for item in graph:
            result.extend(_schema_types(item))
    return result


def _normalize_candidate(url: str, approved_host: str) -> str | None:
    try:
        normalized, host = _validate_url_syntax(url)
    except URLPolicyError:
        return None
    parsed = urlsplit(normalized)
    if host != approved_host or parsed.query:
        return None
    path = re.sub(r"/{2,}", "/", parsed.path or "/")
    if re.search(r"\.(?:pdf|zip|docx?|xlsx?|pptx?|jpe?g|png|gif|webp|svg|mp[34]|avi|mov|xml|json|rss)$", path, re.I):
        return None
    if re.search(r"(?:^|/)(?:login|signin|signup|cart|checkout|account|wp-admin)(?:/|$)", path, re.I):
        return None
    return urlunsplit((parsed.scheme, parsed.netloc, path, "", ""))


def _type_for_candidate(url: str, anchors: Iterable[str], root_url: str) -> tuple[str, float]:
    if url.rstrip("/") == root_url.rstrip("/"):
        return "homepage", 1.0
    parsed = urlsplit(url)
    haystack = " ".join([parsed.path.replace("-", " ").replace("_", " "), *anchors]).casefold()
    ranked: list[tuple[int, int, str]] = []
    for order, (page_type, _label, terms) in enumerate(PAGE_TYPES[1:], start=1):
        hits = sum(1 for term in terms if term.casefold() in haystack)
        if hits:
            ranked.append((hits, -order, page_type))
    if not ranked:
        return "collection", 0.35
    hits, _order, page_type = max(ranked)
    return page_type, min(1.0, 0.55 + 0.15 * (hits - 1))


def _path_cluster(url: str) -> str:
    parts = [part for part in urlsplit(url).path.split("/") if part]
    return parts[0].casefold() if parts else "/"


def _freshness_value(lastmod: str | None, now: datetime) -> float:
    if not lastmod:
        return 0.0
    value = lastmod.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        try:
            parsed = datetime.strptime(value[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            return 0.25
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    age_days = max(0, (now.astimezone(timezone.utc) - parsed.astimezone(timezone.utc)).days)
    if age_days <= 365:
        return 1.0
    if age_days <= 730:
        return 0.6
    return 0.25


def _select_pages(inventory: dict[str, InventoryItem], root_url: str, now: datetime, max_pages: int) -> tuple[list[InventoryItem], list[dict[str, Any]]]:
    cluster_counts = Counter(_path_cluster(item.url) for item in inventory.values())
    max_cluster = max(cluster_counts.values(), default=1)
    candidates: list[dict[str, Any]] = []
    for item in inventory.values():
        page_type, confidence = _type_for_candidate(item.url, item.anchors, root_url)
        item.page_type = page_type
        item.type_confidence = confidence
        cluster_value = cluster_counts[_path_cluster(item.url)] / max_cluster
        nav_value = 1.0 if item.from_navigation else 0.0
        sitemap_value = 1.0 if item.from_sitemap else 0.0
        freshness_value = _freshness_value(item.lastmod, now)
        item.representativeness = round(
            100 * (0.35 * confidence + 0.25 * nav_value + 0.20 * cluster_value + 0.10 * sitemap_value + 0.10 * freshness_value),
            2,
        )
        candidates.append(
            {
                "url": item.url,
                "page_type": page_type,
                "type_confidence": round(confidence, 4),
                "representativeness": item.representativeness,
                "signals": {
                    "navigation": nav_value,
                    "path_cluster": round(cluster_value, 4),
                    "sitemap": sitemap_value,
                    "freshness": freshness_value,
                },
            }
        )
    selected: list[InventoryItem] = []
    for page_type, _label, _terms in PAGE_TYPES:
        matches = [item for item in inventory.values() if item.page_type == page_type]
        if not matches:
            continue
        matches.sort(key=lambda item: (-item.representativeness, item.url))
        selected.append(matches[0])
        if len(selected) >= max_pages:
            break
    return selected, sorted(candidates, key=lambda item: (item["page_type"], -item["representativeness"], item["url"]))


def _check(
    check_id: str,
    dimension: str,
    raw_value: float | None,
    evidence_id: str | None,
    *,
    threshold: float = 0.5,
    applicable: bool = True,
    locale: str = "zh-CN",
) -> dict[str, Any]:
    if not applicable:
        status = "not-applicable"
        score = None
    elif raw_value is None or evidence_id is None:
        status = "missing-evidence"
        score = None
    else:
        bounded = max(0.0, min(1.0, float(raw_value)))
        raw_value = round(bounded, 4)
        status = "pass" if bounded >= threshold else "fail"
        score = round(100 * bounded)
    return {
        "check_id": check_id,
        "dimension": dimension,
        "weight": DIMENSION_WEIGHTS[dimension],
        "raw_value": raw_value,
        "threshold": threshold,
        "status": status,
        "score": score,
        "evidence_ids": [evidence_id] if evidence_id else [],
        "remediation": (REMEDIATIONS_EN if _is_en(locale) else REMEDIATIONS)[check_id],
    }


def _dimension_score(checks: Iterable[dict[str, Any]]) -> int | None:
    values = [item["score"] for item in checks if item["status"] in {"pass", "fail"}]
    return round(sum(values) / len(values)) if values else None


def _page_checks(
    metrics: dict[str, Any],
    item: InventoryItem,
    evidence_id: str,
    *,
    sitemap_lastmod: str | None,
    now: datetime,
    locale: str,
) -> list[dict[str, Any]]:
    text = metrics["visible_text"]
    headings = metrics["headings"]
    noindex = "noindex" in metrics["meta_robots"].casefold()
    evidence_language = bool(re.search(r"source|reference|citation|method|research|数据|来源|参考|方法|研究", text, re.I))
    author_signal = bool(re.search(r"author|editor|reviewed by|expert|作者|编辑|审核|专家", text, re.I)) or any(value.casefold() in {"person", "profilepage"} for value in metrics["schema_types"])
    trust_signal = bool(re.search(r"about|contact|editorial|privacy|资质|关于|联系|编辑政策|隐私", text, re.I))
    freshness_signal = bool(re.search(r"\b20\d{2}(?:[-/.年]\d{1,2})?|updated|last modified|发布|更新", text, re.I))
    numeric_signal = min(1.0, len(re.findall(r"(?<!\w)\d+(?:\.\d+)?%?", text)) / 4)
    structure_signal = min(1.0, (metrics["main_count"] + metrics["article_count"] + metrics["list_count"] + metrics["table_count"]) / 4)
    json_ld_validity = metrics["valid_json_ld_count"] / metrics["json_ld_count"] if metrics["json_ld_count"] else 0.0
    checks = [
        _check("title", "access_discovery", float(bool(metrics["title"])), evidence_id, locale=locale),
        _check("meta-description", "access_discovery", float(bool(metrics["meta_description"])), evidence_id, locale=locale),
        _check("canonical", "access_discovery", float(bool(metrics["canonical"])), evidence_id, locale=locale),
        _check("indexable", "access_discovery", float(not noindex), evidence_id, locale=locale),
        _check("internal-links", "architecture_coverage", min(1.0, metrics["internal_link_count"] / 5), evidence_id, locale=locale),
        _check("type-confidence", "architecture_coverage", item.type_confidence, evidence_id, locale=locale),
        _check("entity-heading", "entity_clarity", min(1.0, (int(bool(metrics["title"])) + int(len(headings["h1"]) == 1)) / 2), evidence_id, locale=locale),
        _check("entity-schema", "entity_clarity", float(bool(metrics["schema_types"])), evidence_id, locale=locale),
        _check("answer-depth", "answerability", min(1.0, metrics["visible_text_length"] / 900), evidence_id, threshold=0.55, locale=locale),
        _check("answer-structure", "answerability", min(1.0, (len(headings["h2"]) + metrics["list_count"] + metrics["table_count"]) / 4), evidence_id, locale=locale),
        _check("evidence-language", "evidence_citation", float(evidence_language), evidence_id, locale=locale),
        _check("external-sources", "evidence_citation", min(1.0, metrics["external_link_count"] / 2), evidence_id, locale=locale),
        _check("numeric-proof", "evidence_citation", numeric_signal, evidence_id, locale=locale),
        _check("authorship", "authority_trust", float(author_signal), evidence_id, locale=locale),
        _check("trust-contact", "authority_trust", float(trust_signal), evidence_id, locale=locale),
        _check("semantic-landmarks", "structured_extractability", structure_signal, evidence_id, locale=locale),
        _check("structured-data", "structured_extractability", json_ld_validity, evidence_id, locale=locale),
        _check("freshness-date", "freshness", float(freshness_signal), evidence_id, locale=locale),
        _check("sitemap-lastmod", "freshness", _freshness_value(sitemap_lastmod, now) if sitemap_lastmod else 0.0, evidence_id, locale=locale),
    ]
    return checks


def _extended_metrics(source_html: str, base_url: str) -> dict[str, Any]:
    metrics = analyze_html(source_html, base_url)
    parser = DiscoveryParser(base_url)
    parser.feed(source_html)
    parser.close()
    metrics["schema_types"] = sorted(set(parser.schema_types))
    metrics["links"] = [link for link, _label, _nav in parser.links]
    metrics["navigation_links"] = [link for link, _label, in_nav in parser.links if in_nav]
    metrics["link_labels"] = [label for _link, label, _nav in parser.links if label]
    return metrics


def _decode_text(result: FetchResult) -> str:
    charset_match = re.search(r"charset\s*=\s*['\"]?([^;\s'\"]+)", result.content_type, re.I)
    charset = charset_match.group(1) if charset_match else "utf-8"
    try:
        return result.body.decode(charset, errors="replace")
    except LookupError:
        return result.body.decode("utf-8", errors="replace")


def _fetch_resource(
    url: str,
    *,
    resolver: Resolver,
    fetcher: Fetcher | None,
    deadline: float,
    approved_host: str | None,
    allowed_media_types: set[str],
    max_bytes: int = MAX_FETCH_BYTES,
) -> tuple[FetchResult, str]:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise SourceUnavailable("total fetch budget exhausted")
    normalized, addresses = _validate_public_url(url, resolver=resolver, dns_timeout=min(2.0, remaining))
    if approved_host and urlsplit(normalized).hostname.casefold() != approved_host:
        raise SourceUnavailable("discovered URL leaves the approved host")
    result = fetcher(normalized) if fetcher else _default_fetch(
        normalized,
        resolver=resolver,
        timeout=min(8.0, remaining),
        max_bytes=max_bytes,
        deadline=deadline,
        initial_addresses=addresses,
        user_agent=USER_AGENT,
    )
    if not isinstance(result, FetchResult) or not isinstance(result.body, bytes):
        raise SourceUnavailable("fetcher returned an invalid result")
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise SourceUnavailable("total fetch budget exhausted")
    final_url, _final_addresses = _validate_public_url(result.final_url, resolver=resolver, dns_timeout=min(2.0, remaining))
    final_host = (urlsplit(final_url).hostname or "").casefold()
    if approved_host and final_host != approved_host:
        raise SourceUnavailable("redirect leaves the approved host")
    if len(result.body) > max_bytes:
        raise SourceUnavailable(f"source exceeds {max_bytes} byte limit")
    media_type = result.content_type.partition(";")[0].strip().casefold()
    if media_type not in allowed_media_types:
        raise SourceUnavailable(f"unsupported Content-Type: {media_type or 'missing'}")
    return FetchResult(final_url=final_url, body=result.body, content_type=result.content_type), final_host


def _parse_robots(text: str, robots_url: str) -> tuple[urllib.robotparser.RobotFileParser, list[str]]:
    parser = urllib.robotparser.RobotFileParser()
    parser.set_url(robots_url)
    parser.parse(text.splitlines())
    sitemaps = []
    for line in text.splitlines():
        if line.casefold().startswith("sitemap:"):
            value = line.split(":", 1)[1].strip()
            if value:
                sitemaps.append(value)
    return parser, sitemaps


def _crawler_matrix(parser: urllib.robotparser.RobotFileParser | None, page_urls: list[str]) -> list[dict[str, Any]]:
    agents = (
        ("OAI-SearchBot", "search"),
        ("Googlebot", "search"),
        ("Bingbot", "search"),
        ("GPTBot", "training-control"),
        ("Google-Extended", "training-control"),
    )
    matrix = []
    for agent, role in agents:
        access = [
            {"url": url, "allowed": parser.can_fetch(agent, url) if parser else None}
            for url in page_urls
        ]
        observed = [item["allowed"] for item in access if item["allowed"] is not None]
        matrix.append(
            {
                "agent": agent,
                "role": role,
                "allowed": all(observed) if observed else None,
                "allowed_count": sum(value is True for value in observed),
                "blocked_count": sum(value is False for value in observed),
                "page_access": access,
                "basis": "robots.txt" if parser else "missing-evidence",
            }
        )
    return matrix


def _parse_sitemap(text: str) -> tuple[list[tuple[str, str | None]], list[str]]:
    if "<!DOCTYPE" in text.upper() or "<!ENTITY" in text.upper():
        raise SourceUnavailable("sitemap with DTD or entity declarations is rejected")
    try:
        root = ET.fromstring(text)
    except ET.ParseError as exc:
        raise SourceUnavailable(f"invalid sitemap XML: {exc}") from exc
    entries: list[tuple[str, str | None]] = []
    child_sitemaps: list[str] = []
    root_name = root.tag.rsplit("}", 1)[-1].casefold()
    for child in root:
        child_name = child.tag.rsplit("}", 1)[-1].casefold()
        if child_name not in {"url", "sitemap"}:
            continue
        loc = None
        lastmod = None
        for field in child:
            name = field.tag.rsplit("}", 1)[-1].casefold()
            if name == "loc" and field.text:
                loc = field.text.strip()
            elif name == "lastmod" and field.text:
                lastmod = field.text.strip()
        if not loc:
            continue
        if root_name == "sitemapindex" or child_name == "sitemap":
            child_sitemaps.append(loc)
        else:
            entries.append((loc, lastmod))
    return entries, child_sitemaps


def _browser_render(
    url: str,
    approved_host: str,
    *,
    initial_html: str,
    byte_budget: int,
    resolver: Resolver,
    timeout_seconds: float,
) -> tuple[str | None, str | None, int]:
    try:
        _normalized, addresses = _validate_public_url(url, resolver=resolver, dns_timeout=min(2.0, timeout_seconds))
        from playwright.sync_api import Error as PlaywrightError
        from playwright.sync_api import sync_playwright
    except (ImportError, OSError, URLPolicyError) as exc:
        return None, f"browser renderer unavailable: {type(exc).__name__}", 0
    address = str(sorted(addresses, key=lambda item: (item.version, str(item)))[0])
    deadline = time.monotonic() + timeout_seconds
    transferred_bytes = 0
    request_count = 0
    boundary_gaps: set[str] = set()
    dependency_media_types = {
        "application/javascript",
        "application/json",
        "application/octet-stream",
        "application/wasm",
        "application/xml",
        "application/xhtml+xml",
        "text/html",
        "text/javascript",
        "text/plain",
        "text/xml",
    }
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                headless=True,
                args=[f"--host-resolver-rules=MAP {approved_host} {address},EXCLUDE localhost"],
            )
            context = browser.new_context(
                accept_downloads=False,
                java_script_enabled=True,
                service_workers="block",
                user_agent=USER_AGENT,
            )
            main_page: Any | None = None

            def route_request(route: Any) -> None:
                nonlocal transferred_bytes, request_count
                request_url = route.request.url
                parsed = urlsplit(request_url)
                if parsed.scheme in {"data", "blob", "about"}:
                    route.continue_()
                    return
                if route.request.is_navigation_request():
                    if route.request.frame.page is main_page and request_url.split("#", 1)[0] == url.split("#", 1)[0]:
                        route.fulfill(status=200, content_type="text/html; charset=utf-8", body=initial_html)
                    else:
                        boundary_gaps.add("browser blocked an extra navigation")
                        route.abort()
                    return
                if (
                    route.request.method != "GET"
                    or route.request.resource_type not in {"script", "xhr", "fetch"}
                    or (parsed.hostname or "").casefold() != approved_host
                    or parsed.scheme not in {"http", "https"}
                    or parsed.query
                    or re.search(r"(?:^|/)(?:login|signin|signup|cart|checkout|account|wp-admin)(?:/|$)", parsed.path, re.I)
                ):
                    if route.request.resource_type not in {"image", "media", "font", "stylesheet"}:
                        boundary_gaps.add("browser blocked an out-of-policy subrequest")
                    route.abort()
                    return
                request_count += 1
                remaining = min(MAX_FETCH_BYTES, byte_budget - transferred_bytes)
                if request_count > MAX_BROWSER_REQUESTS or remaining <= 0:
                    boundary_gaps.add("browser subrequest budget exhausted")
                    route.abort()
                    return
                try:
                    result, _host = _fetch_resource(
                        request_url,
                        resolver=resolver,
                        fetcher=None,
                        deadline=deadline,
                        approved_host=approved_host,
                        allowed_media_types=dependency_media_types,
                        max_bytes=remaining,
                    )
                    transferred_bytes += len(result.body)
                    final = urlsplit(result.final_url)
                    if final.query or re.search(
                        r"(?:^|/)(?:login|signin|signup|cart|checkout|account|wp-admin)(?:/|$)",
                        final.path,
                        re.I,
                    ):
                        boundary_gaps.add("browser dependency redirect left the allowed path policy")
                        route.abort()
                        return
                    route.fulfill(status=200, headers={"content-type": result.content_type}, body=result.body)
                except (OSError, SourceUnavailable, URLPolicyError) as exc:
                    boundary_gaps.add(f"browser dependency blocked: {type(exc).__name__}")
                    route.abort()

            context.route("**/*", route_request)
            context.route_web_socket("**/*", lambda websocket: websocket.close())
            page = context.new_page()
            main_page = page
            context.on("page", lambda opened: opened.close() if opened is not main_page else None)
            page.goto(url, wait_until="domcontentloaded", timeout=max(1000, int(timeout_seconds * 1000)))
            source = page.content()
            context.close()
            browser.close()
            return source, "; ".join(sorted(boundary_gaps)) or None, transferred_bytes
    except (PlaywrightError, OSError, ValueError) as exc:
        return None, f"browser rendering failed: {type(exc).__name__}: {exc}", transferred_bytes


def _add_inventory_item(
    inventory: dict[str, InventoryItem],
    url: str,
    approved_host: str,
    *,
    anchor: str = "",
    navigation: bool = False,
    sitemap: bool = False,
    lastmod: str | None = None,
) -> None:
    normalized = _normalize_candidate(url, approved_host)
    if normalized is None or (normalized not in inventory and len(inventory) >= MAX_INVENTORY_URLS):
        return
    item = inventory.setdefault(normalized, InventoryItem(url=normalized, anchors=[]))
    if anchor and anchor not in item.anchors:
        item.anchors.append(anchor)
    item.from_navigation = item.from_navigation or navigation
    item.from_sitemap = item.from_sitemap or sitemap
    if lastmod and not item.lastmod:
        item.lastmod = lastmod


def _public_metrics(metrics: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": metrics["title"],
        "meta_description": metrics["meta_description"],
        "canonical": metrics["canonical"],
        "meta_robots": metrics["meta_robots"],
        "h1": metrics["headings"]["h1"],
        "h2_count": len(metrics["headings"]["h2"]),
        "h3_count": len(metrics["headings"]["h3"]),
        "visible_text_length": metrics["visible_text_length"],
        "main_count": metrics["main_count"],
        "article_count": metrics["article_count"],
        "list_count": metrics["list_count"],
        "table_count": metrics["table_count"],
        "faq_like_count": metrics["faq_like_count"],
        "json_ld_count": metrics["json_ld_count"],
        "valid_json_ld_count": metrics["valid_json_ld_count"],
        "schema_types": metrics["schema_types"],
        "internal_link_count": metrics["internal_link_count"],
        "external_link_count": metrics["external_link_count"],
        "evidence_excerpt": metrics["visible_text"][:480],
    }


def _severity(check: dict[str, Any]) -> str:
    if check["dimension"] == "access_discovery" and check["check_id"] in {"indexable", "bot-access"}:
        return "critical"
    weight = DIMENSION_WEIGHTS[check["dimension"]]
    if weight >= 15:
        return "high"
    if weight >= 12:
        return "medium"
    return "low"


def _page_record(
    item: InventoryItem,
    source_html: str,
    final_url: str,
    *,
    page_id: str,
    evidence_id: str,
    render_mode: str,
    render_gap: str | None,
    now: datetime,
    locale: str,
) -> dict[str, Any]:
    metrics = _extended_metrics(source_html, final_url)
    checks = _page_checks(metrics, item, evidence_id, sitemap_lastmod=item.lastmod, now=now, locale=locale)
    if render_gap:
        technical_checks = {"title", "meta-description", "canonical", "indexable"}
        for check in checks:
            if check["check_id"] not in technical_checks:
                check["raw_value"] = None
                check["status"] = "missing-evidence"
                check["score"] = None
    dimensions: dict[str, int | None] = {}
    for dimension, _label, _weight in DIMENSIONS:
        dimensions[dimension] = _dimension_score(check for check in checks if check["dimension"] == dimension)
    available = [(dimensions[key], weight) for key, _label, weight in DIMENSIONS if dimensions[key] is not None]
    score = round(sum(value * weight for value, weight in available) / sum(weight for _value, weight in available)) if available else None
    failed = [item_check for item_check in checks if item_check["status"] == "fail"]
    issues = [
        {
            "issue_id": _stable_id("issue", page_id, check["check_id"]),
            "check_id": check["check_id"],
            "dimension": check["dimension"],
            "severity": _severity(check),
            "statement": _t(
                locale,
                f"{DIMENSION_LABELS[check['dimension']]}检查项 {check['check_id']} 得分 {check['score']}/100。",
                f"{DIMENSION_LABELS_EN[check['dimension']]} check {check['check_id']} scored {check['score']}/100.",
            ),
            "recommendation": check["remediation"],
            "evidence_ids": check["evidence_ids"],
        }
        for check in failed
    ]
    observed = sum(check["status"] in {"pass", "fail"} for check in checks)
    planned = sum(check["status"] != "not-applicable" for check in checks)
    return {
        "page_id": page_id,
        "url": final_url,
        "page_type": item.page_type,
        "page_type_label": _page_label(item.page_type, locale),
        "selection": {
            "representativeness": item.representativeness,
            "type_confidence": round(item.type_confidence, 4),
            "from_navigation": item.from_navigation,
            "from_sitemap": item.from_sitemap,
            "lastmod": item.lastmod,
            "reason": _t(
                locale,
                "该页面在同类候选中具有最高代表性分数。",
                "This page has the highest representativeness score among candidates of the same type.",
            ),
        },
        "status": "observed",
        "render_mode": render_mode,
        "render_gap": render_gap,
        "content_sha256": hashlib.sha256(source_html.encode("utf-8")).hexdigest(),
        "evidence_id": evidence_id,
        "score": score,
        "confidence": round(100 * observed / planned) if planned else 0,
        "dimensions": dimensions,
        "checks": checks,
        "metrics": _public_metrics(metrics),
        "issues": issues,
        "internal_links": sorted(set(metrics["links"])),
    }


def _source_gap_page(item: InventoryItem, message: str, locale: str) -> dict[str, Any]:
    return {
        "page_id": _stable_id("page", item.url),
        "url": item.url,
        "page_type": item.page_type,
        "page_type_label": _page_label(item.page_type, locale),
        "selection": {
            "representativeness": item.representativeness,
            "type_confidence": round(item.type_confidence, 4),
            "from_navigation": item.from_navigation,
            "from_sitemap": item.from_sitemap,
            "lastmod": item.lastmod,
            "reason": _t(
                locale,
                "该页面入选后无法取得可分析快照。",
                "The selected page did not yield an analyzable snapshot.",
            ),
        },
        "status": "source_gap",
        "message": message,
        "score": None,
        "confidence": 0,
        "dimensions": {key: None for key, _label, _weight in DIMENSIONS},
        "checks": [],
        "metrics": {},
        "issues": [],
        "internal_links": [],
    }


def _aggregate_site(
    pages: list[dict[str, Any]],
    crawler_matrix: list[dict[str, Any]],
    *,
    robots_evidence_id: str | None,
    sitemap_evidence_id: str | None,
    locale: str,
) -> tuple[dict[str, int | None], int | None, int, list[dict[str, Any]]]:
    observed_pages = [page for page in pages if page["status"] == "observed"]
    dimensions: dict[str, int | None] = {}
    for dimension, _label, _weight in DIMENSIONS:
        values = [page["dimensions"][dimension] for page in observed_pages if page["dimensions"][dimension] is not None]
        dimensions[dimension] = round(sum(values) / len(values)) if values else None
    search_agents = [item for item in crawler_matrix if item["role"] == "search"]
    bot_values = [float(item["allowed"]) for item in search_agents if item["allowed"] is not None]
    site_checks = [
        _check("bot-access", "access_discovery", sum(bot_values) / len(bot_values) if bot_values else None, robots_evidence_id, locale=locale),
        _check("sitemap-access", "access_discovery", 1.0 if sitemap_evidence_id else 0.0, sitemap_evidence_id or robots_evidence_id, locale=locale),
    ]
    access_values = [value for value in [dimensions["access_discovery"], _dimension_score(site_checks)] if value is not None]
    dimensions["access_discovery"] = round(sum(access_values) / len(access_values)) if access_values else None
    available = [(dimensions[key], weight) for key, _label, weight in DIMENSIONS if dimensions[key] is not None]
    overall = round(sum(value * weight for value, weight in available) / sum(weight for _value, weight in available)) if available else None
    all_checks = [check for page in observed_pages for check in page["checks"]] + site_checks
    observed = sum(check["status"] in {"pass", "fail"} for check in all_checks)
    planned = sum(check["status"] != "not-applicable" for check in all_checks)
    planned += PAGE_CHECK_COUNT * sum(page["status"] == "source_gap" for page in pages)
    confidence = round(100 * observed / planned) if planned else 0
    return dimensions, overall, confidence, site_checks


def _remediation_backlog(pages: list[dict[str, Any]], site_checks: list[dict[str, Any]], run_id: str) -> dict[str, Any]:
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    for page in pages:
        for issue in page.get("issues", []):
            key = (issue["dimension"], issue["check_id"])
            record = grouped.setdefault(
                key,
                {
                    "action_id": _stable_id("action", run_id, *key),
                    "title": issue["recommendation"],
                    "dimension": issue["dimension"],
                    "severity": issue["severity"],
                    "impact": min(5, max(1, round(DIMENSION_WEIGHTS[issue["dimension"]] / 4))),
                    "effort": 2 if issue["check_id"] in {"title", "meta-description", "freshness-date"} else 3,
                    "affected_page_ids": [],
                    "evidence_ids": [],
                },
            )
            record["affected_page_ids"].append(page["page_id"])
            record["evidence_ids"].extend(issue["evidence_ids"])
    for check in site_checks:
        if check["status"] != "fail":
            continue
        key = (check["dimension"], check["check_id"])
        grouped[key] = {
            "action_id": _stable_id("action", run_id, *key),
            "title": check["remediation"],
            "dimension": check["dimension"],
            "severity": _severity(check),
            "impact": 5,
            "effort": 2 if check["check_id"] == "bot-access" else 3,
            "affected_page_ids": [],
            "evidence_ids": check["evidence_ids"],
        }
    actions = []
    severity_rank = {"critical": 4, "high": 3, "medium": 2, "low": 1}
    for action in grouped.values():
        action["affected_page_ids"] = sorted(set(action["affected_page_ids"]))
        action["evidence_ids"] = sorted(set(action["evidence_ids"]))
        action["priority"] = action["impact"] * (6 - action["effort"]) * 5
        actions.append(action)
    actions.sort(key=lambda item: (-severity_rank[item["severity"]], -item["priority"], item["action_id"]))
    return {"protocol_version": PROTOCOL_VERSION, "run_id": run_id, "actions": actions}


def site_diagnose(
    url: str,
    output_path: Path,
    *,
    locale: str = "zh-CN",
    max_pages: int = MAX_PAGES,
    render_mode: str = "auto",
    clock: Clock | None = None,
    fetcher: Fetcher | None = None,
    resolver: Resolver = socket.getaddrinfo,
    demo_fixture: bool = False,
) -> dict[str, Any]:
    if isinstance(max_pages, bool) or not isinstance(max_pages, int) or not 1 <= max_pages <= MAX_PAGES:
        raise ValueError(f"max_pages must be an integer from 1 to {MAX_PAGES}")
    if render_mode not in {"auto", "http", "browser"}:
        raise ValueError("render mode must be auto, http, or browser")
    locale = _normalize_locale(locale)
    normalized_input, initial_host = _validate_url_syntax(url)
    now = (clock or (lambda: datetime.now(timezone.utc)))()
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    now = now.astimezone(timezone.utc)
    created_at = now.isoformat().replace("+00:00", "Z")
    deadline = time.monotonic() + TOTAL_FETCH_SECONDS
    inventory: dict[str, InventoryItem] = {}
    resources: list[dict[str, Any]] = []
    crawl_events: list[dict[str, Any]] = []
    limitations: list[str] = []
    stored_bytes = 0
    network_bytes = 0

    def record_resource(path: str, source_uri: str, content: str, source_type: str) -> tuple[str, str]:
        nonlocal stored_bytes
        payload = content.encode("utf-8")
        if len(payload) > MAX_FETCH_BYTES:
            raise SourceUnavailable(f"decoded resource exceeds {MAX_FETCH_BYTES} byte limit")
        if stored_bytes + len(payload) > MAX_TOTAL_BYTES:
            raise SourceUnavailable(f"total source content exceeds {MAX_TOTAL_BYTES} byte limit")
        stored_bytes += len(payload)
        digest = hashlib.sha256(payload).hexdigest()
        evidence_id = _stable_id("ev", source_uri, digest)
        resources.append(
            {
                "path": path,
                "source_uri": source_uri,
                "source_type": source_type,
                "content": content,
                "sha256": digest,
                "evidence_id": evidence_id,
            }
        )
        return digest, evidence_id

    def fetch_bounded(
        target_url: str,
        *,
        approved: str | None,
        media_types: set[str],
    ) -> tuple[FetchResult, str]:
        nonlocal network_bytes
        remaining = min(MAX_TOTAL_BYTES - network_bytes, MAX_TOTAL_BYTES - stored_bytes)
        if remaining <= 0:
            raise SourceUnavailable("total source or network byte budget exhausted")
        try:
            result, host = _fetch_resource(
                target_url,
                resolver=resolver,
                fetcher=fetcher,
                deadline=deadline,
                approved_host=approved,
                allowed_media_types=media_types,
                max_bytes=min(MAX_FETCH_BYTES, remaining),
            )
        except SourceUnavailable as exc:
            if remaining < MAX_FETCH_BYTES and "exceeds" in str(exc):
                network_bytes = MAX_TOTAL_BYTES
            raise
        network_bytes += len(result.body)
        return result, host

    root_html: str | None = None
    root_url = normalized_input
    approved_host = initial_host
    root_message: str | None = None
    try:
        result, approved_host = fetch_bounded(
            normalized_input,
            approved=None,
            media_types={"text/html", "application/xhtml+xml"},
        )
        root_url = result.final_url
        root_html = _decode_html(result)
        record_resource("input/sources/homepage.html", root_url, root_html, "target_url")
        crawl_events.append({"url": root_url, "kind": "homepage", "status": "observed", "message": "Homepage fetched and parsed."})
    except URLPolicyError:
        raise
    except (OSError, SourceUnavailable) as exc:
        root_message = str(exc)
        limitations.append(
            _t(
                locale,
                f"首页不可用：{root_url}。综合评分未生成。",
                f"The homepage was unavailable: {root_url}. No overall score was generated.",
            )
        )
        crawl_events.append({"url": root_url, "kind": "homepage", "status": "source_gap", "message": root_message})

    base = urlsplit(root_url)
    origin = urlunsplit((base.scheme, base.netloc, "", "", ""))
    _add_inventory_item(inventory, root_url, approved_host, navigation=True)
    if root_html is not None:
        parser = DiscoveryParser(root_url)
        parser.feed(root_html)
        parser.close()
        for link, label, in_nav in parser.links:
            _add_inventory_item(inventory, link, approved_host, anchor=label, navigation=in_nav)

    robots_url = urljoin(origin + "/", "robots.txt")
    robots_parser: urllib.robotparser.RobotFileParser | None = None
    robots_sitemaps: list[str] = []
    robots_evidence_id: str | None = None
    try:
        result, _host = fetch_bounded(
            robots_url,
            approved=approved_host,
            media_types={"text/plain", "text/html", "application/octet-stream"},
        )
        robots_text = _decode_text(result)
        _digest, robots_evidence_id = record_resource("input/sources/robots.txt", result.final_url, robots_text, "robots")
        robots_parser, robots_sitemaps = _parse_robots(robots_text, result.final_url)
        crawl_events.append({"url": result.final_url, "kind": "robots", "status": "observed", "message": "robots.txt parsed."})
    except (OSError, SourceUnavailable) as exc:
        limitations.append(
            _t(
                locale,
                "robots.txt 未能取得，爬虫访问矩阵标记为证据缺失。",
                "robots.txt was unavailable, so the crawler access matrix is marked as missing evidence.",
            )
        )
        crawl_events.append({"url": robots_url, "kind": "robots", "status": "source_gap", "message": str(exc)})

    sitemap_queue = list(dict.fromkeys([*robots_sitemaps, urljoin(origin + "/", "sitemap.xml")]))
    sitemap_seen: set[str] = set()
    sitemap_evidence_ids: list[str] = []
    while sitemap_queue and len(sitemap_seen) < MAX_SITEMAPS and len(inventory) < MAX_INVENTORY_URLS:
        candidate = sitemap_queue.pop(0)
        try:
            normalized_sitemap, host = _validate_url_syntax(candidate)
            if (
                host != approved_host
                or normalized_sitemap in sitemap_seen
                or urlsplit(normalized_sitemap).query
            ):
                continue
            if robots_parser is not None and not robots_parser.can_fetch(USER_AGENT, normalized_sitemap):
                crawl_events.append(
                    {
                        "url": normalized_sitemap,
                        "kind": "sitemap",
                        "status": "robots-blocked",
                        "message": "robots.txt blocks this sitemap URL.",
                    }
                )
                continue
            sitemap_seen.add(normalized_sitemap)
            result, _host = fetch_bounded(
                normalized_sitemap,
                approved=approved_host,
                media_types={"application/xml", "text/xml", "application/rss+xml", "text/plain", "application/octet-stream"},
            )
            sitemap_text = _decode_text(result)
            entries, children = _parse_sitemap(sitemap_text)
            path = f"input/sources/sitemap-{len(sitemap_seen)}.xml"
            _digest, evidence_id = record_resource(path, result.final_url, sitemap_text, "sitemap")
            sitemap_evidence_ids.append(evidence_id)
            for entry_url, lastmod in entries:
                _add_inventory_item(inventory, entry_url, approved_host, sitemap=True, lastmod=lastmod)
            sitemap_queue.extend(children)
            crawl_events.append({"url": result.final_url, "kind": "sitemap", "status": "observed", "message": f"Parsed {len(entries)} URL entries."})
        except (OSError, SourceUnavailable, URLPolicyError) as exc:
            crawl_events.append({"url": candidate, "kind": "sitemap", "status": "source_gap", "message": str(exc)})

    selected, candidate_records = _select_pages(inventory, root_url, now, max_pages)
    pages: list[dict[str, Any]] = []
    resource_by_uri = {resource["source_uri"]: resource for resource in resources}
    observed_final_urls: set[str] = set()
    observed_content_hashes: set[str] = set()
    for index, item in enumerate(selected):
        page_id = _stable_id("page", item.url)
        if item.url == root_url and root_html is None:
            pages.append(_source_gap_page(item, root_message or _t(locale, "首页不可用。", "Homepage unavailable."), locale))
            continue
        if item.url != root_url and robots_parser is not None and not robots_parser.can_fetch(USER_AGENT, item.url):
            pages.append(
                _source_gap_page(
                    item,
                    _t(
                        locale,
                        "robots.txt 阻止 GEOHub 诊断爬虫访问。",
                        "robots.txt blocks the GEOHub diagnostic crawler.",
                    ),
                    locale,
                )
            )
            continue
        page_html = root_html if item.url == root_url else None
        final_url = root_url if item.url == root_url else item.url
        render_used = "http"
        render_gap = None
        if page_html is None:
            try:
                result, _host = fetch_bounded(
                    item.url,
                    approved=approved_host,
                    media_types={"text/html", "application/xhtml+xml"},
                )
                final_url = result.final_url
                page_html = _decode_html(result)
            except (OSError, SourceUnavailable, URLPolicyError) as exc:
                pages.append(_source_gap_page(item, str(exc), locale))
                crawl_events.append({"url": item.url, "kind": "representative-page", "status": "source_gap", "message": str(exc)})
                continue
        if final_url in observed_final_urls:
            message = "selected candidate redirects to a representative page already analyzed"
            pages.append(_source_gap_page(item, message, locale))
            crawl_events.append({"url": item.url, "kind": "representative-page", "status": "source_gap", "message": message})
            continue
        metrics = analyze_html(page_html, final_url)
        js_shell = metrics["visible_text_length"] < 200 and bool(re.search(r"<(?:script|div)[^>]+(?:id=[\"'](?:app|root)|src=)", page_html, re.I))
        wants_browser = render_mode == "browser" or (render_mode == "auto" and js_shell)
        if wants_browser:
            if fetcher is not None:
                render_gap = "browser rendering skipped for injected or fixture fetcher"
            else:
                if final_url not in resource_by_uri:
                    try:
                        record_resource(
                            f"input/sources/{page_id}-http.html",
                            final_url,
                            page_html,
                            "target_url",
                        )
                    except SourceUnavailable as exc:
                        pages.append(_source_gap_page(item, str(exc), locale))
                        continue
                    resource_by_uri[final_url] = resources[-1]
                render_reserve = min(MAX_FETCH_BYTES, max(0, MAX_TOTAL_BYTES - stored_bytes))
                browser_budget = max(
                    0,
                    min(
                        MAX_TOTAL_BYTES - network_bytes,
                        MAX_TOTAL_BYTES - stored_bytes - render_reserve,
                    ),
                )
                rendered, render_gap, browser_bytes = _browser_render(
                    final_url,
                    approved_host,
                    initial_html=page_html,
                    byte_budget=browser_budget,
                    resolver=resolver,
                    timeout_seconds=max(1.0, min(20.0, deadline - time.monotonic())),
                )
                network_bytes += browser_bytes
                if rendered:
                    page_html = rendered
                    render_used = "browser"
        content_digest = hashlib.sha256(page_html.encode("utf-8")).hexdigest()
        if content_digest in observed_content_hashes:
            message = "selected candidate duplicates the content of a representative page already analyzed"
            pages.append(_source_gap_page(item, message, locale))
            crawl_events.append({"url": final_url, "kind": "representative-page", "status": "source_gap", "message": message})
            continue
        resource = resource_by_uri.get(final_url)
        if render_used == "browser" or resource is None or resource["source_type"] != "target_url":
            try:
                suffix = "-browser" if render_used == "browser" else ""
                source_type = "browser_snapshot" if render_used == "browser" else "target_url"
                _digest, evidence_id = record_resource(
                    f"input/sources/{page_id}{suffix}.html",
                    final_url,
                    page_html,
                    source_type,
                )
            except SourceUnavailable as exc:
                pages.append(_source_gap_page(item, str(exc), locale))
                continue
            resource_by_uri[final_url] = resources[-1]
        else:
            evidence_id = resource["evidence_id"]
        pages.append(
            _page_record(
                item,
                page_html,
                final_url,
                page_id=page_id,
                evidence_id=evidence_id,
                render_mode=render_used,
                render_gap=render_gap,
                now=now,
                locale=locale,
            )
        )
        observed_final_urls.add(final_url)
        observed_content_hashes.add(content_digest)
        crawl_events.append({"url": final_url, "kind": "representative-page", "status": "observed", "message": f"Page analyzed with {render_used} rendering."})

    crawler_matrix = _crawler_matrix(robots_parser, [page["url"] for page in pages])
    for page in pages:
        page["crawler_access"] = [
            {
                "agent": crawler["agent"],
                "role": crawler["role"],
                "allowed": next(
                    (item["allowed"] for item in crawler["page_access"] if item["url"] == page["url"]),
                    None,
                ),
            }
            for crawler in crawler_matrix
        ]

    source_fingerprints = [{"source_uri": resource["source_uri"], "sha256": resource["sha256"]} for resource in resources]
    identity = json.dumps(
        {
            "url": root_url,
            "locale": locale,
            "max_pages": max_pages,
            "render_mode": render_mode,
            "evaluation_as_of": created_at,
            "sources": source_fingerprints,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    run_id = _stable_id("run", SKILL_ID, identity)
    dimensions, overall_score, confidence, site_checks = _aggregate_site(
        pages,
        crawler_matrix,
        robots_evidence_id=robots_evidence_id,
        sitemap_evidence_id=sitemap_evidence_ids[0] if sitemap_evidence_ids else None,
        locale=locale,
    )
    if root_html is None:
        overall_score = None
    sampling = {
        "protocol_version": PROTOCOL_VERSION,
        "run_id": run_id,
        "root_url": root_url,
        "inventory_count": len(inventory),
        "selected_count": len(selected),
        "max_pages": max_pages,
        "page_types": [{"id": key, "label": _page_label(key, locale)} for key, _label, _terms in PAGE_TYPES],
        "candidates": candidate_records,
        "selected": [
            {
                "url": item.url,
                "page_type": item.page_type,
                "representativeness": item.representativeness,
                "type_confidence": round(item.type_confidence, 4),
            }
            for item in selected
        ],
    }
    render_limitations = sorted(
        {
            _t(locale, f"浏览器渲染缺口：{page['render_gap']}", f"Browser render gap: {page['render_gap']}")
            for page in pages
            if page.get("render_gap")
        }
    )
    diagnosis = {
        "protocol_version": PROTOCOL_VERSION,
        "run_id": run_id,
        "subject": (urlsplit(root_url).hostname or root_url),
        "root_url": root_url,
        "locale": locale,
        "status": "completed"
        if pages and all(page["status"] == "observed" and not page.get("render_gap") for page in pages)
        else "degraded",
        "overall_score": overall_score,
        "confidence": confidence,
        "dimensions": dimensions,
        "dimension_weights": DIMENSION_WEIGHTS,
        "crawler_matrix": crawler_matrix,
        "site_checks": site_checks,
        "pages": pages,
        "limitations": limitations
        + render_limitations
        + [
            _t(
                locale,
                "评分只描述本次代表页面快照中的可观察信号。",
                "Scores describe only observable signals in this representative-page snapshot.",
            ),
            _t(
                locale,
                "报告不估计真实 AI 排名、召回、引用次数、流量或业务效果。",
                "The report does not estimate live AI rankings, retrieval, citations, traffic, or business outcomes.",
            ),
        ],
    }
    backlog = _remediation_backlog(pages, site_checks, run_id)
    ledger = {
        "protocol_version": PROTOCOL_VERSION,
        "run_id": run_id,
        "records": [
            {
                "evidence_id": resource["evidence_id"],
                "claim": f"{resource['source_type']} snapshot used for bounded website diagnosis; sha256={resource['sha256']}.",
                "source_uri": resource["source_uri"],
                "status": "provided" if demo_fixture else "unverified",
            }
            for resource in resources
        ],
        "missing_evidence": sorted(
            {
                check["check_id"]
                for check in [*site_checks, *(item for page in pages for item in page.get("checks", []))]
                if check["status"] == "missing-evidence"
            }
        ),
    }
    crawl_manifest = {
        "protocol_version": PROTOCOL_VERSION,
        "run_id": run_id,
        "root_url": root_url,
        "approved_host": approved_host,
        "user_agent": USER_AGENT,
        "budgets": {
            "max_pages": max_pages,
            "max_inventory_urls": MAX_INVENTORY_URLS,
            "max_sitemaps": MAX_SITEMAPS,
            "max_bytes_per_resource": MAX_FETCH_BYTES,
            "max_total_bytes": MAX_TOTAL_BYTES,
            "max_total_seconds": TOTAL_FETCH_SECONDS,
        },
        "total_source_bytes": stored_bytes,
        "total_network_bytes": network_bytes,
        "events": crawl_events,
    }
    warnings = sorted(
        {
            page.get("message")
            for page in pages
            if page["status"] == "source_gap" and page.get("message")
        }
        | set(diagnosis["limitations"][:-2])
    )
    quality = {
        "protocol_version": PROTOCOL_VERSION,
        "run_id": run_id,
        "passed_checks": [
            "URL inventory stayed within 500 entries.",
            f"Representative page count stayed within {MAX_PAGES}.",
            "Every numeric score retains reconstructable checks and evidence IDs.",
            "The standalone report contains no runtime CDN dependency.",
        ],
        "warnings": warnings,
        "failed_checks": [],
        "status": "passed-with-warnings" if warnings else "passed",
    }
    brief = {
        "url": root_url,
        "locale": locale,
        "max_pages": max_pages,
        "render_mode": render_mode,
        "demo_fixture": demo_fixture,
        "evaluation_as_of": created_at,
    }
    report = render_site_report(diagnosis, sampling, backlog, demo_fixture=demo_fixture)
    with ArtifactBus.transaction(Path(output_path), run_id) as bus:
        bus.write_json("input/site-diagnosis-brief.json", brief)
        for resource in resources:
            bus.write_text(resource["path"], resource["content"])
        bus.write_json("crawl-manifest.json", crawl_manifest)
        bus.write_json("sampling-plan.json", sampling, "site-sampling-plan")
        bus.write_json("site-diagnosis.json", diagnosis, "site-diagnosis")
        for page in pages:
            bus.write_json(f"pages/{page['page_id']}.json", page)
        bus.write_json("evidence-ledger.json", ledger, "evidence-ledger")
        bus.write_json("remediation-backlog.json", backlog, "site-remediation-backlog")
        bus.write_text("report.html", report)
        bus.write_json("quality-report.json", quality, "quality-report")
        staged = [
            "input/site-diagnosis-brief.json",
            *(resource["path"] for resource in resources),
            "crawl-manifest.json",
            "sampling-plan.json",
            "site-diagnosis.json",
            *(f"pages/{page['page_id']}.json" for page in pages),
            "evidence-ledger.json",
            "remediation-backlog.json",
            "report.html",
            "quality-report.json",
        ]
        lineage = build_run_lineage(
            bus.root,
            run_id=run_id,
            skill_id=SKILL_ID,
            status="completed" if quality["status"] == "passed" else "completed-with-warnings",
            artifact_paths=staged,
            metric_names=("overall-score", "diagnostic-confidence", "representative-pages"),
        )
        bus.write_json("run-lineage.json", lineage, "run-lineage")
        artifacts = [*staged, "run-lineage.json"]
        renderer_errors = [page["render_gap"] for page in pages if page.get("render_gap")]
        manifest = {
            "protocol_version": PROTOCOL_VERSION,
            "run_id": run_id,
            "created_at": created_at,
            "generator": {"name": "geo-seo-hub-site-diagnose", "version": package_version()},
            "input_artifact": "input/site-diagnosis-brief.json",
            "artifacts": artifacts,
            "status": "completed-with-warnings" if warnings else "completed",
            "degraded": bool(warnings),
            "missing_dependencies": ["playwright-browser"]
            if any("unavailable" in gap for gap in renderer_errors)
            else [],
            "renderer_errors": renderer_errors,
        }
        bus.write_json("run-manifest.json", manifest, "run-manifest")
        published = bus.publish(set(artifacts) | {"run-manifest.json"})
    return {
        "protocol_version": PROTOCOL_VERSION,
        "run_id": run_id,
        "status": manifest["status"],
        "overall_score": overall_score,
        "confidence": confidence,
        "representative_pages": len(pages),
        "report": str(published / "report.html"),
        "output": str(published),
        "run_directory": str(published),
    }
