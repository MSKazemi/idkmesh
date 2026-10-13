# Source-backed documentation update: API metrics interval diagnostics — 2026-10-13

**User request:** review the repository code and improve documentation.
**Branch starting revision:** `main@a0cd473de57059ca376e8fb88fb693bdbe0d1a23`.
**Review mode:** AI-assisted inspection via connected GitHub APIs, not a full-file security review or an independently executed runtime test.

## What was checked

Inspected the repository README, agent/contribution instructions, documentation and architecture indexes, CLI and HTTP references, the existing executable/module catalogs, open PRs, the code behind the Control Tower metrics route (`idkmesh/control_tower_ui.py`), the counter implementation (`idkmesh/api_observability.py`), the newly merged interval function (`idkmesh/otel_metrics.py`), and `tests/test_api_observability_intervals.py`. The newer interval evaluator was not explained in the existing operator-facing guides.

## What was changed

Added a [source-backed metrics interval guide](../reference/API_METRICS_INTERVAL_GUIDE.md) with a self-contained, dependency-free in-memory example, fixed-bucket interpretation, a distinction between HTTP snapshot collection and trusted process epochs, and the eight current UNKNOWN reasons. Added `tests/test_api_metrics_interval_docs.py` to execute the example and check that every source-defined UNKNOWN reason is explained. Updated the observability specification, API quickstart, documentation index, and troubleshooting help to link the guide and clarify authority.

## Evidence and limitations

- Reviewed source-level definitions, HTTP handler, signatures, and existing tests on the stated branch baseline.
- This is a documentation-and-test addition, **not** implementation of collector identity, 5-minute rolling SLOs, external OTLP export, alerts, new HTTP routes, or changes to capability evidence levels.
- **Local pytest was not run.** The available execution environment cannot resolve GitHub to clone the repository. Exact-head PR CI and the focused `python -m pytest -q tests/test_api_metrics_interval_docs.py tests/test_api_observability_intervals.py` are required before merge.
- No independent human or production review is claimed. AI-assisted source reading and authoring were used.

**Community impact:** new users can understand raw service counters and avoid incorrectly treating a restart, invalid snapshot, or empty interval as a measured zero-error service.
