# Installation

GEO SEO Hub uses `geo-seo-hub` for the Python distribution and CLI, and `geo_seo_hub` for the Python module.

Supported Python range: 3.11-3.14.

CI covers Linux on Python 3.11-3.14 and macOS installation simulation. Windows remains unsupported and unclaimed in 0.6.0.

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
| Source ZIP | Reproducible source snapshot, CLI use, development, tests, evals, and local package builds |
| Unified ZIP | One root Skill with all seven active provider entries |
| `geo` provider ZIP | Registry-driven routing and workflow orchestration |
| Discover, Diagnose, Content, Measure, Strategy, or Knowledge provider ZIP | Installing one active capability as the root Skill |
| Codex or Claude ZIP | Target-specific adapter layout with all seven provider entries |

Version `0.6.0` produces eleven community archives. The source ZIP includes `tests/`, `evals/`, the hash-locked CI dependency set, and the verification scripts they require. This source snapshot carries no independently verified GitHub Release assets. Build artifacts from a source checkout with `python3 scripts/package.py --target all --channel community`, or run the attested release workflow. Install a provider, unified, Codex, or Claude ZIP by safely extracting it into the target's skill directory. Each adapter contains one `SKILL.md`, runtime source, schemas, registry, project metadata, version, and legal notices.

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

Update Python imports to `geo_seo_hub`. Existing Skill IDs stay unchanged. Version 0.3 added `geo-measure`; version 0.5 activated `geo-strategy` and `geo-knowledge`; version 0.6 adds TaskPlan and gated workflow execution. Artifact protocol `1.0.0` stays unchanged. Workflow state uses version `2.0.0`; see [migration-0.6.md](migration-0.6.md).

## Release evidence and verification

After building and verifying all eleven ZIPs:

```bash
python3 scripts/generate_sbom.py
python3 scripts/generate_provenance.py
python3 scripts/verify_provenance.py
python3 scripts/render_production_readiness.py
```

Local provenance declares `local-unsigned`, `trusted: false`, and no SLSA level. A GitHub Actions release build uses `actions/attest@v4`. Verify each CI artifact with `gh attestation verify <artifact> -R yaojingang/geo-seo-hub` before making a trusted-builder statement.
