# E040 — Review capacity as a carrying-capacity governor

## Question

IDKMesh's ACE/community design already uses the logistic review-capacity term

```text
Capacity(L) = 1 / (1 + exp((L - K) / tau))
```

and the live ACE ledger explicitly records `K = 8` and `tau = 2` as bootstrap hypotheses that still need calibration from real review-latency/attention evidence.

This experiment asks a narrower question before any calibration claim:

> **Does the proposed feedback shape actually create negative feedback on review backlog, or can an autonomous contributor population still drive review load upward without bound?**

This is motivated by issues #23 and #57 and by the repository's new bounded autonomous-agent population. It is an offline model only. It does not change ACE state, create Growth Seeds, throttle contributors, or grant merge/admission authority.

## Preregistered hypothesis

For a constant potential arrival rate `A` and reviewer service capacity `S`:

1. if `A <= S`, neither an open-loop queue nor the logistic governor should create backlog from an empty queue;
2. if `A > S`, open-loop admission should accumulate backlog approximately linearly;
3. under logistic admission, the queue should approach a finite fixed point whenever positive service exists;
4. the fixed point should satisfy

```text
A * Capacity(L*) = S
```

and therefore, for an interior equilibrium,

```text
L* = K + tau * ln(A / S - 1).
```

If the zero-backlog gate already admits no more than service can review, the physical queue boundary makes `L* = 0` instead.

These claims are about the mathematical feedback mechanism, not human/community behavior.

## Model

`sim/e040_review_capacity.py` is deterministic and dependency-free. Each discrete step has:

- `potential_arrivals`: review work that could be admitted;
- `service`: work reviewers can finish;
- `load`: unfinished review work;
- `open-loop`: admit all potential arrivals;
- `logistic`: admit `potential_arrivals * Capacity(load)`.

Metrics include final/peak/mean load, total admitted/reviewed/throttled work, queue area, a queue-area-per-reviewed-unit delay proxy, and the analytic equilibrium where defined.

The default ladder keeps the current ACE bootstrap shape (`K=8`, `tau=2`) visible without pretending it is calibrated:

```bash
PYTHONPATH=. python3 sim/e040_review_capacity.py --pretty
```

A focused overload case is:

```bash
PYTHONPATH=. python3 sim/e040_review_capacity.py \
  --potential-arrivals 3 \
  --service 1 \
  --steps 400 \
  --k 8 \
  --tau 2 \
  --pretty
```

For that cell the analytic logistic fixed point is

```text
8 + 2 * ln(2) = 9.386294...
```

while the open-loop queue adds two units of unresolved work per step. The regression test checks convergence to the analytic fixed point rather than storing a hand-authored simulation result.

## Falsification criteria

This experiment fails its stated mechanism if any of the following occurs:

- logistic capacity is not monotone decreasing in load;
- the simulated overload trajectory does not approach the derived fixed point;
- an under-capacity empty queue develops backlog without another source of work;
- zero service is rendered as a finite equilibrium;
- results depend on hidden randomness;
- the artifact claims policy activation authority.

The tests in `tests/test_e040_review_capacity.py` pin those invariants.

## What this does **not** establish

This model does **not** establish that `K=8`, `tau=2`, or any arrival/service unit is appropriate for real maintainers. In particular:

- GitHub PRs have heterogeneous review cost;
- reviewer capacity is not constant;
- review can create rework rather than simply drain a queue;
- contributors may abandon, wait, or switch tasks under delay;
- throttling autonomous project agents is ethically and operationally different from throttling independent human contributors;
- first-response latency and review quality may matter more than backlog count;
- the current ACE `review_load` is a weighted proxy, not a measured queue length.

Real policy calibration therefore still requires observed review time, latency, recurrence, and workload evidence. E023's preregistered first-review-latency study is one relevant source when it matures.

## Community Impact

The value of this experiment is anti-Goodhart: it makes one attractive ecological analogy executable and falsifiable before the repository treats it as truth. It also gives the autonomous-agent swarm a concrete warning: **more generation capacity is not useful if verification/review service is the bottleneck**.

No contributor score, reputation, or individual productivity metric is produced. The intended unit is aggregate review work, and the output is diagnostic research evidence only.

## AI/tool provenance

Implemented by the IDKmesh Community & Research autonomous ChatGPT agent on 2026-09-12 after inspecting current `main`, open PRs/changed files, recent CI, `AGENTS.md`, `PROJECT_RULES.md`, the pending autonomous-swarm policy, the ACE ledger issue #23, and ACE controller issue #57.

The branch was created from exact `main` head `5a211bd9a79cd789e948b5c69beb5b256bcf60c0`. The selected files were new and did not overlap any open pull request at selection time. The automation environment did not provide a local repository execution shell, so exact-head GitHub CI is the execution evidence required before integration.
