# Routing Contract

The registry at 'registry/skills.yaml' is the source of truth.

- 'active': runnable only when 'entry' points to an existing skill.
- 'pending-implementation': reserved protocol surface with no runnable entry.
- 'planned': roadmap intent with no runnable entry.
- 'active_placeholder' must remain false for every unavailable route.

Routing uses normalized phrase matching plus an optional cache-only semantic scorer. Unmatched and fully negated requests abstain. Broad requests with explicit GEO language may select `geo`. Equal lexical scores and close semantic scores are disclosed through `alternatives` and may require clarification.

The router may suggest 'geo-discover' when a downstream route is unavailable. A suggestion is not an assertion that discovery fulfills the unavailable stage.

`geo-discover`, `geo-diagnose`, `geo-content`, `geo-measure`, `geo-strategy`, and `geo-knowledge` are active alongside the `geo` umbrella router. `geo-publish` remains a planned route with no runnable entry. `seo` is a compatibility package and is not a Registry route in 0.6.0.

Workflow recipes carry their own status. The router exposes `workflow` for an exact recipe match, including its status and runnable state. A pending workflow keeps every step disabled as a group, even when its individual skills are active. The top-level `skill_id` identifies the first actual Skill node.

`strategy-observation-loop` is active because its TaskPlan and workflow-state runtime enforce publication approval, a validated publication receipt, a validated engine observation bundle, and measurement in that order. GEOHub does not publish content or collect platform observations inside this workflow.

Every route includes `decision.type`, `matched_intents`, `uncovered_intents`, `score`, `threshold_version`, and `alternatives`. Only `single_skill` and active `workflow` decisions are runnable. `clarify`, `abstain`, and `unavailable` close execution authority.
