# GEO SEO Hub

**Version 0.2.0 · Experimental · GEO-first · SEO-ready**

GEO SEO Hub is an open, protocol-first agent skill hub with active GEO workflows and an SEO-ready shared foundation. The current vertical slice turns generative engine optimization work into auditable, reusable runs through a registry-driven router, an Artifact Bus, deterministic discovery, evidence-lined diagnosis, offline content production, JSON Schema contracts, and four active skills.

The skills are Library-engineered packages while product behavior remains **Experimental**. `maturity_tier=library` describes packaging rigor and does not claim production outcome quality.

## Current scope

- `geo`: routes Chinese and English requests through the registry and reports unavailable routes honestly.
- `geo-discover`: converts a validated GEO brief into a deterministic query map, opportunity map, evidence ledger, run manifest, and quality report.
- `geo-diagnose`: evaluates explicit brand, site, or page sources and emits a structured diagnosis, deterministic report, evidence ledger, remediation query map, opportunity map, quality report, and run manifest.
- `geo-content`: creates evidence-lined titles, explainers, comparisons, rankings, page blueprints, refinements, and article-friendly artifacts as JSON, Markdown, and standalone HTML; DOCX/PDF are optional render layers.
- strategy, knowledge, publish, and measure: visible roadmap routes with `planned` status.

The resolver keeps single-intent routing minimal and exposes two exact multi-stage DAGs: `brand-baseline-lite` (discover → diagnose) and `content-campaign` (discover → content). A planned route is never executed; it returns the closest active suggestion, required inputs, and closest v0 artifact. Route requests are bounded to 8,000 characters and 16,384 UTF-8 bytes. See `skills/RESOLVER.md` and `docs/architecture.md`.

No connector, platform sampling, search volume, ranking, or conversion data is inferred. Missing evidence remains explicit in generated artifacts.

## GEO and SEO boundary

GEO SEO Hub treats GEO and SEO as related capability domains with a shared search foundation. Query intent, source evidence, brand facts, entity structure, content specifications, site parsing, quality reports, and Artifact Bus contracts can serve both domains.

Version 0.2.0 ships executable GEO discovery, diagnosis, content, and routing. Dedicated SEO workflows and outcome claims for technical SEO, SERP and keyword data, indexation, Core Web Vitals, internal linking, Search Console, and traffic measurement remain future Registry additions.

Version 0.2 establishes `geo-seo-hub` as the distribution and CLI namespace, `geo_seo_hub` as the Python module, and `share/geo-seo-hub` as the installed data root. The `geo-*` Skill IDs and Artifact Bus protocol `1.0.0` remain stable.

## Quick start

Supported Python range: 3.11-3.14.

```bash
git clone https://github.com/yaojingang/geo-seo-hub.git
cd geo-seo-hub
python3 -m venv .venv
.venv/bin/python -m pip install .
.venv/bin/geo-seo-hub --version
.venv/bin/geo-seo-hub route --text "帮我挖掘 AI 搜索问题"
```

For development and the full release gate:

```bash
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/python scripts/verify_all.py
```

Community packages:

```bash
python3 scripts/package.py --target all --channel community
python3 scripts/verify_packages.py
python3 scripts/install_simulation.py --target all
```

The eight artifacts are a source ZIP, one unified single-Skill ZIP, four provider Skill ZIPs, and Codex/Claude adapter ZIPs. Each ZIP supports `pip install .` from its extraction root. Unified and target adapters contain four parseable provider entries and wrappers. Every community artifact is `AGPL-3.0-only`; commercial metadata remains `inquiry_only`. Version `0.2.0` has no GitHub Release assets; build packages from a source checkout. See `docs/installation.md`.

Version 0.2 removes the pre-release 0.1 runtime aliases. Recreate the environment before installing 0.2; the exact historical mapping remains in the migration ledger and third-party notice.

The CLI prints JSON. The `--output` value is a runs root; discover, diagnose, and content write protocol `1.0.0` runs to `<output>/<run-id>/` and return that actual run directory. Content runs never access the network, snapshot relative source files for offline replay, escape user text in standalone HTML, and keep optional renderer failures explicit. If DOCX/PDF dependencies are missing, core output succeeds and the run manifest records `degraded` plus `missing_dependencies`. Install `.[render]` to request DOCX/PDF support. Diagnose fetches only explicit public HTTP(S) canonical URLs without query strings, accepts HTML/XHTML, performs no crawl expansion, and snapshots successful pages for offline replay. Unavailable or unsupported sources remain gaps. Its scores do not represent live AI-platform recall, ranking, or citation share.

## License and governance

The open-source repository is licensed under `AGPL-3.0-only`. Commercial licensing is currently `inquiry_only`; see `COMMERCIAL-LICENSING.md`. The contributor agreement remains under legal review, so external code merges are paused.

`make verify` and `python3 scripts/verify_all.py` run the complete repository, evidence, test, evaluation, package, and isolated-install gates. `make repo-verify` runs the fast structural check. The gates use synthetic fixtures and require no external service or secret.

Copyright © 2026 姚金刚 / Yao.
