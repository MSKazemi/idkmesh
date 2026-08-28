# Task 004 Non-Finite RWVB Calibration

## Question

Can the provisional Task 004 evaluator distinguish a real finite-domain repair
from a lexical near-miss while preserving RWVB behavior for valid inputs?

## Pre-outcome novelty audit

Repository history and all pull requests were searched for `RWVB`,
`verification_backpressure`, and non-finite validation. PRs #47 and #92 added
the controller and its synthetic benchmark, but no published change validates
all floating-point `Candidate` and `ControllerConfig` fields with
`math.isfinite`. Task 004 therefore remains outcome-unseen at frozen source
`a69aa0ae1ae4862e507511cbd9ad854237d0ad32`.

## Evaluator correction

The initial proxy required only `math.isfinite` to be added and the original
impact guard to be removed. An inert candidate can satisfy both by assigning
`math.isfinite` to an unused constant and rewriting the same comparison as
`0.0 > self.impact`. The defect remains, so that proxy is Goodhartable.

Before freeze, the plan is strengthened to require the actual finite-value
branch plus explicit `Candidate` and `ControllerConfig` validation calls. The
new plan digest is:

`sha256:e42cbd25ee956fe6d5fe4f0f9ca01d805f28dab3aa9c0601869c16cddd420834`

This remains a static proxy, not proof. A separate evaluator-owned behavioral
matrix is authoritative calibration evidence.

## Behavioral matrix

The straightforward candidate checks five `Candidate` floats and six
`ControllerConfig` floats against `NaN`, positive infinity, and negative
infinity: 33 invalid cases. Every case must fail during validation. A finite
control must retain exactly the frozen debt, priority, scheduling, and fan-out
outputs.

The inert decoy must preserve finite behavior while allowing at least one
non-finite value through validation. Canonical EvaluatorPlan v0.4 must support
the straightforward transition and reject the decoy.

## Boundaries

- Calibration candidates are not scored benchmark outcomes.
- The scaffold stays at `stage=scaffold` with no definition digest.
- The canonical verifier remains metadata-only.
- Candidate execution is isolated to a disposable frozen-source checkout.
- Worker and verifier have no canonical-write, push, approval, merge, spending,
  or automatic-selection authority.

## Exact calibration evidence

PR #233 exact head `44590d08274dcf0ebdf9f1680c18875a977e2fdc` passed:

- run `33220488843`, job `99013300808`;
- artifact `9704970824`;
- artifact ZIP `sha256:7fd46152e98946619603411c5b982d496dd434246f14306e4ad8064cfd6e5fdb`;
- straightforward ResultManifest `sha256:9b873d0b734fbed6b9b069f49344b533f72456cb08a1579e2d7d102b507ce8cd`;
- straightforward VerificationResult `sha256:30efcf3e86c8f68f1326a85a91e479670071eca2a913b40d1fc88afb458fcdf1`;
- inert-decoy ResultManifest `sha256:2944cecb26876fe0a4340333a3c14dc253928b13d77426013f4901ea3c64fc91`;
- inert-decoy VerificationResult `sha256:fc2881809825978c0bca41575be204b641c71f9d9cf4de7e0b7827bf2e3ad44b`.

PR #233 merged as `621e648d6eb9503489a7cbddd53f95bfaf9941e7`.
The receipt removes Task 004 from the calibration-pending set but leaves Task
001 pending, `freeze_ready=false`, and every scored evidence field empty. A
fresh novelty audit is still required before any later freeze. Related: #180.
