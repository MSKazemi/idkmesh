# E031 — Does *learning* the goal rescue the consensus swarm?

## Research question

[E024](E024-matched-budget-emergence.md)'s limitation on its own headline result
has two halves. [E030](E030-supplied-goal-membership.md) measured the first: the
supplied plausible-goal set contains the goal the environment later switches to,
and the two arms that read that set are handed the answer. The finding was
arm-specific and inverted what E024 feared — the Quality-Diversity archive keeps
`95.6%`–`98.4%` of its lead when the future goal is not a member, while the
majority-vote swarm loses its entire lead and goes negative in three of four
panels.

This is the second half, quoted verbatim from E024:

> the plausible goals are supplied by the experimenter rather than **learned**
> … This is a test of retaining alternatives under known goal ambiguity, not a
> learned Goal Graph.

E031 builds the learned Goal Graph and points it where E030 says the confound
actually lives: at `majority`, not at the archive.

The answer is yes, with a condition that inverts the obvious design. Learning
the goal helps **only if the swarm does not begin learning until the goal has
already moved**. An arm that learns from post-change evidence alone posts the
best mean of any variant in all eight cells of the matrix and cuts the published
`majority` row's catastrophic seeds in every one of them — `38-39` to `20-22`
where the new goal is one of the supplied hypotheses, `42-43` to `25-29` where
it is not. The same filter, learning from generation 0, is the single worst
thing that can be done to the arm: it concentrates the swarm onto an objective
that is about to be replaced, and its catastrophic seeds roughly double.

A second result is a warning about how far the first generalises. Simply
*spreading* the swarm's beliefs — no evidence, no updating, in one case a single
jitter at initialisation then frozen for fifty generations — takes `38/100`
catastrophic seeds to `0/100` when the goal the environment moves to is one of
the four supplied hypotheses. Against E030's parity-matched goal that is **not**
in that set, every one of those spread arms is *worse* than doing nothing:
`0/100` becomes `51/100`, and the frozen-jitter arm becomes the worst
non-learning arm in the table at `71/100`.

So the swarm's failure mode is removable two ways, and only one of them
survives the goal leaving the box. Diversity around four supplied points rescues
it when the answer is among those points. Learning after the change rescues it
either way.

## The arm

`learned` is `majority` with beliefs that update. Every structural choice is
identical — one hypothesis per agent, drawn from the same supplied set with the
same random draw, a strict-majority pairwise vote, one consensus artifact, the
same matched evaluation budget — except that the swarm is a **particle filter**
and its hypotheses move.

That identity is not a claim, it is a reduction. At a flat likelihood
(`epsilon = 0.5`) no weight ever changes, the effective sample size never drops,
no resampling fires, the filter consumes no random number, and the arm
reproduces **the published `majority` row of `matched_budget_emergence.run_seed`
bit-for-bit** — same seed derivation, same rng consumption, same trace, same
`verification_attempts`. The test suite pins that against the live baseline, on
both a perfect and an imperfect panel. Every difference reported below is
therefore attributable to the parameters the ladder varies, and to nothing
else — not to a changed vote rule, a shifted random stream, or an extra draw
consumed somewhere.

The credibility-weighted vote is what makes that possible: mass above one half
with uniform weights *is* the strict-majority rule, `count >= n//2 + 1`, exactly,
for every agent count. The test suite checks that over the full range of counts
rather than at one size.

## The evidence channel, and why it is deliberately weak

The obvious feedback signal — the delivered artifact's realized utility — is too
strong to be interesting. `utility` is `min(1, Σ wᵢxᵢ + 0.08·√(x₀x₄))`, so an
arm that observes the value and knows the traits it shipped can subtract the
interaction term and read off **one linear equation in the goal weights per
generation**. Four or five independent deliveries and a least-squares solve
recover the goal exactly. An experiment built on that measures whether a 4×4
system can be inverted, not whether a swarm can learn.

So the observation is **ordinal**: the swarm ships an artifact and learns only
whether it did better or worse than the one it shipped before. That is what a
deployed system actually gets — a preference, a regression signal, a rollback —
and it is the same shape as the vote the swarm already takes internally. It
cannot be algebraically inverted. A test asserts the likelihood never consumes
the delivered value itself.

Particles that predicted the observed direction are up-weighted by `1 − ε` and
the rest by `ε`. When the effective sample size falls below half the particle
count the filter systematically resamples and **jitters** the survivors on the
simplex. The jitter is what makes this a *learned* Goal Graph rather than a
re-weighted oracle: particles start at the supplied hypotheses but are not
confined to them, so the filter *can* converge on a goal that was never in the
box. Whether it does is Result 1's question, and the answer is no.

## The variant ladder

Each rung exists to rule out one alternative explanation for the rung above it.
This is a decomposition, not a parameter sweep.

| variant | what it is | what it rules out |
|---|---|---|
| `control` | flat likelihood | — it *is* the published `majority` arm |
| `learned` | the filter, from generation 0 | — |
| `learned-no-jitter` | particles pinned to the supplied points | "the harm was leaving the set" |
| `placebo` | the same concentration dynamics driven by **coin flips** | "the harm was concentrating the posterior" |
| `placebo-no-jitter` | the placebo with its particles pinned | "the benefit came from the reweighting" |
| `diffusion` | no likelihood, no reweighting, no resampling — beliefs only drift | "the benefit needed evidence" |
| `diffusion-slow` | a quarter of that drift rate | "the diffusion rate was tuned" |
| `vote-noise` | loosens the consensus **without touching a belief** | "any less-rigid consensus would do" |
| `diverse-init` | spread **once** at initialisation, then frozen forever | "the beliefs have to keep moving" |
| `learned-after-change` | learns only from post-change evidence | "learning is what hurts" — it separates learning from learning *early* |
| `oracle-reset` | told for free exactly when the goal moved | "knowing when to discount the old evidence would have fixed it" |

`oracle-reset` is an upper bound, not a proposal. No deployed system is handed
its own change point.

## Reproduction

```bash
PYTHONPATH=. python3 sim/e031_learned_goal_filter.py --mode matrix --seeds 100 \
  --output experiments/results/E031-learned-goal-filter.json

PYTHONPATH=. python3 sim/e031_learned_goal_filter.py --mode trajectory \
  --seed 7 --variant learned \
  --output experiments/results/E031-trajectory-seed7-learned.json
```

100 seeds, 64 agents, 50 generations, change at 25, 8 niche bins, the four
[E027](E027-defect-propagation.md) verifier panels, both
[E030](E030-supplied-goal-membership.md) goal conditions, defect channel
disarmed. `epsilon = 0.3`, `jitter = 0.05`, resample below `0.5` ESS.
Catastrophe threshold is E024's absolute cutoff, `0.64 × 25 = 16.0` AUC, so the
counts here are directly comparable to E024's, E027's, E028's and E030's.

The five published arms are **recomputed live in the same run** rather than
quoted, so the baseline each variant is measured against is this run's, and the
test suite checks the `control` variant equals that run's own `majority` row.

Recomputed sweeps should be compared **by value, not byte-for-byte** — the
simulators go through `exp` and `**`, whose last-place rounding differs across
CPUs and C libraries.

## Result 1 — the filter learns, and that is what hurts

One seed, four variants, two numbers per generation: the distance from the
swarm's posterior mean to the goal actually in force (**error**), and the mean
distance of its particles from that posterior mean (**spread**). Seed 7, perfect
panel, held condition; the committed trajectories are in
`experiments/results/E031-trajectory-seed7-*.json`.

| | 0 | 6 | 12 | 18 | 24 ‖ | 25 | 31 | 37 | 43 | 49 | AUC |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `control` error | `0.171` | `0.171` | `0.171` | `0.171` | `0.171` | `0.204` | `0.204` | `0.204` | `0.204` | `0.204` | `22.50` |
| `control` spread | `0.147` | `0.147` | `0.147` | `0.147` | `0.147` | `0.147` | `0.147` | `0.147` | `0.147` | `0.147` | |
| `learned` error | `0.171` | **`0.061`** | `0.076` | `0.074` | `0.075` | `0.362` | `0.351` | `0.318` | `0.300` | `0.300` | **`15.66`** |
| `learned` spread | `0.147` | `0.115` | `0.115` | `0.131` | `0.131` | `0.131` | `0.131` | `0.146` | `0.147` | `0.147` | |
| `diffusion` error | `0.171` | `0.180` | `0.170` | `0.171` | `0.172` | `0.200` | `0.188` | `0.187` | `0.192` | `0.190` | `21.98` |
| `diffusion` spread | `0.147` | `0.170` | `0.193` | `0.220` | `0.241` | `0.253` | `0.263` | `0.277` | `0.294` | `0.299` | |
| `diverse-init` error | `0.171` | `0.171` | `0.171` | `0.171` | `0.171` | `0.205` | `0.205` | `0.205` | `0.205` | `0.205` | `16.59` |
| `diverse-init` spread | `0.183` | `0.183` | `0.183` | `0.183` | `0.183` | `0.183` | `0.183` | `0.183` | `0.183` | `0.183` | |

The filter works. It takes the swarm's belief error from `0.171` to `0.061`
within six generations — a genuine 2.8× improvement over a control whose
posterior, by construction, never moves at all. It pays for that with spread,
which falls from `0.147` to `0.115`. Then the goal changes, and the same
concentration that made it right about the old world makes it the worst arm in
the new one: error jumps to `0.362` and it ends at `0.300`, *further* from the
truth than the control that learned nothing.

`diffusion` never improves its error at all — `0.171` to `0.190`, against the
control's `0.171` to `0.204` — while its spread more than doubles. `diverse-init`
holds both numbers flat for fifty generations, at the control's error and above
its spread.

This is one seed, chosen to show the belief dynamics rather than the outcome;
seed 7 is not catastrophic for any of these arms, and the AUC column is included
only so the trajectory is not read as decoupled from the result. The outcome
claims are in Result 2.

## Result 2 — the ladder, where the new goal is one of the supplied four

100 seeds, perfect panel, `held` condition. `cat` is catastrophic seeds out of
100 against the `16.0` cutoff. `error` is the mean distance from the swarm's
posterior mean to the true goal at the last generation — how *right* it is.
`spread` is the mean distance of its particles from that posterior mean — how
*varied* it is. The two are independent, and the table is sorted by `cat`.

| variant | AUC mean | cat | error | spread | evidence used |
|---|---|---|---|---|---|
| `diffusion` | `19.172` | **`0`** | `0.222` | `0.2810` | none |
| `diffusion-slow` | `18.748` | **`0`** | `0.222` | `0.1977` | none |
| `diverse-init` | `18.267` | **`0`** | `0.219` | `0.1752` | none |
| `placebo` | `18.922` | `4` | `0.224` | `0.1970` | none (coin flips) |
| `learned-after-change` | **`19.821`** | `22` | `0.163` | `0.1432` | ordinal, post-change |
| `vote-noise` | `17.246` | `28` | `0.219` | `0.1448` | none (vote only) |
| `oracle-reset` | `18.676` | `29` | **`0.099`** | `0.1356` | ordinal + free change point |
| `control` (= published `majority`) | `18.886` | `38` | `0.219` | `0.1448` | none |
| `placebo-no-jitter` | `18.636` | `47` | `0.222` | `0.1409` | none (coin flips) |
| `learned` | `15.115` | `77` | `0.330` | `0.1481` | ordinal |
| `learned-no-jitter` | `14.241` | **`99`** | `0.343` | **`0.0966`** | ordinal |

Read the `error` column against `cat` and there is no relationship. The most
accurate posterior measured here — `oracle-reset` at `0.099`, handed its own
change point for free — sits at `29`, worse than three arms that end no more
accurate than the control. The two least accurate arms are also the two worst,
but they are the two that *learned*, which is a different variable.

Read the `spread` column and, in this condition, the picture resolves. Take the
seven variants that carry no evidence about the goal and sort them by it:

| variant | spread | catastrophic |
|---|---|---|
| `placebo-no-jitter` | `0.1409` | `47` |
| `control` | `0.1448` | `38` |
| `vote-noise` | `0.1448` | `28` |
| `diverse-init` | `0.1752` | **`0`** |
| `placebo` | `0.1970` | `4` |
| `diffusion-slow` | `0.1977` | **`0`** |
| `diffusion` | `0.2810` | **`0`** |

Every arm above `0.175` is at `0`–`4`. Every arm at or below `0.145` is at
`28`–`47`. It does not matter where the spread came from: a filter reweighting
on coin flips, a drift applied every fifth generation, and a one-shot jitter at
initialisation that is then **frozen for the entire run** all land on the same
side of it. `diverse-init` in particular has no likelihood, no reweighting, no
resampling and no drift — nothing that could respond to the goal changing at
generation 25 — and it reaches `0/100`. Whatever is happening, it is not
adaptation.

Three rival explanations are ruled out inside this condition:

- **"Any less-rigid consensus would do."** `vote-noise` flips a quarter of the
  vote outcomes — at the noise level that minimised catastrophic seeds over a
  `0.02`–`0.50` sweep (`0.02`→`36`, `0.05`→`37`, `0.10`→`34`, `0.25`→`28`,
  `0.50`→`71`), so the rival gets its best case — without touching a single
  belief. It reaches `28` and pays `-1.64` AUC for it. Diffusion reaches `0`
  and *gains* `+0.29`. Loosening the vote costs mean AUC against the control in
  all eight cells of the matrix; a test pins that.
- **"It is the reweighting, not the spread."** `placebo` and `placebo-no-jitter`
  are the same coin-flip filter with the particles free or pinned: `4` against
  `47`.
- **"The drift is quietly finding the new goal."** Belief error at the end is
  `0.222` for `diffusion` against `0.219` for the control. The spread arms end
  *no more accurate*. They are not learning anything.

## Result 3 — the same ladder, where the new goal is not in the set

Everything above is measured against a goal the swarm was handed in advance.
E030 built a parity-matched substitute that is **not** a member of
`PLAUSIBLE_GOALS` — same distance from the initial goal, same attainable
ceiling, same transfer regret, only membership changes. Rerun the identical
ladder in that condition, same panel, same 100 seeds:

| variant | held cat | **unheld cat** | held AUC | unheld AUC |
|---|---|---|---|---|
| `diffusion` | `0` | **`51`** | `19.172` | `17.716` |
| `diffusion-slow` | `0` | **`57`** | `18.748` | `17.105` |
| `diverse-init` | `0` | **`71`** | `18.267` | `16.417` |
| `placebo` | `4` | **`55`** | `18.922` | `17.562` |
| `learned-after-change` | `22` | **`29`** | `19.821` | `19.367` |
| `vote-noise` | `28` | `46` | `17.246` | `16.651` |
| `oracle-reset` | `29` | `32` | `18.676` | `18.029` |
| `control` | `38` | `43` | `18.886` | `18.392` |
| `placebo-no-jitter` | `47` | `47` | `18.636` | `18.124` |
| `learned` | `77` | `98` | `15.115` | `13.549` |
| `learned-no-jitter` | `99` | `99` | `14.241` | `13.257` |

The spread result does not survive. Every arm that was at `0`–`4` is now at
`51`–`71`, and **every one of them is worse than the control**, which moves only
`38`→`43`. The ordering by spread inverts: in the `held` condition the
least-spread non-learning arm fails `47` times and the most-spread arm `0`; in
`unheld` the least-spread arm fails `47` times and the most-spread arm `51`.
Two tests assert the ordering in one direction and its inversion in the other,
so the record cannot drift back to the simpler story.

The mechanism this exposes is geometric, and it is a property of the *set*, not
of diversity. The held goal **is** one of the four supplied points, so perturbing
sixty-four agents around those points scatters some of them onto and around it;
that is the whole rescue. E030's substitute is by construction not a member, and
its nearest supplied hypothesis is `0.206398` away — recorded in
`experiments/results/E030-goal-parity.json` as
`distance_to_nearest_held_hypothesis` — while the jitter scale is `0.05`. The
drift cannot reach it. All it does there is cost the swarm the consensus it had,
which is why every spread arm ends up below the control.

The verifier panel is not a factor in any of this. Across the four E027 panels
within a condition, no variant's catastrophic count moves by more than `8`,
while the same variant moves by up to `71` between the two goal conditions. A
test pins both halves of that.

## Result 4 — the variable that survives is *when* the learning happens

One arm is better than the control in all eight cells, on both the tail and the
mean:

| cell | `control` cat → AUC | `learned-after-change` cat → AUC |
|---|---|---|
| perfect / held | `38` → `18.886` | `22` → `19.821` |
| independent / held | `38` → `18.886` | `22` → `19.821` |
| measured / held | `38` → `18.926` | `20` → `19.757` |
| stress / held | `39` → `19.029` | `22` → `19.880` |
| perfect / unheld | `43` → `18.392` | `29` → `19.367` |
| independent / unheld | `43` → `18.392` | `29` → `19.367` |
| measured / unheld | `42` → `18.414` | `27` → `19.324` |
| stress / unheld | `43` → `18.445` | `25` → `19.375` |

It is also the **best mean of any variant in every cell**, spread arms included,
and it beats `oracle-reset` — which is handed the change point for free but still
carries its pre-change evidence — on the tail in every cell. It improves the
posterior in both conditions (`0.163` against the control's `0.219` held,
`0.252` against `0.279` unheld), on a mean of only `3.0`–`3.4` observations.

The contrast with `learned` is the whole finding. Same filter, same likelihood,
same jitter, same resampling — the only difference is that one of them is
allowed to update before generation 25 and the other is not. `learned` goes to
`76`–`80` catastrophic held and `97`–`98` unheld; `learned-after-change` goes to
`20`–`22` and `25`–`29`. Learning is not harmful. Learning an objective that is
about to be replaced is, and it is harmful enough to more than cancel the
benefit of learning the one that replaces it.

Result 1's trajectory shows the mechanism on one seed: `learned` takes its
belief error from `0.171` to `0.061` in six generations and pays for it in
spread. Across the full 100 seeds the same collapse reads as a spread of
`0.1351` at the moment of the change against the control's `0.1448` — the swarm
arrives at generation 25 concentrated on an objective that has just stopped
being true. Pin the particles so it cannot re-diffuse afterwards and it reaches
`97`–`100` catastrophic in every cell, at the lowest spread in the table.

## Interpretation

E024 asked, in issue #22's words, whether a population can **reliably** evolve
toward a coherent system, and answered that the archive's contribution is
removing a failure mode rather than raising a mean. E030 showed the consensus
swarm's apparent contribution was the supplied answer. E031 asked whether
learning the answer recovers it.

The finding, stated as narrowly as the evidence supports:

- **A learned Goal Graph does help this arm, but only if it discards evidence
  gathered before the goal moved.** Learning from post-change evidence alone is
  the best variant in all eight cells on the mean and beats the control on the
  tail in all eight. It is also better than being handed the change point for
  free, which is the stronger statement: the problem is not detecting the change,
  it is that the pre-change posterior is actively worth less than no posterior.
- **Learning from generation 0 is the worst intervention in the ladder.** It
  roughly doubles catastrophic seeds held and takes them to `97`–`98` unheld.
  The filter demonstrably works — belief error `0.171`→`0.061` in six
  generations — and that is precisely why it fails.
- **Belief accuracy does not predict the outcome.** The most accurate posterior
  in the held condition belongs to `oracle-reset`, and three arms that end no
  more accurate than the control beat it outright.
- **Belief spread removes the failure mode, and only inside the supplied set.**
  `38/100`→`0/100` with no evidence at all when the new goal is one of the four
  hypotheses; `43/100`→`51/100` when it is not. This is the sharpest limit in
  the record, and it is stated as a limit rather than a result because the
  intuitive reading — "keep the population diverse" — is exactly the reading the
  `unheld` column refutes.

That composes with E030 one level down, in both directions. There, the archive's
advantage survived losing a correct hypothesis because what it retained was
*diverse artifacts*, evaluated against the world. Here, diverse *beliefs* rescue
the swarm only while the world stays inside the beliefs — because a belief, unlike
an artifact, is never checked against anything. The through-line for issue #22 is
that what makes a population reliably arrive somewhere coherent, on this
landscape, is what it keeps **and tests**, not what it holds.

Two things this does not show. First, none of these variants reaches the archive:
`qd` is ahead of every belief variant in every cell — `21.81`–`22.40` against a
best of `19.88` — so this is about how to stop a consensus swarm failing, not
about closing the gap to an archive. Second, `diffusion` and `diverse-init` are
diagnostics, not designs, and Result 3 is why: they are tuned, without meaning to
be, to a hypothesis set that contains the answer.

## Limitations

- **The evidence channel is ordinal by construction.** A value channel would let
  an arm solve for the goal in four generations, which would measure linear
  algebra. That is a defensible choice but it is a choice, and a system with
  richer feedback than "better or worse than last time" is not modelled here.
- **The post-change evidence rate is low.** Learning happens only in generations
  where the consensus actually changed — a mean of `3.0`–`3.4` post-change
  observations for `learned-after-change` across the eight cells. The belief-error columns exist so a
  null result is readable, and they show the filter *does* learn pre-change, but
  a richer evidence rate could change the balance.
- **Spread is measured, not controlled.** In the `held` condition the seven
  non-learning arms fall cleanly either side of a `~0.15`/`~0.175` gap, but no
  arm was run at a prescribed spread, so that gap is read off seven points
  rather than swept. The claim is that spread orders these arms in that
  condition, not that `0.16` is a boundary.
- **The spread result does not generalise past the supplied set, and that is
  the sharpest limit here.** Result 3 measures the inversion directly: every
  arm that reaches `0`–`4` catastrophic seeds against a goal inside the set
  reaches `51`–`71` against E030's parity-matched goal outside it, worse than
  doing nothing. Anyone quoting the `38/100`→`0/100` number without the
  condition attached is quoting half a result.
- **One substitute direction.** `unheld` is E030's single parity-matched goal,
  not a distribution over non-member goals. The inversion is measured once, in
  one direction, at a distance of `0.206398` from the nearest supplied
  hypothesis. Whether the rescue degrades smoothly with that distance or falls
  off a cliff is not measured.
- **Spread does not explain the learning arms.** Result 4 is explicit about
  this: `learned` ends at a spread marginally above the control and still fails
  more than twice as often, because its collapse happened before the change.
  Two mechanisms, reported as two.
- **`learned-after-change` is handed the change point too.** It does not detect
  the change; it is told when to start. It is a cleaner upper bound than
  `oracle-reset` — it discards the pre-change posterior rather than being told
  when to discount it — but it is still an upper bound, and a deployed system
  would need change detection this experiment does not model.
- **`oracle-reset` is an upper bound, not a design.** It is told for free exactly
  when the goal moved.
- **One filter family.** Particles on the simplex with Gaussian jitter and
  systematic resampling. A different belief representation could behave
  differently, and the `diverse-init` result in particular says something about
  *this* landscape's geometry around the four supplied points.
- **The defect channel is disarmed.** E027 and E028 cover it. Arming a second
  confound at once would make any effect unattributable.
- **The landscape is synthetic**, as in every experiment from E011 onward.

## Decision

E024's caveat is now closed on both halves, and neither closure went the way the
caveat implied. E030 showed the *supplied* half costs the archive almost nothing
and costs the swarm everything. E031 shows the *not-learned* half is real but
inverted in sign: a learned Goal Graph does help this arm, and only if it throws
away everything it learned before the goal moved.

Any future record quoting `majority` must therefore say four things: its measured
advantage on this landscape is contingent on the supplied set containing the
answer (E030); giving it a filter that learns from generation 0 roughly doubles
its failure rate (E031); learning from post-change evidence alone is the best
variant measured here, in all eight cells, on both the tail and the mean (E031);
and the evidence-free rescue — perturbing the beliefs once at initialisation —
works only while the goal stays inside the supplied set and is worse than nothing
outside it (E031).

Issue #22 remains open. E031 closes none of it by itself; it removes the second
of the two named confounds from the arm that carried them, and it adds a
condition to the first removal that E030 could not have seen on its own.
