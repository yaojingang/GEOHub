# Installation

GEO SEO Hub uses `geo-seo-hub` for the Python distribution and CLI, and `geo_seo_hub` for the Python module.

Supported Python range: 3.11-3.14.

```bash
git clone https://github.com/yaojingang/geo-seo-hub.git
cd geo-seo-hub
python3 -m venv .venv
.venv/bin/python -m pip install .
.venv/bin/geo-seo-hub --version
.venv/bin/geo-seo-hub route --text "Discover AI search questions"
```

## Choose a package

| Package | Use it for |
|---|---|
| Source ZIP | Full source checkout, CLI use, development, and local package builds |
| Unified ZIP | One root Skill with all five active provider entries |
| `geo` provider ZIP | Registry-driven routing and workflow orchestration |
| Discover, Diagnose, Content, or Measure provider ZIP | Installing one active capability as the root Skill |
| Codex or Claude ZIP | Target-specific adapter layout with all five provider entries |

Version `0.3.0` has no GitHub Release or prebuilt release assets. Build the nine community artifacts from a source checkout with `python3 scripts/package.py --target all --channel community`. Install a provider, unified, Codex, or Claude ZIP by safely extracting it into the target's skill directory. Each adapter contains one `SKILL.md`, runtime source, schemas, research registry, capability registry, project metadata, version, and legal notices.

Every community ZIP has a self-contained `pyproject.toml` and runtime data layout. For direct command-line use after extraction, create an isolated environment and install that extracted directory before invoking its wrapper:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install .
.venv/bin/python scripts/run_route.py --help
```

Provider hosts may supply the same declared dependencies in their managed runtime. The install simulation provisions a fresh environment for every extracted ZIP, runs `pip install .` from that ZIP root, resolves a routed provider entry, and invokes a provider wrapper with a synthetic fixture.

Run `python3 scripts/verify_packages.py` before distribution and `python3 scripts/install_simulation.py --target all` after building. Generated `dist/` archives and temporary installation roots are scratch outputs and remain uncommitted.

For development, install `.[dev]` and run `python3 scripts/verify_all.py`. The project-level `make verify` target invokes the same complete gate; `make repo-verify` is the fast structural check.

## Namespace migration from pre-release 0.1 snapshots

Development snapshots before 0.2 used a retired runtime namespace recorded in the [migration source ledger](migration-source-ledger.md). Version 0.2 uses the following canonical names:

| Surface | Version 0.2 name |
|---|---|
| Distribution and CLI | `geo-seo-hub` |
| Python module | `geo_seo_hub` |
| Installed data | `share/geo-seo-hub` |
| Artifact generators and URNs | `geo-seo-hub-*` and `urn:geo-seo-hub:*` |
| Source, unified, Codex, and Claude ZIPs | `geo-seo-hub-*.zip` |

Create a fresh environment for 0.2. Existing development environments should remove the retired snapshot before reinstalling; the exact removal command is recorded with the historical mapping in the migration ledger.

```bash
python3 -m pip install .
geo-seo-hub --version
```

Update Python imports to `geo_seo_hub`. The `geo`, `geo-discover`, `geo-diagnose`, and `geo-content` Skill IDs and protocol `1.0.0` stay unchanged; version 0.3 adds the active `geo-measure` ID.
