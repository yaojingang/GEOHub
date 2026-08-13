from __future__ import annotations

from typing import Any


def _get_path(value: Any, dotted_path: str) -> Any:
    current = value
    for part in dotted_path.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return None
    return current


def score_output(task: dict[str, Any], output: dict[str, Any]) -> dict[str, Any]:
    """Score one output against task-owned, implementation-independent assertions."""
    assertions = task["assertions"]
    required_paths = assertions.get("required_json_paths", [])
    required_terms = assertions.get("required_terms", [])
    forbidden_terms = assertions.get("forbidden_terms", [])
    serialized = str(output).casefold()

    path_checks = {path: _get_path(output, path) is not None for path in required_paths}
    term_checks = {term: term.casefold() in serialized for term in required_terms}
    forbidden_checks = {term: term.casefold() not in serialized for term in forbidden_terms}
    checks = [*path_checks.values(), *term_checks.values(), *forbidden_checks.values()]
    contract_compliance = 1.0 if checks and all(checks) else 0.0

    allowed_sources = set(assertions.get("allowed_source_ids", []))
    claims = output.get("claims", []) if isinstance(output.get("claims", []), list) else []
    factual_claims = [claim for claim in claims if isinstance(claim, dict) and claim.get("factual", True)]
    supported = 0
    fabricated: set[str] = set()
    for claim in factual_claims:
        source_ids = claim.get("source_ids", [])
        valid_ids = [source_id for source_id in source_ids if source_id in allowed_sources]
        fabricated.update(source_id for source_id in source_ids if source_id not in allowed_sources)
        if valid_ids:
            supported += 1
    citation_support = supported / len(factual_claims) if factual_claims else 1.0

    return {
        "passed": contract_compliance == 1.0 and citation_support >= 0.95 and not fabricated,
        "contract_compliance": contract_compliance,
        "claim_faithfulness": citation_support,
        "citation_support": citation_support,
        "answer_relevance": sum(term_checks.values()) / len(term_checks) if term_checks else 1.0,
        "boundary_safety": 1.0 if all(forbidden_checks.values()) else 0.0,
        "fabricated_citations": len(fabricated),
        "failures": {
            "missing_paths": sorted(path for path, passed in path_checks.items() if not passed),
            "missing_terms": sorted(term for term, passed in term_checks.items() if not passed),
            "forbidden_terms": sorted(term for term, passed in forbidden_checks.items() if not passed),
            "fabricated_source_ids": sorted(fabricated),
        },
    }
