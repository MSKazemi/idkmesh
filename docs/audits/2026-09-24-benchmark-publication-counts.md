# Independent verification of the benchmark publication counts

Refs: issue 541. Date: 2026-09-24.

## Source commit

- Commit checked: `8a295e3a693842374481f7c309aa764e1048bb6a` (short form `8a295e3`).
- `main` was in sync with `upstream/main` when I created my working branch.

## Environment

- macOS (arm64), Python 3.13.15 in a fresh virtual environment (`.venv`).
- Dependencies installed from `requirements-phase0.txt` plus `pytest`.

## Baseline checks (done)

- `make test`: 2683 passed, 2 skipped, 1 failed.
  - Failing test: `tests/test_local_agent_runner.py::LocalAgentRunnerTests::test_local_agent_boundary_rejects_implicit_host_env_and_repo_artifacts` (`AssertionError: LocalRunnerError not raised`, line 604).
  - It also fails when run alone, on an unmodified checkout. I did not investigate it and did not change anything for it.
  - The 2 skipped tests are the optional SDK conformance tests (a2a-sdk and mcp are not installed).
- `PYTHONPATH=. python tools/benchmark_publication.py --check`: **pass** ("benchmark publication is up to date").
- Observation: the same command without `PYTHONPATH=.` fails with `AttributeError: 'NoneType' object has no attribute 'validate_cohort'`. I did not change anything for this.

## Method for the independent count

For each of the four cohort files under `benchmarks/*/cohort.json`, I did the following by hand, reading the raw JSON (not `benchmarks/publication.json` or `benchmarks/PUBLICATION.md`, and not `tools/benchmark_publication.py`):

1. Counted the number of task objects inside the top-level `"tasks"` array.
2. For each task, read `evidence.attempts` and counted the entries (an empty array means zero attempts for that task).
3. For each task, read the `evidence.status` field (`"verified"`, `"pending"`, or `"excluded"`) and counted a task as verified only when `status == "verified"`. This is the field the schema itself uses to mark verification; I did not infer verification from the presence of an `outcome` value.
4. Compared each cohort's `definition_digest` (when present) against the digest listed for that cohort in `benchmarks/PUBLICATION.md`, using `grep`.
5. Summed tasks, attempts, and verified counts across the four cohorts.

## Counts I derived

| Cohort | Tasks | Verified | Attempts | `definition_digest` matches PUBLICATION.md |
| --- | ---: | ---: | ---: | --- |
| `phase-b2-successor-five` | 5 | 5 | 5 | yes |
| `phase-b2-first-five-v2` | 5 | 0 | 0 | yes |
| `phase-b2-successor-v2` | 5 | 0 | 0 | n/a — cohort is `stage: scaffold`; its `description` field states it intentionally has no `definition_digest` until it is frozen |
| `phase-b2-first-five` | 5 | 0 | 0 | yes (matches the `predecessor_burned_definition_digest` recorded in `phase-b2-successor-five/cohort.json`) |
| **Total** | **20** | **5** | **5** | |

These totals match the published summary in `benchmarks/PUBLICATION.md`: "4 cohorts · 20 tasks · 5 with a verified outcome · 5 attempts".

`PYTHONPATH=. python tools/benchmark_publication.py --check` reports **pass** ("benchmark publication is up to date").

## Discrepancies or ambiguities

None found. My independently derived counts match the published totals exactly, for all four cohorts.

## Additional observations (not discrepancies in the counts)

- Running `tools/benchmark_publication.py --check` **without** `PYTHONPATH=.` fails with `AttributeError: 'NoneType' object has no attribute 'validate_cohort'` (and a second `AttributeError` for `CohortError`) on an unmodified checkout. `PYTHONPATH=.` is required for this script to run, even though `CONTRIBUTING.md`'s note that `PYTHONPATH=.` is no longer needed applies to `pytest` only (via `pytest.ini`), not to this standalone script.
- On this machine (macOS, Python 3.13.15), `make test` reports 2683 passed, 2 skipped, 1 failed, on an unmodified checkout of the commit above. The failing test is `tests/test_local_agent_runner.py::LocalAgentRunnerTests::test_local_agent_boundary_rejects_implicit_host_env_and_repo_artifacts` (`AssertionError: LocalRunnerError not raised`, line 604). It also fails in isolation. I did not investigate further and made no changes related to it. The 2 skipped tests are the optional SDK conformance tests (a2a-sdk and mcp are not installed, as expected per `interop/README.md`).

## AI assistance

I used an AI assistant (Claude) to help me understand the project's documentation and JSON schema, translate terminology, and plan the verification method. The counting itself — reading each `cohort.json`, counting tasks/attempts, checking each `status` field, and comparing digests — was done by me, manually, cohort by cohort. No script or model performed the count.