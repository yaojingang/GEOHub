from geo_seo_hub.quality.metrics import score_output


def _task():
    return {
        "assertions": {
            "required_json_paths": ["answer", "claims"],
            "required_terms": ["supported"],
            "forbidden_terms": ["fabricated"],
            "allowed_source_ids": ["source-1"],
        }
    }


def test_claim_metrics_reward_only_allowed_citation_support():
    metrics = score_output(
        _task(),
        {
            "answer": "A supported answer.",
            "claims": [
                {"text": "Supported claim", "factual": True, "source_ids": ["source-1"]},
                {"text": "Unsupported claim", "factual": True, "source_ids": []},
            ],
        },
    )

    assert metrics["contract_compliance"] == 1.0
    assert metrics["citation_support"] == 0.5
    assert metrics["fabricated_citations"] == 0
    assert metrics["passed"] is False


def test_unknown_source_and_forbidden_term_fail_the_output():
    metrics = score_output(
        _task(),
        {
            "answer": "A fabricated but supported-sounding answer.",
            "claims": [
                {"text": "Unknown source", "factual": True, "source_ids": ["source-2"]}
            ],
        },
    )

    assert metrics["boundary_safety"] == 0.0
    assert metrics["fabricated_citations"] == 1
    assert metrics["failures"]["fabricated_source_ids"] == ["source-2"]
    assert metrics["passed"] is False
