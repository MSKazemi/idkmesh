# BYO-Agent Challenge 001: ResultManifest conformance

**Status:** public onboarding/conformance challenge.  
**Authority:** none. A passing score is not merge approval, independent review,
or evidence that one model/agent is generally better than another.  
**Source revision:** `1db0aa0cc525e3179f179661ba1623381d889c89`.  
**Pinned schema blob:** `e2cd2f55cff59bb306ba74bfc63ff8f4c6ffd934`.  
**Related:** issue #461, `schemas/result-manifest.schema.json`.

This is the first bounded "bring your own agent" challenge requested by the
IDKMesh growth flywheel. It gives a human, coding agent, or human+agent pair one
small repository-native task: classify six candidate objects as valid or invalid
under the **existing canonical ResultManifest v0.1 schema**.

The fixtures and evaluator are intentionally public. That makes this useful for
onboarding, conformance, tool integration, and reproducibility; it makes it
**unsuitable as a hidden benchmark** or as evidence of model superiority.

## Why this integrates with IDKMesh

ResultManifest is already the worker-to-verification evidence boundary used by
IDKMesh. The challenge does not invent a second result format. Its evaluator
loads `schemas/result-manifest.schema.json` directly with JSON Schema Draft
2020-12 and verifies the file's Git blob object ID before scoring. If that schema
changes, this challenge fails closed until it is deliberately versioned or its
source/schema pin is updated. This prevents a historical challenge from silently
changing meaning when the canonical contract evolves.

The challenge is deliberately read-only and zero-network. It cannot push,
approve, merge, mutate issues, spend project funds, or turn participant
self-reports into trusted evidence.

## Task

Read `challenge.json`, then create a submission JSON with exactly one boolean
classification for each `case_id`:

```json
{
  "version": 1,
  "challenge_id": "byo-agent-001-result-manifest-conformance",
  "participant": {
    "kind": "ai_agent",
    "tool": "your-agent-or-tool",
    "model": "model-if-known",
    "source_revision": "git-revision-you-used"
  },
  "measurements": {
    "wall_seconds": 12.5,
    "human_review_minutes": 0
  },
  "answers": [
    {"case_id": "minimal-completed", "schema_valid": true}
  ]
}
```

The snippet is structural only: a real submission must include **all six** case
IDs exactly once. `kind` is one of `human`, `ai_agent`, or `human_ai`. Timing and
human-review fields are optional and are retained only as
`self_reported_unverified`; do not use them as measured performance unless an
independent protocol later verifies them.

## Evaluate

From the repository root, after the normal phase-0 dependencies are installed:

```bash
python scripts/byo_agent_challenge.py \
  examples/challenges/byo-agent-001/challenge.json \
  /path/to/submission.json
```

Exit codes are stable for automation:

- `0` — structurally valid submission and all classifications correct;
- `1` — structurally valid submission with at least one wrong classification;
- `2` — malformed challenge/submission, schema-pin drift, or an unreadable input.

The JSON report reveals the schema-derived truth and the first failing schema
keyword/path for invalid cases. That is intentional: this is an open conformance
exercise, not a secret test set.

## Reproducibility and scientific limits

The only claim made by this challenge is narrow and mechanically checkable:
for the frozen challenge file and pinned canonical schema blob at the recorded
source revision, the evaluator deterministically scores the submitted
classifications.

It does **not** establish:

- coding capability;
- general agent quality;
- causal benefit from multi-agent coordination;
- independent human review;
- security of arbitrary agent output;
- hidden-test performance;
- comparative efficiency from self-reported timing.

Those questions require separate preregistered tasks, independent verification,
and controlled resource accounting. Publishing negative or incomplete challenge
results is welcome; the project should not select only perfect outcomes.

## Public outcome table

Add a row only for a publicly inspectable submission/PR whose exact source
revision and evaluator output are available. Owner-controlled agents must be
identified as such and must not be counted as external human participation.

| Submission / PR | Participant kind | Tool / model | Score | Wall time* | Human review* | Evidence |
| --- | --- | --- | ---: | ---: | ---: | --- |

\* Self-reported unless the linked evidence states an independent measurement
protocol.

## Maintainer verification

For changes to this challenge or evaluator, run at least:

```bash
PYTHONPATH=. python -m pytest -q tests/test_byo_agent_challenge.py
PYTHONPATH=. python -m pytest -q
```

The focused tests pin canonical-schema path **and exact blob**, fail-closed
submission structure, correct/wrong scoring, strict deterministic JSON,
authority flags, and CLI exit codes. Repository PR gates remain the integration
authority for the exact head.

## Provenance / run record

This artifact was created by the owner-controlled IDKMesh hourly issue steward
on 2026-09-17 as one bounded implementation slice of issue #461. The steward
inspected current `main`, the open issue/PR queue, repository contribution rules,
the canonical ResultManifest schema, and existing ACE/community mechanisms before
selecting this scope. No external participant or independent reviewer is claimed,
and no paid compute or network-dependent model service is required to run it.
