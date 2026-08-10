# Diagnosis Method

## Diagnosis brief

The JSON object requires `subject` and `scope`, where scope is `brand`, `site`, or `page`. It accepts `target_urls`, `source_html`, `evidence`, `locale`, `audience`, and `goals`. Supply at least one target URL, HTML source, or evidence record. All strings must contain non-whitespace text. The normalized brief trims `subject`, `locale`, `audience`, goals, paths, IDs, claims, and source URIs. Goal, target, and source lists preserve input order; evidence records sort by their generated IDs. HTML snapshot content is preserved exactly after decoding to the stored UTF-8 representation. Evidence records contain a unique input `evidence_id` label, `claim`, and absolute canonical `source_uri`. The runner replaces input labels with stable IDs derived from normalized claim and source URI content.

`source_html` accepts inline HTML, one snapshot object, or an array of at most five snapshot objects. A snapshot object requires `path` and may preserve `source_uri`, `sha256`, `source_id`, and `source_type`. A file-backed fixture must be a relative regular file inside the diagnosis brief directory. The reader walks from the brief directory through no-follow directory file descriptors, then size-checks and reads the same regular-file descriptor, so symbolic-link and path-replacement races fail closed. The runner caps each HTML source at 2 MB, snapshots every accepted local or remote page under `input/sources/`, and rewrites the copied brief to those self-contained relative paths. Re-running that normalized brief uses snapshots and requires no network for successful sources.

## Source boundary

Only explicit user-supplied HTTP(S) targets are fetched. Use public canonical URLs with no query string; fragments are removed before requests and identity calculation. The runner performs no sitemap discovery, crawl expansion, or link following. URLs with userinfo and hosts resolving to localhost, loopback, link-local, private, reserved, or another non-public address are rejected. The connection binds to a validated public IP while HTTPS keeps the original hostname for SNI and certificate checks. Each redirect resolves and binds again. Remote responses must explicitly declare `text/html` or `application/xhtml+xml`; a missing or different media type becomes `source_gap`. Fetching accepts at most five URLs, uses an 8-second per-source deadline beginning before DNS, a 30-second total fetch budget, a 2-second DNS cap within both remaining budgets, a 2 MB per-source cap, and a 5 MB total source cap. The diagnosis brief itself is capped at 1 MB. Budget is checked before DNS for every URL; DNS, connection, and reads receive only the smaller remaining budget, and exhausted remaining URLs become source gaps without resolution.

Unreachable or unavailable allowed sources become `source_gap` entries and limitations. Page observations are never filled from assumptions.

The Artifact Bus writes a complete run in a hidden same-filesystem staging directory, verifies its file set against `run-manifest.json`, and atomically publishes the final `run-*` directory. Failed and competing publications leave no partial visible run.

## Analysis

HTML parsing uses the Python standard library. Page signals include title, meta description, canonical, meta robots, H1-H3, main and article landmarks, lists, tables, FAQ-like text, JSON-LD, visible-text length, and internal/external link counts.

Brand scope checks coverage for identity, offering, audience, differentiation, proof, and contact facts. Site and page scopes score discoverability, structure, extractability, evidence, authority, and freshness.

Findings label their basis as `observed`, `provided`, `input_gap`, or `inferred`. Observed, provided, and inferred findings require `evidence_id`. Input gaps carry a null evidence ID and a concrete collection action.

`diagnosis-funnel.json` separates three stages. Candidate eligibility records direct page observations. Citation selection records evidence-lined readiness proxies. Answer absorption remains `not-observed` because diagnosis does not collect platform answers. Source ecosystem roles are derived only from input source type and hostname comparison; they do not assert ownership or authority.

Source SHA-256 digests bind the run and generated page evidence IDs to the analyzed content. Provided evidence IDs derive from normalized claim and source URI content. The remediation query map gives every opportunity a valid query lineage under protocol `1.0.0`.

## Interpretation boundary

Scores are bounded heuristics over supplied sources. They do not represent real AI-platform recall, ranking, citations, traffic, or market share. Read `research-context.json`, `diagnosis-funnel.json`, `limitations`, and `source_status` with every report.
