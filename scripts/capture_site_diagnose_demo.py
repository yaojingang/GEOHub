#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "reports" / "examples" / "geo-site-diagnose-demo.html"
OUTPUTS = (
    ("desktop", 1440, 1000, ROOT / "reports" / "examples" / "geo-site-diagnose-demo-desktop.png"),
    ("mobile", 390, 844, ROOT / "reports" / "examples" / "geo-site-diagnose-demo-mobile.png"),
)
MODULE_OUTPUTS = (
    ("discovery", "#discovery", ROOT / "reports" / "examples" / "geo-site-diagnose-demo-discovery.png"),
    ("actions", "#actions", ROOT / "reports" / "examples" / "geo-site-diagnose-demo-actions.png"),
)
VALIDATION_VIEWPORTS = (("desktop-1280", 1280, 900), ("mobile-375", 375, 812), ("narrow-320", 320, 740))
EXPECTED_CHARTS = 23
EXPECTED_FUNNEL_RETENTION = [90, 100, 100, 100]


def _validate(page, label: str, width: int) -> None:
    page.wait_for_function("window.__GEO_REPORT_READY__ !== undefined")
    ready = page.evaluate("window.__GEO_REPORT_READY__")
    if ready["figures"] != EXPECTED_CHARTS or ready["charts"] != EXPECTED_CHARTS:
        gaps = page.locator('[data-chart-status="gap"]').evaluate_all("elements => elements.map(element => element.dataset.chart)")
        raise RuntimeError(f"{label} charts={ready}, gaps={gaps}")
    overflow = page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
    if overflow > 1:
        raise RuntimeError(f"{label} horizontal overflow={overflow}px")
    if page.locator(".report-nav").evaluate("element => getComputedStyle(element).position") != "sticky":
        raise RuntimeError(f"{label} navigation is not sticky")
    funnel_retention = page.evaluate(
        """() => {
          const element = document.querySelector('[data-chart="funnel"]');
          const chart = element && echarts.getInstanceByDom(element);
          if (!chart) return null;
          const data = chart.getOption().series[1].data;
          return data.map(item => typeof item === "object" ? item.value : item);
        }"""
    )
    if funnel_retention != EXPECTED_FUNNEL_RETENTION:
        raise RuntimeError(f"{label} funnel retention is distorted: {funnel_retention}")
    heading_geometry = page.locator(".module").evaluate_all(
        """modules => modules.map(module => {
          const box = selector => module.querySelector(selector).getBoundingClientRect();
          const title = box('.module-header h2');
          const description = box('.module-header p');
          const index = box('.module-index');
          const verdictLabel = box('.module-verdict strong');
          const verdictText = box('.module-verdict span');
          return {
            id: module.id,
            lefts: [title.left, description.left, index.left, verdictLabel.left, verdictText.left],
            indexBottom: index.bottom,
            titleTop: title.top,
            verdictLabelBottom: verdictLabel.bottom,
            verdictTextTop: verdictText.top,
          };
        })"""
    )
    for geometry in heading_geometry:
        if max(geometry["lefts"]) - min(geometry["lefts"]) > 1:
            raise RuntimeError(f"{label} module {geometry['id']} heading left edges diverge: {geometry['lefts']}")
        if geometry["indexBottom"] >= geometry["titleTop"]:
            raise RuntimeError(f"{label} module {geometry['id']} index is not above its title")
        if geometry["verdictTextTop"] <= geometry["verdictLabelBottom"]:
            raise RuntimeError(f"{label} module {geometry['id']} verdict content did not wrap to a new line")
    mobile_display = page.locator(".nav-mobile").evaluate("element => getComputedStyle(element).display")
    if (width < 1024 and mobile_display == "none") or (width >= 1024 and mobile_display != "none"):
        raise RuntimeError(f"{label} navigation breakpoint is inconsistent")
    if width >= 1024:
        groups = page.locator(".chart-panel").evaluate_all(
            """elements => Object.values(elements.reduce((groups, element) => {
              const box = element.getBoundingClientRect();
              const key = Math.round(box.top);
              (groups[key] ||= []).push(Math.round(box.height * 10) / 10);
              return groups;
            }, {})).filter(group => group.length > 1)"""
        )
        if any(max(group) - min(group) > 2 for group in groups):
            raise RuntimeError(f"{label} chart rows are not equal height: {groups}")
        page.locator("#evidence").scroll_into_view_if_needed()
        page.wait_for_timeout(150)
        active = page.locator('.nav-links a[href="#evidence"]').get_attribute("aria-current")
        if active != "true":
            raise RuntimeError(f"{label} scroll spy did not activate the evidence module")
    print_state = page.evaluate(
        """() => {
          window.dispatchEvent(new Event('beforeprint'));
          const opened = [...document.querySelectorAll('details')].every(item => item.open);
          window.dispatchEvent(new Event('afterprint'));
          return opened;
        }"""
    )
    if not print_state:
        raise RuntimeError(f"{label} print preparation did not open every evidence table")


def main() -> int:
    if not REPORT.is_file():
        raise FileNotFoundError("generate the demo report before capturing screenshots")
    with sync_playwright() as runtime:
        try:
            browser = runtime.chromium.launch(headless=True)
        except Exception:
            browser = runtime.chromium.launch(channel="chrome", headless=True)
        try:
            for label, width, height in VALIDATION_VIEWPORTS:
                page = browser.new_page(viewport={"width": width, "height": height}, device_scale_factor=1)
                console_errors: list[str] = []
                external_requests: list[str] = []
                page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
                page.on("request", lambda request: external_requests.append(request.url) if request.url.startswith(("http://", "https://")) else None)
                page.goto(REPORT.resolve().as_uri(), wait_until="networkidle")
                _validate(page, label, width)
                if console_errors or external_requests:
                    raise RuntimeError(f"{label} report browser errors={console_errors}, external_requests={external_requests}")
                page.close()
            for label, width, height, output in OUTPUTS:
                page = browser.new_page(viewport={"width": width, "height": height}, device_scale_factor=1)
                console_errors: list[str] = []
                external_requests: list[str] = []
                page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
                page.on("request", lambda request: external_requests.append(request.url) if request.url.startswith(("http://", "https://")) else None)
                page.goto(REPORT.resolve().as_uri(), wait_until="networkidle")
                _validate(page, label, width)
                if console_errors or external_requests:
                    raise RuntimeError(f"{label} report browser errors={console_errors}, external_requests={external_requests}")
                page.evaluate("window.scrollTo(0, 0)")
                page.wait_for_timeout(100)
                page.screenshot(path=str(output), full_page=False)
                page.close()
            for label, selector, output in MODULE_OUTPUTS:
                page = browser.new_page(viewport={"width": 1440, "height": 1000}, device_scale_factor=1)
                console_errors: list[str] = []
                external_requests: list[str] = []
                page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
                page.on("request", lambda request: external_requests.append(request.url) if request.url.startswith(("http://", "https://")) else None)
                page.goto(REPORT.resolve().as_uri(), wait_until="networkidle")
                _validate(page, label, 1440)
                if console_errors or external_requests:
                    raise RuntimeError(f"{label} report browser errors={console_errors}, external_requests={external_requests}")
                page.locator(".report-nav").evaluate("element => { element.style.visibility = 'hidden'; }")
                if selector == "#actions":
                    page.locator("#actions details").evaluate_all("elements => elements.forEach(element => { element.open = false; })")
                target = page.locator(selector)
                target.scroll_into_view_if_needed()
                page.wait_for_timeout(100)
                target.screenshot(path=str(output))
                page.close()
        finally:
            browser.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
