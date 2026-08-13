from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from typing import Any
from urllib.parse import urlsplit, urlunsplit


def _canonical_http_uri(value: str) -> str:
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError as exc:
        raise ValueError(f"invalid citation URI: {value}") from exc
    scheme = parsed.scheme.casefold()
    if scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError(f"invalid citation URI: {value}")
    hostname = parsed.hostname.casefold()
    if ":" in hostname and not hostname.startswith("["):
        hostname = f"[{hostname}]"
    default_port = (scheme == "http" and port == 80) or (scheme == "https" and port == 443)
    netloc = hostname if port is None or default_port else f"{hostname}:{port}"
    path = parsed.path or "/"
    return urlunsplit((scheme, netloc, path, parsed.query, ""))


def validate_observation_bundle(bundle: dict[str, Any]) -> None:
    panel = bundle["panel"]
    queries = panel["queries"]
    query_by_id = {query["query_id"]: query for query in queries}
    if len(query_by_id) != len(queries):
        raise ValueError("query panel contains duplicate query_id")
    observation_ids: set[str] = set()
    slots: set[tuple[str, str, str, int]] = set()
    expected_engines = set(panel["expected_engines"])
    expected_timepoints = set(panel["expected_timepoints"])
    expected_repetitions = panel["expected_repetitions"]
    collection_methods = {observation["collection_method"] for observation in bundle["observations"]}
    if len(collection_methods) > 1:
        raise ValueError("observation bundle cannot mix collection methods")
    for observation in bundle["observations"]:
        observation_id = observation["observation_id"]
        if observation_id in observation_ids:
            raise ValueError(f"duplicate observation_id: {observation_id}")
        observation_ids.add(observation_id)
        slot = (
            observation["engine"],
            observation["timepoint"],
            observation["query_id"],
            observation["repetition"],
        )
        if slot in slots:
            raise ValueError(f"duplicate observation slot: {slot}")
        slots.add(slot)
        query = query_by_id.get(observation["query_id"])
        if query is None or query["query_text"] != observation["query_text"]:
            raise ValueError(f"observation query does not match panel: {observation_id}")
        if observation["engine"] not in expected_engines:
            raise ValueError(f"unexpected observation engine: {observation['engine']}")
        if observation["timepoint"] not in expected_timepoints:
            raise ValueError(f"unexpected observation timepoint: {observation['timepoint']}")
        if observation["repetition"] > expected_repetitions:
            raise ValueError(f"unexpected observation repetition: {observation['repetition']}")
        if observation["panel_version"] != panel["panel_version"]:
            raise ValueError(f"observation panel version mismatch: {observation_id}")
        citation_positions = [citation["position"] for citation in observation["citations"]]
        if len(citation_positions) != len(set(citation_positions)):
            raise ValueError(f"duplicate citation position: {observation_id}")
        for citation in observation["citations"]:
            _canonical_http_uri(citation["uri"])
    for target_uri in bundle["subject"]["target_source_uris"]:
        _canonical_http_uri(target_uri)


def _metric(numerator: float, denominator: int, missing_count: int = 0) -> dict[str, Any]:
    value = numerator / denominator if denominator else 0.0
    return {
        "value": round(value, 6),
        "numerator": round(float(numerator), 6),
        "denominator": denominator,
        "missing_count": missing_count,
    }


def _components(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    aliases = tuple(alias.casefold() for alias in bundle["subject"]["aliases"])
    target_uris = {
        _canonical_http_uri(uri)
        for uri in bundle["subject"]["target_source_uris"]
    }
    result = []
    for observation in sorted(
        bundle["observations"],
        key=lambda item: (
            item["engine"],
            item["timepoint"],
            item["query_id"],
            item["repetition"],
        ),
    ):
        answer = observation["answer_text"].casefold()
        mention = int(any(alias in answer for alias in aliases))
        citations = [
            {**citation, "canonical_uri": _canonical_http_uri(citation["uri"])}
            for citation in observation["citations"]
        ]
        target_citations = [citation for citation in citations if citation["canonical_uri"] in target_uris]
        best_target_position = min((citation["position"] for citation in target_citations), default=None)
        target_position_weight = 1.0 / best_target_position if best_target_position else 0.0
        result.append(
            {
                "observation_id": observation["observation_id"],
                "engine": observation["engine"],
                "timepoint": observation["timepoint"],
                "query_id": observation["query_id"],
                "repetition": observation["repetition"],
                "mention": mention,
                "target_source_included": int(bool(target_citations)),
                "target_citation_count": len(target_citations),
                "citation_count": len(citations),
                "position_weighted_component": round((mention + target_position_weight) / 2.0, 6),
            }
        )
    return result


def _aggregate(
    components: list[dict[str, Any]],
    *,
    panel_query_count: int,
    expected_slots: int,
) -> dict[str, Any]:
    observed = len(components)
    missing = max(0, expected_slots - observed)
    mentioned = sum(item["mention"] for item in components)
    source_included = sum(item["target_source_included"] for item in components)
    target_citations = sum(item["target_citation_count"] for item in components)
    citations = sum(item["citation_count"] for item in components)
    position_weighted = sum(item["position_weighted_component"] for item in components)
    observed_queries = len({item["query_id"] for item in components})
    return {
        "mention_rate": _metric(mentioned, expected_slots, missing),
        "source_inclusion_rate": _metric(source_included, expected_slots, missing),
        "citation_share": _metric(target_citations, citations + missing, missing + sum(item["citation_count"] == 0 for item in components)),
        "position_weighted_visibility": _metric(position_weighted, expected_slots, missing),
        "answer_coverage": _metric(observed_queries, panel_query_count, panel_query_count - observed_queries),
        "observation_coverage": _metric(observed, expected_slots, missing),
        "missing_observation_rate": _metric(missing, expected_slots, missing),
    }


def build_visibility_payload(bundle: dict[str, Any], run_id: str) -> dict[str, Any]:
    validate_observation_bundle(bundle)
    panel = bundle["panel"]
    components = _components(bundle)
    panel_query_count = len(panel["queries"])
    expected_slots = (
        panel_query_count
        * len(panel["expected_engines"])
        * len(panel["expected_timepoints"])
        * panel["expected_repetitions"]
    )
    metrics = _aggregate(components, panel_query_count=panel_query_count, expected_slots=expected_slots)
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for component in components:
        grouped[component["engine"]].append(component)
    engine_expected_slots = panel_query_count * len(panel["expected_timepoints"]) * panel["expected_repetitions"]
    by_engine = {
        engine: _aggregate(
            grouped.get(engine, []),
            panel_query_count=panel_query_count,
            expected_slots=engine_expected_slots,
        )
        for engine in sorted(panel["expected_engines"])
    }
    gaps = []
    if metrics["missing_observation_rate"]["numerator"]:
        gaps.append("missing observations prevent a complete panel comparison")
    if bundle["observations"] and bundle["observations"][0]["collection_method"] == "recorded_fixture":
        gaps.append("recorded fixtures do not prove live engine visibility")
    semantic_payload = {
        "bundle_id": bundle["bundle_id"],
        "panel_version": panel["panel_version"],
        "query_panel": [query["query_text"] for query in panel["queries"]],
        "metrics": metrics,
        "by_engine": by_engine,
        "query_components": components,
        "gaps": gaps,
    }
    semantic_digest = hashlib.sha256(
        json.dumps(semantic_payload, ensure_ascii=False, sort_keys=True, allow_nan=False).encode("utf-8")
    ).hexdigest()
    return {
        "protocol_version": "1.0.0",
        "run_id": run_id,
        "bundle_id": bundle["bundle_id"],
        "panel_version": panel["panel_version"],
        "query_panel": [query["query_text"] for query in panel["queries"]],
        "semantic_digest": semantic_digest,
        "metrics": metrics,
        "by_engine": by_engine,
        "query_components": components,
        "gaps": gaps,
    }
