# E029 — The first real model attempts on the frozen benchmark

**Status: negative result, and the first one this repository has ever been
entitled to. 60 real attempts by a pinned open-weight model produced 0
candidates the independent verifier was even asked to judge. 56 of the 60
failures were failures of the unified-diff protocol, not of the proposed
change.**

## Why this experiment exists

Every benchmark result in `results/benchmarks/` before this one was produced by
a script. The five "real" attempts under
`results/benchmarks/phase-b2-successor-five/` declare
`"worker": {"type": "system"}` with adapters named `bounded-source-transform`,
`deterministic-text-rewrite` and `deterministic-document-rewrite`, and every one
of them records `"tokens": 0` and sub-second wall time. They are deterministic
rewriters. No language model had ever generated a candidate for a WorkUnit in
this repository; the only live-model evidence in the tree is verifier-side
(E016).

`tools/open_model_benchmark_probe.py` was written for exactly this gap and then
never run: before this experiment it was referenced by no workflow, no test and
no committed result. E029 runs it.

## What was run

- **Producer**: `Qwen/Qwen2.5-Coder-0.5B-Instruct` at revision
  `bbf27711794f58ebd1796058f4280b53c32e19fc` — the revision already pinned in
  the probe. Open weights, CPU inference, **USD 0.00 of paid API spend**.
- **Sandbox**: one Docker container per attempt with `--network none`,
  `--read-only`, `--cap-drop ALL`, `--security-opt no-new-privileges`,
  `--pids-limit 128`, `--memory 6g`, `--cpus 2.0`, `--user 65534:65534`, and a
  `noexec,nosuid` tmpfs for `/tmp`. The container receives one prompt file and
  a writable output directory. It never receives repository credentials, the
  source checkout, or the EvaluatorPlan. The sandbox was not weakened at any
  point to make an attempt succeed.
- **Image**: built by `tools/open_model_producer_image.sh` from
  `tools/open_model_producer.Dockerfile` — added here, because the probe named
  an image the repository had no recipe for. The weights are baked in so the
  runtime container needs no network at all. Inside the container the entry
  point is `tools/open_model_text_generator.py`, which loads the pinned local
  snapshot, reads the one mounted prompt file, and writes the raw response and
  its generation metadata to the one writable output directory. It has no
  repository credentials, no source checkout and no evaluator input, and it is
  the only program the model's weights are ever loaded by in this experiment.
- **Tasks**: all 10 frozen work units — 5 in `benchmarks/phase-b2-first-five/`
  (source revision `9c53bb4069a5`) and 5 in
  `benchmarks/phase-b2-successor-v2/` (source revision `a69aa0ae1ae4`). Each
  probe re-checks that its source checkout is at the declared revision and that
  the EvaluatorPlan is bound to the exact WorkUnit digest.
- **Attempts**: 6 per task, 60 total. Attempt 1 is the probe's default greedy
  decode (`do_sample=False`, seed 0). Attempts 2–6 are independent samples
  (`temperature=0.8`, `top_p=0.95`, seeds 1–5). Within every task all 6
  responses are distinct. Across tasks they are **not** — see "The task prompt
  stops mattering" below.
- **Verification path**: unchanged. Host-side extraction of a single-file
  textual patch, `git apply` against the immutable checkout, then the existing
  `experiments/evaluator_plan_runner.py` verifier.

Evidence: `results/benchmarks/phase-b2-open-model-qwen25coder05b/`, one
directory per attempt holding the probe evidence, the raw model response, the
generation metadata, and the extracted patch where one existed. Aggregated by
`tools/open_model_probe_summary.py` into `cohort-summary.json`.

The prompt itself is not committed — it embeds the whole frozen source file, so
storing 60 copies would add megabytes of duplicated repository content. Its
digest is recorded per attempt and is **reproducible**: rebuilding all 10
prompts with `build_prompt` from the pinned WorkUnits and the two immutable
source checkouts regenerates all 10 recorded `prompt_digest` values exactly,
`10 reproduced, 0 mismatched`.

## The result

```
tasks                                  : 10
attempts                               : 60
attempts producing a well-formed patch :  0
attempts the verifier accepted         :  0
exact 95% upper bound on acceptance    :  0.0487
paid API spend                         :  USD 0.00
```

**Zero of sixty.** The independent verifier was never invoked, because no
attempt cleared the host-side normalization that precedes it. One-sided
Clopper-Pearson puts the per-attempt success probability of this producer on
this benchmark below 4.9%.

## The finding: this measured diff compliance, not coding ability

The failures are not spread across "the model wrote the wrong change". They
concentrate almost entirely before any repository content is consulted:

| failure class | attempts | what it means |
|---|---:|---|
| protocol | 56 | the response was not a single well-formed unified diff against the one allowed path |
| content | 4 | `git apply` parsed the diff and then declined to apply it |

Broken out:

| detail | attempts |
|---|---:|
| `git apply: corrupt patch` | 28 |
| reported as targeting a path other than the allowed one | 12 |
| no `diff --git` block anywhere in the response | 8 |
| old/new target paths not preserved exactly | 7 |
| `git apply: patch does not apply to the frozen source` | 4 |
| more than one file diff in one response | 1 |

Only the 4 `patch does not apply` attempts said anything at all about the
*change* the model proposed. The other 56 measured whether a 0.5B model can emit a byte-exact
unified diff, which it cannot.

The mechanism is visible in the generation metadata: **49 of 60 attempts
(81.7%) ran to the 1536-token cap without ever emitting a stop token.** The
model does not write a minimal hunk. It starts a plausible `diff --git` header
and then reproduces the file body as ordinary source text, so the hunk line
counts stop matching and `git apply` reports a corrupt patch. Mean inference
time was 507 s per attempt (min 57 s, max 781 s) for 245,640 input and 80,416
output tokens in total — 8.5 hours of sandboxed CPU inference.

This is a finding about the harness as much as about the model. The strict
single-file textual-diff producer contract is a **capability floor**: a producer
must be able to emit exact diff syntax before the benchmark can measure anything
else about it. Any future comparison across producers on this cohort has to
report protocol failures separately, or it will silently attribute a formatting
deficit to reasoning.

## The task prompt stops mattering

Once the model enters file-reproduction mode, what it was asked to do drops out
of the output entirely. The 60 responses carry only **47 distinct digests**. The
13 collisions are not repeats within a task — every task has 6 distinct
responses — they are attempts on *different tasks* that produced the
byte-identical 1536-token response:

| shared response | tasks | attempt slots |
|---|---|---|
| `sha256:a9b40d3…` | first-five tasks 001, 002, 003, 004 | 2 |
| `sha256:d739247…` | first-five tasks 001, 002, 003, 004 | 3 |
| `sha256:9fde7ed…` | first-five tasks 001, 002, 003, 004 | 4 |
| `sha256:ce25d5f…` | first-five tasks 001, 002, 003, 004 | 6 |
| `sha256:4d62982…` | first-five tasks 001, 003 | 1 (greedy) |

Those four tasks share one allowed path, `tools/benchmark_cohort.py`, so their
prompts share the frozen source block and differ only in the task id, objective
and context. The prompts are genuinely different — 10 distinct
`prompt_digest` values over the 60 attempts, one per task, each independently
reproduced above. Yet at four of the five sampled seeds the model emitted the
same 1536 tokens for four different objectives, and every one of those responses
ran to the token cap.

That is the sharpest available statement of the finding: **at this scale the
output is a function of the file in the prompt and the sampling seed, not of the
change requested.** The one task in that cohort with a different allowed path
(`task-005`, a Markdown specification) never collides, and neither does the
successor-v2 task that names the same file at a different frozen revision. A per-task
view cannot see any of this: 6 of 6 distinct for every task is true and, on its
own, misleading. `tools/open_model_probe_summary.py` therefore reports the
per-task count, the global count, and the explicit cross-task collision list
side by side, and its `--self-test` pins a case where per-task diversity is
full and a cross-task collision still exists.

## Pairwise failure correlation is undefined here, not zero

The 5 independent samples per task were run specifically so that pairwise
failure correlation between real attempts could be measured for the first time.
It cannot be, and the reason matters:

```
attempt slots                     : 2, 3, 4, 5, 6
tasks with complete coverage      : 10 / 10
marginal failure rate             : 1.000
mean pairwise phi                 : undefined
```

Every attempt failed, so the per-attempt failure indicator is the constant 1 and
has zero variance. Correlation between two constants is undefined. This is the
same trap E016 documented on the verifier side, where near-zero `rho` described
the instrument rather than the panel: **a degenerate correlation must be
reported as undefined, never as 0.0 and never as "independent".**
`tools/open_model_probe_summary.py` emits `null` with an explicit reason rather
than a number, and its `--self-test` asserts that behaviour.

Measuring attempt correlation on this cohort needs a producer that clears the
protocol floor often enough for the failure indicator to vary. That is the
precondition, and E029 establishes that this producer does not meet it.

## Defects found in the harness, not fixed here

Three, recorded rather than repaired, because changing them mid-experiment would
have changed the contract being measured:

1. **The out-of-scope-path rejection overstates what happened.** 12 attempts
   were rejected with "model patch targeted a path other than the WorkUnit
   allowed path". In **11** of them the diff header names the allowed path on
   *both* sides and differs only by a missing `a/` prefix
   (`diff --git tools/benchmark_cohort.py b/tools/benchmark_cohort.py`). Those
   are diff-format failures, not containment breaches. The message reads as a
   security event and is not one. (The 12th is a genuine degeneracy: the header
   collapsed into the token `bef` repeated several hundred times.)
2. **`worker.id` is hardcoded** to `github-actions/qwen2.5-coder-0.5b` in the
   ResultManifest the probe emits, including for purely local runs. It did not
   contaminate this cohort only because every attempt was rejected before a
   manifest was written.
3. **The probe had no image recipe.** It named
   `idkmesh-open-model-producer:task001` and nothing in the repository built it,
   which is a large part of why it had never been run. Closed here.

> **Defects 1 and 2 are now closed in a follow-up**, after this cohort was
> recorded, so the contract measured above is the one the numbers were produced
> under. A header that names only the allowed path is now reported as
> `model patch header is malformed but names only the allowed path`, still a
> protocol rejection but no longer worded as a containment breach; and
> `worker.id` now records the execution context (`local/...` or
> `github-actions/...`) instead of always claiming CI. The
> `allowed_path_rejections` block in `cohort-summary.json` is kept so this
> cohort's 12 rejections stay readable — it should be `0` for any run made after
> the fix.

## Reproducing

```bash
./tools/open_model_producer_image.sh
git worktree add --detach /tmp/src-v2 a69aa0ae1ae4
python tools/open_model_benchmark_probe.py \
  --source /tmp/src-v2 \
  --work-unit benchmarks/phase-b2-successor-v2/work-units/task-002-router-nonfinite-numbers.work-unit.json \
  --evaluator-plan benchmarks/phase-b2-successor-v2/evaluators/task-002-router-nonfinite-numbers.evaluator-plan.json \
  --output-root results/benchmarks/phase-b2-open-model-qwen25coder05b/phase-b2-successor-v2/task-002-router-nonfinite-numbers/attempt-001 \
  --attempt 1
python tools/open_model_probe_summary.py \
  --results-root results/benchmarks/phase-b2-open-model-qwen25coder05b
```

The greedy path reproduces exactly: task-002's attempt 1 was run twice, once
alone and once inside the 60-attempt matrix under heavy load, and both produced
the byte-identical response
`sha256:24c3f262b6de2a655ab986e217c9c435317941e5b656b7f35e83707bb29a3e30`.

## What this does and does not license

It licenses one sentence that could not previously be written: **IDKMesh has run
real language-model coding attempts against its own frozen benchmark, under a
network-isolated sandbox, at zero paid cost, and has the per-attempt evidence to
show for it.**

It licenses nothing about larger models. A 0.5B instruct model is the smallest
serious code model available; 0/60 here is evidence about the bottom of the
capability range and about the producer contract, and **must not be quoted as
evidence that model-produced candidates fail in general.** The honest next step
is a producer in the 7B–32B open-weight range on the same 10 work units with the
same sandbox, reporting protocol and content failures separately, so that the
first non-degenerate attempt-correlation measurement becomes possible.
