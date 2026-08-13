from __future__ import annotations

import hashlib
import http.client
import ipaddress
import json
import queue
import re
import socket
import ssl
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Callable, Iterable
from urllib.parse import urljoin, urlsplit, urlunsplit

from .artifact_bus import ArtifactBus
from .research import build_research_context
from .quality.lineage import build_run_lineage
from .intelligence.audit import (
    build_audit_extension,
    gather_brand_observations,
    gather_page_observations,
    run_audit_catalog,
)
from .validation import load_bounded_json, normalize_artifact_uri, read_bounded_regular_file, strict_json_loads, validate_artifact
from .version import package_version

PROTOCOL_VERSION = "1.0.0"
GENERATOR_VERSION = package_version()
MAX_FETCH_BYTES = 2 * 1024 * 1024
MAX_INPUT_BYTES = 1024 * 1024
MAX_TOTAL_SOURCE_BYTES = 5 * 1024 * 1024
MAX_TARGET_URLS = 5
FETCH_TIMEOUT_SECONDS = 8
DNS_TIMEOUT_SECONDS = 2
TOTAL_FETCH_SECONDS = 30
MAX_REDIRECTS = 3
Clock = Callable[[], datetime]
Resolver = Callable[..., list[tuple[Any, ...]]]


class URLPolicyError(ValueError):
    """Raised when a requested URL violates the explicit public-web boundary."""


class SourceUnavailable(RuntimeError):
    """Raised when an allowed source cannot be obtained."""


@dataclass(frozen=True)
class FetchResult:
    final_url: str
    body: bytes
    content_type: str = ""


Fetcher = Callable[[str], FetchResult]


def _stable_id(prefix: str, *parts: str) -> str:
    canonical = "\x1f".join(parts).encode("utf-8")
    return f"{prefix}-{hashlib.sha256(canonical).hexdigest()[:12]}"


def _require_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-blank string")
    return value.strip()


def _normalize_provenance_uri(value: Any, field: str) -> str:
    uri = normalize_artifact_uri(value, field=field)
    parsed = urlsplit(uri)
    if parsed.scheme.casefold() in {"http", "https"}:
        if parsed.query:
            raise ValueError(f"{field} must be a public canonical URL without credentials or query")
        return urlunsplit((parsed.scheme.casefold(), parsed.netloc, parsed.path, "", ""))
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, parsed.query, ""))


def _source_html_items(value: Any) -> list[str | dict[str, Any]]:
    if isinstance(value, list):
        if not 1 <= len(value) <= MAX_TARGET_URLS:
            raise ValueError(f"source_html must contain between 1 and {MAX_TARGET_URLS} items")
        return value
    return [value]


def _validate_source_html_item(item: Any, field: str) -> None:
    if isinstance(item, str):
        _require_text(item, field)
        if len(item.encode("utf-8")) > MAX_FETCH_BYTES:
            raise ValueError(f"{field} exceeds {MAX_FETCH_BYTES} bytes")
        return
    if not isinstance(item, dict):
        raise ValueError(f"{field} must be non-blank HTML or a file snapshot object")
    allowed = {"path", "source_uri", "sha256", "source_id", "source_type"}
    if set(item) - allowed or "path" not in item:
        raise ValueError(f"{field} has invalid file snapshot fields")
    _require_text(item.get("path"), f"{field}.path")
    if "source_uri" in item:
        _normalize_provenance_uri(item["source_uri"], f"{field}.source_uri")
    if "sha256" in item and not re.fullmatch(r"[0-9a-f]{64}", _require_text(item["sha256"], f"{field}.sha256")):
        raise ValueError(f"{field}.sha256 must be a lowercase SHA-256 digest")
    if "source_id" in item:
        source_id = _require_text(item["source_id"], f"{field}.source_id")
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", source_id):
            raise ValueError(f"{field}.source_id has an invalid format")
    if item.get("source_type", "source_html") not in {"source_html", "target_url"}:
        raise ValueError(f"{field}.source_type must be source_html or target_url")


def validate_diagnosis_brief(brief: Any) -> dict[str, Any]:
    if not isinstance(brief, dict):
        raise ValueError("diagnosis brief must be a JSON object")
    allowed = {
        "subject",
        "scope",
        "target_urls",
        "source_html",
        "evidence",
        "locale",
        "audience",
        "goals",
    }
    extra = sorted(set(brief) - allowed)
    if extra:
        raise ValueError(f"diagnosis brief has unknown fields: {', '.join(extra)}")
    _require_text(brief.get("subject"), "subject")
    if brief.get("scope") not in {"brand", "site", "page"}:
        raise ValueError("scope must be one of: brand, site, page")

    targets = brief.get("target_urls", [])
    if not isinstance(targets, list):
        raise ValueError("target_urls must be an array")
    if len(targets) > MAX_TARGET_URLS:
        raise ValueError(f"target_urls must contain at most {MAX_TARGET_URLS} URLs")
    for index, value in enumerate(targets):
        _require_text(value, f"target_urls[{index}]")

    source_html = brief.get("source_html")
    source_item_count = 0
    if source_html is not None:
        source_items = _source_html_items(source_html)
        source_item_count = len(source_items)
        for index, item in enumerate(source_items):
            _validate_source_html_item(item, f"source_html[{index}]")
    if len(targets) + source_item_count > MAX_TARGET_URLS:
        raise ValueError(
            f"target_urls and source_html together must contain at most {MAX_TARGET_URLS} sources"
        )

    evidence = brief.get("evidence", [])
    if not isinstance(evidence, list):
        raise ValueError("evidence must be an array")
    evidence_ids: list[str] = []
    for index, record in enumerate(evidence):
        if not isinstance(record, dict) or set(record) != {"evidence_id", "claim", "source_uri"}:
            raise ValueError(
                f"evidence[{index}] must contain evidence_id, claim, and source_uri only"
            )
        evidence_ids.append(_require_text(record.get("evidence_id"), f"evidence[{index}].evidence_id"))
        _require_text(record.get("claim"), f"evidence[{index}].claim")
        _normalize_provenance_uri(record.get("source_uri"), f"evidence[{index}].source_uri")
    if len(evidence_ids) != len(set(evidence_ids)):
        raise ValueError("diagnosis brief contains duplicate evidence_id values")

    if not targets and source_html is None and not evidence:
        raise ValueError("at least one of target_urls, source_html, or evidence is required")

    if "locale" in brief:
        _require_text(brief["locale"], "locale")
    if "audience" in brief:
        _require_text(brief["audience"], "audience")
    goals = brief.get("goals", [])
    if not isinstance(goals, list):
        raise ValueError("goals must be an array")
    for index, goal in enumerate(goals):
        _require_text(goal, f"goals[{index}]")
    return brief


def _resolved_addresses(
    hostname: str,
    resolver: Resolver,
    *,
    timeout: float = DNS_TIMEOUT_SECONDS,
) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    try:
        return [ipaddress.ip_address(hostname)]
    except ValueError:
        pass
    results: queue.Queue[tuple[str, Any]] = queue.Queue(maxsize=1)

    def resolve() -> None:
        try:
            results.put(("ok", resolver(hostname, None, type=socket.SOCK_STREAM)))
        except BaseException as exc:  # keep resolver failures inside the bounded worker
            results.put(("error", exc))

    worker = threading.Thread(target=resolve, daemon=True)
    worker.start()
    worker.join(max(0.01, min(DNS_TIMEOUT_SECONDS, timeout)))
    if worker.is_alive():
        raise SourceUnavailable(f"DNS resolution timed out for {hostname}")
    outcome, value = results.get_nowait()
    if outcome == "error":
        raise SourceUnavailable(f"DNS resolution failed for {hostname}: {value}") from value
    answers = value
    addresses: list[ipaddress.IPv4Address | ipaddress.IPv6Address] = []
    for answer in answers:
        try:
            addresses.append(ipaddress.ip_address(answer[4][0]))
        except (IndexError, TypeError, ValueError):
            continue
    if not addresses:
        raise SourceUnavailable(f"DNS resolution returned no addresses for {hostname}")
    return addresses


def _validate_url_syntax(url: str) -> tuple[str, str]:
    value = _require_text(url, "target URL")
    parsed = urlsplit(value)
    if parsed.scheme.casefold() not in {"http", "https"}:
        raise URLPolicyError("target URL scheme must be http or https")
    if parsed.username is not None or parsed.password is not None:
        raise URLPolicyError("target URL must not contain credentials")
    if parsed.query:
        raise URLPolicyError("target URL must not contain a query string")
    if not parsed.hostname:
        raise URLPolicyError("target URL must include a hostname")
    try:
        parsed.port
    except ValueError as exc:
        raise URLPolicyError(f"target URL has an invalid port: {exc}") from exc
    hostname = parsed.hostname.rstrip(".").casefold()
    if hostname == "localhost" or hostname.endswith(".localhost"):
        raise URLPolicyError("localhost targets are forbidden")
    try:
        literal_address = ipaddress.ip_address(hostname)
    except ValueError:
        pass
    else:
        if not literal_address.is_global:
            raise URLPolicyError("target URL resolves to a non-public address")
    normalized = urlunsplit((parsed.scheme.casefold(), parsed.netloc, parsed.path, "", ""))
    return normalized, hostname


def _validate_public_url(
    url: str,
    *,
    resolver: Resolver,
    dns_timeout: float = DNS_TIMEOUT_SECONDS,
) -> tuple[str, list[ipaddress.IPv4Address | ipaddress.IPv6Address]]:
    normalized, hostname = _validate_url_syntax(url)
    addresses = _resolved_addresses(hostname, resolver, timeout=dns_timeout)
    if any(not address.is_global for address in addresses):
        raise URLPolicyError("target URL resolves to a non-public address")
    return normalized, addresses


def validate_public_url(
    url: str,
    *,
    resolver: Resolver = socket.getaddrinfo,
    dns_timeout: float = DNS_TIMEOUT_SECONDS,
) -> str:
    normalized, _addresses = _validate_public_url(
        url,
        resolver=resolver,
        dns_timeout=dns_timeout,
    )
    return normalized


def _default_fetch(
    url: str,
    *,
    resolver: Resolver,
    timeout: int = FETCH_TIMEOUT_SECONDS,
    max_bytes: int = MAX_FETCH_BYTES,
    max_redirects: int = MAX_REDIRECTS,
    deadline: float | None = None,
    initial_addresses: list[ipaddress.IPv4Address | ipaddress.IPv6Address] | None = None,
) -> FetchResult:
    current = url
    source_deadline = min(
        time.monotonic() + timeout,
        deadline if deadline is not None else float("inf"),
    )
    for redirect_count in range(max_redirects + 1):
        remaining = source_deadline - time.monotonic()
        if remaining <= 0:
            raise SourceUnavailable(f"fetch timeout exceeded for {url}")
        try:
            if redirect_count == 0 and initial_addresses is not None:
                addresses = initial_addresses
            else:
                current, addresses = _validate_public_url(
                    current,
                    resolver=resolver,
                    dns_timeout=remaining,
                )
        except URLPolicyError as exc:
            raise SourceUnavailable(f"redirect target rejected by URL policy: {exc}") from exc
        parsed = urlsplit(current)
        address = str(sorted(addresses, key=lambda item: (item.version, str(item)))[0])
        port = parsed.port or (443 if parsed.scheme.casefold() == "https" else 80)
        request_target = parsed.path or "/"
        if parsed.query:
            request_target += f"?{parsed.query}"
        host_header = parsed.hostname or ""
        if ":" in host_header:
            host_header = f"[{host_header}]"
        if parsed.port and parsed.port not in {80, 443}:
            host_header = f"{host_header}:{parsed.port}"
        headers = {
            "Host": host_header,
            "User-Agent": "Yao-GEO-Diagnose/0.1 (+explicit-user-url-only)",
            "Accept": "text/html,application/xhtml+xml",
            "Connection": "close",
        }
        try:
            remaining = source_deadline - time.monotonic()
            if remaining <= 0:
                raise SourceUnavailable(f"fetch timeout exceeded for {url}")
            if parsed.scheme.casefold() == "https":
                connection: http.client.HTTPConnection = _BoundHTTPSConnection(
                    parsed.hostname or "", address, port=port, timeout=max(0.1, remaining)
                )
            else:
                connection = http.client.HTTPConnection(
                    address,
                    port=port,
                    timeout=max(0.1, remaining),
                )
            connection.request("GET", request_target, headers=headers)
            response = connection.getresponse()
        except (OSError, http.client.HTTPException, ssl.SSLError) as exc:
            raise SourceUnavailable(f"unable to fetch {current}: {exc}") from exc
        try:
            if response.status in {301, 302, 303, 307, 308}:
                location = response.getheader("Location")
                if not location:
                    raise SourceUnavailable(f"redirect from {current} has no Location header")
                if redirect_count >= max_redirects:
                    raise SourceUnavailable(f"redirect limit exceeded for {url}")
                current = urljoin(current, location)
                continue
            if response.status < 200 or response.status >= 300:
                raise SourceUnavailable(f"HTTP {response.status} while fetching {current}")
            body_parts: list[bytes] = []
            byte_count = 0
            while True:
                remaining = source_deadline - time.monotonic()
                if remaining <= 0:
                    raise SourceUnavailable(f"fetch timeout exceeded for {url}")
                if connection.sock is not None:
                    connection.sock.settimeout(max(0.1, remaining))
                chunk = response.read(min(64 * 1024, max_bytes + 1 - byte_count))
                if not chunk:
                    break
                body_parts.append(chunk)
                byte_count += len(chunk)
                if byte_count > max_bytes:
                    raise SourceUnavailable(f"source exceeds {max_bytes} byte fetch limit")
            body = b"".join(body_parts)
            return FetchResult(
                final_url=current,
                body=body,
                content_type=response.getheader("Content-Type", "") or "",
            )
        finally:
            connection.close()
    raise SourceUnavailable(f"redirect limit exceeded for {url}")


class _BoundHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, hostname: str, address: str, *, port: int, timeout: int):
        super().__init__(hostname, port=port, timeout=timeout, context=ssl.create_default_context())
        self._validated_address = address

    def connect(self) -> None:
        raw_socket = socket.create_connection(
            (self._validated_address, self.port),
            self.timeout,
            self.source_address,
        )
        self.sock = self._context.wrap_socket(raw_socket, server_hostname=self.host)


def _decode_html(result: FetchResult) -> str:
    charset_match = re.search(r"charset\s*=\s*['\"]?([^;\s'\"]+)", result.content_type, re.I)
    charset = charset_match.group(1) if charset_match else "utf-8"
    try:
        return result.body.decode(charset, errors="replace")
    except LookupError:
        return result.body.decode("utf-8", errors="replace")


class PageAnalyzer(HTMLParser):
    def __init__(self, base_url: str):
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.title = ""
        self.meta_description = ""
        self.canonical = ""
        self.meta_robots = ""
        self.headings: dict[str, list[str]] = {"h1": [], "h2": [], "h3": []}
        self.main_count = 0
        self.article_count = 0
        self.list_count = 0
        self.table_count = 0
        self.json_ld_count = 0
        self.valid_json_ld_count = 0
        self.links: list[str] = []
        self._capture: str | None = None
        self._capture_parts: list[str] = []
        self._hidden_depth = 0
        self._visible_parts: list[str] = []
        self._json_ld_depth = 0
        self._json_ld_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.casefold()
        values = {key.casefold(): (value or "") for key, value in attrs}
        if tag in {"script", "style", "noscript", "template"}:
            self._hidden_depth += 1
        if tag == "script" and values.get("type", "").casefold() == "application/ld+json":
            self.json_ld_count += 1
            self._json_ld_depth = self._hidden_depth
            self._json_ld_parts = []
        if tag == "title" or tag in self.headings:
            self._capture = tag
            self._capture_parts = []
        if tag == "meta":
            key = values.get("name", "").casefold()
            if key == "description" and not self.meta_description:
                self.meta_description = values.get("content", "").strip()
            if key == "robots" and not self.meta_robots:
                self.meta_robots = values.get("content", "").strip()
        if tag == "link" and "canonical" in values.get("rel", "").casefold().split():
            self.canonical = values.get("href", "").strip()
        if tag == "a" and values.get("href"):
            self.links.append(urljoin(self.base_url, values["href"].strip()))
        if tag == "main":
            self.main_count += 1
        elif tag == "article":
            self.article_count += 1
        elif tag in {"ul", "ol", "dl"}:
            self.list_count += 1
        elif tag == "table":
            self.table_count += 1

    def handle_endtag(self, tag: str) -> None:
        tag = tag.casefold()
        if self._capture == tag:
            value = " ".join(" ".join(self._capture_parts).split())
            if tag == "title":
                self.title = value
            elif value:
                self.headings[tag].append(value)
            self._capture = None
            self._capture_parts = []
        if tag == "script" and self._json_ld_depth:
            try:
                strict_json_loads("".join(self._json_ld_parts))
            except (ValueError, TypeError):
                pass
            else:
                self.valid_json_ld_count += 1
            self._json_ld_depth = 0
            self._json_ld_parts = []
        if tag in {"script", "style", "noscript", "template"} and self._hidden_depth:
            self._hidden_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._capture:
            self._capture_parts.append(data)
        if self._json_ld_depth:
            self._json_ld_parts.append(data)
        if not self._hidden_depth and data.strip():
            self._visible_parts.append(data.strip())

    def metrics(self) -> dict[str, Any]:
        visible_text = " ".join(" ".join(self._visible_parts).split())
        origin = urlsplit(self.base_url).hostname
        internal = 0
        external = 0
        for link in self.links:
            host = urlsplit(link).hostname
            if host and host == origin:
                internal += 1
            elif host:
                external += 1
        faq_like = len(re.findall(r"(?:\?|？)", visible_text))
        faq_like += sum(1 for text in self.headings["h2"] + self.headings["h3"] if re.search(r"faq|常见问题|问答", text, re.I))
        return {
            "title": self.title,
            "meta_description": self.meta_description,
            "canonical": self.canonical,
            "meta_robots": self.meta_robots,
            "headings": self.headings,
            "main_count": self.main_count,
            "article_count": self.article_count,
            "list_count": self.list_count,
            "table_count": self.table_count,
            "faq_like_count": faq_like,
            "json_ld_count": self.json_ld_count,
            "valid_json_ld_count": self.valid_json_ld_count,
            "visible_text_length": len(visible_text),
            "internal_link_count": internal,
            "external_link_count": external,
            "visible_text": visible_text,
        }


def analyze_html(html: str, base_url: str) -> dict[str, Any]:
    parser = PageAnalyzer(base_url)
    parser.feed(html)
    parser.close()
    return parser.metrics()


def _finding(
    run_id: str,
    category: str,
    statement: str,
    recommendation: str,
    *,
    severity: str,
    source_kind: str,
    evidence_id: str | None,
) -> dict[str, Any]:
    return {
        "finding_id": _stable_id("finding", run_id, category, statement, evidence_id or "gap"),
        "category": category,
        "severity": severity,
        "source_kind": source_kind,
        "statement": statement,
        "evidence_id": evidence_id,
        "recommendation": recommendation,
    }


def _page_findings(run_id: str, source_id: str, evidence_id: str, metrics: dict[str, Any]) -> tuple[dict[str, int], list[dict[str, Any]]]:
    findings: list[dict[str, Any]] = []

    def add(category: str, passed: bool, observation: str, recommendation: str) -> None:
        findings.append(
            _finding(
                run_id,
                category,
                f"{source_id}: {observation}",
                recommendation,
                severity="info" if passed else "warning",
                source_kind="observed",
                evidence_id=evidence_id,
            )
        )

    discoverability_parts = [bool(metrics["title"]), bool(metrics["meta_description"]), bool(metrics["canonical"])]
    noindex = "noindex" in metrics["meta_robots"].casefold()
    discoverability_parts.append(not noindex)
    add("discoverability", bool(metrics["title"]), "title is present" if metrics["title"] else "title is missing", "Add a concise, subject-specific title." )
    add("discoverability", bool(metrics["meta_description"]), "meta description is present" if metrics["meta_description"] else "meta description is missing", "Add a factual summary for search and answer surfaces.")
    add("discoverability", bool(metrics["canonical"]), "canonical link is present" if metrics["canonical"] else "canonical link is missing", "Declare the preferred canonical URL.")
    add("discoverability", not noindex, f"robots directive is '{metrics['meta_robots'] or 'unspecified'}'", "Remove noindex when the page is intended for public discovery.")

    h1_count = len(metrics["headings"]["h1"])
    structure_ok = h1_count == 1 and bool(metrics["headings"]["h2"])
    add("structure", h1_count == 1, f"H1 count is {h1_count}", "Use one descriptive H1.")
    add("structure", bool(metrics["headings"]["h2"]), f"H2 count is {len(metrics['headings']['h2'])}", "Organize the main answer into descriptive H2 sections.")

    extraction_signals = metrics["main_count"] + metrics["article_count"] + metrics["list_count"] + metrics["table_count"] + metrics["valid_json_ld_count"]
    add("extractability", extraction_signals > 0, f"semantic extraction signal count is {extraction_signals}", "Use main/article landmarks and structured lists or tables where they fit.")
    add("extractability", metrics["visible_text_length"] >= 300, f"visible text length is {metrics['visible_text_length']} characters", "Provide enough visible, self-contained text to answer the page topic.")

    evidence_signal = bool(re.search(r"source|reference|citation|method|数据|来源|参考|方法", metrics["visible_text"], re.I))
    add("evidence", evidence_signal, "evidence-language signal is present" if evidence_signal else "no evidence-language signal was detected", "Attach claims to named sources or a transparent method.")
    authority_signal = bool(re.search(r"author|editor|expert|about|contact|作者|专家|关于|联系", metrics["visible_text"], re.I))
    add("authority", authority_signal, "authority signal is present" if authority_signal else "no authority signal was detected", "Show accountable authorship, expertise, or organization details.")
    freshness_signal = bool(re.search(r"\b20\d{2}[-/.年]\d{1,2}|updated|last modified|更新", metrics["visible_text"], re.I))
    add("freshness", freshness_signal, "freshness signal is present" if freshness_signal else "no freshness signal was detected", "Show a meaningful published or updated date where freshness matters.")

    scores = {
        "discoverability": round(100 * sum(discoverability_parts) / len(discoverability_parts)),
        "structure": 100 if structure_ok else (50 if h1_count == 1 or bool(metrics["headings"]["h2"]) else 0),
        "extractability": min(100, (50 if metrics["visible_text_length"] >= 300 else 20 if metrics["visible_text_length"] else 0) + min(50, extraction_signals * 10)),
        "evidence": 100 if evidence_signal else 20,
        "authority": 100 if authority_signal else 20,
        "freshness": 100 if freshness_signal else 20,
    }
    readiness = round(sum(scores.values()) / len(scores))
    findings.append(
        _finding(
            run_id,
            "answer-readiness",
            f"{source_id}: combined observed signals yield a bounded answer-readiness heuristic of {readiness}/100.",
            "Use the dimension findings as the remediation guide and re-run against the updated source.",
            severity="info" if readiness >= 70 else "opportunity",
            source_kind="inferred",
            evidence_id=evidence_id,
        )
    )
    return scores, findings


BRAND_CATEGORIES = {
    "identity": ("brand", "company", "organization", "品牌", "公司", "机构"),
    "offering": ("product", "service", "solution", "产品", "服务", "方案"),
    "audience": ("customer", "user", "team", "客户", "用户", "团队"),
    "differentiation": ("different", "unique", "advantage", "差异", "优势", "独特"),
    "proof": ("evidence", "case", "customer", "source", "证据", "案例", "来源"),
    "contact": ("contact", "address", "location", "联系", "地址", "所在地"),
}


def _brand_findings(run_id: str, sources: list[dict[str, Any]], provided: list[dict[str, Any]]) -> tuple[dict[str, int], list[dict[str, Any]]]:
    corpus_items: list[tuple[str, str, str]] = []
    for source in sources:
        corpus_items.append((source["metrics"]["visible_text"], "observed", source["evidence_id"]))
    for record in provided:
        corpus_items.append((record["claim"], "provided", record["evidence_id"]))
    findings: list[dict[str, Any]] = []
    for record in provided:
        findings.append(
            _finding(
                run_id,
                "provided-evidence",
                f"Provided evidence states: {record['claim']}",
                "Verify this claim against its authoritative source before publication.",
                severity="opportunity",
                source_kind="provided",
                evidence_id=record["evidence_id"],
            )
        )
    covered = 0
    for category, terms in BRAND_CATEGORIES.items():
        match = next(
            ((text, kind, evidence_id) for text, kind, evidence_id in corpus_items if any(term.casefold() in text.casefold() for term in terms)),
            None,
        )
        if match:
            covered += 1
            _, _kind, evidence_id = match
            findings.append(_finding(run_id, f"brand-{category}", f"The supplied sources cover the brand fact category '{category}'.", "Keep this fact current and attach it to a stable authoritative source.", severity="info", source_kind="inferred", evidence_id=evidence_id))
        else:
            findings.append(_finding(run_id, f"brand-{category}", f"The supplied sources do not establish the brand fact category '{category}'.", "Add an explicit, source-backed fact for this category.", severity="warning", source_kind="input_gap", evidence_id=None))
    evidence_score = min(100, len(provided) * 25 + len(sources) * 20)
    scores = {
        "brand_fact_coverage": round(100 * covered / len(BRAND_CATEGORIES)),
        "evidence": evidence_score,
        "authority": 80 if any(record["source_uri"].startswith(("http://", "https://")) for record in provided) or sources else 30,
        "freshness": 60 if any(re.search(r"\b20\d{2}\b|updated|更新", text, re.I) for text, _, _ in corpus_items) else 20,
    }
    return scores, findings


def validate_diagnosis(artifact: Any, *, evidence_ids: Iterable[str] | None = None) -> None:
    if not isinstance(artifact, dict):
        raise ValueError("diagnosis.json must be an object")
    required = {"protocol_version", "run_id", "subject", "scope", "status", "scores", "findings", "limitations", "source_status"}
    v2_fields = {"audit_catalog_version", "scoring_policy_version", "audit_results", "audit_score", "execution", "semantic_digest"}
    if not required <= set(artifact) or set(artifact) - required not in (set(), v2_fields):
        raise ValueError("diagnosis.json fields do not match the diagnosis contract")
    if artifact["protocol_version"] != PROTOCOL_VERSION or artifact["scope"] not in {"brand", "site", "page"}:
        raise ValueError("diagnosis.json has an invalid protocol version or scope")
    if artifact["status"] not in {"completed", "degraded"}:
        raise ValueError("diagnosis.json status must be completed or degraded")
    _require_text(artifact["run_id"], "diagnosis.run_id")
    _require_text(artifact["subject"], "diagnosis.subject")
    if not isinstance(artifact["scores"], dict) or not artifact["scores"]:
        raise ValueError("diagnosis.scores must be a non-empty object")
    if any(not isinstance(score, int) or isinstance(score, bool) or not 0 <= score <= 100 for score in artifact["scores"].values()):
        raise ValueError("diagnosis scores must be integers from 0 to 100")
    if not isinstance(artifact["findings"], list):
        raise ValueError("diagnosis.findings must be an array")
    finding_ids: set[str] = set()
    known_evidence_ids = set(evidence_ids) if evidence_ids is not None else None
    for finding in artifact["findings"]:
        expected = {"finding_id", "category", "severity", "source_kind", "statement", "evidence_id", "recommendation"}
        if not isinstance(finding, dict) or set(finding) != expected:
            raise ValueError("diagnosis finding fields do not match the contract")
        finding_id = _require_text(finding["finding_id"], "finding.finding_id")
        if finding_id in finding_ids:
            raise ValueError("diagnosis contains duplicate finding_id values")
        finding_ids.add(finding_id)
        if finding["source_kind"] not in {"observed", "provided", "input_gap", "inferred"}:
            raise ValueError("finding.source_kind is invalid")
        if finding["severity"] not in {"info", "opportunity", "warning"}:
            raise ValueError("finding.severity is invalid")
        _require_text(finding["statement"], "finding.statement")
        _require_text(finding["recommendation"], "finding.recommendation")
        if finding["source_kind"] in {"observed", "provided", "inferred"}:
            finding_evidence_id = _require_text(finding["evidence_id"], "finding.evidence_id")
            if known_evidence_ids is not None and finding_evidence_id not in known_evidence_ids:
                raise ValueError(
                    f"finding.evidence_id is absent from the evidence ledger: {finding_evidence_id}"
                )
        elif finding["evidence_id"] is not None:
            raise ValueError("input_gap finding evidence_id must be null")
    if not isinstance(artifact["limitations"], list) or any(not isinstance(value, str) or not value.strip() for value in artifact["limitations"]):
        raise ValueError("diagnosis.limitations must contain non-blank strings")
    if not isinstance(artifact["source_status"], list):
        raise ValueError("diagnosis.source_status must be an array")
    source_ids: set[str] = set()
    for source in artifact["source_status"]:
        expected = {"source_id", "source_type", "source_uri", "status", "message", "observations"}
        if not isinstance(source, dict) or set(source) != expected:
            raise ValueError("diagnosis source_status fields do not match the contract")
        source_id = _require_text(source["source_id"], "source_status.source_id")
        if source_id in source_ids:
            raise ValueError("diagnosis contains duplicate source_id values")
        source_ids.add(source_id)
        if source["source_type"] not in {"target_url", "source_html", "evidence"}:
            raise ValueError("source_status.source_type is invalid")
        if source["status"] not in {"observed", "provided", "source_gap"}:
            raise ValueError("source_status.status is invalid")
        _require_text(source["source_uri"], "source_status.source_uri")
        _require_text(source["message"], "source_status.message")
        if source["status"] == "observed" and not isinstance(source["observations"], dict):
            raise ValueError("observed source_status requires observations")
        if source["observations"] is not None and not isinstance(source["observations"], dict):
            raise ValueError("source_status.observations must be an object or null")
    if v2_fields <= set(artifact):
        if artifact["audit_catalog_version"] != "1.0.0" or artifact["scoring_policy_version"] != "1.0.0":
            raise ValueError("diagnosis audit catalog or scoring policy version is invalid")
        if not isinstance(artifact["audit_results"], list) or not artifact["audit_results"]:
            raise ValueError("diagnosis audit_results must be a non-empty array")
        for audit in artifact["audit_results"]:
            if audit.get("status") not in {"pass", "fail", "not-applicable", "missing-evidence"}:
                raise ValueError("diagnosis audit status is invalid")
            if not set(audit.get("evidence_ids", [])) <= (known_evidence_ids or set()):
                raise ValueError("diagnosis audit evidence_ids must resolve in the evidence ledger")
            remediation = audit.get("remediation", {})
            if remediation.get("audit_id") != audit.get("audit_id"):
                raise ValueError("diagnosis audit remediation must trace to its audit")
        score = artifact["audit_score"]
        if score.get("scoring_policy_version") != "1.0.0" or score.get("denominator", 0) < 0:
            raise ValueError("diagnosis audit score is invalid")
        if artifact["execution"].get("mode") not in {"deterministic", "research", "provider"}:
            raise ValueError("diagnosis execution mode is invalid")
        if re.fullmatch(r"[0-9a-f]{64}", artifact["semantic_digest"]) is None:
            raise ValueError("diagnosis semantic digest is invalid")


def _load_source_html(
    value: str | dict[str, Any],
    input_path: Path,
    *,
    index: int,
) -> tuple[str, str, str, str]:
    if isinstance(value, dict):
        path = Path(value["path"].strip())
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("source_html fixture path must stay relative to the brief directory")
        parts = path.parts
        if not parts:
            raise ValueError("source_html fixture path must name a file")
        try:
            html = read_bounded_regular_file(
                input_path.parent / path,
                max_bytes=MAX_FETCH_BYTES,
                field="source_html fixture",
            ).decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError(f"source_html fixture must be UTF-8: {path}") from exc
        digest = hashlib.sha256(html.encode("utf-8")).hexdigest()
        declared_digest = value.get("sha256", "").strip()
        if declared_digest and declared_digest != digest:
            raise ValueError(f"source_html[{index}] digest does not match its file snapshot")
        source_uri = _normalize_provenance_uri(
            value.get("source_uri", f"urn:geo-seo-hub:input:source-html:{index + 1}"),
            f"source_html[{index}].source_uri",
        )
        return (
            html,
            source_uri,
            value.get("source_id", f"source-html-{index + 1}").strip(),
            value.get("source_type", "source_html"),
        )
    return (
        value,
        f"urn:geo-seo-hub:input:source-html:{index + 1}",
        f"source-html-{index + 1}",
        "source_html",
    )


def _public_observations(metrics: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": metrics["title"],
        "meta_description": metrics["meta_description"],
        "canonical": metrics["canonical"],
        "meta_robots": metrics["meta_robots"],
        "h1": metrics["headings"]["h1"],
        "h2": metrics["headings"]["h2"],
        "h3": metrics["headings"]["h3"],
        "main_count": metrics["main_count"],
        "article_count": metrics["article_count"],
        "list_count": metrics["list_count"],
        "table_count": metrics["table_count"],
        "faq_like_count": metrics["faq_like_count"],
        "json_ld_count": metrics["json_ld_count"],
        "valid_json_ld_count": metrics["valid_json_ld_count"],
        "visible_text_length": metrics["visible_text_length"],
        "internal_link_count": metrics["internal_link_count"],
        "external_link_count": metrics["external_link_count"],
    }


def _build_diagnosis_query_map(
    run_id: str,
    findings: Iterable[dict[str, Any]],
    *,
    audience: str,
) -> tuple[dict[str, Any], dict[str, str]]:
    queries = []
    finding_queries: dict[str, str] = {}
    for finding in findings:
        if finding["severity"] == "info":
            continue
        query_id = _stable_id("qry", finding["finding_id"])
        finding_queries[finding["finding_id"]] = query_id
        action = finding["recommendation"]
        queries.append(
            {
                "query_id": query_id,
                "question": action,
                "intent": "act",
                "audience": audience,
                "scenario": "GEO diagnosis remediation",
                "parent_query_id": None,
                "rewrites": {
                    "standalone": action,
                    "retrieval": f"{finding['category']} GEO remediation",
                    "evidence": f"{finding['category']} evidence and verification method",
                },
                "evidence_status": "provided" if finding["evidence_id"] else "missing",
            }
        )
    if not queries:
        query_id = _stable_id("qry", run_id, "maintain")
        finding_queries["maintain"] = query_id
        queries.append(
            {
                "query_id": query_id,
                "question": "Maintain the observed GEO signals and verify them during the next review.",
                "intent": "act",
                "audience": audience,
                "scenario": "GEO diagnosis maintenance",
                "parent_query_id": None,
                "rewrites": {
                    "standalone": "Maintain and re-verify the observed GEO signals.",
                    "retrieval": "GEO maintenance review",
                    "evidence": "GEO maintenance evidence verification",
                },
                "evidence_status": "provided",
            }
        )
    return {"protocol_version": PROTOCOL_VERSION, "run_id": run_id, "queries": queries}, finding_queries


def _opportunities(
    run_id: str,
    findings: Iterable[dict[str, Any]],
    finding_queries: dict[str, str],
) -> dict[str, Any]:
    asset_types = {
        "structure": "article",
        "discoverability": "landing-page",
        "extractability": "faq",
        "evidence": "knowledge-entry",
        "authority": "knowledge-entry",
        "freshness": "article",
    }
    opportunities = []
    for finding in findings:
        if finding["severity"] == "info":
            continue
        category = finding["category"]
        base_category = category.removeprefix("brand-")
        opportunities.append(
            {
                "opportunity_id": _stable_id("opp", finding["finding_id"]),
                "query_ids": [finding_queries[finding["finding_id"]]],
                "asset_type": asset_types.get(base_category, "knowledge-entry"),
                "priority": 90 if finding["severity"] == "warning" else 70,
                "rationale": finding["recommendation"],
                "evidence_status": "provided" if finding["evidence_id"] else "missing",
            }
        )
    return {"protocol_version": PROTOCOL_VERSION, "run_id": run_id, "opportunities": opportunities}


def _build_diagnosis_funnel(
    run_id: str,
    analyzed_sources: list[dict[str, Any]],
    provided: list[dict[str, Any]],
    source_status: list[dict[str, Any]],
    ledger_records: list[dict[str, Any]],
) -> dict[str, Any]:
    primary_hosts = {
        urlsplit(source["source_uri"]).hostname.casefold()
        for source in analyzed_sources
        if urlsplit(source["source_uri"]).hostname
    }
    ecosystem = []
    for source in source_status:
        if source["source_type"] in {"target_url", "source_html"}:
            role = "primary-input"
            basis = "input-source-type"
        else:
            hostname = urlsplit(source["source_uri"]).hostname
            if hostname:
                role = "primary-input" if hostname.casefold() in primary_hosts else "third-party-evidence"
                basis = "hostname-comparison"
            else:
                role = "unknown"
                basis = "insufficient-metadata"
        ecosystem.append(
            {
                "source_id": source["source_id"],
                "source_uri": source["source_uri"],
                "role": role,
                "classification_basis": basis,
                "status": source["status"],
            }
        )

    observed_ids = sorted(source["evidence_id"] for source in analyzed_sources)
    selection_ids = sorted({record["evidence_id"] for record in ledger_records})
    funnel = {
        "protocol_version": PROTOCOL_VERSION,
        "run_id": run_id,
        "effect_guarantee": False,
        "stages": [
            {
                "stage": "candidate-eligibility",
                "status": "observed" if observed_ids else "source-gap",
                "causal_status": "observed" if observed_ids else "not-observed",
                "evidence_ids": observed_ids,
                "signals": ["discoverability", "indexability", "structural accessibility"] if observed_ids else [],
                "limitations": ["Eligibility observations cover only supplied or explicitly requested sources and do not prove engine retrieval."],
            },
            {
                "stage": "citation-selection",
                "status": "proxy" if selection_ids else "source-gap",
                "causal_status": "proxy" if selection_ids else "not-observed",
                "evidence_ids": selection_ids,
                "signals": ["semantic relevance", "extractability", "evidence and authority"] if selection_ids else [],
                "limitations": ["Selection signals are readiness proxies and do not estimate citation probability."],
            },
            {
                "stage": "answer-absorption",
                "status": "not-observed",
                "causal_status": "not-observed",
                "evidence_ids": [],
                "signals": [],
                "limitations": ["No platform answer observations were supplied, so answer absorption cannot be measured."],
            },
        ],
        "source_ecosystem": ecosystem,
    }
    validate_artifact("diagnosis-funnel", funnel)
    return funnel


def _render_report(diagnosis: dict[str, Any], opportunities: dict[str, Any]) -> str:
    lines = [
        f"# GEO Diagnosis: {diagnosis['subject']}",
        "",
        f"Scope: `{diagnosis['scope']}`  ",
        f"Status: `{diagnosis['status']}`",
        "",
        "## Scores",
        "",
        "| Dimension | Score |",
        "| --- | ---: |",
    ]
    lines.extend(f"| {name.replace('_', ' ').title()} | {score}/100 |" for name, score in sorted(diagnosis["scores"].items()))
    lines.extend(["", "## Findings", ""])
    for finding in diagnosis["findings"]:
        evidence = finding["evidence_id"] or "input gap"
        lines.extend(
            [
                f"### {finding['category'].replace('-', ' ').title()} · {finding['severity']}",
                "",
                finding["statement"],
                "",
                f"Evidence: `{evidence}` · Basis: `{finding['source_kind']}`",
                "",
                f"Action: {finding['recommendation']}",
                "",
            ]
        )
    lines.extend(["## Opportunity map", ""])
    if opportunities["opportunities"]:
        for item in opportunities["opportunities"]:
            lines.append(f"- Priority {item['priority']}: {item['rationale']} (`{item['opportunity_id']}`)")
    else:
        lines.append("- No remediation opportunity was generated from the supplied sources.")
    lines.extend(["", "## Source status", ""])
    for source in diagnosis["source_status"]:
        lines.append(f"- `{source['status']}` {source['source_uri']}: {source['message']}")
    lines.extend(["", "## Limitations", ""])
    if diagnosis["limitations"]:
        lines.extend(f"- {item}" for item in diagnosis["limitations"])
    else:
        lines.append("- No additional limitations were recorded for this bounded run.")
    lines.extend(
        [
            "",
            "This report evaluates supplied and directly requested sources. It makes no claim about live AI-platform recall, ranking, or citation share.",
            "",
        ]
    )
    return "\n".join(lines)


def diagnose(
    input_path: Path,
    output_path: Path,
    *,
    clock: Clock | None = None,
    fetcher: Fetcher | None = None,
    resolver: Resolver = socket.getaddrinfo,
    execution_mode: str = "legacy",
) -> dict[str, Any]:
    if execution_mode not in {"legacy", "deterministic", "research", "provider"}:
        raise ValueError("execution mode must be legacy, deterministic, research, or provider")
    execution_failures = (
        ["provider mode has no configured audit adapter; deterministic audits completed"]
        if execution_mode == "provider"
        else []
    )
    brief = validate_diagnosis_brief(
        load_bounded_json(input_path, max_bytes=MAX_INPUT_BYTES, field="diagnosis brief")
    )
    now = (clock or (lambda: datetime.now(timezone.utc)))()
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    created_at = now.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

    normalized_brief = dict(brief)
    normalized_brief["subject"] = brief["subject"].strip()
    for field in ("locale", "audience"):
        if field in brief:
            normalized_brief[field] = brief[field].strip()
    if "goals" in brief:
        normalized_brief["goals"] = [goal.strip() for goal in brief["goals"]]

    provided = []
    for record in brief.get("evidence", []):
        claim = record["claim"].strip()
        source_uri = _normalize_provenance_uri(record["source_uri"], "evidence.source_uri")
        provided.append(
            {
                "evidence_id": _stable_id("ev", claim, source_uri),
                "claim": claim,
                "source_uri": source_uri,
            }
        )
    provided.sort(key=lambda item: item["evidence_id"])
    normalized_evidence_ids = [record["evidence_id"] for record in provided]
    if len(normalized_evidence_ids) != len(set(normalized_evidence_ids)):
        raise ValueError("diagnosis brief contains duplicate normalized evidence records")
    analyzed_sources: list[dict[str, Any]] = []
    source_status: list[dict[str, Any]] = []
    limitations: list[str] = []
    if provided:
        normalized_brief["evidence"] = provided
    total_source_bytes = 0
    fetch_deadline = time.monotonic() + TOTAL_FETCH_SECONDS

    for index, record in enumerate(provided):
        source_status.append(
            {
                "source_id": f"evidence-{index + 1}",
                "source_type": "evidence",
                "source_uri": record["source_uri"],
                "status": "provided",
                "message": "Evidence claim was supplied by the user and was not independently verified.",
                "observations": None,
            }
        )

    source_items = _source_html_items(brief["source_html"]) if "source_html" in brief else []
    loaded_source_ids: set[str] = set()
    for index, source_item in enumerate(source_items):
        html, source_uri, source_id, source_type = _load_source_html(
            source_item,
            input_path,
            index=index,
        )
        if source_id in loaded_source_ids:
            raise ValueError(f"source_html contains duplicate source_id: {source_id}")
        loaded_source_ids.add(source_id)
        source_bytes = html.encode("utf-8")
        if total_source_bytes + len(source_bytes) > MAX_TOTAL_SOURCE_BYTES:
            raise ValueError(
                f"total source content exceeds {MAX_TOTAL_SOURCE_BYTES} byte limit"
            )
        total_source_bytes += len(source_bytes)
        content_sha256 = hashlib.sha256(source_bytes).hexdigest()
        metrics = analyze_html(html, source_uri)
        analyzed_sources.append({"source_id": source_id, "source_uri": source_uri, "source_type": source_type, "content_sha256": content_sha256, "metrics": metrics, "html": html})
        if source_type == "target_url":
            source_status.append({"source_id": source_id, "source_type": source_type, "source_uri": source_uri, "status": "observed", "message": "The explicit public URL snapshot was parsed.", "observations": _public_observations(metrics)})
        else:
            source_status.append({"source_id": source_id, "source_type": source_type, "source_uri": source_uri, "status": "provided", "message": "HTML was supplied by the user and parsed locally.", "observations": _public_observations(metrics)})

    failed_target_urls: list[str] = []
    for index, target_url in enumerate(brief.get("target_urls", [])):
        source_id = f"url-{index + 1}"
        if source_id in loaded_source_ids:
            raise ValueError(f"target URL source_id collides with source_html: {source_id}")
        clean_target, _hostname = _validate_url_syntax(target_url)
        source_deadline = min(
            fetch_deadline,
            time.monotonic() + FETCH_TIMEOUT_SECONDS,
        )
        remaining = source_deadline - time.monotonic()
        if remaining <= 0:
            source_status.append({"source_id": source_id, "source_type": "target_url", "source_uri": clean_target, "status": "source_gap", "message": "total fetch budget exhausted", "observations": None})
            limitations.append(f"Source unavailable: {clean_target}. No page observation was inferred for it.")
            failed_target_urls.append(clean_target)
            continue
        try:
            clean_target, initial_addresses = _validate_public_url(
                target_url,
                resolver=resolver,
                dns_timeout=remaining,
            )
            remaining = source_deadline - time.monotonic()
            if remaining <= 0:
                raise SourceUnavailable("total fetch budget exhausted")
            result = fetcher(clean_target) if fetcher else _default_fetch(
                clean_target,
                resolver=resolver,
                timeout=remaining,
                deadline=source_deadline,
                initial_addresses=initial_addresses,
            )
            if not isinstance(result, FetchResult):
                raise SourceUnavailable("fetcher returned an invalid result")
            if not isinstance(result.body, bytes):
                raise SourceUnavailable("fetcher result body must be bytes")
            try:
                remaining = source_deadline - time.monotonic()
                if remaining <= 0:
                    raise SourceUnavailable("total fetch budget exhausted")
                clean_final = validate_public_url(
                    result.final_url,
                    resolver=resolver,
                    dns_timeout=remaining,
                )
            except URLPolicyError as exc:
                raise SourceUnavailable(f"final fetch target rejected by URL policy: {exc}") from exc
            media_type = result.content_type.partition(";")[0].strip().casefold()
            if media_type not in {"text/html", "application/xhtml+xml"}:
                raise SourceUnavailable(
                    f"unsupported Content-Type for HTML diagnosis: {media_type or 'missing'}"
                )
            if len(result.body) > MAX_FETCH_BYTES:
                raise SourceUnavailable(f"source exceeds {MAX_FETCH_BYTES} byte fetch limit")
            html = _decode_html(result)
            snapshot_bytes = html.encode("utf-8")
            if len(snapshot_bytes) > MAX_FETCH_BYTES:
                raise SourceUnavailable(
                    f"decoded HTML snapshot exceeds {MAX_FETCH_BYTES} byte limit"
                )
            if total_source_bytes + len(snapshot_bytes) > MAX_TOTAL_SOURCE_BYTES:
                raise SourceUnavailable(
                    f"total source content exceeds {MAX_TOTAL_SOURCE_BYTES} byte limit"
                )
            total_source_bytes += len(snapshot_bytes)
        except URLPolicyError:
            raise
        except (OSError, SourceUnavailable) as exc:
            source_status.append({"source_id": source_id, "source_type": "target_url", "source_uri": clean_target, "status": "source_gap", "message": str(exc), "observations": None})
            limitations.append(f"Source unavailable: {clean_target}. No page observation was inferred for it.")
            failed_target_urls.append(clean_target)
            continue
        content_sha256 = hashlib.sha256(snapshot_bytes).hexdigest()
        metrics = analyze_html(html, clean_final)
        analyzed_sources.append({"source_id": source_id, "source_uri": clean_final, "source_type": "target_url", "content_sha256": content_sha256, "metrics": metrics, "html": html})
        source_status.append({"source_id": source_id, "source_type": "target_url", "source_uri": clean_final, "status": "observed", "message": "The explicit public URL snapshot was parsed.", "observations": _public_observations(metrics)})

    if failed_target_urls:
        normalized_brief["target_urls"] = failed_target_urls
    else:
        normalized_brief.pop("target_urls", None)
    if analyzed_sources:
        normalized_brief["source_html"] = [
            {
                "path": f"sources/{source['source_id']}.html",
                "source_uri": source["source_uri"],
                "sha256": source["content_sha256"],
                "source_id": source["source_id"],
                "source_type": source["source_type"],
            }
            for source in analyzed_sources
        ]
    else:
        normalized_brief.pop("source_html", None)

    source_fingerprints = [
        {
            "source_id": source["source_id"],
            "source_uri": source["source_uri"],
            "content_sha256": source["content_sha256"],
        }
        for source in analyzed_sources
    ]
    source_fingerprints.extend(
        {
            "source_id": source["source_id"],
            "source_uri": source["source_uri"],
            "status": "source_gap",
        }
        for source in source_status
        if source["status"] == "source_gap"
    )
    identity_brief = dict(normalized_brief)
    if analyzed_sources:
        identity_brief["source_html"] = [
            {
                "source_uri": source["source_uri"],
                "sha256": source["content_sha256"],
                "source_id": source["source_id"],
                "source_type": source["source_type"],
            }
            for source in analyzed_sources
        ]
    canonical = json.dumps(
        {
            "brief": identity_brief,
            "sources": source_fingerprints,
            **({"execution_mode": execution_mode} if execution_mode != "legacy" else {}),
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    run_id = _stable_id("run", "diagnose", canonical)
    ledger_records = [{**record, "status": "provided"} for record in provided]
    for source in analyzed_sources:
        evidence_id = _stable_id(
            "ev",
            source["source_uri"],
            source["content_sha256"],
        )
        source["evidence_id"] = evidence_id
        source_label = "User-provided HTML snapshot" if source["source_type"] == "source_html" else "Directly fetched page snapshot"
        ledger_records.append(
            {
                "evidence_id": evidence_id,
                "claim": f"{source_label} used for structural observations; sha256={source['content_sha256']}.",
                "source_uri": source["source_uri"],
                "status": "provided" if source["source_type"] == "source_html" else "unverified",
            }
        )

    findings: list[dict[str, Any]] = []
    if brief["scope"] == "brand":
        scores, findings = _brand_findings(run_id, analyzed_sources, provided)
    else:
        score_sets: list[dict[str, int]] = []
        for source in analyzed_sources:
            source_scores, source_findings = _page_findings(run_id, source["source_id"], source["evidence_id"], source["metrics"])
            score_sets.append(source_scores)
            findings.extend(source_findings)
        if score_sets:
            scores = {name: round(sum(item[name] for item in score_sets) / len(score_sets)) for name in score_sets[0]}
        else:
            scores = {name: 0 for name in ("discoverability", "structure", "extractability", "evidence", "authority", "freshness")}
            findings.append(_finding(run_id, "source-coverage", "No page source was available for structural diagnosis.", "Provide a retrievable public URL or a source_html fixture.", severity="warning", source_kind="input_gap", evidence_id=None))
        for record in provided:
            findings.append(_finding(run_id, "provided-evidence", f"Provided evidence states: {record['claim']}", "Verify this claim against its authoritative source before publication.", severity="opportunity", source_kind="provided", evidence_id=record["evidence_id"]))

    if not analyzed_sources and brief["scope"] in {"site", "page"}:
        limitations.append("No page structure was observed; page-level scores are zero and indicate missing input coverage.")
    if not brief.get("target_urls") and not any(
        source["source_type"] == "target_url" for source in analyzed_sources
    ):
        limitations.append("No live URL was requested, so network availability and current published-page state were not assessed.")
    limitations = list(dict.fromkeys(limitations))
    degraded = any(item["status"] == "source_gap" for item in source_status) or (brief["scope"] in {"site", "page"} and not analyzed_sources)
    diagnosis_artifact = {
        "protocol_version": PROTOCOL_VERSION,
        "run_id": run_id,
        "subject": normalized_brief["subject"],
        "scope": brief["scope"],
        "status": "degraded" if degraded else "completed",
        "scores": scores,
        "findings": findings,
        "limitations": limitations,
        "source_status": source_status,
    }
    evidence_ids = [record["evidence_id"] for record in ledger_records]
    if len(evidence_ids) != len(set(evidence_ids)):
        raise ValueError("diagnosis evidence ledger contains duplicate evidence_id values")
    semantic_digest: str | None = None
    if execution_mode != "legacy":
        if brief["scope"] == "brand":
            observations = [gather_brand_observations([record["evidence_id"] for record in provided])]
        else:
            observations = [
                gather_page_observations(
                    source["metrics"],
                    source_id=source["source_id"],
                    evidence_id=source["evidence_id"],
                )
                for source in analyzed_sources
            ]
            if not observations:
                observations = [gather_brand_observations([])]
        audit_results = run_audit_catalog(observations)
        extension = build_audit_extension(
            audit_results,
            execution_mode=execution_mode,
            failures=execution_failures,
        )
        diagnosis_artifact.update(extension)
        semantic_digest = extension["semantic_digest"]
    validate_diagnosis(diagnosis_artifact, evidence_ids=evidence_ids)
    missing_evidence = [finding["statement"] for finding in findings if finding["source_kind"] == "input_gap"]
    evidence_ledger = {"protocol_version": PROTOCOL_VERSION, "run_id": run_id, "records": ledger_records, "missing_evidence": sorted(set(missing_evidence))}
    query_map, finding_queries = _build_diagnosis_query_map(
        run_id,
        findings,
        audience=normalized_brief.get("audience", "general user"),
    )
    opportunity_map = _opportunities(run_id, findings, finding_queries)
    diagnosis_funnel = _build_diagnosis_funnel(
        run_id,
        analyzed_sources,
        provided,
        source_status,
        ledger_records,
    )
    research_context = build_research_context(run_id, "geo-diagnose")
    warnings = list(limitations)
    warnings.extend(execution_failures)
    if any(finding["severity"] == "warning" for finding in findings):
        warnings.append("One or more diagnosis findings require remediation or additional evidence.")
    warnings = list(dict.fromkeys(warnings))
    quality_report = {
        "protocol_version": PROTOCOL_VERSION,
        "run_id": run_id,
        "passed_checks": [
            "diagnosis brief validated",
            "finding evidence lineage validated",
            "shared artifacts validated against protocol 1.0.0",
            "report rendered deterministically from structured diagnosis",
            f"execution mode recorded: {execution_mode}",
        ],
        "warnings": warnings,
        "failed_checks": [],
        "status": "passed-with-warnings" if warnings else "passed",
    }
    for artifact, schema_name in (
        (evidence_ledger, "evidence-ledger"),
        (query_map, "query-map"),
        (opportunity_map, "opportunity-map"),
        (quality_report, "quality-report"),
    ):
        validate_artifact(schema_name, artifact)

    report = _render_report(diagnosis_artifact, opportunity_map)
    lineage_inputs = [
        "input/diagnosis-brief.json",
        *(f"input/sources/{source['source_id']}.html" for source in analyzed_sources),
        "diagnosis.json",
        "diagnosis-funnel.json",
        "report.md",
        "evidence-ledger.json",
        "query-map.json",
        "opportunity-map.json",
        "quality-report.json",
        "research-context.json",
    ]
    manifest_paths = [*lineage_inputs, "run-lineage.json"]
    run_manifest = {
        "protocol_version": PROTOCOL_VERSION,
        "run_id": run_id,
        "created_at": created_at,
        "generator": {"name": "geo-seo-hub-diagnose", "version": GENERATOR_VERSION},
        "input_artifact": "input/diagnosis-brief.json",
        "artifacts": manifest_paths,
        "status": "completed-with-warnings" if warnings or degraded else "completed",
    }
    validate_artifact("run-manifest", run_manifest)

    run_path = output_path / run_id
    with ArtifactBus.transaction(output_path, run_id) as bus:
        bus.write_json("input/diagnosis-brief.json", normalized_brief)
        for source in analyzed_sources:
            bus.write_text(f"input/sources/{source['source_id']}.html", source["html"])
        bus.write_json("diagnosis.json", diagnosis_artifact)
        bus.write_json("diagnosis-funnel.json", diagnosis_funnel, "diagnosis-funnel")
        bus.write_text("report.md", report)
        bus.write_json("evidence-ledger.json", evidence_ledger, "evidence-ledger")
        bus.write_json("query-map.json", query_map, "query-map")
        bus.write_json("opportunity-map.json", opportunity_map, "opportunity-map")
        bus.write_json("quality-report.json", quality_report, "quality-report")
        bus.write_json("research-context.json", research_context, "research-context")
        lineage = build_run_lineage(
            bus.root,
            run_id=run_id,
            skill_id="geo-diagnose",
            status=run_manifest["status"],
            artifact_paths=lineage_inputs,
            metric_names=("finding-count", "warning-count"),
        )
        bus.write_json("run-lineage.json", lineage, "run-lineage")
        bus.write_json("run-manifest.json", run_manifest, "run-manifest")
        bus.publish(set(manifest_paths) | {"run-manifest.json"})
    result = {
        "run_id": run_id,
        "status": run_manifest["status"],
        "diagnosis_status": diagnosis_artifact["status"],
        "output": str(run_path.resolve()),
        "finding_count": len(findings),
        "warning_count": len(warnings),
        "execution_mode": execution_mode,
    }
    if semantic_digest is not None:
        result["semantic_digest"] = semantic_digest
    return result
