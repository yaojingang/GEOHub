# Migration to 0.7.0

GEOHub 0.7.0 keeps Artifact Bus protocol `1.0.0`, existing Skill IDs, provider commands, Python imports, workflow state `2.0.0`, and previously published run directories compatible.

## New capability

`geo-site-diagnose` accepts one public HTTP(S) URL and writes a new run directory with bounded discovery, representative-page sampling, evidence-linked scores, page analyses, a remediation backlog, and `report.html`.

The standalone report uses internal format version `2`: a pure-white ten-module layout, 23 chart views in the complete fixture, sticky section navigation, and evidence-aware chart fallbacks. Artifact Bus protocol and Skill contract versions remain `1.0.0`, so existing run consumers stay compatible.

```bash
geo-seo-hub site-diagnose --url https://example.com --output runs
```

Existing `geo-diagnose --input ... --output ...` behavior stays available for brand diagnosis, single-page analysis, replay snapshots, and up to five explicit sources. Requests that explicitly ask for automatic multi-page discovery and a visual site report route to `geo-site-diagnose`.

## Packaging

The active capability count increases from seven to eight. A full community build now produces twelve archives. Unified and target adapters include `run_site_diagnose.py` plus the vendored Apache ECharts runtime and notices.

## Optional browser rendering

HTTP remains the default collection path. Install `.[render]` and a Playwright Chromium browser to render detected JavaScript shells. Missing browser support produces `render_gap` evidence and leaves the run replayable.

## Rollback

Remove individual 0.7 site-diagnosis run directories when their output is no longer needed. A code rollback should move the Site Diagnose runtime, Registry entry, schemas, CLI, package asset, wrapper, and documentation together. Existing 0.6 runs require no conversion.
