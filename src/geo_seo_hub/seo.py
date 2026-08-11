from __future__ import annotations

import hashlib
import html
import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from .artifact_bus import ArtifactBus
from .validation import load_bounded_json, normalize_artifact_uri, validate_artifact
from .version import package_version

PROTOCOL_VERSION = "1.0.0"
GENERATOR_VERSION = package_version()
Clock = Callable[[], datetime]

_MODES = (
    ("implementation-request", ("修复", "实现", "改代码", "fix", "implement")),
    ("migration", ("迁移", "redirect map", "site move", "migration")),
    ("incident", ("流量下降", "traffic drop", "search console", "gsc")),
    ("experiment", ("实验", "对照组", "holdout", "seo test", "experiment")),
    ("international-commerce", ("hreflang", "多语言", "电商", "商品变体", "ecommerce", "international")),
    ("keyword-map", ("keyword-to-page", "页面映射", "关键词研究", "search intent", "organic keyword")),
    ("technical-audit", ("审计", "诊断", "audit", "diagnose", "canonical", "robots.txt", "sitemap", "technical seo", "index", "indexability")),
)

_ENGINE_MARKERS = {
    "google": ("google", "ai overview", "search console", "gsc"),
    "bing": ("bing", "indexnow"),
    "openai": ("openai", "chatgpt"),
    "perplexity": ("perplexity",),
}

def _text(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).split())

def _stable_id(prefix: str, value: str) -> str:
    return f"{prefix}-{hashlib.sha256(value.encode('utf-8')).hexdigest()[:12]}"

def _has_marker(text: str, marker: str) -> bool:
    if marker.isascii():
        pattern = re.escape(marker).replace(r"\ ", r"\s+")
        return re.search(rf"(?<![\w-]){pattern}(?![\w-])", text, flags=re.IGNORECASE) is not None
    return marker in text

def _mode(request: str) -> str:
    return next((mode for mode, markers in _MODES if any(_has_marker(request, marker) for marker in markers)), "advisory")

def _surfaces(request: str) -> list[str]:
    lowered = request.casefold()
    surfaces = ["organic-search"]
    if any(term in lowered for term in ("ai search", "ai 搜索", "ai overview", "chatgpt", "perplexity")):
        surfaces.append("ai-search")
    if any(term in lowered for term in ("图片", "image search")):
        surfaces.append("image-search")
    if any(term in lowered for term in ("视频", "video search")):
        surfaces.append("video-search")
    return surfaces

def _engines(request: str) -> list[str]:
    engines = [name for name, markers in _ENGINE_MARKERS.items() if any(_has_marker(request, marker) for marker in markers)]
    return engines or ["unspecified"]

def _normalize(brief: dict[str, Any]) -> dict[str, Any]:
    evidence = []
    for item in brief["evidence"]:
        evidence.append({"evidence_id": _text(item["evidence_id"]), "claim": _text(item["claim"]), "source_uri": normalize_artifact_uri(item["source_uri"], field="SEO evidence source URI"), "evidence_type": item["evidence_type"]})
    urls = [normalize_artifact_uri(value, field="SEO target URL") for value in brief["target_urls"]]
    rollback_boundary = brief["rollback_boundary"]
    return {"protocol_version": PROTOCOL_VERSION, "brief_id": _text(brief["brief_id"]), "request": _text(brief["request"]), "target_urls": sorted(set(urls)), "market": _text(brief["market"]), "language": _text(brief["language"]), "authorized_action": brief["authorized_action"], "rollback_boundary": _text(rollback_boundary) if rollback_boundary is not None else None, "evidence": sorted(evidence, key=lambda item: item["evidence_id"].casefold())}

def _action_plan(mode: str) -> list[dict[str, Any]]:
    common = [
        {"stage":"scope", "objective":"Confirm outcome, market, language, search surface, target inventory, and permitted action.", "required_evidence":[], "verification":"The scope and exclusions are explicit."},
        {"stage":"access-and-discovery", "objective":"Check crawler access, URL discovery, robots controls, sitemaps, status paths, and internal discovery.", "required_evidence":["HTTP responses", "robots and sitemap artifacts"], "verification":"Every conclusion names its checked artifact and coverage."},
        {"stage":"fetch-render-and-indexability", "objective":"Separate fetched HTML, rendered DOM, index eligibility, canonical signals, and platform processing.", "required_evidence":["rendered page or crawl evidence"], "verification":"Observed, inferred, and missing evidence remain separate."},
    ]
    specific = {
        "keyword-map": ("intent-and-page-map", "Map real search intent and page roles without inventing demand metrics.", ["query or SERP evidence"]),
        "incident": ("segmented-diagnosis", "Segment page, query, market, device, search type, and time before testing competing causes.", ["Search Console or equivalent first-party export"]),
        "migration": ("migration-control", "Build URL mappings and align redirects, canonicals, hreflang, sitemaps, monitoring, and rollback.", ["old and new URL inventory"]),
        "experiment": ("experiment-design", "Define hypothesis, unit, comparison, guardrails, window, and inconclusive outcome.", ["baseline and treatment inventory"]),
        "international-commerce": ("specialty-review", "Review locale URLs, reciprocal hreflang, variants, pagination, and visible product facts.", ["locale or product inventory"]),
        "implementation-request": ("implementation-gate", "Capture before evidence, explicit target and authorization, minimal changes, tests, and rollback.", ["explicit write authorization, target URL, and rollback boundary"]),
    }.get(mode)
    if specific:
        common.append({"stage":specific[0], "objective":specific[1], "required_evidence":specific[2], "verification":"The output records scope, evidence, owner, and rerun method."})
    return common

def _missing(brief: dict[str, Any], mode: str, *, write_authorized: bool) -> list[str]:
    evidence_types = {item["evidence_type"] for item in brief["evidence"]}
    missing = []
    if not ({"rendered_dom", "crawl"} & evidence_types): missing.append("rendered page or crawl evidence")
    if not ({"search_console", "webmaster_tools"} & evidence_types): missing.append("indexation outcome evidence")
    if mode == "keyword-map" and "serp" not in evidence_types: missing.append("query or SERP evidence")
    if mode == "incident" and "search_console" not in evidence_types: missing.append("Search Console or equivalent first-party export")
    if mode == "implementation-request" and not write_authorized: missing.append("explicit write authorization, target URL, and rollback boundary")
    return missing

def _markdown(plan: dict[str, Any]) -> str:
    safe = lambda value: re.sub(r"([\\`*{}\[\]()#+\-.!_>~|=])", r"\\\1", html.escape(value, quote=False))
    lines = [f"# One-line SEO plan: {safe(plan['request'])}", "", f"- Work mode: {plan['work_mode']}", f"- Claim status: {plan['claim_status']}", f"- Write authorized: {str(plan['write_authorized']).lower()}", "", "## Action plan", ""]
    lines.extend(f"- **{safe(item['stage'])}** — {safe(item['objective'])}" for item in plan["action_plan"])
    lines.extend(["", "## Missing evidence", ""])
    lines.extend(f"- {safe(item)}" for item in plan["missing_evidence"] or ["None declared"])
    lines.extend(["", "## Guardrails", ""])
    lines.extend(f"- {safe(item)}" for item in plan["guardrails"])
    return "\n".join(lines) + "\n"

def seo(input_path: Path, output_path: Path, *, clock: Clock | None = None) -> dict[str, Any]:
    raw = load_bounded_json(input_path, max_bytes=2 * 1024 * 1024, field="SEO brief")
    validate_artifact("seo-brief", raw)
    brief = _normalize(raw)
    validate_artifact("seo-brief", brief)
    evidence_ids = [item["evidence_id"] for item in brief["evidence"]]
    if len(evidence_ids) != len(set(evidence_ids)):
        raise ValueError("SEO brief contains duplicate evidence_id values")
    canonical = json.dumps(brief, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    run_id = _stable_id("run", canonical)
    mode = _mode(brief["request"])
    write_authorized = mode == "implementation-request" and brief["authorized_action"] == "implementation" and bool(brief["target_urls"]) and brief["rollback_boundary"] is not None
    missing = _missing(brief, mode, write_authorized=write_authorized)
    plan = {"protocol_version":PROTOCOL_VERSION, "run_id":run_id, "brief_id":brief["brief_id"], "request":brief["request"], "work_mode":mode, "claim_status":"evidence-bounded" if brief["evidence"] else "advisory", "write_authorized":write_authorized, "rollback_boundary":brief["rollback_boundary"], "search_surfaces":_surfaces(brief["request"]), "engine_scope":_engines(brief["request"]), "coverage":{"target_count":len(brief["target_urls"]), "evidence_count":len(brief["evidence"]), "evidence_types":sorted({item["evidence_type"] for item in brief["evidence"]})}, "findings":[], "action_plan":_action_plan(mode), "missing_evidence":missing, "guardrails":["Do not invent search volume, difficulty, rankings, traffic, backlinks, crawl, index, competitor, conversion, or citation metrics.", "Keep observed facts, inference, hypotheses, and missing evidence distinct.", "Crawling, indexing, ranking, rich results, traffic, revenue, and AI citations are never guaranteed.", "Audit and planning are read-only; implementation requires explicit authorization, before evidence, tests, and rollback."]}
    validate_artifact("seo-plan", plan)
    ledger = {"protocol_version":PROTOCOL_VERSION, "run_id":run_id, "records":[{"evidence_id":item["evidence_id"], "claim":item["claim"], "source_uri":item["source_uri"], "status":"provided"} for item in brief["evidence"]], "missing_evidence":missing}
    warnings = ["The run is an evidence-bounded plan and does not claim rankings, indexation, traffic, or AI citations.", *missing]
    quality = {"protocol_version":PROTOCOL_VERSION, "run_id":run_id, "passed_checks":["SEO brief contract valid", "URLs and evidence URIs credential-safe", "work mode selected deterministically", "action boundary and evidence gaps explicit", "no unsupported site finding generated"], "warnings":warnings, "failed_checks":[], "status":"passed-with-warnings"}
    validate_artifact("evidence-ledger", ledger); validate_artifact("quality-report", quality)
    now = (clock or (lambda: datetime.now(timezone.utc)))()
    if now.tzinfo is None: now = now.replace(tzinfo=timezone.utc)
    artifacts = ["input/seo-brief.json", "seo-plan.json", "report.md", "evidence-ledger.json", "quality-report.json"]
    manifest = {"protocol_version":PROTOCOL_VERSION, "run_id":run_id, "created_at":now.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"), "generator":{"name":"geo-seo-hub-seo", "version":GENERATOR_VERSION}, "input_artifact":"input/seo-brief.json", "artifacts":artifacts, "status":"completed-with-warnings"}
    validate_artifact("run-manifest", manifest)
    run_path = output_path / run_id
    with ArtifactBus.transaction(output_path, run_id) as bus:
        bus.write_json("input/seo-brief.json", brief, "seo-brief"); bus.write_json("seo-plan.json", plan, "seo-plan"); bus.write_text("report.md", _markdown(plan)); bus.write_json("evidence-ledger.json", ledger, "evidence-ledger"); bus.write_json("quality-report.json", quality, "quality-report"); bus.write_json("run-manifest.json", manifest, "run-manifest"); bus.publish(set(artifacts) | {"run-manifest.json"})
    return {"run_id":run_id, "status":manifest["status"], "output":str(run_path.resolve()), "work_mode":mode, "warning_count":len(warnings)}
