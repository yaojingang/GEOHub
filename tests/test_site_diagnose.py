from __future__ import annotations

import json
import re
import socket
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

import pytest

import geo_seo_hub.site_diagnose as site_module
from geo_seo_hub.diagnose import FetchResult, SourceUnavailable, URLPolicyError
from geo_seo_hub.site_diagnose import (
    DIMENSION_WEIGHTS,
    MAX_PAGES,
    USER_AGENT,
    _fetch_resource,
    _normalize_candidate,
    _parse_sitemap,
    site_diagnose,
)
from geo_seo_hub.site_report import CHARTS, CHART_CONTRACTS, COPY


FIXTURE = Path(__file__).parent / "fixtures" / "site-diagnose-demo"


def _resolver(host: str, port: int, *_args, **_kwargs):
    return [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("93.184.216.34", port))]


def _private_resolver(host: str, port: int, *_args, **_kwargs):
    return [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("127.0.0.1", port))]


def _fetcher(url: str) -> FetchResult:
    manifest = json.loads((FIXTURE / "manifest.json").read_text(encoding="utf-8"))
    parsed = urlsplit(url)
    if parsed.netloc != "demo.geohub.invalid":
        raise SourceUnavailable("off-host fixture URL")
    if parsed.path == "/robots.txt":
        relative, media_type = "robots.txt", "text/plain; charset=utf-8"
    elif parsed.path == "/sitemap.xml":
        relative, media_type = "sitemap.xml", "application/xml; charset=utf-8"
    else:
        relative = manifest["pages"].get(parsed.path)
        if relative is None:
            raise SourceUnavailable("missing fixture URL")
        media_type = "text/html; charset=utf-8"
    return FetchResult(url, (FIXTURE / relative).read_bytes(), media_type)


def _run(tmp_path: Path, *, max_pages: int = 10):
    return site_diagnose(
        "https://demo.geohub.invalid/",
        tmp_path,
        max_pages=max_pages,
        render_mode="http",
        clock=lambda: datetime(2026, 8, 25, 8, 0, tzinfo=timezone.utc),
        fetcher=_fetcher,
        resolver=_resolver,
        demo_fixture=True,
    )


def test_demo_site_selects_ten_unique_types_and_publishes_contract(tmp_path):
    result = _run(tmp_path)
    run = Path(result["run_directory"])
    diagnosis = json.loads((run / "site-diagnosis.json").read_text(encoding="utf-8"))
    sampling = json.loads((run / "sampling-plan.json").read_text(encoding="utf-8"))
    assert result["representative_pages"] == MAX_PAGES
    assert len({page["page_type"] for page in diagnosis["pages"]}) == MAX_PAGES
    assert sampling["selected_count"] == MAX_PAGES
    assert sum(DIMENSION_WEIGHTS.values()) == 100
    expected = {
        "crawl-manifest.json", "sampling-plan.json", "site-diagnosis.json",
        "evidence-ledger.json", "remediation-backlog.json", "report.html",
        "quality-report.json", "run-lineage.json", "run-manifest.json",
    }
    assert expected.issubset({path.name for path in run.iterdir()})
    assert len(list((run / "pages").glob("*.json"))) == MAX_PAGES


def test_scores_reconstruct_from_checks_and_dimension_weights(tmp_path):
    run = Path(_run(tmp_path)["run_directory"])
    diagnosis = json.loads((run / "site-diagnosis.json").read_text(encoding="utf-8"))
    assert sum(diagnosis["dimension_weights"].values()) == 100
    for page in diagnosis["pages"]:
        assert all(
            check["weight"] == diagnosis["dimension_weights"][check["dimension"]]
            for check in page["checks"]
        )
        for dimension, value in page["dimensions"].items():
            check_scores = [
                check["score"] for check in page["checks"]
                if check["dimension"] == dimension and check["status"] in {"pass", "fail"}
            ]
            assert value == round(sum(check_scores) / len(check_scores))
            assert all(check["evidence_ids"] for check in page["checks"] if check["status"] in {"pass", "fail"})
        reconstructed = round(sum(page["dimensions"][key] * weight for key, weight in DIMENSION_WEIGHTS.items()) / 100)
        assert page["score"] == reconstructed


def test_report_is_offline_escaped_responsive_and_printable(tmp_path):
    report = Path(_run(tmp_path)["report"]).read_text(encoding="utf-8")
    assert "GEOHub 演示固件" in report
    assert "cdn.jsdelivr" not in report and "unpkg.com" not in report
    assert "https://demo.geohub.invalid/" in report
    assert "/" + "Users/" not in report and "C:\\" + "Users\\" not in report
    assert "@media (max-width: 1023px)" in report
    assert "@media (max-width: 380px)" in report
    assert "@media print" in report
    assert "<noscript>" in report
    assert report.count("data-chart=\"") == 23
    assert report.count("data-source-fields=\"") == 23
    assert report.count('<section class="module') == 10
    assert 'data-report-format-version="2"' in report
    assert "Content-Security-Policy" in report and "connect-src 'none'" in report
    assert "decal: { show: false }" in report
    assert "decal: { show: true }" not in report
    assert 'type: "sunburst"' not in report
    assert "symbol: action.severity" not in report
    assert 'symbol: "circle", data: priorityPoints' in report
    assert "short(action.title, 12)" not in report
    assert 'stack: "severity"' in report
    assert "wrapAxisLabel" in report
    report_css = (Path(__file__).parents[1] / "skills/geo-site-diagnose/assets/report.css").read_text(encoding="utf-8")
    assert "linear-gradient" not in report_css and "box-shadow" not in report_css
    for selector in (
        ".report-head",
        ".metric-strip",
        ".module",
        ".module-verdict",
        ".chart-insight",
        ".module-notes",
        ".page-list",
        ".page-audit",
        ".issue-list li",
    ):
        match = re.search(rf"{re.escape(selector)}\s*\{{([^}}]*)\}}", report_css)
        assert match is not None
        assert "border-top" not in match.group(1) and "border-bottom" not in match.group(1)
    assert "border-bottom" in re.search(r"\.report-nav\s*\{([^}]*)\}", report_css).group(1)
    assert "border:" in re.search(r"\.chart-panel\s*\{([^}]*)\}", report_css).group(1)
    assert "background: #ffffff" in report
    assert 'class="nav-links"' in report and 'class="nav-mobile"' in report
    assert "原始正文摘录" in report


def test_report_chart_source_uses_clear_solid_visual_encodings():
    report_js = (Path(__file__).parents[1] / "skills/geo-site-diagnose/assets/report.js").read_text(encoding="utf-8")
    assert "decal: { show: false }" in report_js
    assert 'type: "sunburst"' not in report_js
    assert "symbol: action.severity" not in report_js
    assert 'symbol: "circle", data: priorityPoints' in report_js
    assert "const pageTypeData" in report_js
    assert "const linkMatrix" in report_js
    assert 'stack: "severity"' in report_js
    assert 'type: "funnel"' not in report_js
    assert "const funnelStages" in report_js
    assert 'barGap: "-100%"' in report_js


def test_module_heading_and_verdict_share_one_left_edge():
    report_css = (Path(__file__).parents[1] / "skills/geo-site-diagnose/assets/report.css").read_text(encoding="utf-8")
    header = re.search(r"\.module-header\s*\{([^}]*)\}", report_css).group(1)
    index_rules = re.findall(r"\.module-index\s*\{([^}]*)\}", report_css)
    index = next(rule for rule in index_rules if "position: absolute" in rule)
    verdict = re.search(r"\.module-verdict\s*\{([^}]*)\}", report_css).group(1)
    verdict_blocks = re.search(r"\.module-verdict strong, \.module-verdict span\s*\{([^}]*)\}", report_css).group(1)
    assert "position: relative" in header and "display: block" in header
    assert "position: absolute" in index and "left: 0" in index and "top: -24px" in index
    assert "display: block" in verdict and "margin: 0 0 22px" in verdict
    assert "display: block" in verdict_blocks


def test_report_visual_rules_and_example_captures_are_governed():
    root = Path(__file__).parents[1]
    design = (root / "skills/geo-site-diagnose/references/report-design-system.md").read_text(encoding="utf-8")
    modules = (root / "skills/geo-site-diagnose/references/report-module-contract.md").read_text(encoding="utf-8")
    risks = (root / "skills/geo-site-diagnose/reports/output-risk-profile.md").read_text(encoding="utf-8")
    for phrase in (
        "decal.show",
        "one circular symbol",
        "never truncate controlled chart labels with an ellipsis",
        "marker-free eight-dimension radar",
        "numbered heatmap",
        "true-proportion retention funnel",
        "one shared left edge",
        "verdict text on the next line",
    ):
        assert phrase in design or phrase in modules
    assert "internal-link graph" not in modules
    assert "internal-link matrix" in modules
    assert "minimum segment widths" in risks
    eval_fixture = root / "skills/geo-site-diagnose/evals/output/fixtures/visual-quality.json"
    eval_cases = (root / "skills/geo-site-diagnose/evals/output/cases.jsonl").read_text(encoding="utf-8")
    assert eval_fixture.is_file()
    assert '"input_files":["fixtures/visual-quality.json"]' in eval_cases
    for name in (
        "geo-site-diagnose-demo.html",
        "geo-site-diagnose-demo-desktop.png",
        "geo-site-diagnose-demo-mobile.png",
        "geo-site-diagnose-demo-discovery.png",
        "geo-site-diagnose-demo-actions.png",
    ):
        path = root / "reports/examples" / name
        assert path.is_file() and path.stat().st_size > 1_000


def test_page_limit_and_same_snapshot_are_deterministic(tmp_path):
    first = _run(tmp_path / "first", max_pages=4)
    second = _run(tmp_path / "second", max_pages=4)
    assert first["run_id"] == second["run_id"]
    assert first["representative_pages"] == 4


def test_private_address_is_rejected_before_fetch(tmp_path):
    with pytest.raises(URLPolicyError):
        site_diagnose(
            "https://private.example/",
            tmp_path,
            fetcher=lambda url: (_ for _ in ()).throw(AssertionError(url)),
            resolver=_private_resolver,
        )


def test_discovery_filters_off_host_queries_downloads_and_login_paths():
    host = "demo.geohub.invalid"
    assert _normalize_candidate("https://outside.invalid/about", host) is None
    assert _normalize_candidate("https://demo.geohub.invalid/about?token=1", host) is None
    assert _normalize_candidate("https://demo.geohub.invalid/report.pdf", host) is None
    assert _normalize_candidate("https://demo.geohub.invalid/login", host) is None
    assert _normalize_candidate("https://demo.geohub.invalid/docs/start#part", host) == "https://demo.geohub.invalid/docs/start"


def test_entity_bearing_sitemap_is_rejected():
    with pytest.raises(SourceUnavailable):
        _parse_sitemap('<!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]><urlset>&xxe;</urlset>')


def test_robots_blocked_representative_page_becomes_source_gap(tmp_path):
    def blocked_fetcher(url: str) -> FetchResult:
        result = _fetcher(url)
        if url.endswith("/robots.txt"):
            body = result.body.replace(b"User-agent: *\nAllow: /", b"User-agent: *\nDisallow: /compare/")
            return FetchResult(url, body, result.content_type)
        if url.endswith("/compare/search-tools"):
            raise AssertionError("robots-blocked page must not be fetched")
        return result

    result = site_diagnose(
        "https://demo.geohub.invalid/", tmp_path, render_mode="http",
        clock=lambda: datetime(2026, 8, 25, tzinfo=timezone.utc),
        fetcher=blocked_fetcher, resolver=_resolver, demo_fixture=True,
    )
    diagnosis = json.loads((Path(result["run_directory"]) / "site-diagnosis.json").read_text(encoding="utf-8"))
    comparison = next(page for page in diagnosis["pages"] if page["page_type"] == "comparison")
    assert comparison["status"] == "source_gap"
    assert "robots.txt" in comparison["message"]
    assert diagnosis["status"] == "degraded"


def test_auto_mode_records_render_gap_for_fixture_javascript_shell(tmp_path):
    def shell_fetcher(url: str) -> FetchResult:
        result = _fetcher(url)
        if url.endswith("/pricing"):
            shell = b'<!doctype html><html><head><title>Pricing</title></head><body><div id="root"></div><script src="/app.js"></script></body></html>'
            return FetchResult(url, shell, "text/html; charset=utf-8")
        return result

    result = site_diagnose(
        "https://demo.geohub.invalid/", tmp_path, render_mode="auto",
        clock=lambda: datetime(2026, 8, 25, tzinfo=timezone.utc),
        fetcher=shell_fetcher, resolver=_resolver, demo_fixture=True,
    )
    diagnosis = json.loads((Path(result["run_directory"]) / "site-diagnosis.json").read_text(encoding="utf-8"))
    pricing = next(page for page in diagnosis["pages"] if page["page_type"] == "transaction")
    assert pricing["status"] == "observed"
    assert pricing["render_gap"] == "browser rendering skipped for injected or fixture fetcher"
    manifest = json.loads((Path(result["run_directory"]) / "run-manifest.json").read_text(encoding="utf-8"))
    assert manifest["missing_dependencies"] == []
    assert manifest["degraded"] is True
    assert diagnosis["confidence"] < 100


def test_homepage_source_gap_suppresses_overall_score(tmp_path):
    def missing_home(url: str) -> FetchResult:
        if url == "https://demo.geohub.invalid/":
            raise SourceUnavailable("homepage unavailable")
        return _fetcher(url)

    result = site_diagnose(
        "https://demo.geohub.invalid/", tmp_path, render_mode="http",
        clock=lambda: datetime(2026, 8, 25, tzinfo=timezone.utc),
        fetcher=missing_home, resolver=_resolver, demo_fixture=True,
    )
    diagnosis = json.loads((Path(result["run_directory"]) / "site-diagnosis.json").read_text(encoding="utf-8"))
    assert diagnosis["overall_score"] is None
    assert diagnosis["pages"][0]["page_type"] == "homepage"
    assert diagnosis["pages"][0]["status"] == "source_gap"


@pytest.mark.parametrize("max_pages", [0, 11, True])
def test_invalid_page_limits_fail_closed(tmp_path, max_pages):
    with pytest.raises(ValueError):
        site_diagnose("https://demo.geohub.invalid/", tmp_path, max_pages=max_pages)


def test_english_locale_localizes_report_and_diagnosis(tmp_path):
    result = site_diagnose(
        "https://demo.geohub.invalid/",
        tmp_path,
        locale="en",
        render_mode="http",
        clock=lambda: datetime(2026, 8, 25, tzinfo=timezone.utc),
        fetcher=_fetcher,
        resolver=_resolver,
        demo_fixture=True,
    )
    run = Path(result["run_directory"])
    report = (run / "report.html").read_text(encoding="utf-8")
    diagnosis = json.loads((run / "site-diagnosis.json").read_text(encoding="utf-8"))
    assert diagnosis["locale"] == "en-US"
    assert diagnosis["pages"][0]["page_type_label"] == "Homepage"
    assert '<html lang="en-US">' in report
    assert "Website GEO Diagnosis" in report
    assert "Page diagnosis" in report
    assert "网站 GEO 诊断报告" not in report


def test_report_controlled_copy_omits_terminal_periods(tmp_path):
    report = Path(_run(tmp_path)["report"]).read_text(encoding="utf-8")
    module_headers = re.findall(r'<header class="module-header">(.*?)</header>', report, re.S)
    assert len(module_headers) == 10
    for header in module_headers:
        values = re.findall(r'<(?:h2|p)>(.*?)</(?:h2|p)>', header, re.S)
        assert values and all(not re.sub(r"<[^>]+>", "", value).strip().endswith(("。", ".")) for value in values)
    captions = re.findall(r'<figcaption>.*?<p>(.*?)</p></figcaption>', report, re.S)
    assert len(captions) == 23
    assert all(not re.sub(r"<[^>]+>", "", caption).strip().endswith(("。", ".")) for caption in captions)


def test_chinese_report_copy_follows_density_limits():
    assert set(CHART_CONTRACTS) == set(CHARTS)
    for title, description, _verdict in COPY["zh-CN"]["modules"].values():
        assert len(title.replace(" ", "")) <= 18
        assert 30 <= len(description.replace(" ", "")) <= 56
    for title, _en_title, caption, _en_caption in CHARTS.values():
        assert len(title.replace(" ", "")) <= 18
        assert 14 <= len(caption.replace(" ", "")) <= 28


def test_homepage_gap_report_does_not_substitute_zero_for_missing_scores(tmp_path):
    def missing_home(url: str) -> FetchResult:
        if url == "https://demo.geohub.invalid/":
            raise SourceUnavailable("homepage unavailable")
        return _fetcher(url)

    result = site_diagnose(
        "https://demo.geohub.invalid/", tmp_path, render_mode="http",
        clock=lambda: datetime(2026, 8, 25, tzinfo=timezone.utc),
        fetcher=missing_home, resolver=_resolver, demo_fixture=True,
    )
    report = Path(result["report"]).read_text(encoding="utf-8")
    assert '"overall":null' in report
    assert "D.overall||0" not in report and "dimension.score||0" not in report
    assert "一个或多个维度缺少证据" in report


def test_report_escapes_hostile_page_title_and_visible_text(tmp_path):
    def hostile_fetcher(url: str) -> FetchResult:
        result = _fetcher(url)
        if url.endswith("/about"):
            body = result.body.replace(
                b"</title>",
                b" %%REPORT_JS%% &lt;/script&gt;&lt;img src=x onerror=alert(1)&gt;</title>",
                1,
            ).replace(
                b"<body>",
                b"<body><p>%%ECHARTS_JS%% &lt;svg onload=alert(2)&gt;</p>",
                1,
            )
            return FetchResult(url, body, result.content_type)
        return result

    result = site_diagnose(
        "https://demo.geohub.invalid/", tmp_path, render_mode="http",
        clock=lambda: datetime(2026, 8, 25, tzinfo=timezone.utc),
        fetcher=hostile_fetcher, resolver=_resolver, demo_fixture=True,
    )
    report = Path(result["report"]).read_text(encoding="utf-8")
    assert "<img src=x onerror=alert(1)>" not in report
    assert "<svg onload=alert(2)>" not in report
    assert "&lt;img src=x onerror=alert(1)&gt;" in report
    assert "&lt;svg onload=alert(2)&gt;" in report
    assert "%%REPORT_JS%%" in report and "%%ECHARTS_JS%%" in report
    assert report.count("window.__GEO_REPORT_READY__ =") == 1


def test_crawler_matrix_covers_every_selected_page(tmp_path):
    run = Path(_run(tmp_path)["run_directory"])
    diagnosis = json.loads((run / "site-diagnosis.json").read_text(encoding="utf-8"))
    page_urls = {page["url"] for page in diagnosis["pages"]}
    for crawler in diagnosis["crawler_matrix"]:
        assert {item["url"] for item in crawler["page_access"]} == page_urls
        assert crawler["allowed_count"] + crawler["blocked_count"] == len(page_urls)


def test_site_fetch_uses_declared_audit_user_agent(monkeypatch):
    captured = {}

    def fake_default_fetch(url, **kwargs):
        captured.update(kwargs)
        return FetchResult(url, b"<title>Audit</title>", "text/html")

    monkeypatch.setattr(site_module, "_default_fetch", fake_default_fetch)
    _fetch_resource(
        "https://demo.geohub.invalid/",
        resolver=_resolver,
        fetcher=None,
        deadline=site_module.time.monotonic() + 5,
        approved_host="demo.geohub.invalid",
        allowed_media_types={"text/html"},
    )
    assert captured["user_agent"] == USER_AGENT


def test_total_byte_budget_stops_additional_fetches(tmp_path, monkeypatch):
    homepage_bytes = len(_fetcher("https://demo.geohub.invalid/").body)
    robots_bytes = len(_fetcher("https://demo.geohub.invalid/robots.txt").body)
    monkeypatch.setattr(site_module, "MAX_TOTAL_BYTES", homepage_bytes + robots_bytes + 5)
    calls = []

    def counted_fetcher(url: str) -> FetchResult:
        calls.append(url)
        return _fetcher(url)

    result = site_diagnose(
        "https://demo.geohub.invalid/",
        tmp_path,
        render_mode="http",
        clock=lambda: datetime(2026, 8, 25, tzinfo=timezone.utc),
        fetcher=counted_fetcher,
        resolver=_resolver,
        demo_fixture=True,
    )
    manifest = json.loads((Path(result["run_directory"]) / "crawl-manifest.json").read_text(encoding="utf-8"))
    assert manifest["total_network_bytes"] <= site_module.MAX_TOTAL_BYTES
    assert len(calls) == 3


def test_duplicate_page_content_becomes_source_gap_and_lowers_confidence(tmp_path):
    about = _fetcher("https://demo.geohub.invalid/about").body

    def duplicate_fetcher(url: str) -> FetchResult:
        result = _fetcher(url)
        if url.endswith("/product/atlas"):
            return FetchResult(url, about, result.content_type)
        return result

    result = site_diagnose(
        "https://demo.geohub.invalid/",
        tmp_path,
        render_mode="http",
        clock=lambda: datetime(2026, 8, 25, tzinfo=timezone.utc),
        fetcher=duplicate_fetcher,
        resolver=_resolver,
        demo_fixture=True,
    )
    diagnosis = json.loads((Path(result["run_directory"]) / "site-diagnosis.json").read_text(encoding="utf-8"))
    offering = next(page for page in diagnosis["pages"] if page["page_type"] == "offering")
    assert offering["status"] == "source_gap"
    assert "duplicates the content" in offering["message"]
    assert diagnosis["confidence"] < 100


def test_unsupported_locale_fails_closed(tmp_path):
    with pytest.raises(ValueError, match="supported Chinese or English"):
        site_diagnose("https://demo.geohub.invalid/", tmp_path, locale="fr-FR")
