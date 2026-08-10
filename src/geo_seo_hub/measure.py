from __future__ import annotations

import html
import hashlib
import json
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import NormalDist
from typing import Any, Callable

from .artifact_bus import ArtifactBus
from .research import build_research_context
from .validation import load_bounded_json, normalize_artifact_uri, validate_artifact
from .version import package_version

PROTOCOL_VERSION = "1.0.0"
GENERATOR_VERSION = package_version()
Clock = Callable[[], datetime]


def _stable_id(prefix: str, *parts: str) -> str:
    canonical = "\x1f".join(parts).encode("utf-8")
    return f"{prefix}-{hashlib.sha256(canonical).hexdigest()[:12]}"


def _normalize_text(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).split())


def _markdown_text(value: str) -> str:
    escaped = html.escape(value, quote=False)
    return re.sub(r"([\\`*{}\[\]()#+\-.!_>~|=])", r"\\\1", escaped)


def _normalize_brief(brief: dict[str, Any]) -> dict[str, Any]:
    normalized = {
        "protocol_version": brief["protocol_version"],
        "measurement_id": _normalize_text(brief["measurement_id"]),
        "subject": _normalize_text(brief["subject"]),
        "study_design": {
            "kind": brief["study_design"]["kind"],
            "intervention": _normalize_text(brief["study_design"]["intervention"])
            if brief["study_design"]["intervention"] is not None
            else None,
            "comparator": _normalize_text(brief["study_design"]["comparator"])
            if brief["study_design"]["comparator"] is not None
            else None,
        },
        "confidence_level": brief["confidence_level"],
        "inclusion_criteria": sorted(
            {_normalize_text(item) for item in brief["inclusion_criteria"]},
            key=lambda value: (value.casefold(), value),
        ),
        "exclusion_criteria": sorted(
            {_normalize_text(item) for item in brief["exclusion_criteria"]},
            key=lambda value: (value.casefold(), value),
        ),
        "observations": [],
    }
    text_fields = (
        "trial_id",
        "query_id",
        "engine",
        "interface",
        "language",
        "geography",
        "model_version",
        "sample_unit",
    )
    nullable_text_fields = ("missing_answer_reason", "exclusion_reason")
    for source in brief["observations"]:
        observation = {field: _normalize_text(source[field]) for field in text_fields}
        observation.update(
            {
                "collected_at": datetime.fromisoformat(
                    source["collected_at"].strip().replace("Z", "+00:00")
                )
                .astimezone(timezone.utc)
                .isoformat(timespec="microseconds")
                .replace("+00:00", "Z"),
                "eligible": source["eligible"],
                "answered": source["answered"],
                "cited": source["cited"],
                "source_uri": normalize_artifact_uri(
                    source["source_uri"], field="measurement source URI"
                ),
            }
        )
        for field in nullable_text_fields:
            observation[field] = _normalize_text(source[field]) if source[field] is not None else None
        normalized["observations"].append(observation)
    normalized["observations"].sort(
        key=lambda item: (item["trial_id"].casefold(), item["trial_id"])
    )
    return normalized


def _rate(numerator: int, denominator: int, confidence_level: float) -> dict[str, Any]:
    if denominator == 0:
        return {
            "numerator": numerator,
            "denominator": denominator,
            "estimate": None,
            "interval_lower": None,
            "interval_upper": None,
            "interval_method": "not-computable",
        }
    estimate = numerator / denominator
    z = NormalDist().inv_cdf(0.5 + confidence_level / 2)
    z_squared = z * z
    denominator_adjusted = 1 + z_squared / denominator
    center = (estimate + z_squared / (2 * denominator)) / denominator_adjusted
    margin = (
        z
        * ((estimate * (1 - estimate) / denominator + z_squared / (4 * denominator * denominator)) ** 0.5)
        / denominator_adjusted
    )
    return {
        "numerator": numerator,
        "denominator": denominator,
        "estimate": round(estimate, 10),
        "interval_lower": round(max(0.0, center - margin), 10),
        "interval_upper": round(min(1.0, center + margin), 10),
        "interval_method": "wilson-score",
    }


def _metrics(observations: list[dict[str, Any]], confidence_level: float) -> dict[str, Any]:
    answered = sum(item["answered"] for item in observations)
    cited = sum(item["cited"] is True for item in observations)
    return {
        "answer_rate": _rate(answered, len(observations), confidence_level),
        "citation_rate": _rate(cited, len(observations), confidence_level),
        "conditional_citation_rate": _rate(cited, answered, confidence_level),
    }


def _measurement_report(brief: dict[str, Any], run_id: str) -> dict[str, Any]:
    observations = brief["observations"]
    eligible = [item for item in observations if item["eligible"]]
    if not eligible:
        raise ValueError("measurement brief must contain at least one eligible trial")
    answered_count = sum(item["answered"] for item in eligible)
    missing = [item for item in eligible if not item["answered"]]
    excluded = [item for item in observations if not item["eligible"]]
    dimensions = {
        "engines": sorted({item["engine"] for item in observations}, key=str.casefold),
        "interfaces": sorted({item["interface"] for item in observations}, key=str.casefold),
        "languages": sorted({item["language"] for item in observations}, key=str.casefold),
        "geographies": sorted({item["geography"] for item in observations}, key=str.casefold),
        "model_versions": sorted({item["model_version"] for item in observations}, key=str.casefold),
        "sample_units": sorted({item["sample_unit"] for item in observations}, key=str.casefold),
        "collected_from": min(item["collected_at"] for item in observations),
        "collected_to": max(item["collected_at"] for item in observations),
    }
    group_fields = ("engine", "interface", "language", "geography", "model_version", "sample_unit")
    groups: dict[tuple[str, ...], list[dict[str, Any]]] = defaultdict(list)
    for item in eligible:
        groups[tuple(item[field] for field in group_fields)].append(item)
    strata = []
    for key in sorted(groups, key=lambda value: tuple(item.casefold() for item in value)):
        items = groups[key]
        strata.append(
            {
                **dict(zip(group_fields, key, strict=True)),
                "trial_count": len(items),
                "answered_count": sum(item["answered"] for item in items),
                "missing_answer_count": sum(not item["answered"] for item in items),
                "metrics": _metrics(items, brief["confidence_level"]),
            }
        )
    limitations = [
        "All rates describe only the declared engines, interfaces, languages, geographies, model versions, sample units, and collection window.",
        "The report does not guarantee ranking, citation, traffic, revenue, or future platform behavior.",
        "Missing eligible answers remain in the unconditional answer and citation denominators.",
    ]
    if brief["study_design"]["kind"] != "observational":
        limitations.append(
            "The declared intervention and comparator are preserved, but this release does not estimate a causal effect."
        )
    if len(eligible) < 2:
        limitations.append(
            "Only one eligible trial was supplied; repeat observations before interpreting the result as a distribution."
        )
    report = {
        "protocol_version": PROTOCOL_VERSION,
        "run_id": run_id,
        "measurement_id": brief["measurement_id"],
        "subject": brief["subject"],
        "study_design": brief["study_design"],
        "confidence_level": brief["confidence_level"],
        "measurement_scope": dimensions,
        "effect_guarantee": False,
        "causal_status": "descriptive",
        "trial_count": len(observations),
        "eligible_trial_count": len(eligible),
        "answered_count": answered_count,
        "missing_answer_count": len(missing),
        "excluded_count": len(excluded),
        "missing_answer_reasons": dict(sorted(Counter(item["missing_answer_reason"] for item in missing).items())),
        "exclusion_reasons": dict(sorted(Counter(item["exclusion_reason"] for item in excluded).items())),
        "inclusion_criteria": brief["inclusion_criteria"],
        "exclusion_criteria": brief["exclusion_criteria"],
        "metrics": _metrics(eligible, brief["confidence_level"]),
        "platform_strata": strata,
        "data_sources": sorted({item["source_uri"] for item in observations}),
        "limitations": limitations,
    }
    validate_artifact("measurement-report", report)
    return report


def _evidence_ledger(brief: dict[str, Any], run_id: str) -> dict[str, Any]:
    records = []
    for item in brief["observations"]:
        outcome = "excluded"
        if item["eligible"]:
            outcome = "answered-and-cited" if item["cited"] is True else "answered-without-citation" if item["answered"] else "missing-answer"
        records.append(
            {
                "evidence_id": _stable_id("ev", item["trial_id"], item["source_uri"], outcome),
                "claim": f"Measurement trial {item['trial_id']} recorded outcome {outcome}.",
                "source_uri": item["source_uri"],
                "status": "provided",
            }
        )
    return {
        "protocol_version": PROTOCOL_VERSION,
        "run_id": run_id,
        "records": records,
        "missing_evidence": [],
    }


def _markdown(report: dict[str, Any]) -> str:
    citation = report["metrics"]["citation_rate"]
    lines = [
        f"# Measurement report: {_markdown_text(report['subject'])}",
        "",
        "## Scope",
        "",
        f"- Trials: {report['trial_count']}",
        f"- Eligible: {report['eligible_trial_count']}",
        f"- Answered: {report['answered_count']}",
        f"- Missing eligible answers: {report['missing_answer_count']}",
        f"- Excluded: {report['excluded_count']}",
        f"- Confidence level: {report['confidence_level']}",
        "",
        "## Citation rate",
        "",
        f"- Numerator / denominator: {citation['numerator']} / {citation['denominator']}",
        f"- Estimate: {citation['estimate']}",
        f"- Interval: [{citation['interval_lower']}, {citation['interval_upper']}] ({citation['interval_method']})",
        "",
        "## Interpretation boundary",
        "",
        *[f"- {item}" for item in report["limitations"]],
        "",
    ]
    return "\n".join(lines)


def measure(
    input_path: Path,
    output_path: Path,
    *,
    clock: Clock | None = None,
) -> dict[str, Any]:
    brief = load_bounded_json(input_path, max_bytes=5 * 1024 * 1024, field="measurement brief")
    validate_artifact("measurement-brief", brief)
    brief = _normalize_brief(brief)
    validate_artifact("measurement-brief", brief)
    trial_ids = [item["trial_id"] for item in brief["observations"]]
    if len(trial_ids) != len(set(trial_ids)):
        raise ValueError("measurement brief contains duplicate trial_id values")

    canonical = json.dumps(brief, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    run_id = _stable_id("run", canonical)
    report = _measurement_report(brief, run_id)
    ledger = _evidence_ledger(brief, run_id)
    research_context = build_research_context(run_id, "geo-measure")
    missing_count = report["missing_answer_count"]
    warnings = ["Measurement output is descriptive and does not estimate or guarantee a causal effect."]
    if missing_count:
        warnings.append(f"{missing_count} eligible trial(s) have missing answers and remain in unconditional denominators.")
    if report["eligible_trial_count"] < 2:
        warnings.append("Only one eligible trial was supplied; repeated observations are required to characterize a distribution.")
    quality = {
        "protocol_version": PROTOCOL_VERSION,
        "run_id": run_id,
        "passed_checks": [
            "measurement brief contract valid",
            "trial identifiers unique",
            "eligible and missing-answer denominators preserved",
            "Wilson intervals computed from declared observations",
            "platform scope and observation sources retained",
            "research context is source-resolved and effect-bounded",
        ],
        "warnings": warnings,
        "failed_checks": [],
        "status": "passed-with-warnings",
    }
    validate_artifact("evidence-ledger", ledger)
    validate_artifact("research-context", research_context)
    validate_artifact("quality-report", quality)

    now = (clock or (lambda: datetime.now(timezone.utc)))()
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    created_at = now.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    manifest_paths = [
        "input/measurement-brief.json",
        "measurement-report.json",
        "report.md",
        "evidence-ledger.json",
        "research-context.json",
        "quality-report.json",
    ]
    manifest = {
        "protocol_version": PROTOCOL_VERSION,
        "run_id": run_id,
        "created_at": created_at,
        "generator": {"name": "geo-seo-hub-measure", "version": GENERATOR_VERSION},
        "input_artifact": "input/measurement-brief.json",
        "artifacts": manifest_paths,
        "status": "completed-with-warnings",
    }
    validate_artifact("run-manifest", manifest)

    run_path = output_path / run_id
    with ArtifactBus.transaction(output_path, run_id) as bus:
        bus.write_json("input/measurement-brief.json", brief, "measurement-brief")
        bus.write_json("measurement-report.json", report, "measurement-report")
        bus.write_text("report.md", _markdown(report))
        bus.write_json("evidence-ledger.json", ledger, "evidence-ledger")
        bus.write_json("research-context.json", research_context, "research-context")
        bus.write_json("quality-report.json", quality, "quality-report")
        bus.write_json("run-manifest.json", manifest, "run-manifest")
        bus.publish(set(manifest_paths) | {"run-manifest.json"})
    return {
        "run_id": run_id,
        "status": manifest["status"],
        "output": str(run_path.resolve()),
        "trial_count": report["trial_count"],
        "eligible_trial_count": report["eligible_trial_count"],
        "warning_count": len(warnings),
    }
