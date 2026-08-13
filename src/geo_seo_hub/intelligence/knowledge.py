from __future__ import annotations

import hashlib
import json
import math
from copy import deepcopy
from typing import Any

from ..validation import validate_artifact


def _digest(payload: Any) -> str:
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _entity_id(entity_type: str, canonical_name: str) -> str:
    identity = f"{entity_type.casefold()}\x1f{canonical_name.casefold()}"
    return f"entity-{hashlib.sha256(identity.encode()).hexdigest()[:16]}"


def _validate_request(request: dict[str, Any]) -> None:
    if not isinstance(request, dict) or set(request) != {"protocol_version", "subject", "query", "sources"}:
        raise ValueError("knowledge request fields are invalid")
    if request.get("protocol_version") != "1.0.0":
        raise ValueError("unsupported knowledge request protocol")
    if not str(request.get("subject", "")).strip():
        raise ValueError("knowledge request requires subject")
    if not isinstance(request["subject"], str):
        raise ValueError("knowledge subject must be a string")
    query = request["query"]
    if not isinstance(query, dict) or set(query) != {"mode", "value"} or query.get("mode") not in {"local", "global"} or not isinstance(query.get("value"), str) or not query["value"].strip():
        raise ValueError("knowledge query fields are invalid")
    if not isinstance(request.get("sources"), list) or not request["sources"]:
        raise ValueError("knowledge request requires approved sources")
    if any(not isinstance(source, dict) for source in request["sources"]):
        raise ValueError("knowledge sources must be objects")
    ids = [source.get("source_id") for source in request["sources"]]
    if any(not value for value in ids) or len(ids) != len(set(ids)):
        raise ValueError("knowledge source IDs must be present and unique")
    for source in request["sources"]:
        if not isinstance(source, dict) or set(source) != {"source_id", "source_uri", "source_hash", "reviewed_at", "entities", "facts", "relations"}:
            raise ValueError("knowledge source fields are invalid")
        for field in ("source_id", "source_uri", "reviewed_at"):
            if not isinstance(source[field], str) or not source[field].strip():
                raise ValueError(f"knowledge source {field} must be non-blank")
        digest = source.get("source_hash")
        if not isinstance(digest, str) or len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
            raise ValueError("knowledge source hashes must be lowercase SHA-256 values")
        if not isinstance(source["entities"], list) or not source["entities"]:
            raise ValueError("knowledge sources require at least one entity")
        if not isinstance(source["facts"], list) or not isinstance(source["relations"], list):
            raise ValueError("knowledge facts and relations must be lists")
        local_ids = []
        for entity in source["entities"]:
            if not isinstance(entity, dict) or set(entity) != {"entity_id", "type", "canonical_name", "aliases", "valid_from"}:
                raise ValueError("knowledge entity fields are invalid")
            if any(not isinstance(entity[field], str) or not entity[field].strip() for field in ("entity_id", "type", "canonical_name", "valid_from")):
                raise ValueError("knowledge entity identity fields must be non-blank")
            aliases = entity["aliases"]
            if not isinstance(aliases, list) or any(not isinstance(alias, str) or not alias.strip() for alias in aliases) or len(aliases) != len(set(aliases)):
                raise ValueError("knowledge entity aliases must be a unique string list")
            local_ids.append(entity["entity_id"])
        if len(local_ids) != len(set(local_ids)):
            raise ValueError("knowledge source-local entity IDs must be unique")
        local_id_set = set(local_ids)
        for fact in source["facts"]:
            if not isinstance(fact, dict) or set(fact) != {"entity_id", "attribute", "value", "valid_from"}:
                raise ValueError("knowledge fact fields are invalid")
            if fact["entity_id"] not in local_id_set or any(not isinstance(fact[field], str) or not fact[field].strip() for field in ("attribute", "value", "valid_from")):
                raise ValueError("knowledge fact values or entity reference are invalid")
        for relation in source["relations"]:
            if not isinstance(relation, dict) or set(relation) != {"subject", "predicate", "object", "confidence", "valid_from"}:
                raise ValueError("knowledge relation fields are invalid")
            if relation["subject"] not in local_id_set or relation["object"] not in local_id_set or any(not isinstance(relation[field], str) or not relation[field].strip() for field in ("predicate", "valid_from")):
                raise ValueError("knowledge relation identity or entity reference is invalid")
            confidence = relation["confidence"]
            if isinstance(confidence, bool) or not isinstance(confidence, (int, float)) or not math.isfinite(float(confidence)) or not 0 <= float(confidence) <= 1:
                raise ValueError("knowledge relation confidence must be between 0 and 1")


def build_knowledge_graph(request: dict[str, Any], existing_graph: dict[str, Any] | None = None) -> dict[str, Any]:
    _validate_request(request)
    incoming_index = {
        source["source_id"]: {
            "source_hash": source["source_hash"],
            "payload_digest": _digest({key: value for key, value in source.items() if key != "source_hash"}),
        }
        for source in request["sources"]
    }
    if existing_graph is not None:
        validate_artifact("knowledge-graph", existing_graph)
        existing_payload = {key: value for key, value in existing_graph.items() if key != "semantic_digest"}
        if existing_graph["semantic_digest"] != _digest(existing_payload):
            raise ValueError("existing knowledge graph semantic digest mismatch")
        existing_index = {
            source["source_id"]: {
                "source_hash": source["source_hash"],
                "payload_digest": source["payload_digest"],
            }
            for source in existing_graph.get("source_index", [])
        }
        if not set(existing_index) <= set(incoming_index):
            raise ValueError("incremental knowledge update requires a full source snapshot containing every existing source")
        for source_id in set(existing_index) & set(incoming_index):
            if (
                existing_index[source_id]["source_hash"] == incoming_index[source_id]["source_hash"]
                and existing_index[source_id]["payload_digest"] != incoming_index[source_id]["payload_digest"]
            ):
                raise ValueError(f"knowledge source payload changed without a new source hash: {source_id}")
        if incoming_index == existing_index and request["subject"] == existing_graph.get("subject"):
            return deepcopy(existing_graph)

    entity_accumulator: dict[tuple[str, str], dict[str, Any]] = {}
    input_to_canonical: dict[tuple[str, str], str] = {}
    for source in request["sources"]:
        for entity in source.get("entities", []):
            identity = (str(entity["type"]).casefold(), str(entity["canonical_name"]).casefold())
            generated_id = _entity_id(entity["type"], entity["canonical_name"])
            input_to_canonical[(source["source_id"], entity["entity_id"])] = generated_id
            current = entity_accumulator.setdefault(
                identity,
                {
                    "entity_id": generated_id,
                    "type": entity["type"],
                    "canonical_name": entity["canonical_name"],
                    "aliases": set(),
                    "source_ids": set(),
                    "valid_from": entity["valid_from"],
                    "reviewed_at": source["reviewed_at"],
                    "facts": {},
                },
            )
            current["aliases"].update(alias for alias in entity.get("aliases", []) if alias != current["canonical_name"])
            current["source_ids"].add(source["source_id"])
            current["valid_from"] = min(current["valid_from"], entity["valid_from"])
            current["reviewed_at"] = max(current["reviewed_at"], source["reviewed_at"])

    by_generated_id = {item["entity_id"]: item for item in entity_accumulator.values()}
    for source in request["sources"]:
        for fact in source.get("facts", []):
            generated_id = input_to_canonical.get((source["source_id"], fact["entity_id"]))
            if generated_id is None:
                raise ValueError(f"fact references unknown entity: {fact['entity_id']}")
            current = by_generated_id[generated_id]
            key = (fact["attribute"], str(fact["value"]), fact["valid_from"])
            fact_item = current["facts"].setdefault(
                key,
                {"attribute": fact["attribute"], "value": str(fact["value"]), "source_ids": set(), "valid_from": fact["valid_from"]},
            )
            fact_item["source_ids"].add(source["source_id"])

    relations_by_key: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for source in request["sources"]:
        for relation in source.get("relations", []):
            subject_id = input_to_canonical.get((source["source_id"], relation["subject"]))
            object_id = input_to_canonical.get((source["source_id"], relation["object"]))
            if subject_id is None or object_id is None:
                raise ValueError("relation references an unknown source-local entity")
            key = (subject_id, relation["predicate"], object_id, relation["valid_from"])
            current = relations_by_key.setdefault(
                key,
                {
                    "relation_id": f"relation-{_digest(key)[:16]}",
                    "subject": subject_id,
                    "predicate": relation["predicate"],
                    "object": object_id,
                    "source_ids": set(),
                    "confidence": 0.0,
                    "valid_from": relation["valid_from"],
                },
            )
            current["source_ids"].add(source["source_id"])
            current["confidence"] = max(current["confidence"], float(relation["confidence"]))

    entities = []
    conflicts = []
    for current in sorted(entity_accumulator.values(), key=lambda item: item["entity_id"]):
        facts = []
        values_by_attribute: dict[str, set[str]] = {}
        for fact in sorted(current["facts"].values(), key=lambda item: (item["attribute"], item["value"], item["valid_from"])):
            fact["source_ids"] = sorted(fact["source_ids"])
            facts.append(fact)
            values_by_attribute.setdefault(fact["attribute"], set()).add(fact["value"])
        for attribute, values in sorted(values_by_attribute.items()):
            if len(values) > 1:
                conflicts.append(
                    {
                        "entity_id": current["entity_id"],
                        "attribute": attribute,
                        "values": sorted(values),
                        "resolution": "preserved-for-review",
                    }
                )
        entities.append(
            {
                "entity_id": current["entity_id"],
                "type": current["type"],
                "canonical_name": current["canonical_name"],
                "aliases": sorted(current["aliases"]),
                "source_ids": sorted(current["source_ids"]),
                "valid_from": current["valid_from"],
                "reviewed_at": current["reviewed_at"],
                "facts": facts,
            }
        )
    relations = []
    for relation in sorted(relations_by_key.values(), key=lambda item: item["relation_id"]):
        relation["source_ids"] = sorted(relation["source_ids"])
        relation["confidence"] = round(relation["confidence"], 6)
        relations.append(relation)

    communities = []
    for entity_type in sorted({entity["type"] for entity in entities}):
        members = sorted(entity["entity_id"] for entity in entities if entity["type"] == entity_type)
        communities.append({"community_id": f"type-{entity_type.casefold().replace(' ', '-')}", "label": entity_type, "entity_ids": members})
    gaps = []
    if conflicts:
        gaps.append("conflicting facts require human review")
    if not relations:
        gaps.append("no approved relations were supplied")
    source_index = [
        {
            **{key: source[key] for key in ("source_id", "source_uri", "source_hash", "reviewed_at")},
            "payload_digest": incoming_index[source["source_id"]]["payload_digest"],
        }
        for source in sorted(request["sources"], key=lambda item: item["source_id"])
    ]
    graph = {
        "protocol_version": "1.0.0",
        "subject": request["subject"],
        "source_index": source_index,
        "entities": entities,
        "relations": relations,
        "communities": communities,
        "conflicts": conflicts,
        "coverage": {
            "source_coverage": round(len(source_index) / len(request["sources"]), 6),
            "sources_indexed": len(source_index),
            "sources_requested": len(request["sources"]),
            "entities": len(entities),
            "relations": len(relations),
        },
        "gaps": gaps,
    }
    graph["semantic_digest"] = _digest(graph)
    validate_artifact("knowledge-graph", graph)
    return graph


def query_knowledge_graph(graph: dict[str, Any], query: dict[str, Any]) -> dict[str, Any]:
    mode = query.get("mode")
    value = str(query.get("value", "")).strip()
    if mode not in {"local", "global"} or not value:
        raise ValueError("knowledge query requires local/global mode and a value")
    if mode == "global":
        return {
            "mode": "global", "query": value, "communities": deepcopy(graph["communities"]),
            "coverage": deepcopy(graph["coverage"]), "conflicts": deepcopy(graph["conflicts"]), "gaps": list(graph["gaps"]),
        }
    needle = value.casefold()
    entities = [
        entity for entity in graph["entities"]
        if needle in entity["canonical_name"].casefold() or any(needle in alias.casefold() for alias in entity["aliases"])
    ]
    ids = {entity["entity_id"] for entity in entities}
    relations = [relation for relation in graph["relations"] if relation["subject"] in ids or relation["object"] in ids]
    neighbor_ids = {relation["subject"] for relation in relations} | {relation["object"] for relation in relations}
    expanded = [entity for entity in graph["entities"] if entity["entity_id"] in neighbor_ids | ids]
    source_ids = sorted({source_id for entity in expanded for source_id in entity["source_ids"]})
    return {"mode": "local", "query": value, "entities": deepcopy(expanded), "relations": deepcopy(relations), "source_ids": source_ids, "gaps": [] if entities else ["no matching entity"]}
