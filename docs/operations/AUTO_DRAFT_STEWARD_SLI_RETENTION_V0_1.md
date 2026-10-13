# Auto Draft PR steward: operations and retention decision

**Issue:** #752. **Status:** owner-facing decision record template, not GA.

The Auto Draft steward opens limited Draft PR shells; it never verifies code,
marks a PR ready, or merges. Existing routine Actions artifacts are retained
for a bounded 14-day window, which is not an archival guarantee.

## Service indicators
| Indicator | Warning | Evidence |
| --- | --- | --- |
| Scheduled job failure | recurring failures across scheduled runs | run IDs and timestamps |
| GitHub API reserve block | multiple consecutive budget blocks | retained report counts |
| Head-moved race | sustained increase above local baseline | recorded exact heads |
| Already-existing PR race | sustained increase | bounded dedupe observations |
| Evidence upload failure | any missing mandatory report | artifact inventory |

The owner must define numeric warning thresholds after observing a baseline.
Unknown workflow data is UNKNOWN, not healthy. A CI queue backlog is a
backpressure signal, not permission to bypass rate limits.

## Retention owner decision
Before GA, explicitly record which governed owner decides (a) that 14 days
is sufficient without long-term archive or (b) that selected evidence will be
promoted to a durable store. Record classification, expected retention,
privacy access, deletion policy and verification digests. Do not save every
15-minute report forever by default.

## Disaster-recovery drill checklist
Move representative reports onto a different filesystem path/machine; validate
with steward-report, rebuild steward-history, compare semantic/input-set SHA-256,
render both local dashboards, and try a tampered report. Record actual commands,
outputs and observed failure modes. This file does not claim that any drill ran.

## Graduation boundary
GA requires observed branch-protection behavior, reviewed archive choice,
portability drill and named SLI monitoring ownership; no simulated human
approval, branch-rule bypass or assumed independent review can replace them.
