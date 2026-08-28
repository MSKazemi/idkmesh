# E016 — Measuring verifier error correlation with live LLM verifiers

**Status: negative result. The experiment did not measure error correlation,
because the verifiers it deployed do not verify.**

## Why this experiment exists

E012, E013 and E015 all carry the same stated limitation: error correlation
`rho` is a knob set inside a synthetic shared-shock mixture, never measured on
anything real. Every downstream claim — including E015's finding that the
`N_eff` heuristic is optimistic — inherits it.

E016 was designed to close that gap by putting real verifiers on a corpus with
executable ground truth, measuring the pairwise error correlation directly, and
checking whether the shared-shock mixture predicts the panel error that a real
panel produces.

## What was run

- **Corpus**: 24 problems x 3 variants = 72 candidate solutions
  (`sim/e016_corpus.py`). Ground truth is not a judgement call: each candidate
  is executed against hidden tests in a subprocess, and `viable` is the exit
  status. 26 viable, 46 non-viable. The labels reproduce exactly on
  regeneration (72/72).
- **Panel**: 20 verifiers = 4 open-weight models
  (`qwen2.5-1.5b`, `llama3.2-1b`, `gemma2-2b`, `smollm2-1.7b`)
  x 5 prompt templates (`direct`, `edge_cases`, `adversarial`, `test_writer`,
  `terse`), one model per VM, served by `llama-server` over its
  OpenAI-compatible endpoint so each family's own chat template applies.
- **Infrastructure**: 20 Azure `Standard_F4s_v2` VMs across two regions,
  one agent per node, 1440 votes total, full 72-task coverage per agent.
- **Artifact**: `results/E016-live-verifier-votes.jsonl.gz` (1440 votes).

## The result

101 of 1440 votes (7.0%) were unparseable. Of the 20 agents:

| shape | agents |
|---|---|
| emitted a single constant verdict for all 72 tasks | 6 |
| >=95% one verdict | 3 |
| varied | 11 |

Accuracy looked superficially reasonable for several agents — but on a corpus
that is 36.1% viable, **"always reject" scores 0.639 and "always accept" scores
0.361**. Accuracy cannot separate a verifier from a constant.

Youden's `J = sensitivity + specificity - 1` can: it is exactly zero for any
task-independent rule, whichever way that rule is biased, and it does not move
with the corpus base rate.

```
mean accuracy p = 0.4743
mean Youden J   = +0.0487
agents whose J is above zero after Bonferroni correction: 0 / 20
```

**No agent's verdicts depend on the code under review beyond chance.**

At panel level the same holds, and the practical consequence is blunt:

```
corpus base rate viable          : 0.361
20-agent majority vote  accuracy : 0.514    J = +0.156
trivial "always reject" accuracy : 0.639    J =  0.000
permutation test on panel J (N=20000): p = 0.13
```

A 20-model, 4-family, 5-prompt panel is **worse than a constant rule that
rejects everything without reading it**, and its discrimination is not
distinguishable from chance.

What the verdicts *do* respond to is who is asked and how. Mean accept rate
moved 0.251 -> 0.731 across prompt templates and 0.137 -> 0.799 across models,
while carrying no task-level signal. The panel measured its own prompts.

## Why the correlation numbers must not be quoted

The analyzer does report `rho` values, and they are near zero
(all-pairs mean `+0.025`). **They are not evidence that real verifiers are
independent.** When error vectors are constant or noise, the correlation
between them is near zero by construction. The number describes the
instrument, not the panel.

This is a live misreading risk — near-zero `rho` is exactly the result E012/E013
would find encouraging — so `sim/e016_analyze.py` now runs the discrimination
screen first and prints a blocking warning above the correlation section when
no agent passes it.

## What this means for the other experiments

- **The stated limitation of E012, E013 and E015 remains open.** `rho` is still
  unmeasured. E016 does not narrow it.
- **E015's conclusions are untouched, and still untested against reality.** The
  `N_eff` critique and the accuracy-dependent ceiling are analytic results about
  the shared-shock model, verified against simulation on all 2592 cells. E016
  neither supports nor undermines them.
- **`effective_n` correctly refused to produce a number.** It guards on
  `acc <= 0.5` and returned `NaN` rather than a plausible-looking effective panel
  size. The guard did its job.

## The engineering lesson, made mechanical

The failure mode was not the models being weak — it was that *weakness on an
imbalanced corpus is indistinguishable from competence if you only look at
accuracy*. An agent answering `NO` to all 72 tasks reports 0.639 and would have
been read as the panel's strongest verifier. It was, in fact, the post-hoc
"best single agent".

So the screen is now part of the tool rather than part of the write-up:
`youden_j()` plus a Bonferroni-corrected panel screen gate the correlation
report. Any future panel must clear it before its `rho` means anything.

## Preregistered gate for a retry

A repeat of E016 should be considered informative only if, **before** any
correlation analysis:

1. at least 3 agents have `J` significantly above 0 after correction;
2. mean panel accuracy `p > 0.5` on a base-rate-balanced corpus;
3. unparseable rate below 2%;
4. no agent is constant or >=95% one-sided.

Likely changes needed: 7-8B or larger verifiers, a balanced corpus (the 26/46
split gave constant rules an unearned edge), and structured/constrained decoding
instead of free-text YES/NO parsing.

## Limitations

- 72 tasks is small; per-agent `J` confidence intervals are correspondingly wide.
  The conclusion rests on all 20 agents failing simultaneously, not on any one.
- Only four model families, all 1-2B. Nothing here generalises to larger models;
  the experiment's own finding is that this size class cannot do the task.
- The corpus is Python function-level correctness only.
- Prompt templates were hand-written and not tuned per family. A better prompt
  might rescue some agents; that possibility is exactly what the retry gate is
  for.
- Verdict parsing takes the last YES/NO token, which is a heuristic and
  contributed to the 7.0% unparseable rate.
