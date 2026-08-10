from __future__ import annotations

import hashlib
import json
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from .artifact_bus import ArtifactBus
from .research import build_research_context
from .validation import load_bounded_json, validate_artifact
from .version import package_version

PROTOCOL_VERSION = "1.0.0"
GENERATOR_VERSION = package_version()
Clock = Callable[[], datetime]


def _stable_id(prefix: str, *parts: str) -> str:
    canonical = "\x1f".join(parts).encode("utf-8")
    return f"{prefix}-{hashlib.sha256(canonical).hexdigest()[:12]}"


def _normalize_text(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).split())


def _ordered(values: list[str] | None, fallback: str | None = None) -> list[str]:
    unique: dict[str, str] = {}
    for value in values or []:
        cleaned = _normalize_text(value)
        if not cleaned:
            continue
        key = cleaned.casefold()
        current = unique.get(key)
        if current is None or cleaned < current:
            unique[key] = cleaned
    ordered = sorted(unique.values(), key=lambda value: (value.casefold(), value))
    if ordered or fallback is None:
        return ordered
    return [fallback]


def _normalize_brief(brief: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(brief)
    for field in ("brief_id", "subject", "brand", "locale"):
        if field in normalized:
            normalized[field] = _normalize_text(normalized[field])
    for field in ("seed_queries", "audiences", "scenarios", "competitors"):
        if field in normalized:
            normalized[field] = _ordered(normalized[field])
    evidence = []
    for record in brief.get("evidence", []):
        item = {
            "evidence_id": _normalize_text(record["evidence_id"]),
            "claim": _normalize_text(record["claim"]),
            "source_uri": record["source_uri"].strip(),
        }
        if "observed_at" in record:
            item["observed_at"] = record["observed_at"].strip()
        evidence.append(item)
    if "evidence" in normalized:
        normalized["evidence"] = sorted(
            evidence,
            key=lambda item: (item["evidence_id"].casefold(), item["evidence_id"]),
        )
    return normalized


def _question(
    locale: str,
    intent: str,
    seed: str,
    audience: str,
    scenario: str,
) -> str:
    if locale.casefold().startswith("zh"):
        templates = {
            "learn": "{audience}在{scenario}场景下，应该如何理解“{seed}”？",
            "compare": "{audience}在{scenario}场景下比较“{seed}”时，应关注哪些差异？",
            "evaluate": "{audience}在{scenario}场景下评估“{seed}”时，需要哪些可验证证据？",
            "act": "{audience}要在{scenario}场景下推进“{seed}”，下一步应该怎么做？",
        }
    else:
        templates = {
            "learn": "How should {audience} understand {seed} in a {scenario} scenario?",
            "compare": "What differences should {audience} assess when comparing {seed} for {scenario}?",
            "evaluate": "What verifiable evidence should {audience} require when evaluating {seed} for {scenario}?",
            "act": "What should {audience} do next to move forward with {seed} for {scenario}?",
        }
    return templates[intent].format(
        audience=audience,
        scenario=scenario,
        seed=seed,
    )


def _build_query_map(brief: dict[str, Any], run_id: str) -> dict[str, Any]:
    locale = brief.get("locale", "zh-CN")
    is_chinese = locale.casefold().startswith("zh")
    audiences = _ordered(brief.get("audiences"), "通用用户" if is_chinese else "general user")[:3]
    scenarios = _ordered(brief.get("scenarios"), "调研" if is_chinese else "research")[:3]
    seeds = _ordered(brief["seed_queries"])[:20]
    if not seeds:
        raise ValueError("GEO brief must contain at least one non-blank seed query")
    evidence_status = "provided" if brief.get("evidence") else "missing"
    queries: list[dict[str, Any]] = []
    for seed in seeds:
        for audience in audiences:
            for scenario in scenarios:
                for intent in ("learn", "compare", "evaluate", "act"):
                    question = _question(locale, intent, seed, audience, scenario)
                    query_id = _stable_id("qry", intent, seed, audience, scenario, locale)
                    queries.append(
                        {
                            "query_id": query_id,
                            "question": question,
                            "intent": intent,
                            "audience": audience,
                            "scenario": scenario,
                            "parent_query_id": None,
                            "rewrites": {
                                "standalone": question,
                                "retrieval": f"{seed} {audience} {scenario} {intent}",
                                "evidence": f"{seed} evidence source methodology {scenario}",
                            },
                            "evidence_status": evidence_status,
                        }
                    )
    query_ids = [item["query_id"] for item in queries]
    normalized_questions = [_normalize_text(item["question"]).casefold() for item in queries]
    if len(query_ids) != len(set(query_ids)):
        raise ValueError("query generation produced duplicate query IDs")
    if len(normalized_questions) != len(set(normalized_questions)):
        raise ValueError("query generation produced duplicate normalized questions")
    return {"protocol_version": PROTOCOL_VERSION, "run_id": run_id, "queries": queries}


def _build_opportunity_map(query_map: dict[str, Any]) -> dict[str, Any]:
    mapping = {
        "learn": ("article", 70),
        "compare": ("comparison", 85),
        "evaluate": ("faq", 80),
        "act": ("landing-page", 75),
    }
    opportunities = []
    for query in query_map["queries"]:
        asset_type, priority = mapping[query["intent"]]
        opportunities.append(
            {
                "opportunity_id": _stable_id("opp", query["query_id"], asset_type),
                "query_ids": [query["query_id"]],
                "asset_type": asset_type,
                "priority": priority,
                "rationale": f"{query['intent']} intent maps to a focused {asset_type} asset.",
                "evidence_status": query["evidence_status"],
            }
        )
    return {
        "protocol_version": PROTOCOL_VERSION,
        "run_id": query_map["run_id"],
        "opportunities": opportunities,
    }


def _build_evidence_ledger(brief: dict[str, Any], run_id: str) -> dict[str, Any]:
    records = [
        {
            "evidence_id": evidence["evidence_id"],
            "claim": evidence["claim"],
            "source_uri": evidence["source_uri"],
            "status": "provided",
        }
        for evidence in sorted(brief.get("evidence", []), key=lambda item: item["evidence_id"])
    ]
    missing = []
    if not records:
        missing.append("Collect authoritative evidence for subject, claims, and recommendations.")
    if brief.get("competitors"):
        missing.append("Collect like-for-like evidence before making competitor comparisons.")
    return {
        "protocol_version": PROTOCOL_VERSION,
        "run_id": run_id,
        "records": records,
        "missing_evidence": missing,
    }


def discover(
    input_path: Path,
    output_path: Path,
    *,
    clock: Clock | None = None,
) -> dict[str, Any]:
    """Generate one validated discover run and return a compact run summary."""
    brief = load_bounded_json(input_path, max_bytes=1024 * 1024, field="GEO brief")
    validate_artifact("geo-brief", brief)
    brief = _normalize_brief(brief)
    validate_artifact("geo-brief", brief)
    evidence_ids = [item["evidence_id"] for item in brief.get("evidence", [])]
    if len(evidence_ids) != len(set(evidence_ids)):
        raise ValueError("GEO brief contains duplicate evidence_id values")
    canonical = json.dumps(brief, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    run_id = _stable_id("run", canonical)
    now = (clock or (lambda: datetime.now(timezone.utc)))()
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    created_at = now.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

    query_map = _build_query_map(brief, run_id)
    opportunity_map = _build_opportunity_map(query_map)
    evidence_ledger = _build_evidence_ledger(brief, run_id)
    research_context = build_research_context(run_id, "geo-discover")
    warnings = []
    if evidence_ledger["missing_evidence"]:
        warnings.append("missing evidence: review evidence-ledger.json before downstream use")
    quality_report = {
        "protocol_version": PROTOCOL_VERSION,
        "run_id": run_id,
        "passed_checks": [
            "geo brief schema valid",
            "query map generated deterministically",
            "query dimensions normalized and deduplicated",
            "opportunity map preserves query lineage",
            "evidence status recorded",
            "research context is source-resolved and effect-bounded",
        ],
        "warnings": warnings,
        "failed_checks": [],
        "status": "passed-with-warnings" if warnings else "passed",
    }

    artifacts = {
        "evidence-ledger.json": (evidence_ledger, "evidence-ledger"),
        "query-map.json": (query_map, "query-map"),
        "opportunity-map.json": (opportunity_map, "opportunity-map"),
        "quality-report.json": (quality_report, "quality-report"),
        "research-context.json": (research_context, "research-context"),
    }
    for artifact, schema_name in artifacts.values():
        validate_artifact(schema_name, artifact)

    manifest_paths = ["input/geo-brief.json", *artifacts.keys()]
    run_manifest = {
        "protocol_version": PROTOCOL_VERSION,
        "run_id": run_id,
        "created_at": created_at,
        "generator": {"name": "geo-seo-hub-discover", "version": GENERATOR_VERSION},
        "input_artifact": "input/geo-brief.json",
        "artifacts": manifest_paths,
        "status": "completed-with-warnings" if warnings else "completed",
    }
    validate_artifact("run-manifest", run_manifest)

    run_path = output_path / run_id
    with ArtifactBus.transaction(output_path, run_id) as bus:
        bus.write_json("input/geo-brief.json", brief, "geo-brief")
        for relative_path, (artifact, schema_name) in artifacts.items():
            bus.write_json(relative_path, artifact, schema_name)
        bus.write_json("run-manifest.json", run_manifest, "run-manifest")
        bus.publish(set(manifest_paths) | {"run-manifest.json"})
    return {
        "run_id": run_id,
        "status": run_manifest["status"],
        "output": str(run_path.resolve()),
        "query_count": len(query_map["queries"]),
        "warning_count": len(warnings),
    }
