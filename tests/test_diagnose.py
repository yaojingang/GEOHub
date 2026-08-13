import json
import inspect
import os
import socket
from datetime import datetime, timezone
from pathlib import Path

import pytest

import geo_seo_hub.validation as validation_module
from geo_seo_hub.diagnose import (
    FetchResult,
    SourceUnavailable,
    URLPolicyError,
    _BoundHTTPSConnection,
    _default_fetch,
    _load_source_html,
    _validate_public_url,
    analyze_html,
    diagnose,
    validate_diagnosis,
    validate_diagnosis_brief,
    validate_public_url,
)
from geo_seo_hub.validation import validate_artifact

FIXTURES = Path(__file__).parent / "fixtures"


def test_json_ld_rejects_nested_nonstandard_constants_across_multiple_scripts():
    html = """
    <script type="application/ld+json">{"@type":"Article","score":1}</script>
    <script type="application/ld+json">{"@type":"Article","nested":{"score":NaN}}</script>
    <script type="application/ld+json">{"@type":"Article","items":[Infinity]}</script>
    <script type="application/ld+json">{"@type":"Article","score":-Infinity}</script>
    <script type="application/ld+json">{"@type":"Article","nested":{"score":1e9999}}</script>
    <script type="application/ld+json">{"@type":"Article","items":[-1e9999]}</script>
    """
    metrics = analyze_html(html, "https://example.com/page")
    assert metrics["json_ld_count"] == 6
    assert metrics["valid_json_ld_count"] == 1

    invalid_only = analyze_html(
        '<script type="application/ld+json">{"nested":[{"score":1e9999}]}</script>',
        "https://example.com/page",
    )
    assert invalid_only["valid_json_ld_count"] == 0


def _clock():
    return datetime(2026, 8, 8, 12, 0, tzinfo=timezone.utc)


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _public_resolver(host, _port, *, type):
    assert type == socket.SOCK_STREAM
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0))]


def test_page_source_html_writes_complete_valid_run(tmp_path):
    runs_root = tmp_path / "runs"
    result = diagnose(FIXTURES / "diagnosis-page.json", runs_root, clock=_clock)
    output = Path(result["output"])

    assert output.parent == runs_root
    assert output.name.startswith("run-")
    assert result["status"] == "completed-with-warnings"
    assert result["diagnosis_status"] == "completed"
    expected = {
        "input/diagnosis-brief.json",
        "input/sources/source-html-1.html",
        "diagnosis.json",
        "diagnosis-funnel.json",
        "report.md",
        "evidence-ledger.json",
        "query-map.json",
        "opportunity-map.json",
        "quality-report.json",
        "research-context.json",
        "run-manifest.json",
        "run-lineage.json",
    }
    assert {str(path.relative_to(output)) for path in output.rglob("*") if path.is_file()} == expected

    for filename, schema_name in {
        "evidence-ledger.json": "evidence-ledger",
        "query-map.json": "query-map",
        "opportunity-map.json": "opportunity-map",
        "quality-report.json": "quality-report",
        "diagnosis-funnel.json": "diagnosis-funnel",
        "research-context.json": "research-context",
        "run-manifest.json": "run-manifest",
        "run-lineage.json": "run-lineage",
    }.items():
        validate_artifact(schema_name, _load(output / filename))
    manifest = _load(output / "run-manifest.json")
    assert set(manifest["artifacts"]) == expected - {"run-manifest.json"}
    normalized_brief = _load(output / "input" / "diagnosis-brief.json")
    assert normalized_brief["source_html"][0]["path"] == "sources/source-html-1.html"
    assert normalized_brief["source_html"][0]["sha256"]

    diagnosis_artifact = _load(output / "diagnosis.json")
    assert diagnosis_artifact["scores"]["discoverability"] == 100
    assert diagnosis_artifact["source_status"][0]["status"] == "provided"
    assert diagnosis_artifact["source_status"][0]["observations"]["title"] == "Acme Knowledge Guide"
    assert diagnosis_artifact["source_status"][0]["observations"]["valid_json_ld_count"] == 1
    ledger_ids = {record["evidence_id"] for record in _load(output / "evidence-ledger.json")["records"]}
    for finding in diagnosis_artifact["findings"]:
        if finding["source_kind"] != "input_gap":
            assert finding["evidence_id"] in ledger_ids

    funnel = _load(output / "diagnosis-funnel.json")
    assert [stage["stage"] for stage in funnel["stages"]] == [
        "candidate-eligibility",
        "citation-selection",
        "answer-absorption",
    ]
    assert funnel["stages"][0]["status"] == "observed"
    assert funnel["stages"][1]["status"] == "proxy"
    assert funnel["stages"][2]["status"] == "not-observed"
    assert funnel["effect_guarantee"] is False
    assert all(
        evidence_id in ledger_ids
        for stage in funnel["stages"]
        for evidence_id in stage["evidence_ids"]
    )
    assert funnel["source_ecosystem"][0]["role"] == "primary-input"

    research = _load(output / "research-context.json")
    assert research["surface"] == "geo-diagnose"
    assert "diagnosis-scores-are-readiness-proxies" in {
        item["principle_id"] for item in research["principles"]
    }

    first_report = (output / "report.md").read_text(encoding="utf-8")
    second = diagnose(FIXTURES / "diagnosis-page.json", tmp_path / "second-runs", clock=lambda: datetime(2027, 1, 1, tzinfo=timezone.utc))
    assert first_report == (Path(second["output"]) / "report.md").read_text(encoding="utf-8")

    replay = diagnose(output / "input" / "diagnosis-brief.json", tmp_path / "replay-runs", clock=_clock)
    assert replay["run_id"] == result["run_id"]


def test_brand_evidence_only_has_provided_lineage(tmp_path):
    result = diagnose(FIXTURES / "diagnosis-brand.json", tmp_path / "runs", clock=_clock)
    output = Path(result["output"])
    diagnosis_artifact = _load(output / "diagnosis.json")
    assert diagnosis_artifact["scope"] == "brand"
    assert diagnosis_artifact["scores"]["brand_fact_coverage"] == 100
    assert {finding["source_kind"] for finding in diagnosis_artifact["findings"]} == {"provided", "inferred"}
    ledger_id = _load(output / "evidence-ledger.json")["records"][0]["evidence_id"]
    assert ledger_id != "ev-acme-about"
    assert {finding["evidence_id"] for finding in diagnosis_artifact["findings"]} == {ledger_id}
    funnel = _load(output / "diagnosis-funnel.json")
    assert funnel["stages"][0]["status"] == "source-gap"
    assert funnel["stages"][1]["status"] == "proxy"
    assert funnel["stages"][1]["evidence_ids"] == [ledger_id]
    assert funnel["stages"][2]["status"] == "not-observed"
    assert funnel["source_ecosystem"][0]["role"] == "third-party-evidence"


def test_missing_all_sources_is_rejected():
    with pytest.raises(ValueError, match="at least one"):
        validate_diagnosis_brief({"subject": "Acme", "scope": "page"})


@pytest.mark.parametrize(
    ("url", "message"),
    [
        ("http://localhost/page", "localhost"),
        ("http://127.0.0.1/page", "non-public"),
        ("http://169.254.1.2/page", "non-public"),
        ("http://10.0.0.1/page", "non-public"),
        ("http://user:secret@example.com/page", "credentials"),
    ],
)
def test_url_policy_rejects_unsafe_targets(url, message):
    with pytest.raises(URLPolicyError, match=message):
        validate_public_url(url, resolver=_public_resolver)


def test_url_policy_rejects_hostname_if_any_dns_answer_is_nonpublic():
    def mixed_resolver(_host, _port, *, type):
        return [
            (socket.AF_INET, type, 6, "", ("93.184.216.34", 0)),
            (socket.AF_INET, type, 6, "", ("10.0.0.1", 0)),
        ]

    with pytest.raises(URLPolicyError, match="non-public"):
        validate_public_url("https://example.com", resolver=mixed_resolver)


@pytest.mark.parametrize("query", ["token=secret", "sig=value", "sessionid=value", "page=2"])
def test_url_policy_rejects_every_nonempty_query_string(query):
    with pytest.raises(URLPolicyError, match="query string"):
        url = f"https://example.com/page?{query}"
        validate_public_url(url, resolver=_public_resolver)


def test_url_fragment_is_removed_before_fetch_identity():
    assert validate_public_url(
        "https://example.com/page#private-fragment",
        resolver=_public_resolver,
    ) == "https://example.com/page"


def test_injected_fetcher_failure_delivers_source_gap(tmp_path):
    brief = tmp_path / "brief.json"
    brief.write_text(
        json.dumps({"subject": "Unavailable page", "scope": "page", "target_urls": ["https://93.184.216.34/page"]}),
        encoding="utf-8",
    )

    def unavailable(_url):
        raise SourceUnavailable("simulated offline source")

    result = diagnose(brief, tmp_path / "runs", clock=_clock, fetcher=unavailable)
    output = Path(result["output"])
    diagnosis_artifact = _load(output / "diagnosis.json")
    assert result["status"] == "completed-with-warnings"
    assert diagnosis_artifact["status"] == "degraded"
    assert diagnosis_artifact["source_status"][0]["status"] == "source_gap"
    assert "No page observation was inferred" in diagnosis_artifact["limitations"][0]
    assert _load(output / "evidence-ledger.json")["records"] == []


def test_injected_fetcher_happy_path_observes_only_explicit_url(tmp_path):
    brief = tmp_path / "brief.json"
    brief.write_text(json.dumps({"subject": "Public page", "scope": "page", "target_urls": ["https://example.com/page"]}), encoding="utf-8")
    calls = []

    def fetch(url):
        calls.append(url)
        return FetchResult(url, b"<title>Public</title><main><h1>Public</h1><h2>Facts</h2><p>Source method by expert, updated 2026. Evidence text long enough.</p></main>", "text/html")

    result = diagnose(brief, tmp_path / "runs", clock=_clock, fetcher=fetch, resolver=_public_resolver)
    assert calls == ["https://example.com/page"]
    output = Path(result["output"])
    diagnosis_artifact = _load(output / "diagnosis.json")
    status = diagnosis_artifact["source_status"]
    assert status[0]["status"] == "observed"
    normalized_input = output / "input" / "diagnosis-brief.json"
    assert "target_urls" not in _load(normalized_input)
    assert (output / "input" / "sources" / "url-1.html").is_file()

    def no_network(_url):
        raise AssertionError("snapshot replay must not fetch the network")

    replay = diagnose(
        normalized_input,
        tmp_path / "replay-runs",
        clock=lambda: datetime(2027, 1, 1, tzinfo=timezone.utc),
        fetcher=no_network,
        resolver=lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("snapshot replay must not resolve DNS")),
    )
    replay_output = Path(replay["output"])
    assert replay["run_id"] == result["run_id"]
    assert _load(replay_output / "diagnosis.json") == diagnosis_artifact
    assert _load(replay_output / "evidence-ledger.json") == _load(output / "evidence-ledger.json")


def test_non_html_response_degrades_without_observed_findings(tmp_path):
    brief = tmp_path / "brief.json"
    brief.write_text(json.dumps({"subject": "Image", "scope": "page", "target_urls": ["https://example.com/image"]}), encoding="utf-8")

    def image_fetch(url):
        return FetchResult(url, b"\x89PNG\r\n", "image/png")

    result = diagnose(brief, tmp_path / "runs", clock=_clock, fetcher=image_fetch, resolver=_public_resolver)
    output = Path(result["output"])
    diagnosis_artifact = _load(output / "diagnosis.json")
    assert diagnosis_artifact["status"] == "degraded"
    assert diagnosis_artifact["source_status"][0]["status"] == "source_gap"
    assert "unsupported Content-Type" in diagnosis_artifact["source_status"][0]["message"]
    assert {finding["source_kind"] for finding in diagnosis_artifact["findings"]} == {"input_gap"}
    assert _load(output / "evidence-ledger.json")["records"] == []


def test_missing_content_type_binary_degrades_without_parsing(tmp_path):
    brief = tmp_path / "brief.json"
    brief.write_text(json.dumps({"subject": "Unknown media", "scope": "page", "target_urls": ["https://example.com/blob"]}), encoding="utf-8")

    def missing_type_fetch(url):
        return FetchResult(url, b"\x00\x01binary-with-html-like-<title>trap</title>")

    result = diagnose(brief, tmp_path / "runs", clock=_clock, fetcher=missing_type_fetch, resolver=_public_resolver)
    diagnosis_artifact = _load(Path(result["output"]) / "diagnosis.json")
    assert diagnosis_artifact["status"] == "degraded"
    assert diagnosis_artifact["source_status"][0]["status"] == "source_gap"
    assert "missing" in diagnosis_artifact["source_status"][0]["message"]
    assert diagnosis_artifact["source_status"][0]["observations"] is None


def test_dns_time_reduces_per_source_fetch_budget(tmp_path, monkeypatch):
    brief = tmp_path / "brief.json"
    brief.write_text(json.dumps({"subject": "Timed", "scope": "page", "target_urls": ["https://example.com/page"]}), encoding="utf-8")
    now = [0.0]

    def monotonic():
        return now[0]

    def slow_resolver(*args, **kwargs):
        now[0] += 3.0
        return _public_resolver(*args, **kwargs)

    captured = {}

    def fake_default_fetch(url, **kwargs):
        captured.update(kwargs)
        return FetchResult(url, b"<title>Timed</title><h1>Timed</h1><h2>Facts</h2>", "text/html")

    monkeypatch.setattr("geo_seo_hub.diagnose.time.monotonic", monotonic)
    monkeypatch.setattr("geo_seo_hub.diagnose._default_fetch", fake_default_fetch)
    diagnose(brief, tmp_path / "runs", clock=_clock, resolver=slow_resolver)
    assert captured["deadline"] == 8.0
    assert captured["timeout"] == 5.0


def test_dns_rebinding_attempt_degrades_without_connecting(tmp_path):
    brief = tmp_path / "brief.json"
    brief.write_text(json.dumps({"subject": "Rebinding", "scope": "page", "target_urls": ["http://example.com"]}), encoding="utf-8")
    answers = iter(["93.184.216.34", "127.0.0.1"])

    def rebinding_resolver(_host, _port, *, type):
        return [(socket.AF_INET, type, 6, "", (next(answers), 0))]

    result = diagnose(brief, tmp_path / "runs", clock=_clock, resolver=rebinding_resolver)
    diagnosis_artifact = _load(Path(result["output"]) / "diagnosis.json")
    assert diagnosis_artifact["status"] == "degraded"
    assert diagnosis_artifact["source_status"][0]["status"] == "source_gap"


def test_private_redirect_becomes_source_gap_policy_error(monkeypatch):
    class RedirectResponse:
        status = 302

        @staticmethod
        def getheader(name, default=None):
            return "http://127.0.0.1/private" if name == "Location" else default

    class FakeConnection:
        def __init__(self, *_args, **_kwargs):
            pass

        def request(self, *_args, **_kwargs):
            pass

        def getresponse(self):
            return RedirectResponse()

        def close(self):
            pass

    monkeypatch.setattr("geo_seo_hub.diagnose.http.client.HTTPConnection", FakeConnection)
    with pytest.raises(SourceUnavailable, match="redirect target rejected"):
        _default_fetch("http://example.com", resolver=_public_resolver)


def test_http_fetch_pins_the_validated_public_ip(monkeypatch):
    resolver_answers = iter(["93.184.216.34", "127.0.0.1"])
    resolver_calls = []
    connected = []

    def changing_resolver(_host, _port, *, type):
        resolver_calls.append(type)
        return [(socket.AF_INET, type, 6, "", (next(resolver_answers), 0))]

    normalized, addresses = _validate_public_url(
        "http://example.com/page",
        resolver=changing_resolver,
    )

    class Response:
        status = 200

        def __init__(self):
            self.sent = False

        @staticmethod
        def getheader(name, default=None):
            return "text/html" if name == "Content-Type" else default

        def read(self, _size):
            if self.sent:
                return b""
            self.sent = True
            return b"<title>Pinned</title>"

    class Connection:
        sock = None

        def __init__(self, host, *, port, timeout):
            connected.append((host, port, timeout))

        def request(self, *_args, **_kwargs):
            pass

        def getresponse(self):
            return Response()

        def close(self):
            pass

    monkeypatch.setattr("geo_seo_hub.diagnose.http.client.HTTPConnection", Connection)
    result = _default_fetch(
        normalized,
        resolver=changing_resolver,
        initial_addresses=addresses,
    )
    assert result.body == b"<title>Pinned</title>"
    assert connected[0][0] == "93.184.216.34"
    assert len(resolver_calls) == 1


def test_https_binding_preserves_hostname_sni_and_default_cert_context(monkeypatch):
    import ssl

    created_contexts = []
    connected = []

    class Context:
        check_hostname = True
        verify_mode = ssl.CERT_REQUIRED

        def wrap_socket(self, raw_socket, *, server_hostname):
            self.server_hostname = server_hostname
            self.raw_socket = raw_socket
            return object()

    def create_default_context():
        context = Context()
        created_contexts.append(context)
        return context

    raw_socket = object()

    def create_connection(endpoint, timeout, source_address):
        connected.append((endpoint, timeout, source_address))
        return raw_socket

    monkeypatch.setattr("geo_seo_hub.diagnose.ssl.create_default_context", create_default_context)
    monkeypatch.setattr("geo_seo_hub.diagnose.socket.create_connection", create_connection)
    connection = _BoundHTTPSConnection(
        "example.com",
        "93.184.216.34",
        port=443,
        timeout=8,
    )
    connection.connect()
    assert connected[0][0] == ("93.184.216.34", 443)
    assert created_contexts[0].server_hostname == "example.com"
    assert created_contexts[0].raw_socket is raw_socket
    assert created_contexts[0].check_hostname is True
    assert created_contexts[0].verify_mode == ssl.CERT_REQUIRED


def test_file_fixture_cannot_escape_brief_directory(tmp_path):
    outside = tmp_path.parent / f"{tmp_path.name}-outside.html"
    outside.write_text("<title>outside</title>", encoding="utf-8")
    brief = tmp_path / "brief.json"
    brief.write_text(json.dumps({"subject": "Escape", "scope": "page", "source_html": {"path": f"../{outside.name}"}}), encoding="utf-8")
    with pytest.raises(ValueError, match="stay relative"):
        diagnose(brief, tmp_path / "runs", clock=_clock)


def test_file_fixture_rejects_symlink_component(tmp_path):
    real = tmp_path / "real"
    real.mkdir()
    (real / "page.html").write_text("<title>real</title>", encoding="utf-8")
    (tmp_path / "linked").symlink_to(real, target_is_directory=True)
    brief = tmp_path / "brief.json"
    brief.write_text(json.dumps({"subject": "Symlink", "scope": "page", "source_html": {"path": "linked/page.html"}}), encoding="utf-8")
    with pytest.raises(ValueError, match="unsafe"):
        diagnose(brief, tmp_path / "runs", clock=_clock)


def test_source_html_uses_shared_bounded_reader_and_rejects_final_symlink_fifo(tmp_path, monkeypatch):
    source = inspect.getsource(_load_source_html)
    assert "read_bounded_regular_file" in source
    assert "os.open" not in source

    brief = tmp_path / "brief.json"
    brief.write_text("{}", encoding="utf-8")
    page = tmp_path / "page.html"
    page.write_text("<title>page</title>", encoding="utf-8")
    linked = tmp_path / "linked.html"
    linked.symlink_to(page)
    with pytest.raises(ValueError, match="unsafe"):
        _load_source_html({"path": linked.name}, brief, index=0)

    fifo = tmp_path / "page.fifo"
    os.mkfifo(fifo)
    real_open = os.open

    def require_nonblock(path, flags, mode=0o777, *, dir_fd=None):
        if path == fifo.name and not flags & os.O_NONBLOCK:
            raise AssertionError("source_html file open must use O_NONBLOCK")
        return real_open(path, flags, mode, dir_fd=dir_fd)

    monkeypatch.setattr(validation_module.os, "open", require_nonblock)
    with pytest.raises(ValueError, match="regular"):
        _load_source_html({"path": fifo.name}, brief, index=0)


def test_fd_reader_uses_opened_file_when_path_is_replaced(tmp_path, monkeypatch):
    brief = tmp_path / "brief.json"
    brief.write_text("{}", encoding="utf-8")
    page = tmp_path / "page.html"
    replacement = tmp_path / "replacement.html"
    page.write_text("<title>Original</title>", encoding="utf-8")
    replacement.write_text("<title>Replacement</title>", encoding="utf-8")
    real_open = os.open
    replaced = False

    def racing_open(path, flags, mode=0o777, *, dir_fd=None):
        nonlocal replaced
        descriptor = real_open(path, flags, mode, dir_fd=dir_fd)
        if path == "page.html" and not flags & os.O_DIRECTORY and not replaced:
            replacement.replace(page)
            replaced = True
        return descriptor

    monkeypatch.setattr(validation_module.os, "open", racing_open)
    html, _uri, _source_id, _source_type = _load_source_html(
        {"path": "page.html"}, brief, index=0
    )
    assert replaced is True
    assert html == "<title>Original</title>"
    assert page.read_text(encoding="utf-8") == "<title>Replacement</title>"


def test_fd_reader_detects_growth_after_fstat_and_closes_all_fds(tmp_path, monkeypatch):
    brief = tmp_path / "brief.json"
    brief.write_text("{}", encoding="utf-8")
    page = tmp_path / "page.html"
    page.write_bytes(b"1234")
    real_open = os.open
    real_close = os.close
    real_fstat = os.fstat
    opened = []
    closed = []
    grew = False

    def tracked_open(*args, **kwargs):
        descriptor = real_open(*args, **kwargs)
        opened.append(descriptor)
        return descriptor

    def growing_fstat(descriptor):
        nonlocal grew
        result = real_fstat(descriptor)
        if not grew:
            with page.open("ab") as stream:
                stream.write(b"56789")
            grew = True
        return result

    def tracked_close(descriptor):
        closed.append(descriptor)
        return real_close(descriptor)

    monkeypatch.setattr("geo_seo_hub.diagnose.MAX_FETCH_BYTES", 8)
    monkeypatch.setattr(validation_module.os, "open", tracked_open)
    monkeypatch.setattr(validation_module.os, "fstat", growing_fstat)
    monkeypatch.setattr(validation_module.os, "close", tracked_close)
    with pytest.raises(ValueError, match="exceeds 8 bytes"):
        _load_source_html({"path": "page.html"}, brief, index=0)
    assert grew is True
    assert set(opened) <= set(closed)


def test_run_and_evidence_ids_change_with_html_content(tmp_path):
    page = tmp_path / "page.html"
    brief = tmp_path / "brief.json"
    brief.write_text(json.dumps({"subject": "Changing page", "scope": "page", "source_html": {"path": "page.html"}}), encoding="utf-8")
    page.write_text("<title>First</title><h1>First</h1>", encoding="utf-8")
    first = diagnose(brief, tmp_path / "first", clock=_clock)
    page.write_text("<title>Second</title><h1>Second</h1>", encoding="utf-8")
    second = diagnose(brief, tmp_path / "second", clock=_clock)
    assert first["run_id"] != second["run_id"]
    first_ledger = _load(Path(first["output"]) / "evidence-ledger.json")
    second_ledger = _load(Path(second["output"]) / "evidence-ledger.json")
    assert first_ledger["records"][0]["evidence_id"] != second_ledger["records"][0]["evidence_id"]


def test_opportunities_reference_generated_query_map(tmp_path):
    result = diagnose(FIXTURES / "diagnosis-brand.json", tmp_path / "runs", clock=_clock)
    output = Path(result["output"])
    query_ids = {item["query_id"] for item in _load(output / "query-map.json")["queries"]}
    for opportunity in _load(output / "opportunity-map.json")["opportunities"]:
        assert set(opportunity["query_ids"]) <= query_ids


@pytest.mark.parametrize(
    "brief",
    [
        {"subject": " ", "scope": "brand", "evidence": [{"evidence_id": "ev", "claim": "claim", "source_uri": "urn:test"}]},
        {"subject": "Acme", "scope": "brand", "evidence": [{"evidence_id": " ", "claim": "claim", "source_uri": "urn:test"}]},
        {"subject": "Acme", "scope": "brand", "goals": ["  "], "evidence": [{"evidence_id": "ev", "claim": "claim", "source_uri": "urn:test"}]},
    ],
)
def test_blank_input_strings_are_rejected(brief):
    with pytest.raises(ValueError, match="non-blank"):
        validate_diagnosis_brief(brief)


def test_duplicate_evidence_ids_are_rejected():
    record = {"evidence_id": "ev-1", "claim": "claim", "source_uri": "urn:test"}
    with pytest.raises(ValueError, match="duplicate evidence_id"):
        validate_diagnosis_brief({"subject": "Acme", "scope": "brand", "evidence": [record, dict(record)]})


def test_input_limits_reject_too_many_targets_and_large_inline_html():
    with pytest.raises(ValueError, match="at most 5"):
        validate_diagnosis_brief({"subject": "Acme", "scope": "page", "target_urls": [f"https://example.com/{index}" for index in range(6)]})
    with pytest.raises(ValueError, match="source_html.*exceeds"):
        validate_diagnosis_brief({"subject": "Acme", "scope": "page", "source_html": "x" * (2 * 1024 * 1024 + 1)})


def test_evidence_claim_content_controls_normalized_id_and_run_id(tmp_path):
    def write_brief(path, claim):
        path.write_text(json.dumps({"subject": "Acme", "scope": "brand", "evidence": [{"evidence_id": "input-label", "claim": claim, "source_uri": "https://example.com/about"}]}), encoding="utf-8")

    first_brief = tmp_path / "first.json"
    second_brief = tmp_path / "second.json"
    write_brief(first_brief, "Acme offers a product.")
    write_brief(second_brief, "Acme offers a verified service.")
    first = diagnose(first_brief, tmp_path / "first-runs", clock=_clock)
    second = diagnose(second_brief, tmp_path / "second-runs", clock=_clock)
    first_ledger = _load(Path(first["output"]) / "evidence-ledger.json")
    second_ledger = _load(Path(second["output"]) / "evidence-ledger.json")
    assert first["run_id"] != second["run_id"]
    assert first_ledger["records"][0]["evidence_id"] != second_ledger["records"][0]["evidence_id"]
    assert _load(Path(first["output"]) / "input" / "diagnosis-brief.json")["evidence"][0]["evidence_id"] == first_ledger["records"][0]["evidence_id"]


def test_exhausted_total_budget_skips_dns_for_all_remaining_urls(tmp_path, monkeypatch):
    brief = tmp_path / "brief.json"
    brief.write_text(json.dumps({"subject": "Budget", "scope": "site", "target_urls": ["https://example.com/one", "https://example.com/two"]}), encoding="utf-8")
    dns_calls = []

    def resolver(*args, **kwargs):
        dns_calls.append((args, kwargs))
        return _public_resolver(*args, **kwargs)

    monkeypatch.setattr("geo_seo_hub.diagnose.TOTAL_FETCH_SECONDS", 0)
    result = diagnose(brief, tmp_path / "runs", clock=_clock, resolver=resolver)
    diagnosis_artifact = _load(Path(result["output"]) / "diagnosis.json")
    assert dns_calls == []
    assert [source["status"] for source in diagnosis_artifact["source_status"]] == ["source_gap", "source_gap"]


def test_normalized_brief_trims_human_text_and_preserves_list_order(tmp_path):
    html = "  <!doctype html><title> Stable snapshot </title>\n"
    (tmp_path / "page.html").write_text(html, encoding="utf-8")
    brief = tmp_path / "brief.json"
    brief.write_text(
        json.dumps(
            {
                "subject": "  Acme  ",
                "scope": "page",
                "source_html": {
                    "path": "  page.html  ",
                    "source_uri": "  https://example.com/page#section  ",
                    "source_id": "  snapshot-1  ",
                },
                "evidence": [
                    {
                        "evidence_id": "  input-label  ",
                        "claim": "  Maintained by Acme.  ",
                        "source_uri": "  https://example.com/about#team  ",
                    }
                ],
                "locale": "  en-US  ",
                "audience": "  evaluator  ",
                "goals": ["  second goal  ", "  first goal  "],
            }
        ),
        encoding="utf-8",
    )
    result = diagnose(brief, tmp_path / "runs", clock=_clock)
    output = Path(result["output"])
    normalized = _load(output / "input" / "diagnosis-brief.json")
    assert normalized["subject"] == "Acme"
    assert normalized["locale"] == "en-US"
    assert normalized["audience"] == "evaluator"
    assert normalized["goals"] == ["second goal", "first goal"]
    assert normalized["evidence"][0]["claim"] == "Maintained by Acme."
    assert normalized["evidence"][0]["source_uri"] == "https://example.com/about"
    assert normalized["source_html"][0]["path"] == "sources/snapshot-1.html"
    assert normalized["source_html"][0]["source_uri"] == "https://example.com/page"
    assert (output / "input" / "sources" / "snapshot-1.html").read_text(encoding="utf-8") == html


def test_diagnosis_validator_rejects_finding_without_ledger_lineage():
    artifact = {
        "protocol_version": "1.0.0",
        "run_id": "run-test",
        "subject": "Acme",
        "scope": "page",
        "status": "completed",
        "scores": {"structure": 50},
        "findings": [
            {
                "finding_id": "finding-1",
                "category": "structure",
                "severity": "warning",
                "source_kind": "observed",
                "statement": "An observed statement.",
                "evidence_id": "ev-missing",
                "recommendation": "Add structure.",
            }
        ],
        "limitations": [],
        "source_status": [],
    }
    with pytest.raises(ValueError, match="absent from the evidence ledger"):
        validate_diagnosis(artifact, evidence_ids=[])
