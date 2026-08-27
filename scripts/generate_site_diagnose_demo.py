#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import socket
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from geo_seo_hub.diagnose import FetchResult, SourceUnavailable  # noqa: E402
from geo_seo_hub.site_diagnose import site_diagnose  # noqa: E402

FIXTURE = ROOT / "tests" / "fixtures" / "site-diagnose-demo"
EXAMPLE = ROOT / "reports" / "examples" / "geo-site-diagnose-demo.html"


def fixture_fetcher(url: str) -> FetchResult:
    manifest = json.loads((FIXTURE / "manifest.json").read_text(encoding="utf-8"))
    parsed = urlsplit(url)
    if parsed.netloc != "demo.geohub.invalid":
        raise SourceUnavailable("fixture blocks off-host access")
    if parsed.path == "/robots.txt":
        path = FIXTURE / "robots.txt"
        content_type = "text/plain; charset=utf-8"
    elif parsed.path == "/sitemap.xml":
        path = FIXTURE / "sitemap.xml"
        content_type = "application/xml; charset=utf-8"
    else:
        relative = manifest["pages"].get(parsed.path)
        if relative is None:
            raise SourceUnavailable(f"fixture URL is unavailable: {parsed.path}")
        path = FIXTURE / relative
        content_type = "text/html; charset=utf-8"
    return FetchResult(final_url=url, body=path.read_bytes(), content_type=content_type)


def public_fixture_resolver(host: str, port: int, *_args, **_kwargs):
    return [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("93.184.216.34", port))]


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="geohub-site-demo-") as raw:
        result = site_diagnose(
            "https://demo.geohub.invalid/",
            Path(raw),
            locale="zh-CN",
            max_pages=10,
            render_mode="http",
            clock=lambda: datetime(2026, 8, 25, 8, 0, tzinfo=timezone.utc),
            fetcher=fixture_fetcher,
            resolver=public_fixture_resolver,
            demo_fixture=True,
        )
        EXAMPLE.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(result["report"], EXAMPLE)
        payload = {**result, "report": str(EXAMPLE.relative_to(ROOT)), "run_directory": "temporary deterministic fixture run"}
        print(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
