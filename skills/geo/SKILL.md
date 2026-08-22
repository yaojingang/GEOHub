---
name: geo
description: Route GEO and generative engine optimization requests to an available GEOHub capability. Use for broad GEO requests, GEOHub workflow selection, capability checks, or requests spanning discovery, brand/site/page diagnosis, content, strategy, knowledge, publishing, and measurement.
---

# GEOHub

## Workflow

1. Read `references/routing-contract.md` and the suite resolver contract at `../RESOLVER.md`.
2. Run `python3 scripts/run_route.py --text "<request>"` or `python -m geo_seo_hub route --text "<request>"`. Add `--lexical-only` for the deterministic baseline or `--plan-output <path>` to compile a TaskPlan.
3. Dispatch only when `decision.type` is `single_skill` or `workflow`, `runnable` is true, and the selected Skill has a non-null entry.
4. For `clarify`, `abstain`, `pending-implementation`, or `planned`, preserve the reported reason, alternatives, required inputs, and execution boundary.

## Output contract

Return the selected skill ID, lifecycle status, runnable flag, reason, entry path, suggestion, typed decision object, and optional stable workflow DAG. When requested, write a validated TaskPlan with its digest and status.

## Boundaries

This skill selects and plans capabilities. Workflow execution requires an explicit TaskPlan, file-backed input map, bounded output root, and every declared approval or external-evidence gate. It does not simulate unavailable stages.
