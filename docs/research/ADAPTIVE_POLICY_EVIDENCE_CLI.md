# Adaptive Policy Evidence CLI

The dependency-free CLI in `tools/adaptive_policy_evidence_cli.py` turns the
N3 shadow-evidence contract into an operational workflow.

It does **not** execute recommendations.

## 1. Freeze a plan before the outcome

Prepare a JSON request that contains:

- exact repository revision;
- explicit pre-outcome `captured_at` timestamp;
- policy ID/version/maturity;
- the complete input state used by the policy;
- hard-gate results;
- the already-eligible choices;
- selected shadow choice and named baseline;
- uncertainty and expected non-monetary cost;
- evidence references;
- limitations.

Then run:

```bash
python tools/adaptive_policy_evidence_cli.py plan \
  --request path/to/request.json \
  --output evidence/adaptive/plans/plan-001.json
```

The output file must not already exist. The CLI refuses to overwrite evidence.

## 2. Join the later observed outcome

After the real process completes unchanged, prepare an observation JSON:

```json
{
  "actual_choice_id": "baseline-choice",
  "observed_at": "2026-09-22T12:05:00Z",
  "outcome": "succeeded",
  "verified_utility": 0.7,
  "escaped_defect": false,
  "high_risk_escape": false,
  "actual_cost": {
    "project_spend_usd": 0,
    "compute_units": 1,
    "review_units": 1,
    "human_attention_units": null
  },
  "evidence_refs": ["verification:..."],
  "limitations": ["shadow choice was not executed"]
}
```

Then run:

```bash
python tools/adaptive_policy_evidence_cli.py outcome \
  --plan evidence/adaptive/plans/plan-001.json \
  --observation path/to/observation.json \
  --output evidence/adaptive/outcomes/outcome-001.json
```

The outcome binds to the exact plan digest.

## 3. Summarize a cohort

Prepare a cohort request:

```json
{
  "plans": [
    "evidence/adaptive/plans/plan-001.json"
  ],
  "outcomes": [
    "evidence/adaptive/outcomes/outcome-001.json"
  ],
  "limitations": [
    "observational shadow cohort; no randomized policy assignment"
  ]
}
```

Then run:

```bash
python tools/adaptive_policy_evidence_cli.py cohort \
  --request path/to/cohort.json \
  --output evidence/adaptive/cohorts/cohort-001.json
```

## Evidence hygiene

Recommended repository layout:

```text
evidence/adaptive/
  plans/
  outcomes/
  cohorts/
```

Do not commit secrets, private prompts, credentials, personal data, or
provider-private material into the evidence corpus.

A real N3 corpus should retain:

- abstentions;
- failed hard gates;
- negative outcomes;
- missing measurements;
- shadow/baseline agreements as well as disagreements.

Do not filter the corpus down to cases where the adaptive policy looked good.

## What N3 can establish

N3 can establish:

- the policy is runnable on real state;
- the policy makes or does not make materially different recommendations;
- hard gates remain intact;
- inputs and costs are or are not measurable;
- assumptions fail or hold on real repository state.

N3 shadow mode generally cannot establish the causal performance of an
unexecuted alternative. That requires a later controlled experiment.


## Temporal ordering

The plan request must include `captured_at`, and the later observation must
include `observed_at`.

The joiner rejects an observation timestamp earlier than the frozen plan's
capture time.

For real N3 evidence, persist the plan before the outcome is known. The explicit
timestamps support audit/replay, while repository/CI artifact history provides
the stronger external evidence that the plan actually existed before the
outcome.
