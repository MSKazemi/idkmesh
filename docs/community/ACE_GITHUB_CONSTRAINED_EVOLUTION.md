# ACE: GitHub-Constrained Self-Improving Community

**Status:** working design for the next ACE iteration.

This document refines [COMMUNITY_GROWTH_ENGINE.md](../../COMMUNITY_GROWTH_ENGINE.md) around a practical constraint: IDKMesh currently lives inside GitHub. Its community-evolution system therefore has to work with GitHub Issues, Pull Requests, reviews, labels, reactions, repository files, Actions, schedules, and API limits instead of assuming an unrestricted autonomous social platform.

The objective is not to automate publicity. It is to create a **self-improving contribution ecology** in which verified useful work makes the next useful contribution easier while the control policy itself learns from evidence.

## 1. The central design rule

Do not implement:

```text
GitHub event -> public comment -> another event -> another public comment -> ...
```

That architecture is noisy, expensive in workflow/API calls, easy to game, and constrained by GitHub recursion/rate protections.

Use a generational architecture:

```text
many repository events
        |
        v
one quiet state / evidence ledger
        |
        v
periodic generation evaluation
        |
        v
choose community mode + policy
        |
        v
at most a small bounded set of public actions
        |
        v
observe verified descendants
        |
        +---------------------------> next generation
```

GitHub is the environment; ACE is the adaptive policy living inside that environment.

## 2. Biological model: reproduction with carrying capacity

Let:

- `P_t` = number of verified parent contributions in generation `t`;
- `D_t` = verified descendant contributions caused by those parents within window `W`;
- `L_t` = review/maintainer load;
- `K_t` = sustainable review capacity.

Define the community reproduction number:

```text
R_c(t, W) = D_t / max(1, P_t)
```

A useful community can become self-sustaining when `R_c > 1`, but only if it does not exceed its verification capacity.

Define the ecological capacity gate:

```text
C_t = 1 / (1 + exp((L_t - K_t) / tau))
```

`C_t` approaches 1 while the review system has capacity and approaches 0 when the project is overloaded.

The effective reproduction pressure is therefore:

```text
R_eff(t) = R_c(t) * C_t
```

The goal is **not maximum `R_c`**. The target is a stable region where verified contribution reproduces while latency, review debt, and maintainer concentration remain bounded.

## 3. Stigmergy: GitHub as the shared environment

Ant colonies coordinate by leaving traces in the environment. ACE can use a digital equivalent without a central dispatcher.

Useful traces include:

- `good first issue` and `help wanted` labels;
- Growth Seed issues;
- links from a merged PR to a reproduction/challenge task;
- acceptance criteria in issue bodies;
- test evidence and benchmark artifacts;
- Goal/Evidence Graph references;
- public decision records;
- reproducibility markers;
- labels that signal verification, risk, or missing expertise.

A contributor should be able to inspect the repository and infer where useful energy is needed without private coordination.

## 4. Evolutionary model: the community policy itself evolves

ACE should not permanently hard-code one growth strategy.

Let the available strategies be:

```text
S = {
  reproduce,
  challenge,
  extend,
  explain,
  newcomer_second_step,
  recruit_reviewer,
  improve_onboarding,
  cross_project_connection
}
```

Each strategy `i` has probability/weight `w_i(t)`.

Measure fitness from **verified descendants per scarce human attention**, not raw interactions:

```text
f_i(t) =
    verified_descendant_value_i
    ----------------------------------
    1 + reviewer_minutes_i + maintainer_minutes_i
    - lambda_spam * noise_i
    - lambda_latency * added_review_delay_i
```

A replicator-style update is:

```text
w_i*(t+1) = w_i(t) * exp(eta * (f_i(t) - mean_fitness(t)))
```

Normalize and add mutation/exploration:

```text
w_i(t+1) =
    (1 - mu) * normalize(w_i*(t+1))
    + mu / |S|
```

`mu > 0` prevents the project from converging permanently on one strategy or one contributor niche.

This is the main mechanism by which the **community-building algorithm improves itself**.

## 5. Statistical physics: exploration temperature

ACE should use an exploration temperature `T_t`.

When evidence is weak or the repository is stagnant, increase `T_t`: try more diverse Growth Seed types and preserve multiple hypotheses.

When evidence is strong and review capacity is constrained, decrease `T_t`: concentrate on proven strategies and consolidation.

A simple policy-selection distribution is:

```text
P(strategy = i) = exp(f_i / T_t) / sum_j exp(f_j / T_t)
```

High `T_t` -> flatter distribution -> exploration.

Low `T_t` -> sharper distribution -> exploitation.

A possible adaptive temperature is:

```text
T_t = clip(T_min, T_max,
           T_0 * uncertainty_t * capacity_t)
```

This is inspired by statistical mechanics/simulated annealing. It is not a claim that GitHub is a physical thermodynamic system.

## 6. Information theory: grow where uncertainty can be reduced

For candidate Growth Seed `s`, estimate:

- `I_s`: expected useful impact;
- `G_s`: expected information gain;
- `B_s`: boundedness/clarity;
- `N_s`: newcomer accessibility;
- `D_s`: diversity/niche value;
- `H_s`: expected reviewer/maintainer attention;
- `X_s`: execution friction;
- `S_s`: spam/noise risk.

Define a potential gradient:

```text
Potential(s) =
  (I_s * G_s * B_s * N_s * D_s)
  --------------------------------
  (1 + H_s + X_s + S_s)
```

ACE should surface a small number of high-potential seeds, not create a large number of generic tasks.

This turns repository growth into a search for **high information gain per unit of human attention**.

## 7. Political science: polycentric and bicameral control

An adaptive community system needs checks on its own growth.

ACE uses a two-gate model for any higher-amplification action.

### Evidence gate

The parent activity must be independently useful or verified.

Examples:

- merged code plus passing independent verification;
- research claim plus reproduction;
- repeated user demand plus a bounded implementation;
- an experiment plus an inspectable result artifact.

### Community-capacity gate

The community must be able to absorb the descendant work.

Check:

- unreviewed PR count;
- median first-response time;
- age of open Growth Seeds;
- active reviewer count;
- maintainer concentration;
- unresolved security/governance debt.

A growth action occurs only when both gates pass.

This is analogous to bicameral checks: **value is insufficient without capacity, and popularity is insufficient without evidence**.

Future IDKMesh cells/subprojects can use polycentric governance: local communities choose local strategies while shared constitutional rules govern security, provenance, interoperability, and high-impact changes.

## 8. Adversarial / Red Queen model

Biological Red Queen dynamics and adversarial strategy suggest a useful rule: every successful capability should periodically face a counter-test.

For a verified parent contribution, ACE may choose among:

```text
build -> reproduce
build -> challenge
build -> security review
claim -> falsification experiment
optimization -> regression benchmark
new workflow -> abuse/threat model
```

This creates a constructive attacker/defender loop without turning the project into conflict between people.

The target is resilience:

```text
progress = capability_gain - unmeasured_failure_surface
```

This is also the useful part of military/OODA-loop inspiration:

```text
Observe -> Orient -> Decide -> Act -> Observe
```

ACE should shorten this loop for evidence while keeping high-impact acts bounded and reviewable.

## 9. Quantum-inspired idea: maintain competing hypotheses, not fake quantum computing

Ordinary GitHub Actions are classical computation. ACE should not claim quantum behavior.

A useful quantum-*inspired* principle is to avoid collapsing uncertain choices too early.

Maintain a probability distribution over policy hypotheses:

```text
p(t) = [p_1, p_2, ..., p_n]
```

Measure policy uncertainty with Shannon entropy:

```text
H(p) = -sum_i p_i log p_i
```

As verified evidence arrives, update probabilities (for example by Bayesian or multiplicative-weights updates). High entropy means several strategies remain plausible; low entropy means evidence supports concentration.

This gives IDKMesh the useful conceptual property often loosely associated with "superposition" while staying mathematically honest: **multiple alternatives remain live until evidence justifies convergence**.

## 10. GitHub constraint model

ACE should treat GitHub limits as part of the optimization problem.

Let:

- `A_t` = GitHub API calls consumed in a window;
- `W_t` = content-generating writes (issues, comments, edits, labels where applicable);
- `G_t` = Actions workflow runs;
- `N_t` = notifications likely generated;
- `B_API`, `B_WRITE`, `B_RUN`, `B_NOTIFY` = internal conservative budgets below platform limits.

Define the automation budget:

```text
B_t = min(
  B_API - A_t,
  B_WRITE - W_t,
  B_RUN - G_t,
  B_NOTIFY - N_t
)
```

No growth policy may spend more than `B_t`.

The internal budgets should be deliberately much smaller than GitHub's maximums. Platform limits are emergency ceilings, not desired operating points.

### Current GitHub facts relevant to ACE

As of 2026-08-28, GitHub documentation states:

- `GITHUB_TOKEN` REST requests are limited to 1,000 requests/hour/repository for ordinary GitHub.com repositories (higher for some Enterprise Cloud cases).
- GitHub also enforces secondary limits; general content creation is documented as no more than roughly 80 content-generating requests/minute and 500/hour, with some endpoints potentially lower and limits subject to change.
- Events caused by the repository `GITHUB_TOKEN` normally do not create another workflow run, with documented exceptions including `workflow_dispatch`, `repository_dispatch`, and special handling for some automation-created pull-request events. This protects against accidental recursive workflows but also means ACE cannot rely on an unrestricted recursive event chain.
- `pull_request_target` runs in a privileged base-repository context. GitHub advises avoiding it where unnecessary and never checking out or executing untrusted PR code in a privileged workflow.
- Issue/PR comments generate notifications and are subject to content/rate controls, so comment-per-event automation is a poor community-growth primitive.
- Standard GitHub-hosted Actions usage is currently free for public repositories, but usage and platform limits still exist.

Sources:

- https://docs.github.com/en/actions/concepts/security/github_token
- https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api
- https://docs.github.com/en/rest/using-the-rest-api/best-practices-for-using-the-rest-api
- https://docs.github.com/en/actions/reference/security/secure-use
- https://docs.github.com/en/actions/concepts/billing-and-usage

## 11. Consequence: quiet observation, rare actuation

The ACE ratio should be deliberately asymmetric:

```text
many observations : few public writes
```

A good initial target is conceptual rather than fixed:

```text
100 observed signals -> 1 or fewer autonomous public growth actions
```

The exact ratio should later be learned from evidence.

Preferred state storage order for GitHub-only v0/v1:

1. one Growth Ledger issue body for small mutable state;
2. repository files for durable schemas, policies, and experiment results;
3. labels/issue bodies for stigmergic public signals;
4. workflow artifacts only for temporary machine outputs;
5. comments only when a human actually benefits from receiving a notification.

## 12. Generational controller

Instead of recursive per-event growth, operate in generations, for example daily or after enough high-value events accumulate.

At generation `t`:

### Observe

Collect/update low-cost state:

- merged PRs;
- issue completion;
- independent reviews/reproductions;
- first-time contributor activity;
- open Growth Seeds;
- review latency/load;
- coarse discovery signals such as star/fork deltas.

### Estimate

Compute:

```text
R_c(t)
C_t
policy fitness f_i(t)
uncertainty H_t
review debt L_t
```

### Select mode

```text
if severe review/security/governance debt:
    CONSOLIDATE
elif R_c < 1 and capacity is healthy:
    EXPLORE
elif R_c >= 1 and capacity is healthy:
    GROW
else:
    DORMANT
```

### Select one bounded action

Examples:

- surface one existing Growth Seed more clearly;
- create one reproduction/challenge seed from a verified parent;
- convert an unclear issue into a bounded newcomer task;
- request one independent review where diversity is valuable;
- improve one onboarding document;
- create no public action at all.

"Do nothing" is a valid policy action.

### Learn

After descendant outcomes become measurable, update strategy weights and temperature.

## 13. Event hierarchy

Not every GitHub event deserves an Actions run forever.

### Tier A: high-value events

Good direct triggers:

- merged/closed PR;
- issue opened/closed where ACE state is needed;
- submitted review if it contributes verification evidence;
- manual `workflow_dispatch`.

### Tier B: medium-value events

Potentially aggregate or sample:

- pushes to main;
- discussions;
- issue comments;
- reactions.

### Tier C: discovery/noise-prone events

Prefer low-frequency aggregate sampling once the repository becomes busy:

- stars;
- forks;
- repeated reactions.

At small scale, direct events are acceptable. At larger scale, one Actions run per star/fork is unnecessarily expensive relative to its information value.

## 14. Anti-Goodhart constitution

ACE must not optimize:

- stars;
- forks;
- issue count;
- comments;
- reactions;
- PR count;
- commit count;
- raw contributor count.

These can all be gamed and can all increase while project health declines.

The leading candidate objective is:

```text
verified useful descendant value
---------------------------------------------
reviewer attention + maintainer attention
+ compute cost + community friction
```

with hard constraints on security, conduct, contributor consent, and maintainer concentration.

## 15. The self-improving loop

The intended loop is:

```text
verified contribution
    -> leaves a legible trace / opportunity
    -> another contributor can act
    -> independent verification
    -> descendant is measured
    -> policy fitness is updated
    -> successful strategy becomes slightly more likely
    -> mutation preserves alternatives
    -> capacity governor limits reproduction
    -> next generation
```

This is a **community metabolism** rather than an advertising bot.

## 16. What should be implemented next

Do not add broad autonomous write capability yet. The repository already has ACE v0 and an active bootstrap cohort.

The next evidence-first steps are:

1. Finish the parent -> seed -> descendant evidence-link schema (current Growth Seed issue).
2. Measure `R_c` from real repository descendants rather than proxy credit.
3. Add a generational evaluation step that computes policy fitness without creating more public content.
4. Add strategy weights and mutation to the Growth Ledger state.
5. Add a strict public-write budget, initially at most one autonomous Growth Seed per generation and only from a verified parent.
6. Add explicit review/security capacity gates.
7. Remove or aggregate low-information event triggers if repository activity becomes high enough that per-event Actions runs are wasteful.
8. Only after several generations of evidence, allow the controller to choose among multiple seed strategies.

The first success criterion is not community size. It is evidence that a verified contribution can reliably create another verified contribution **without increasing maintainer effort at the same rate**.
