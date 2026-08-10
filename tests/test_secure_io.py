import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

import geo_seo_hub.validation as validation_module
from geo_seo_hub.content import content
from geo_seo_hub.diagnose import diagnose
from geo_seo_hub.discover import discover
from geo_seo_hub.measure import measure
from geo_seo_hub.validation import read_bounded_regular_file


def _discover_payload():
    return {
        "protocol_version": "1.0.0",
        "brief_id": "secure-io",
        "subject": "Original subject",
        "seed_queries": ["secure query"],
    }


def _diagnose_payload():
    return {
        "subject": "Original subject",
        "scope": "brand",
        "evidence": [
            {
                "evidence_id": "secure-io",
                "claim": "A bounded provided claim.",
                "source_uri": "https://example.invalid/secure-io",
            }
        ],
    }


def _content_payload():
    return {"mode": "title", "topic": "Secure lexical path"}


def _measure_payload():
    return {
        "protocol_version": "1.0.0",
        "measurement_id": "secure-io",
        "subject": "Secure measurement",
        "study_design": {"kind": "observational", "intervention": None, "comparator": None},
        "confidence_level": 0.95,
        "inclusion_criteria": ["Answered fixture"],
        "exclusion_criteria": ["Transport failure"],
        "observations": [
            {
                "trial_id": "secure-trial",
                "query_id": "secure-query",
                "engine": "Fixture",
                "interface": "file",
                "language": "en",
                "geography": "test",
                "collected_at": "2026-08-11T00:00:00Z",
                "model_version": "fixture-1",
                "sample_unit": "query-response",
                "eligible": True,
                "answered": True,
                "cited": False,
                "missing_answer_reason": None,
                "exclusion_reason": None,
                "source_uri": "urn:geo-measure:secure-trial",
            }
        ],
    }


@pytest.mark.parametrize(
    "runner,payload",
    [
        (
            discover,
            {
                **_discover_payload(),
                "evidence": [
                    {
                        "evidence_id": "credential-source",
                        "claim": "A supplied claim.",
                        "source_uri": "https://example.invalid/source?sig=secret",
                    }
                ],
            },
        ),
        (
            diagnose,
            {
                **_diagnose_payload(),
                "evidence": [
                    {
                        "evidence_id": "credential-source",
                        "claim": "A supplied claim.",
                        "source_uri": "urn:geo-diagnose:source?signature=secret",
                    }
                ],
            },
        ),
        (
            content,
            {
                **_content_payload(),
                "evidence": [
                    {
                        "label": "credential-source",
                        "claim": "A supplied claim.",
                        "source_uri": "https://user:secret@example.invalid/source",
                    }
                ],
            },
        ),
        (
            measure,
            {
                **_measure_payload(),
                "observations": [
                    {
                        **_measure_payload()["observations"][0],
                        "source_uri": "urn:geo-measure:source?access_token=secret",
                    }
                ],
            },
        ),
    ],
)
def test_public_artifact_source_uris_reject_credentials(runner, payload, tmp_path):
    brief = tmp_path / "credential-source.json"
    brief.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="credentials"):
        runner(brief, tmp_path / "runs")


def test_content_snapshot_source_uri_is_normalized_before_publication(tmp_path):
    source = tmp_path / "source.md"
    source.write_text("A bounded source document.", encoding="utf-8")
    payload = {
        **_content_payload(),
        "source_content": {
            "path": "source.md",
            "source_uri": "  https://example.invalid/source#private-fragment  ",
        },
    }
    brief = tmp_path / "brief.json"
    brief.write_text(json.dumps(payload), encoding="utf-8")

    result = content(brief, tmp_path / "runs")
    normalized = json.loads(
        (Path(result["output"]) / "input" / "content-brief.json").read_text(encoding="utf-8")
    )

    assert normalized["source_content"]["source_uri"] == "https://example.invalid/source"


@pytest.mark.parametrize(
    "runner,payload",
    [
        (discover, _discover_payload()),
        (diagnose, _diagnose_payload()),
        (content, _content_payload()),
        (measure, _measure_payload()),
    ],
)
def test_brief_reader_rejects_final_and_parent_symlinks(runner, payload, tmp_path):
    real_parent = tmp_path / "real"
    real_parent.mkdir()
    real_brief = real_parent / "brief.json"
    real_brief.write_text(json.dumps(payload), encoding="utf-8")
    final_link = tmp_path / "brief-link.json"
    final_link.symlink_to(real_brief)
    parent_link = tmp_path / "parent-link"
    parent_link.symlink_to(real_parent, target_is_directory=True)
    for unsafe in (final_link, parent_link / "brief.json"):
        with pytest.raises(ValueError, match="unsafe|regular"):
            runner(unsafe, tmp_path / f"runs-{unsafe.parent.name}")


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS trusted /var alias contract")
@pytest.mark.parametrize(
    "runner,payload",
    [
        (discover, _discover_payload()),
        (diagnose, _diagnose_payload()),
        (content, _content_payload()),
        (measure, _measure_payload()),
    ],
)
def test_macos_lexical_var_alias_accepts_active_entry_briefs(runner, payload):
    with tempfile.TemporaryDirectory(prefix="geo-seo-hub-lexical-") as raw:
        assert raw.startswith("/var/folders/")
        root = Path(raw)
        brief = root / "brief.json"
        brief.write_text(json.dumps(payload), encoding="utf-8")
        result = runner(brief, root / "runs")
        assert result["status"].startswith("completed")


@pytest.mark.parametrize(
    "runner,raw",
    [
        (
            discover,
            '{"protocol_version":"1.0.0","brief_id":"strict","subject":"Strict","seed_queries":[NaN]}',
        ),
        (
            diagnose,
            '{"subject":"Strict","scope":"brand","evidence":[{"evidence_id":"ev","claim":Infinity,"source_uri":"urn:test"}]}',
        ),
        (content, '{"mode":"title","topic":{"nested":-Infinity}}'),
        (measure, '{"protocol_version":"1.0.0","measurement_id":"strict","subject":"Strict","study_design":{"kind":"observational","intervention":null,"comparator":null},"confidence_level":NaN,"inclusion_criteria":["x"],"exclusion_criteria":["y"],"observations":[]}'),
    ],
)
def test_all_brief_entrypoints_reject_nonstandard_json_constants(runner, raw, tmp_path):
    brief = tmp_path / "brief.json"
    brief.write_text(raw, encoding="utf-8")
    with pytest.raises(ValueError, match="non-standard JSON constant"):
        runner(brief, tmp_path / "runs")


@pytest.mark.parametrize("literal", ("1e9999", "-1e9999"))
@pytest.mark.parametrize(
    "runner,raw_template",
    [
        (
            discover,
            '{{"protocol_version":"1.0.0","brief_id":"strict","subject":{{"nested":{literal}}},"seed_queries":["query"]}}',
        ),
        (
            diagnose,
            '{{"subject":"Strict","scope":"brand","evidence":[{{"evidence_id":"ev","claim":{{"nested":{literal}}},"source_uri":"urn:test"}}]}}',
        ),
        (content, '{{"mode":"title","topic":{{"nested":[{literal}]}}}}'),
        (measure, '{{"protocol_version":"1.0.0","measurement_id":"strict","subject":"Strict","study_design":{{"kind":"observational","intervention":null,"comparator":null}},"confidence_level":{literal},"inclusion_criteria":["x"],"exclusion_criteria":["y"],"observations":[]}}'),
    ],
)
def test_all_brief_entrypoints_reject_nested_numeric_overflow(
    runner,
    raw_template,
    literal,
    tmp_path,
):
    brief = tmp_path / "brief.json"
    brief.write_text(raw_template.format(literal=literal), encoding="utf-8")
    runs = tmp_path / "runs"
    with pytest.raises(ValueError, match="non-finite JSON number"):
        runner(brief, runs)
    assert not runs.exists()


def test_bounded_reader_rejects_fifo_without_blocking(tmp_path):
    fifo = tmp_path / "brief.fifo"
    os.mkfifo(fifo)
    with pytest.raises(ValueError, match="regular"):
        read_bounded_regular_file(fifo, max_bytes=128, field="brief")


def test_bounded_reader_uses_open_descriptor_when_path_is_replaced(tmp_path, monkeypatch):
    brief = tmp_path / "brief.json"
    brief.write_bytes(b"original")
    replacement = tmp_path / "replacement.json"
    replacement.write_bytes(b"replacement")
    real_open = os.open
    replaced = False
    observed_flags = []

    def racing_open(path, flags, mode=0o777, *, dir_fd=None):
        nonlocal replaced
        observed_flags.append(flags)
        descriptor = real_open(path, flags, mode, dir_fd=dir_fd)
        if not replaced and dir_fd is not None and path == "brief.json":
            os.replace(replacement, brief)
            replaced = True
        return descriptor

    monkeypatch.setattr(validation_module.os, "open", racing_open)
    assert read_bounded_regular_file(brief, max_bytes=128, field="brief") == b"original"
    required = os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC
    assert observed_flags and all(flags & required == required for flags in observed_flags)


def test_bounded_reader_rejects_growth_after_fstat(tmp_path, monkeypatch):
    brief = tmp_path / "brief.json"
    brief.write_bytes(b"0123456789abcdef")
    real_read = os.read
    grew = False

    def growing_read(file_descriptor, count):
        nonlocal grew
        chunk = real_read(file_descriptor, count)
        if chunk and not grew:
            with brief.open("ab") as stream:
                stream.write(b"x" * 64)
            grew = True
        return chunk

    monkeypatch.setattr(validation_module.os, "read", growing_read)
    with pytest.raises(ValueError, match="exceeds"):
        read_bounded_regular_file(brief, max_bytes=32, field="brief")
