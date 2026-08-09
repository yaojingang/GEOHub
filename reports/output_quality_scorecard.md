# Output Quality Scorecard

Release: 0.2.0 Experimental

| Area | Evidence | Status |
| --- | --- | --- |
| Routing | 60+ Chinese/English active, planned, unknown, mixed, and adversarial cases | covered |
| Discovery determinism | Stable-ID and repeat-output tests | covered |
| Evidence discipline | Missing-evidence fixture and warning assertion | covered |
| Artifact contracts | Eight schemas plus generated-artifact validation | covered |
| External platform accuracy | No connector or sampling implementation | missing evidence |
| Content offline boundary | Contract and source-shortfall cases | covered |
| Diagnosis retrieval safety | SSRF/fd/size/timeout and replay tests | covered |
| Community ZIP installation | Per-archive fresh venv, `pip install .`, route-entry resolution, and provider fixture execution | covered |
| Optional rendering degradation | Manifest records `degraded` and exact missing dependencies while core output succeeds | covered |
| Python compatibility | CI 3.11/3.13/3.14 plus local fresh Python 3.14 evidence | covered |
| Human blind review | Pack generated; no decisions recorded | missing evidence |
| Public benchmark quality | No real-platform benchmark run in this phase | missing evidence |

Promotion beyond Experimental requires the missing external evidence and review of downstream diagnose/content stages. Experimental 0.2.0 source publication remains within the current gate scope.
