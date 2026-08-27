from __future__ import annotations

import html
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

from .paths import repository_root


SKILL_ID = "geo-site-diagnose"
REPORT_FORMAT_VERSION = 2

DIMENSIONS: tuple[tuple[str, str, str, int], ...] = (
    ("access_discovery", "可访问与发现", "Access and discovery", 15),
    ("architecture_coverage", "内容架构覆盖", "Architecture coverage", 10),
    ("entity_clarity", "实体清晰度", "Entity clarity", 12),
    ("answerability", "可回答性", "Answerability", 15),
    ("evidence_citation", "证据与可引用性", "Evidence and citability", 16),
    ("authority_trust", "权威与信任", "Authority and trust", 12),
    ("structured_extractability", "结构化与可提取性", "Structure and extractability", 12),
    ("freshness", "新鲜度与维护", "Freshness and maintenance", 8),
)

COPY = {
    "zh-CN": {
        "title": "网站 GEO 诊断报告",
        "summary": "代表页面的技术发现、内容证据与回答准备度快照",
        "fixture": "GEOHub 演示固件",
        "score": "综合分",
        "confidence": "诊断置信度",
        "inventory": "发现 URL",
        "selected": "典型页面",
        "observed": "成功分析",
        "gaps": "来源缺口",
        "navigation": "报告导航",
        "menu": "打开目录",
        "skip": "跳到报告正文",
        "verdict": "诊断结论",
        "evidence": "关键证据",
        "action": "优先动作",
        "data": "查看图表数据",
        "gap": "当前证据不足，图表未生成",
        "no_data": "暂无可用数据",
        "page_details": "页面检查明细",
        "raw_evidence": "原始证据",
        "raw_excerpt": "原始正文摘录",
        "observed_links": "观察链接",
        "issues": "页面问题与修复",
        "checks": "查看全部检查明细",
        "method": "方法与边界",
        "method_text": "最多分析十个代表页面，分数仅描述本次快照中的可观察信号；报告不估计真实 AI 排名、召回、引用次数、流量或业务效果",
        "modules": {
            "overview": ("GEO 综合结论", "用八维加权评分定位整站 GEO 准备度、优势维度分布与主要诊断短板", "综合分与置信度共同解释当前结论，优先处理最低分的高权重维度"),
            "discovery": ("可访问与发现", "核对搜索型与训练控制型爬虫规则，以及从发现到可分析的页面转化", "发现链路决定页面能否进入后续解析，阻断项应先于内容优化处理"),
            "architecture": ("内容架构覆盖", "系统验证十类页面覆盖、抽样代表性与典型页面之间的内部连接关系", "覆盖完整度与内部连接共同影响主题入口和页面发现效率"),
            "entity": ("实体清晰度", "比较标题主语与实体 Schema 信号，识别品牌和主题表达的缺口位置", "清晰且一致的实体信号有助于页面被准确归类和引用"),
            "answerability": ("可回答性", "评估可见正文深度、分段结构和能够直接提取的答案组织总体质量水平", "回答结构与内容深度需要同时达标，单纯增加篇幅无法补足组织缺口"),
            "evidence": ("证据与可引用性", "检查来源语言、外部原始链接与带上下文的数字证明完整度整体表现", "可追溯证据提升事实密度，也降低引用时的验证成本"),
            "authority": ("权威与信任", "核对作者归属、机构主体与联系信号，并比较代表页面的信任准备度", "责任主体和可联系信息是内容可信度的重要基础"),
            "structure": ("结构化与新鲜度", "观察语义结构、Schema 覆盖和站点地图更新时间的分布质量表现", "机器可提取结构与可信更新时间共同支持稳定解析"),
            "pages": ("典型页面详诊", "横向比较页面与维度分数，再逐页核对原始证据、具体问题和修复动作", "页面级差异能够验证整站平均分，并定位具体执行入口"),
            "actions": ("修复路线与总结", "按问题层级、影响和实施成本安排清晰且可执行的网站优化任务顺序", "先处理高影响低成本动作，再推进需要跨页面协作的结构性改造"),
        },
        "nav": ("总览", "发现", "架构", "实体", "回答", "证据", "权威", "结构", "页面", "行动"),
    },
    "en-US": {
        "title": "Website GEO Diagnosis",
        "summary": "A representative-page snapshot of technical discovery, evidence, and answer readiness",
        "fixture": "GEOHub demo fixture",
        "score": "Overall score",
        "confidence": "Diagnostic confidence",
        "inventory": "Discovered URLs",
        "selected": "Representative pages",
        "observed": "Analyzed pages",
        "gaps": "Source gaps",
        "navigation": "Report navigation",
        "menu": "Open contents",
        "skip": "Skip to report content",
        "verdict": "Diagnostic verdict",
        "evidence": "Key evidence",
        "action": "Priority action",
        "data": "View chart data",
        "gap": "Evidence is insufficient, so this chart was not generated",
        "no_data": "No usable data",
        "page_details": "Page check details",
        "raw_evidence": "Raw evidence",
        "raw_excerpt": "Raw content excerpt",
        "observed_links": "Observed links",
        "issues": "Page issues and repairs",
        "checks": "View all check details",
        "method": "Method and limits",
        "method_text": "The report analyzes up to ten representative pages and scores only observable signals in this snapshot; it does not estimate live AI rankings, retrieval, citation counts, traffic, or business outcomes",
        "modules": {
            "overview": ("GEO conclusion", "Use eight weighted dimensions to locate site readiness, strengths, and primary gaps", "Read the overall score with confidence, then address the lowest high-weight dimensions first"),
            "discovery": ("Access and discovery", "Review search and training-control crawler rules and the path from discovery to analysis", "Discovery determines whether later extraction can happen, so resolve blockers before content work"),
            "architecture": ("Architecture coverage", "Validate ten page families, representativeness, and links among selected pages", "Coverage and internal connections shape topic entry points and discovery efficiency"),
            "entity": ("Entity clarity", "Compare heading subjects and entity Schema signals across representative pages", "Clear and consistent entity signals support accurate classification and citation"),
            "answerability": ("Answerability", "Assess content depth, sectional structure, and directly extractable answer patterns", "Answer structure and depth must work together to support useful extraction"),
            "evidence": ("Evidence and citability", "Check source language, primary external links, and contextual numeric proof", "Traceable evidence raises factual density and lowers verification effort"),
            "authority": ("Authority and trust", "Review authorship, accountable organizations, and contact signals across pages", "Accountability and contact information form a core trust foundation"),
            "structure": ("Structure and freshness", "Inspect semantic structure, Schema coverage, and sitemap update patterns", "Extractable structure and credible update dates support stable parsing"),
            "pages": ("Page diagnosis", "Compare page and dimension scores, then inspect evidence, issues, and repairs page by page", "Page-level differences validate site averages and locate execution entry points"),
            "actions": ("Remediation roadmap", "Sequence improvements by issue hierarchy, impact, effort, and priority", "Start with high-impact low-effort actions, then move to structural changes across pages"),
        },
        "nav": ("Overview", "Discovery", "Architecture", "Entity", "Answers", "Evidence", "Authority", "Structure", "Pages", "Actions"),
    },
}

CHARTS = {
    "radar": ("八维诊断雷达", "Eight-dimension radar", "展示整站八维 GEO 准备度轮廓", "Show the site readiness profile"),
    "dimensions": ("维度加权对比", "Weighted dimension comparison", "同时读取各维度分数与诊断权重", "Read scores with diagnostic weights"),
    "crawlers": ("爬虫访问矩阵", "Crawler access matrix", "区分搜索发现爬虫与训练控制规则", "Separate search access and training control"),
    "funnel": ("诊断准备度漏斗", "Diagnostic readiness funnel", "定位从 URL 发现到证据准备的页面损耗", "Locate page loss in the discovery path"),
    "types": ("页面类型覆盖", "Page type coverage", "查看十类内容的代表页面覆盖状态", "Review representative status across ten families"),
    "representativeness": ("页面代表性排序", "Page representativeness ranking", "验证典型页面抽样质量与置信度", "Validate representative-page selection"),
    "links": ("典型页面内链图", "Representative-page link graph", "观察选中典型页面之间的内部连接", "Inspect connections among selected pages"),
    "entity_matrix": ("实体信号矩阵", "Entity signal matrix", "核对标题主语与实体 Schema 完整度", "Review heading subjects and entity Schema"),
    "entity_ranking": ("实体清晰度排序", "Entity clarity ranking", "识别实体表达清晰度较弱的页面", "Find pages with weaker entity expression"),
    "answer_ranking": ("可回答性排序", "Answerability ranking", "比较典型页面的回答准备度分数", "Compare page answer readiness"),
    "answer_scatter": ("深度与结构分布", "Depth and structure distribution", "同时观察可见正文深度与结构密度", "Compare content depth and structural density"),
    "evidence_matrix": ("引用证据矩阵", "Citation evidence matrix", "核对来源、外部链接与数字证明信号", "Review sources, external links, and numeric proof"),
    "evidence_ranking": ("可引用性排序", "Citability ranking", "定位证据与引用准备度较低的页面", "Locate pages with weaker citation readiness"),
    "authority_matrix": ("信任信号矩阵", "Trust signal matrix", "核对作者归属与可联系信息信号", "Review authorship and contact signals"),
    "authority_ranking": ("权威准备度排序", "Authority readiness ranking", "比较页面的责任主体与信任信号", "Compare accountable-entity signals"),
    "schema": ("Schema 类型结构", "Schema type structure", "汇总代表页面中已观察的结构化类型", "Summarize structured types across pages"),
    "structured_matrix": ("结构化检查矩阵", "Structured check matrix", "核对语义地标与结构化数据完整度", "Review semantic landmarks and structured data"),
    "freshness": ("更新时间分布", "Update-date distribution", "查看站点地图 lastmod 可信度", "Inspect sitemap lastmod coverage"),
    "page_heatmap": ("页面维度热力图", "Page-dimension heatmap", "横向定位页面与维度之间的分数差异", "Locate page-level differences"),
    "distribution": ("页面得分分布", "Page score distribution", "观察代表页面样本的得分区间分布", "Review score bands in the sample"),
    "severity": ("问题层级旭日图", "Issue hierarchy sunburst", "按诊断维度与问题严重度聚合问题", "Group issues by dimension and severity"),
    "priority": ("影响与成本分布", "Impact and effort distribution", "识别高影响且低实施成本的行动", "Find high-impact low-effort actions"),
    "priority_ranking": ("修复优先级排序", "Remediation priority ranking", "按可执行优先级安排修复任务顺序", "Sequence actions by executable priority"),
}

CHART_CONTRACTS = {
    "radar": ("dimensions.score", "all eight dimensions are numeric", "explicit dimension evidence gap"),
    "dimensions": ("dimensions.score, dimensions.weight", "at least one numeric dimension", "available-dimension ranking"),
    "crawlers": ("crawler_matrix.page_access", "crawler and selected-page records exist", "explicit access evidence gap"),
    "funnel": ("inventory_count, selected_count, observed_count, evidence_ready_count", "all stage counts are numeric", "stage data table"),
    "types": ("pages.type, pages.status", "at least one selected page", "page coverage table"),
    "representativeness": ("pages.selection.representativeness", "at least one numeric selection score", "selection table"),
    "links": ("pages.internal_links", "at least two nodes and one observed edge", "page relationship table"),
    "entity_matrix": ("checks.entity-heading, checks.entity-schema", "selected-page records exist", "missing-state matrix and table"),
    "entity_ranking": ("pages.dimensions.entity_clarity", "at least one numeric page score", "available-page ranking"),
    "answer_ranking": ("pages.dimensions.answerability", "at least one numeric page score", "available-page ranking"),
    "answer_scatter": ("metrics.visible_text_length, headings, lists, tables", "at least one observed page metric", "page metric table"),
    "evidence_matrix": ("checks.evidence-language, checks.external-sources, checks.numeric-proof", "selected-page records exist", "missing-state matrix and table"),
    "evidence_ranking": ("pages.dimensions.evidence_citation", "at least one numeric page score", "available-page ranking"),
    "authority_matrix": ("checks.authorship, checks.trust-contact", "selected-page records exist", "missing-state matrix and table"),
    "authority_ranking": ("pages.dimensions.authority_trust", "at least one numeric page score", "available-page ranking"),
    "schema": ("metrics.schema_types", "at least one observed Schema type", "explicit Schema evidence gap"),
    "structured_matrix": ("checks.semantic-landmarks, checks.structured-data", "selected-page records exist", "missing-state matrix and table"),
    "freshness": ("pages.selection.lastmod", "at least one valid lastmod date", "explicit freshness evidence gap"),
    "page_heatmap": ("pages.dimensions", "at least one observed page", "missing-state heatmap and table"),
    "distribution": ("pages.score", "at least one observed page", "ranked bars for samples below three"),
    "severity": ("pages.issues.dimension, pages.issues.severity", "at least one failed check", "explicit issue evidence gap"),
    "priority": ("actions.impact, actions.effort, actions.priority", "at least one scored action", "remediation table"),
    "priority_ranking": ("actions.priority", "at least one scored action", "remediation table"),
}


def _is_en(locale: str) -> bool:
    return locale.startswith("en")


def _text(locale: str, zh: str, en: str) -> str:
    return en if _is_en(locale) else zh


def _escape(value: Any) -> str:
    if value is None:
        return "-"
    if isinstance(value, (dict, list, tuple)):
        value = json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False)
    return html.escape(str(value), quote=True)


def _asset(name: str) -> str:
    root = repository_root()
    candidates = (
        root / "skills" / SKILL_ID / "assets" / name,
        root / "assets" / "providers" / SKILL_ID / name,
        root / "assets" / name,
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate.read_text(encoding="utf-8")
    raise RuntimeError(f"packaged report asset is missing: {name}")


def _safe_json(value: Any) -> str:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
        .replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )


def _dimension_label(key: str, locale: str) -> str:
    for dimension, zh, en, _weight in DIMENSIONS:
        if dimension == key:
            return _text(locale, zh, en)
    return key


def _score_band(score: int | None, locale: str) -> tuple[str, str]:
    if score is None:
        return _text(locale, "证据不足", "Insufficient evidence"), "muted"
    if score >= 85:
        return _text(locale, "高准备度", "High readiness"), "good"
    if score >= 70:
        return _text(locale, "基础稳健", "Sound foundation"), "good"
    if score >= 55:
        return _text(locale, "需要改进", "Needs improvement"), "warn"
    if score >= 40:
        return _text(locale, "高风险", "High risk"), "risk"
    return _text(locale, "发现受阻", "Discovery blocked"), "risk"


def _check_map(page: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {check["check_id"]: check for check in page.get("checks", [])}


def _report_payload(diagnosis: dict[str, Any], sampling: dict[str, Any], backlog: dict[str, Any]) -> dict[str, Any]:
    locale = diagnosis["locale"]
    pages = diagnosis["pages"]
    observed = [page for page in pages if page["status"] == "observed"]
    schema_counts = Counter(schema for page in observed for schema in page.get("metrics", {}).get("schema_types", []))
    page_urls = {page["url"]: page["page_id"] for page in observed}
    links: set[tuple[str, str]] = set()
    for page in observed:
        for link in page.get("internal_links", []):
            normalized = link.split("#", 1)[0]
            if normalized in page_urls and normalized != page["url"]:
                links.add((page["page_id"], page_urls[normalized]))
    score_bins = {"0–39": 0, "40–54": 0, "55–69": 0, "70–84": 0, "85–100": 0}
    for page in observed:
        score = page.get("score")
        if not isinstance(score, (int, float)):
            continue
        bucket = "0–39" if score < 40 else "40–54" if score < 55 else "55–69" if score < 70 else "70–84" if score < 85 else "85–100"
        score_bins[bucket] += 1
    payload_pages = []
    for page in pages:
        checks = _check_map(page)
        payload_pages.append(
            {
                "id": page["page_id"],
                "label": page["page_type_label"],
                "type": page["page_type"],
                "url": page["url"],
                "status": page["status"],
                "score": page.get("score"),
                "confidence": page.get("confidence"),
                "dimensions": page.get("dimensions", {}),
                "selection": page.get("selection", {}),
                "metrics": page.get("metrics", {}),
                "checks": {
                    check_id: {
                        "status": check.get("status"),
                        "score": check.get("score"),
                        "raw": check.get("raw_value"),
                    }
                    for check_id, check in checks.items()
                },
            }
        )
    return {
        "reportFormatVersion": REPORT_FORMAT_VERSION,
        "locale": locale,
        "labels": {
            "allowed": _text(locale, "允许", "Allowed"),
            "blocked": _text(locale, "阻止", "Blocked"),
            "unknown": _text(locale, "未知", "Unknown"),
            "score": _text(locale, "分数", "Score"),
            "weight": _text(locale, "权重", "Weight"),
            "impact": _text(locale, "影响", "Impact"),
            "effort": _text(locale, "实施成本", "Effort"),
            "priority": _text(locale, "优先级", "Priority"),
            "discovered": _text(locale, "发现 URL", "Discovered URLs"),
            "selected": _text(locale, "典型页面", "Representative pages"),
            "observed": _text(locale, "成功分析", "Analyzed pages"),
            "ready": _text(locale, "证据准备", "Evidence ready"),
            "contentDepth": _text(locale, "可见正文", "Visible content"),
            "structureDensity": _text(locale, "结构密度", "Structure density"),
            "missing": _text(locale, "缺失", "Missing"),
            "observedStatus": _text(locale, "已分析", "Analyzed"),
            "sourceGap": _text(locale, "来源缺口", "Source gap"),
        },
        "overall": diagnosis.get("overall_score"),
        "confidence": diagnosis.get("confidence"),
        "dimensions": [
            {"id": key, "label": _dimension_label(key, locale), "weight": weight, "score": diagnosis.get("dimensions", {}).get(key)}
            for key, _zh, _en, weight in DIMENSIONS
        ],
        "pages": payload_pages,
        "crawlerMatrix": diagnosis.get("crawler_matrix", []),
        "inventoryCount": sampling.get("inventory_count", 0),
        "selectedCount": sampling.get("selected_count", 0),
        "observedCount": len(observed),
        "evidenceReadyCount": sum((page.get("dimensions", {}).get("evidence_citation") or 0) >= 50 for page in observed),
        "schemas": [{"name": name, "value": count} for name, count in sorted(schema_counts.items())],
        "scoreBins": score_bins,
        "graph": {
            "nodes": [{"id": page["page_id"], "name": page["page_type_label"], "value": page.get("score")} for page in observed],
            "links": [{"source": source, "target": target} for source, target in sorted(links)],
        },
        "issues": [
            {"dimension": issue["dimension"], "severity": issue["severity"], "page": page["page_id"]}
            for page in observed for issue in page.get("issues", [])
        ],
        "actions": backlog.get("actions", []),
    }


def _table(headers: Iterable[str], rows: Iterable[Iterable[Any]], *, numeric_from: int | None = None) -> str:
    head = "".join(f"<th scope='col'>{_escape(value)}</th>" for value in headers)
    body_rows = []
    for row in rows:
        cells = []
        for index, value in enumerate(row):
            class_name = " class='numeric'" if numeric_from is not None and index >= numeric_from else ""
            cells.append(f"<td{class_name}>{_escape(value)}</td>")
        body_rows.append("<tr>" + "".join(cells) + "</tr>")
    body = "".join(body_rows) or "<tr><td colspan='9'>-</td></tr>"
    return f"<div class='table-scroll'><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>"


def _chart_figure(chart_id: str, locale: str, table_html: str, *, span: int = 6, large: bool = False) -> str:
    zh_title, en_title, zh_caption, en_caption = CHARTS[chart_id]
    title = _text(locale, zh_title, en_title)
    caption = _text(locale, zh_caption, en_caption)
    chart_class = "chart chart-large" if large else "chart"
    source_fields, eligibility, fallback = CHART_CONTRACTS[chart_id]
    return f"""<figure class="chart-panel span-{span}" data-chart-figure="{chart_id}" data-source-fields="{_escape(source_fields)}" data-eligibility="{_escape(eligibility)}" data-fallback="{_escape(fallback)}">
      <figcaption><h3>{_escape(title)}</h3><p>{_escape(caption)}</p></figcaption>
      <div id="chart-{chart_id.replace('_', '-')}" class="{chart_class}" role="img" aria-label="{_escape(title)}" data-chart="{chart_id}"></div>
      <p class="chart-insight" data-chart-insight="{chart_id}">{_escape(caption)}</p>
      <div class="chart-gap" data-chart-gap="{chart_id}" hidden></div>
      <details class="fallback"><summary>{_escape(COPY[locale]['data'])}</summary>{table_html}</details>
    </figure>"""


def _module_header(module_id: str, index: int, locale: str) -> str:
    title, description, verdict = COPY[locale]["modules"][module_id]
    return f"""<header class="module-header">
      <span class="module-index">{index:02d}</span>
      <h2>{_escape(title)}</h2>
      <p>{_escape(description)}</p>
    </header><p class="module-verdict"><strong>{_escape(COPY[locale]['verdict'])}</strong><span>{_escape(verdict)}</span></p>"""


def _module_notes(locale: str, evidence: str, action: str) -> str:
    return f"""<div class="module-notes"><p><strong>{_escape(COPY[locale]['evidence'])}</strong>{_escape(evidence)}</p><p><strong>{_escape(COPY[locale]['action'])}</strong>{_escape(action)}</p></div>"""


def _render_page(page: dict[str, Any], locale: str) -> str:
    title = page.get("metrics", {}).get("title") or page["page_type_label"]
    if page["status"] != "observed":
        return f"""<article class="page-audit source-gap" id="{_escape(page['page_id'])}">
          <div class="page-kicker">{_escape(page['page_type_label'])} · {_text(locale, '来源缺口', 'Source gap')}</div>
          <h3>{_escape(title)}</h3><p class="url">{_escape(page['url'])}</p>
          <p>{_escape(page.get('message') or COPY[locale]['gap'])}</p>
        </article>"""
    metrics = page["metrics"]
    dimensions = "".join(
        f"<div class='dimension-line'><span>{_escape(_dimension_label(key, locale))}</span><strong>{_escape(value)}</strong><i><b style='width:{int(value) if isinstance(value, (int, float)) else 0}%'></b></i></div>"
        for key, value in page["dimensions"].items()
    )
    schema = ", ".join(metrics.get("schema_types", [])) or COPY[locale]["no_data"]
    crawler_values = [entry["allowed"] for entry in page.get("crawler_access", []) if entry["role"] == "search"]
    metric_rows = (
        (_text(locale, "可见正文", "Visible content"), f"{metrics['visible_text_length']:,}"),
        ("H2 / H3", f"{metrics['h2_count']} / {metrics['h3_count']}"),
        (_text(locale, "内链 / 外链", "Internal / external links"), f"{metrics['internal_link_count']} / {metrics['external_link_count']}"),
        (_text(locale, "列表 / 表格", "Lists / tables"), f"{metrics['list_count']} / {metrics['table_count']}"),
        (_text(locale, "搜索爬虫访问", "Search crawler access"), f"{sum(value is True for value in crawler_values)} / {len(crawler_values)}"),
        (_text(locale, "FAQ 信号", "FAQ signals"), metrics["faq_like_count"]),
        ("Schema", schema),
    )
    metrics_html = "".join(f"<div><dt>{_escape(label)}</dt><dd>{_escape(value)}</dd></div>" for label, value in metric_rows)
    issues = "".join(
        f"<li><span class='severity severity-{_escape(issue['severity'])}'>{_escape(issue['severity'])}</span><div><strong>{_escape(issue['statement'])}</strong><p>{_escape(issue['recommendation'])}</p></div></li>"
        for issue in page.get("issues", [])[:8]
    ) or f"<li><div><strong>{_text(locale, '当前检查未发现失败项', 'No failed checks in this snapshot')}</strong></div></li>"
    links = "".join(f"<li class='url'>{_escape(link)}</li>" for link in page.get("internal_links", [])[:10]) or f"<li>{_escape(COPY[locale]['no_data'])}</li>"
    check_rows = [
        (
            check["check_id"], _dimension_label(check["dimension"], locale), check.get("raw_value"), check.get("threshold"),
            f"{check['weight']}%", check["status"], check.get("score"), ", ".join(check.get("evidence_ids", [])) or "-", check["remediation"],
        )
        for check in page.get("checks", [])
    ]
    selection = page.get("selection", {})
    reason = str(selection.get("reason", "")).rstrip("。.")
    render_note = f" · {_text(locale, '渲染缺口', 'Render gap')} {_escape(page['render_gap'])}" if page.get("render_gap") else ""
    return f"""<article class="page-audit" id="{_escape(page['page_id'])}">
      <header class="page-heading"><div><div class="page-kicker">{_escape(page['page_type_label'])} · {_text(locale, '代表性', 'Representativeness')} {float(selection.get('representativeness', 0)):.0f}</div><h3>{_escape(title)}</h3><p class="url">{_escape(page['url'])}</p></div><div class="page-score"><strong>{_escape(page.get('score'))}</strong><span>/100</span></div></header>
      <p class="selection-reason">{_escape(reason)} · {_text(locale, '抓取模式', 'Render mode')} {_escape(page.get('render_mode'))} · {_text(locale, '证据置信度', 'Evidence confidence')} {_escape(page.get('confidence'))}%{render_note}</p>
      <div class="page-grid"><div class="dimension-stack">{dimensions}</div><dl class="metric-list">{metrics_html}</dl></div>
      <details class="evidence-details"><summary>{_escape(COPY[locale]['raw_evidence'])}</summary><dl class="evidence-list"><div><dt>ID</dt><dd class="url">{_escape(page['evidence_id'])}</dd></div><div><dt>SHA-256</dt><dd class="url">{_escape(page['content_sha256'])}</dd></div><div><dt>{_escape(COPY[locale]['raw_excerpt'])}</dt><dd>{_escape(metrics.get('evidence_excerpt'))}</dd></div><div><dt>{_escape(COPY[locale]['observed_links'])}</dt><dd><ul>{links}</ul></dd></div></dl></details>
      <h4>{_escape(COPY[locale]['issues'])}</h4><ul class="issue-list">{issues}</ul>
      <details class="check-details"><summary>{_escape(COPY[locale]['checks'])} ({len(check_rows)})</summary>{_table((_text(locale,'检查项','Check'), _text(locale,'维度','Dimension'), _text(locale,'原始值','Raw value'), _text(locale,'阈值','Threshold'), _text(locale,'权重','Weight'), _text(locale,'状态','Status'), _text(locale,'得分','Score'), 'Evidence ID', _text(locale,'修复动作','Remediation')), check_rows)}</details>
    </article>"""


def _report_body(diagnosis: dict[str, Any], sampling: dict[str, Any], backlog: dict[str, Any], *, demo_fixture: bool) -> str:
    locale = diagnosis["locale"]
    copy = COPY[locale]
    pages = diagnosis["pages"]
    observed = [page for page in pages if page["status"] == "observed"]
    gaps = len(pages) - len(observed)
    score = diagnosis.get("overall_score")
    band, band_class = _score_band(score, locale)
    dimensions_table = _table(
        (_text(locale, "维度", "Dimension"), _text(locale, "分数", "Score"), _text(locale, "权重", "Weight")),
        ((_dimension_label(key, locale), diagnosis.get("dimensions", {}).get(key), f"{weight}%") for key, _zh, _en, weight in DIMENSIONS),
        numeric_from=1,
    )
    page_table = _table(
        (_text(locale, "页面类型", "Page type"), _text(locale, "分数", "Score"), _text(locale, "状态", "Status"), "URL"),
        (
            (
                page["page_type_label"], page.get("score"),
                _text(locale, "已分析", "Analyzed") if page["status"] == "observed" else _text(locale, "来源缺口", "Source gap"),
                page["url"],
            )
            for page in pages
        ),
    )
    check_table = lambda ids: _table(
        (_text(locale, "页面", "Page"), *ids),
        ((page["page_type_label"], *(_check_map(page).get(check, {}).get("score") for check in ids)) for page in pages),
        numeric_from=1,
    )
    action_table = _table(
        ("#", _text(locale, "行动", "Action"), _text(locale, "维度", "Dimension"), _text(locale, "级别", "Severity"), _text(locale, "影响", "Impact"), _text(locale, "成本", "Effort"), _text(locale, "优先级", "Priority")),
        ((index, action["title"], _dimension_label(action["dimension"], locale), action["severity"], action["impact"], action["effort"], action["priority"]) for index, action in enumerate(backlog.get("actions", [])[:20], 1)),
        numeric_from=4,
    )
    chart_tables = {
        "radar": dimensions_table, "dimensions": dimensions_table,
        "crawlers": _table((_text(locale, "爬虫", "Crawler"), _text(locale, "角色", "Role"), _text(locale, "允许", "Allowed"), _text(locale, "阻止", "Blocked")), ((c["agent"], c["role"], c["allowed_count"], c["blocked_count"]) for c in diagnosis.get("crawler_matrix", [])), numeric_from=2),
        "funnel": _table((_text(locale, "阶段", "Stage"), _text(locale, "数量", "Count")), ((copy["inventory"], sampling.get("inventory_count")), (copy["selected"], sampling.get("selected_count")), (copy["observed"], len(observed))), numeric_from=1),
        "types": page_table, "representativeness": page_table, "links": page_table,
        "entity_matrix": check_table(("entity-heading", "entity-schema")), "entity_ranking": page_table,
        "answer_ranking": page_table, "answer_scatter": page_table,
        "evidence_matrix": check_table(("evidence-language", "external-sources", "numeric-proof")), "evidence_ranking": page_table,
        "authority_matrix": check_table(("authorship", "trust-contact")), "authority_ranking": page_table,
        "schema": page_table, "structured_matrix": check_table(("semantic-landmarks", "structured-data")), "freshness": page_table,
        "page_heatmap": page_table, "distribution": page_table,
        "severity": action_table, "priority": action_table, "priority_ranking": action_table,
    }
    nav_links = "".join(f"<a href='#{module_id}'>{_escape(label)}</a>" for module_id, label in zip(copy["modules"], copy["nav"], strict=True))
    fixture = f"<span class='fixture-label'>{_escape(copy['fixture'])}</span>" if demo_fixture else ""
    metrics = ((copy["confidence"], f"{diagnosis.get('confidence', 0)}%"), (copy["inventory"], sampling.get("inventory_count", 0)), (copy["selected"], sampling.get("selected_count", 0)), (copy["observed"], len(observed)), (copy["gaps"], gaps))
    metric_html = "".join(f"<div><strong>{_escape(value)}</strong><span>{_escape(label)}</span></div>" for label, value in metrics)
    chart = lambda chart_id, span=6, large=False: _chart_figure(chart_id, locale, chart_tables[chart_id], span=span, large=large)
    top_action = backlog.get("actions", [{}])[0].get("title") if backlog.get("actions") else copy["no_data"]
    page_sections = "".join(_render_page(page, locale) for page in pages)
    return f"""<a class="skip" href="#main-content">{_escape(copy['skip'])}</a>
<nav class="report-nav" aria-label="{_escape(copy['navigation'])}"><div class="nav-inner"><a class="brand" href="#overview">GEOHub / SITE DIAGNOSIS</a><div class="nav-links">{nav_links}</div><details class="nav-mobile"><summary>{_escape(copy['menu'])}</summary><div>{nav_links}</div></details></div></nav>
<main id="main-content">
  <header class="report-head"><div><span class="eyebrow">Evidence-lined website audit</span><h1>{_escape(copy['title'])}</h1><p>{_escape(diagnosis['subject'])} · {_escape(copy['summary'])}</p>{fixture}</div><div class="score-lockup"><span>{_escape(copy['score'])}</span><strong>{_escape(score)}</strong><em class="{band_class}">{_escape(band)}</em></div></header>
  <div class="metric-strip">{metric_html}</div>
  <section class="module module-overview" id="overview">{_module_header('overview', 1, locale)}<div class="chart-grid">{chart('radar', 7, True)}{chart('dimensions', 5, True)}</div>{_module_notes(locale, f"{len([value for value in diagnosis.get('dimensions', {}).values() if value is not None])} / 8 {_text(locale, '个维度具备评分证据', 'dimensions have scoring evidence')}", str(top_action))}</section>
  <section class="module" id="discovery">{_module_header('discovery', 2, locale)}<div class="chart-grid">{chart('crawlers', 7)}{chart('funnel', 5)}</div>{_module_notes(locale, f"{len(diagnosis.get('crawler_matrix', []))} {_text(locale, '类爬虫规则已核对', 'crawler policies reviewed')}", _text(locale, '优先解除搜索发现阻断并补齐站点地图证据', 'Resolve search discovery blocks and sitemap gaps first'))}</section>
  <section class="module" id="architecture">{_module_header('architecture', 3, locale)}<div class="chart-grid">{chart('types', 4)}{chart('representativeness', 4)}{chart('links', 4)}</div>{_module_notes(locale, f"{sampling.get('selected_count', 0)} / 10 {_text(locale, '类页面已覆盖', 'page families covered')}", _text(locale, '补齐缺失页面类型并增加描述性内部链接', 'Fill missing page families and add descriptive internal links'))}</section>
  <section class="module" id="entity">{_module_header('entity', 4, locale)}<div class="chart-grid">{chart('entity_matrix', 7)}{chart('entity_ranking', 5)}</div>{_module_notes(locale, _text(locale, '标题主语与实体 Schema 已按页核对', 'Heading subjects and entity Schema were reviewed by page'), _text(locale, '统一标题、H1 与实体结构化标记中的核心名称', 'Align core names across titles, H1s, and entity markup'))}</section>
  <section class="module" id="answerability">{_module_header('answerability', 5, locale)}<div class="chart-grid">{chart('answer_ranking', 5)}{chart('answer_scatter', 7)}</div>{_module_notes(locale, _text(locale, '正文长度与结构密度均来自可见页面快照', 'Content depth and structure density come from visible snapshots'), _text(locale, '先补充可直接回答问题的段落，再用小标题和列表组织', 'Add direct answer passages, then organize them with headings and lists'))}</section>
  <section class="module" id="evidence">{_module_header('evidence', 6, locale)}<div class="chart-grid">{chart('evidence_matrix', 7)}{chart('evidence_ranking', 5)}</div>{_module_notes(locale, _text(locale, '来源语言、外链与数字证明均保留检查证据 ID', 'Source language, links, and numeric proof retain evidence IDs'), _text(locale, '把来源、方法与数字口径放在对应主张附近', 'Place sources, methods, and numeric definitions near each claim'))}</section>
  <section class="module" id="authority">{_module_header('authority', 7, locale)}<div class="chart-grid">{chart('authority_matrix', 7)}{chart('authority_ranking', 5)}</div>{_module_notes(locale, _text(locale, '作者与联系信号按代表页面逐项判断', 'Authorship and contact signals were checked per page'), _text(locale, '明确作者、审核者或机构主体并补充可验证资历', 'Name authors, reviewers, or organizations and add verifiable credentials'))}</section>
  <section class="module" id="structure">{_module_header('structure', 8, locale)}<div class="chart-grid">{chart('schema', 4)}{chart('structured_matrix', 4)}{chart('freshness', 4)}</div>{_module_notes(locale, f"{sum(len(page.get('metrics', {}).get('schema_types', [])) for page in observed)} Schema {_text(locale, '类型实例已观察', 'type instances observed')}", _text(locale, '让 Schema 与可见正文一致，并维护真实 lastmod', 'Keep Schema aligned with visible content and maintain accurate lastmod values'))}</section>
  <section class="module" id="pages">{_module_header('pages', 9, locale)}<div class="chart-grid">{chart('page_heatmap', 7)}{chart('distribution', 5)}</div>{_module_notes(locale, f"{len(observed)} {_text(locale, '个页面具备完整检查记录', 'pages have complete check records')}", _text(locale, '从低分页面的高权重失败项开始修复', 'Start with high-weight failures on lower-scoring pages'))}<div class="page-list">{page_sections}</div></section>
  <section class="module" id="actions">{_module_header('actions', 10, locale)}<div class="chart-grid">{chart('severity', 4)}{chart('priority', 4)}{chart('priority_ranking', 4)}</div>{_module_notes(locale, f"{len(backlog.get('actions', []))} {_text(locale, '项行动已完成影响与成本评估', 'actions have impact and effort estimates')}", str(top_action))}<details class="action-details" open><summary>{_text(locale, '查看修复清单', 'View remediation backlog')}</summary>{action_table}</details></section>
  <footer><h2>{_escape(copy['method'])}</h2><p>{_escape(copy['method_text'])}</p></footer>
</main>
<noscript><div class="noscript-note">{_text(locale, '当前浏览器未运行脚本，数据表与逐页分析仍可阅读', 'Scripts are disabled; data tables and page analyses remain readable')}</div></noscript>"""


def render_site_report(
    diagnosis: dict[str, Any],
    sampling: dict[str, Any],
    backlog: dict[str, Any],
    *,
    demo_fixture: bool,
) -> str:
    locale = "en-US" if _is_en(diagnosis.get("locale", "zh-CN")) else "zh-CN"
    diagnosis = {**diagnosis, "locale": locale}
    controlled = [value for module in COPY[locale]["modules"].values() for value in module]
    controlled.extend(value for chart in CHARTS.values() for value in (chart[1], chart[3]) if _is_en(locale))
    controlled.extend(value for chart in CHARTS.values() for value in (chart[0], chart[2]) if not _is_en(locale))
    if any(value.endswith(("。", ".")) for value in controlled):
        raise RuntimeError("controlled report copy must omit terminal periods")
    payload = _report_payload(diagnosis, sampling, backlog)
    shell = _asset("report-shell.html")
    css = _asset("report.css").replace("</style", "<\\/style")
    script = _asset("report.js").replace("</script", "<\\/script")
    echarts = _asset("echarts.min.js").replace("</script", "<\\/script")
    body = _report_body(diagnosis, sampling, backlog, demo_fixture=demo_fixture)
    replacements = {
        "%%LANG%%": locale,
        "%%TITLE%%": _escape(f"{COPY[locale]['title']} · {diagnosis['subject']}"),
        "%%REPORT_CSS%%": css,
        "%%REPORT_BODY%%": body,
        "%%ECHARTS_JS%%": echarts,
        "%%REPORT_DATA%%": _safe_json(payload),
        "%%REPORT_JS%%": script,
        "%%REPORT_FORMAT_VERSION%%": str(REPORT_FORMAT_VERSION),
    }
    template_markers = set(re.findall(r"%%[A-Z0-9_]+%%", shell))
    missing = sorted(set(replacements) - template_markers)
    unknown = sorted(template_markers - set(replacements))
    if missing or unknown:
        raise RuntimeError(f"report template marker mismatch: missing={missing}, unknown={unknown}")
    return re.sub(
        r"%%[A-Z0-9_]+%%",
        lambda match: replacements[match.group(0)],
        shell,
    )
