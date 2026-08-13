# Strategy output contract

The run contains `strategy-candidates.json`, `fidelity-report.json`, `experiment-plan.json`, `publication-handoff.json`, `strategy-memory.json`, `quality-report.json`, `run-lineage.json`, and `run-manifest.json` plus the input snapshot.

`publication-handoff.json` stays `awaiting_external_publication`. `strategy-memory.json` starts with zero promoted records. A downstream observer may promote a candidate only with a verified publication, unchanged query panel, completed observation window, passing fidelity, and positive weighted metric delta.
