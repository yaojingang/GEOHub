# Migration to 0.6.0

GEOHub 0.6.0 keeps Artifact Bus protocol `1.0.0`, existing Skill IDs, provider commands, Python imports, and generated run directories compatible. Router execution authority becomes stricter, and durable workflow state moves from `1.0.0` to `2.0.0`.

## Router behavior

Route responses now include a decision object with `type`, matched and uncovered intents, score, threshold version, and alternatives. Requests outside the GEO domain, fully negated requests, and vague text without an explicit GEO capability intent return `abstain` with `runnable=false`. Connected multi-intent requests without one exact active workflow return `clarify`.

The reviewed changes to the 373-case legacy corpus are recorded in `evals/router_behavior_migration_0.6.json`. Every recorded change preserves the selected Skill and workflow while closing execution authority. No unexplained legacy behavior change is accepted by the test gate.

## Semantic model

Core installation remains deterministic and has no model dependency. Install the optional extra and prepare the model during an explicit network-enabled setup step:

```bash
python3 -m pip install '.[semantic]'
python3 scripts/prepare_semantic_model.py --cache-dir .model-cache
```

At runtime, pass `--semantic-cache .model-cache`. FastEmbed is opened with local-files-only behavior. When the package or model cache is absent, the CLI uses the lexical baseline and reports `semantic_status=unavailable`; `--lexical-only` reports `semantic_status=disabled`. The 600-case natural-language dataset carries proposed labels; the semantic promotion gate stays locked until human adjudication is recorded.

## TaskPlan and workflow execution

Compile a plan:

```bash
geo-seo-hub route \
  --text "先拓词，再诊断网站" \
  --plan-output task-plan.json
```

Create an input map whose keys match `required_inputs`, then start the workflow. The output directory must stay beneath the workflow state directory.

```bash
geo-seo-hub workflow start \
  --plan task-plan.json \
  --state workflow/workflow-state.json \
  --inputs workflow/inputs.json \
  --output workflow/runs
```

Use `workflow status`, `approve`, `resume-external`, `retry`, and `abort` for the remaining lifecycle. Required input files receive SHA-256 digests when state is created and are rechecked before every bound read. Publication and observation evidence references are relative to the state directory, schema-validated before the workflow advances, recorded with SHA-256, and rechecked whenever durable state is loaded. Each local Skill process has a hard timeout plus bounded output capture, artifact count, and artifact size.

## Workflow state migration

Version `1.0.0` state does not load as executable state in 0.6.0. Migrate it explicitly:

```bash
geo-seo-hub workflow migrate --state workflow/workflow-state.json
```

The command validates legacy checkpoint checksums, creates `workflow-state.json.v1.backup` with exclusive permissions, writes a validated `2.0.0` state atomically, and becomes idempotent after success. If the backup path already exists while the source still reports v1, migration stops for operator review.

## Strategy observation loop

`strategy-observation-loop` is active in 0.6.0. Its TaskPlan sequence is:

1. `geo-strategy`
2. human approval of the exact handoff and rollback boundary
3. external `publication-receipt`
4. external `engine-observation-bundle`
5. `geo-measure`

GEOHub performs the local strategy and measurement nodes. Publication and platform observation remain external activities represented by validated evidence.

## Rollback

Keep generated run directories and the v1 backup. Roll back code, Registry, TaskPlan schema, workflow-state schema, router, CLI, and workflow runtime together. A 0.5 runtime can read its original v1 backup; it cannot interpret TaskPlans or v2 state.
