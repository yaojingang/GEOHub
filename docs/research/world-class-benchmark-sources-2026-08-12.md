# GEOHub world-class benchmark source ledger

Snapshot date: 2026-08-12, Asia/Shanghai  
Local revision: `9c21f09ee30998172267eebefcd114b7e6438134`  
Scope: GEO SEO Hub 0.2.0, four active skills, shared Python runtime, schemas, tests, package and release gates.

## Local evidence

- `README.md`, `docs/architecture.md`, `docs/artifact-contract.md`, `docs/evaluation-policy.md`
- `registry/skills.yaml`, `skills/RESOLVER.md`
- Four `SKILL.md` files, manifests, interface contracts, references, Skill IR and output scorecards
- `src/geo_seo_hub/` runtime, eight JSON Schemas, packaging scripts and CI workflow
- `reports/eval-summary.md`, `reports/yao-meta-gates.md`, `reports/trust-report.md`, `reports/package-verification.md`, `reports/install-simulation.md`, `reports/skill-atlas.json`
- Test run on 2026-08-12: 483 collected, 482 passed, 1 skipped
- Existing deterministic evaluation evidence: 373 router cases, 27 skill trigger cases and 20 output contract cases, all reported as passing

## Selected world-class comparators

GitHub community figures are an API snapshot taken on 2026-08-12. Stars support project reach and adoption only. Technical fit and primary-source evidence determine selection.

| GEOHub element | Selected comparator | Community snapshot | Primary reason for selection |
| --- | --- | ---: | --- |
| Skill package format | [Agent Skills](https://github.com/agentskills/agentskills) | 24,178 stars | Open skill format, progressive disclosure, validation and cross-client portability |
| Capability registry | [Backstage](https://github.com/backstage/backstage) | 34,121 stars | Typed catalog entities, ownership, lifecycle, discoverability and plugin ecosystem |
| Intent routing | [Semantic Router](https://github.com/aurelio-labs/semantic-router) | 3,797 stars | Semantic and hybrid routing, local encoders and threshold optimization |
| Durable workflows | [LangGraph](https://github.com/langchain-ai/langgraph) | 39,531 stars | Stateful graphs, checkpoints, interrupts, recovery and human input |
| Typed contracts | [Pydantic](https://github.com/pydantic/pydantic) | 28,528 stars | One typed source for validation, serialization and JSON Schema generation |
| Run and artifact lifecycle | [MLflow](https://github.com/mlflow/mlflow) | 27,480 stars | Runs, artifacts, traces, evaluations, lineage and production monitoring |
| Evidence lineage | [OpenLineage](https://github.com/OpenLineage/OpenLineage) | 2,599 stars | Extensible run, job and dataset lineage standard built on OpenAPI |
| Query discovery | [HyDE](https://github.com/texttron/hyde) | 583 stars | Research-backed zero-shot query transformation for dense retrieval |
| GEO objective and benchmark | [GEO, KDD 2024](https://arxiv.org/abs/2311.09735) | paper | GEO-bench and black-box visibility optimization established a scientific target |
| Closed-loop GEO learning | [MAGEO](https://github.com/Wu-beining/MAGEO) | 39 stars | ACL 2026 research code with multi-agent planning, fidelity gates, memory and iterative scoring |
| Page diagnosis | [Lighthouse](https://github.com/GoogleChrome/lighthouse) | 30,650 stars | Gatherer, audit, scoring, report and custom-audit architecture |
| Evidence-lined content | [STORM](https://github.com/stanford-oval/storm) | 30,929 stars | Perspective-guided questions, research, outline, cited drafting and polishing |
| Comparison and ranking | [Scikit-Criteria](https://github.com/quatrope/scikit-criteria) | 103 stars | MCDA method library with TOPSIS, ELECTRE and scientific Python integration |
| Agent evaluation | [Inspect AI](https://github.com/UKGovernmentBEIS/inspect_ai) | 2,529 stars | Tasks, solvers, scorers, model-graded evals, tools and inspectable logs |
| Factual output evaluation | [Ragas](https://github.com/vibrantlabsai/ragas) | 15,291 stars | Objective and model-assisted metrics, test generation and production feedback loops |
| Observability and drift | [OpenTelemetry](https://github.com/open-telemetry/opentelemetry-specification) | 4,302 stars | Portable traces, metrics, logs, context propagation and collector architecture |
| Supply-chain provenance | [SLSA](https://github.com/slsa-framework/slsa) | 1,908 stars | Verifiable build provenance and supply-chain integrity levels |
| Knowledge operations | [GraphRAG](https://github.com/microsoft/graphrag) | 35,446 stars | Entity and relationship extraction, community summaries, local and global retrieval |
| Secure network input | [OWASP SSRF Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html) | standard | Canonical allowlist, DNS, redirect and network-boundary guidance for SSRF defense |

## Primary-source observations used in the report

- Agent Skills recommends progressive disclosure: metadata at discovery, `SKILL.md` at activation and resources on demand.
- Backstage centers a software catalog with typed entities, owners, lifecycle metadata, documentation and templates.
- Semantic Router defines routes through sample utterances, supports local and remote encoders, hybrid routing and threshold optimization.
- LangGraph provides stateful graph execution with durability, checkpoints and human interruption points.
- MLflow combines traces, evaluation, prompt management, run tracking, artifact storage and monitoring.
- OpenLineage defines extensible run, job and dataset entities with custom facets.
- HyDE generates a hypothetical document, encodes it and retrieves real documents in that embedding space.
- The foundational GEO paper introduces GEO-bench and a black-box optimization framework for generative-engine visibility.
- MAGEO adds preference profiles, multi-candidate editing, answer-level DSV-CF metrics, a fidelity gate, hierarchical memory and early stopping.
- Lighthouse separates data gathering, audits, scoring and reports, and supports custom audits and CI assertions.
- STORM separates research, outline generation, article generation and polishing. It uses perspective-guided questions and source-grounded simulated conversations.
- Inspect AI supports prompt engineering, tool use, multi-turn dialogue and model-graded evaluations. Its companion collection contains reusable evaluations.
- Ragas combines metrics, test generation, integrations and production feedback loops.
- OpenTelemetry represents traces as DAGs of spans and standardizes traces, metrics, logs, baggage and context propagation.
- SLSA makes build provenance independently verifiable and ties artifacts to source and trusted builders.
- GraphRAG extracts structured entities and relationships, then supports local, global, DRIFT and basic retrieval paths.

## Evidence limits

- The assessment contains expert scores. They organize the comparison and do not represent a laboratory benchmark.
- GitHub stars are time-sensitive adoption signals. They do not prove algorithmic quality.
- GEOHub has no provider-backed model runs, public live-engine benchmark, recorded human blind-review decisions or adoption telemetry in the audited snapshot.
- MAGEO is new research code with limited community adoption. It was selected for domain fit and method relevance.
- Scikit-Criteria has a smaller community footprint. It was selected for methodological depth and reproducible MCDA primitives.
