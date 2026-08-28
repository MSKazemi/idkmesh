# IDKMesh Autocatalytic Community Evolution (ACE)

**Status:** Experimental design + implementable v0.

IDKMesh should not depend on continuous manual promotion by one maintainer. The repository itself should become an adaptive system in which useful activity increases the probability of more useful activity.

This document defines **ACE — Autocatalytic Community Evolution**: a GitHub-native feedback algorithm inspired by branching processes, ecology, evolutionary dynamics, stigmergy, economics, political science, psychology, and information theory.

The goal is not artificial engagement. The goal is **verified community reproduction**:

> A useful contribution should leave behind clearer knowledge, lower friction, and one or more bounded opportunities that make the next useful contribution easier.

The system should grow only while the community has enough review and governance capacity to absorb that growth.

---

## 1. The central quantity: community reproduction number

Treat accepted community work like a branching process.

For a verified activity `e` (merged PR, useful review, resolved issue, reproduced experiment, documentation improvement), define its number of useful descendants within a time window `W`.

Examples of descendants:

- a newcomer claims a follow-up task created from the contribution;
- a second contributor reproduces or challenges the result;
- an accepted PR creates a documented extension point that is later implemented;
- a first-time contributor returns for a second verified contribution;
- a question becomes a bounded experiment that another person completes.

Define:

```text
R_community(W) = verified descendant contributions / verified parent contributions
```

Interpretation:

- `R_community < 1`: activity is not reproducing; the community tends to decay without outside effort.
- `R_community ~= 1`: community activity is roughly self-sustaining.
- `R_community > 1`: useful activity can compound.
- very high `R_community` while review capacity is low is dangerous: it can produce noise, burnout, or low-quality work.

ACE therefore does **not** maximize `R_community` blindly. It tries to keep effective reproduction above one **only while verification and review capacity remain healthy**.

---

## 2. Hybrid inspiration

### Biology — reproduction + carrying capacity

A contribution can reproduce into new contribution opportunities, but reproduction must slow when the ecosystem is saturated.

### Ecology — niches instead of one monoculture

The project should maintain useful niches for coders, researchers, reviewers, documenters, security contributors, designers, domain experts, and community builders.

### Evolution — replicator-mutator dynamics

Growth strategies that generate durable verified descendants should receive more future attention. A small mutation/exploration rate prevents the system from converging forever on one fashionable strategy.

### Ant colonies / stigmergy — leave signals in the environment

Useful work should leave visible traces: labels, linked issues, reproducible artifacts, evidence reports, follow-up tasks, unanswered questions, or clearer documentation. Contributors coordinate through these public traces rather than requiring a central dispatcher.

### Economics — allocate scarce attention by marginal value

Maintainer and reviewer attention is scarce. The system should allocate it to actions with high expected verified value per unit of human attention.

### Political science — polycentric governance + checks

No single popularity score should control project evolution. Future cells/subprojects should have local autonomy, while shared rules constrain security, provenance, and constitutional changes.

A growth action should pass two independent tests:

1. **Evidence chamber:** is the underlying work useful, reproducible, or well-supported?
2. **Community chamber:** will the action improve discoverability, onboarding, retention, diversity, or maintainability without creating excessive burden?

### Psychology — autonomy, competence, relatedness

A newcomer should be offered a choice of bounded tasks, receive fast evidence that their work mattered, and see a path to deeper responsibility. ACE should not manipulate attention; it should reduce friction and make useful participation intrinsically legible.

### Physics / information theory — gradients and criticality

Contributors tend to flow toward work that has visible value and low friction. ACE should surface steep **information gradients**: tasks where a small amount of effort can resolve a large uncertainty or unlock many downstream tasks.

The system should operate near a productive edge: enough open opportunities for exploration, but not so many that review queues become unstable.

---

## 3. Event -> evidence -> seed -> descendant

ACE treats GitHub as the first event bus.

```text
GitHub activity
  commit / push / issue / PR / review / star / fork / discussion
        |
        v
Event feature vector
        |
        v
quality x novelty x capacity gate
        |
        v
reproductive credit
        |
        +--> update public Growth Ledger
        |
        +--> if gate passes: create/refresh one bounded Growth Seed
        |
        v
new contributor/reviewer/reproducer claims seed
        |
        v
verification
        |
        v
measured descendant fitness
        |
        v
adapt future growth strategy
```

Every event can affect the state. **Not every event should generate a public comment, issue, or notification.** That distinction is essential for avoiding automation spam.

---

## 4. Event value

For event `e`, define:

- `Q_e` = verified usefulness signal;
- `D_e` = discovery/onboarding signal;
- `R_e` = retention/relationship signal;
- `L_e` = expected additional review load;
- `N_e` = novelty/diversity multiplier.

A simple v0 activity energy is:

```text
A_e = Q_e + D_e + R_e
```

Repeated event types receive diminishing novelty:

```text
N_e = 1 / sqrt(1 + count(event_type))
```

This prevents the engine from treating 100 identical low-information events as 100 independent discoveries.

---

## 5. Carrying capacity

Let `L` be a smoothed review-load proxy and `K` the desired review capacity. Define:

```text
Capacity(L) = 1 / (1 + exp((L - K) / tau))
```

When review load is low, `Capacity` is close to one. As review load exceeds the healthy range, reproduction pressure falls automatically.

Possible empirical inputs later:

- median time to first response;
- open PR count;
- PR age distribution;
- unreviewed first-time contributor PRs;
- unresolved security/governance work;
- active reviewer count;
- maintainer concentration.

This creates **density-dependent growth**, analogous to ecological carrying capacity.

---

## 6. Reproductive credit

Each event adds reproductive credit:

```text
DeltaCredit_e = A_e * N_e * Capacity(L)
```

Credit decays over time:

```text
Credit(t + dt) = Credit(t) * exp(-lambda * dt) + DeltaCredit_e
```

Decay matters because old popularity should not permanently dominate present decisions.

Credit is a system budget, not personal reputation.

A growth action can consume credit. This converts raw activity into **rate-limited reproduction**.

---

## 7. Growth seeds

A **Growth Seed** is a bounded, publicly useful opportunity created from verified project activity.

Seed types:

1. **Reproduce** — independently run/test a merged result.
2. **Extend** — implement a clearly bounded next step.
3. **Challenge** — try to falsify an assumption or benchmark.
4. **Explain** — make a difficult result newcomer-legible.
5. **Translate** — improve access for another language/community.
6. **Secure** — threat-model or adversarially test a change.
7. **Measure** — add an observable metric or experiment.
8. **Connect** — integrate a result with another open project/protocol.
9. **Review** — independent review where verification diversity matters.
10. **Onboard** — turn a solved problem into a tutorial/example that lowers future contribution friction.

The best seed is not necessarily the easiest task. It is the task with the highest expected combination of usefulness, information gain, accessibility, and downstream branching.

---

## 8. Seed priority: useful potential gradient

For candidate seed `s`, define:

- `I_s` = expected impact;
- `G_s` = expected information gain;
- `C_s` = clarity / boundedness;
- `V_s` = diversity value (opens an underrepresented niche);
- `F_s` = freshness;
- `H_s` = human review cost;
- `X_s` = execution friction.

A candidate score:

```text
Potential(s) = (I_s * G_s * C_s * V_s * F_s) / (1 + H_s + X_s)
```

The repository should expose high-potential seeds in issues, `good first issue`, `help wanted`, experiment lists, and generated contribution queues.

GitHub explicitly surfaces public issues with `good first issue` in newcomer-oriented discovery surfaces, so this label is not cosmetic; it can be part of the growth mechanism.

---

## 9. Adaptive strategy allocation: replicator-mutator bandit

ACE should eventually compare multiple growth strategies rather than assuming one onboarding pattern is universally best.

Let strategy `i` have weight `w_i` and measured fitness `f_i`, where fitness is based on verified descendants per unit of reviewer/maintainer attention.

A discrete replicator update is:

```text
w_i' proportional to w_i * exp(eta * (f_i - mean_fitness))
```

Then add mutation/exploration:

```text
w_i'' = (1 - mu) * normalize(w_i') + mu / number_of_strategies
```

`mu > 0` prevents permanent lock-in.

Candidate strategies:

- reproduction-task strategy;
- first-contribution -> second-contribution strategy;
- documentation-to-code bridge;
- challenge/reproduction strategy;
- cross-project integration strategy;
- language/localization strategy;
- reviewer recruitment strategy;
- public benchmark strategy.

A contextual-bandit version can later choose different strategies for different repository states.

---

## 10. Quorum sensing before amplification

Nature often waits for enough local signal before switching behavior. ACE should do the same.

High-amplification actions should require a quorum of independent evidence, for example:

```text
Amplify only if:
  verification_passed
  AND independent_signal_count >= q
  AND review_capacity > minimum
  AND spam_risk < threshold
```

Examples of independent signals:

- merged code + independent test;
- research result + reproduction;
- issue demand + working prototype;
- multiple distinct contributors requesting the same capability.

This prevents one noisy event from becoming a self-reinforcing hype loop.

---

## 11. Anti-Goodhart and anti-gaming rules

ACE must not reward raw activity volume.

Do **not** optimize directly for:

- stars;
- forks;
- comment count;
- commit count;
- issue count;
- PR count;
- reaction count;
- social impressions.

These are signals, not objectives.

Primary objective candidates:

```text
verified useful descendants
--------------------------------------------
reviewer time + maintainer time + compute cost
```

Safeguards:

- per-actor rate limits for credit-producing actions;
- diminishing returns for repeated correlated activity;
- independent verification for high-value events;
- no automatic DMs or unsolicited @mentions;
- no automated mass issue creation;
- no auto-merge from the growth engine;
- no personal leaderboard as the primary reward mechanism;
- explicit rollback if review latency or conduct problems rise;
- keep constitutional/governance changes outside automatic actuation.

---

## 12. GitHub-native implementation

GitHub Actions can trigger on repository events including issues, issue comments, pull requests, reviews, pushes, forks, stars (`watch`), discussions, and schedules.

ACE v0 uses this infrastructure as follows:

### Public Growth Ledger

A single issue titled **`[ACE] Community Growth Ledger`** stores the current adaptive state in a machine-readable block plus a human-readable summary.

Each supported event:

1. decays old state;
2. updates event counts;
3. updates review-load proxy;
4. computes novelty and capacity;
5. adds reproductive credit;
6. updates the same ledger issue body.

Editing one ledger is much quieter than creating a comment for every event.

### Explicit first actuator

A merged pull request labeled **`growth:spawn`** may create one follow-up Growth Seed issue for independent reproduction/extension.

This is deliberately opt-in in v0. It lets us test whether automatically spawned opportunities produce useful descendants before allowing the engine to decide spawning autonomously.

### Why the engine does not recursively explode

Actions made using GitHub's repository `GITHUB_TOKEN` normally do not create another workflow run, which helps prevent accidental recursive workflow cascades.

---

## 13. v0 event weights

These are hypotheses, not truths. They should be replaced with measured values.

| Event | Q usefulness | D discovery | R retention | Review-load delta |
| --- | ---: | ---: | ---: | ---: |
| push to main | 0.25 | 0.10 | 0.00 | 0.05 |
| issue opened | 0.10 | 0.60 | 0.20 | 0.30 |
| issue closed | 0.80 | 0.10 | 0.20 | -0.20 |
| PR opened | 0.20 | 0.70 | 0.40 | 1.00 |
| merged PR | 2.50 | 0.40 | 1.00 | -0.70 |
| non-merged PR closed | 0.10 | 0.05 | 0.10 | -0.50 |
| PR review submitted | 0.80 | 0.10 | 0.50 | -0.20 |
| star (`watch`) | 0.00 | 0.35 | 0.00 | 0.00 |
| fork | 0.10 | 0.90 | 0.10 | 0.00 |
| discussion created | 0.10 | 0.50 | 0.20 | 0.20 |
| discussion answered | 0.50 | 0.10 | 0.50 | -0.10 |

A star has low direct usefulness because popularity is not proof. A merged and reviewed contribution has much higher reproductive value.

---

## 14. State machine

ACE can operate in four modes:

```text
DORMANT -> EXPLORE -> GROW -> CONSOLIDATE
   ^          |         |          |
   +----------+---------+----------+
```

### DORMANT

Little recent useful activity. Prioritize discoverability, clear questions, demos, and newcomer tasks.

### EXPLORE

Activity exists but evidence is sparse. Encourage diverse small experiments and multiple niches.

### GROW

Verified activity is reproducing and review capacity is healthy. Allow more Growth Seeds and cross-project invitations.

### CONSOLIDATE

Review load, confusion, or governance debt is high. Reduce spawning and prioritize review, docs, cleanup, mentoring, and maintainership distribution.

The mode is determined from smoothed reproductive credit, review capacity, and descendant fitness rather than from follower counts.

---

## 15. The self-growing loop we want

A healthy iteration looks like:

```text
1. A contributor merges a useful PR.
2. ACE records high verified reproductive credit.
3. The PR leaves one bounded follow-up seed.
4. A newcomer can understand and claim it quickly.
5. The newcomer receives fast independent review.
6. Their result is merged/reproduced.
7. The system detects a verified descendant.
8. The successful seed strategy receives slightly more future probability.
9. The newcomer is offered a deeper but still bounded next step.
10. Review capacity is checked before additional spawning.
```

The important multiplication is not:

```text
activity -> more activity
```

It is:

```text
verified value -> lower friction -> new bounded opportunity
              -> new contributor -> verification -> retained capability
```

---

## 16. Experiments

### Experiment ACE-1 — Can one merged contribution create one viable descendant?

For 10 merged PRs, manually mark a subset `growth:spawn`. Measure:

- seed issue views/claims;
- claim -> PR conversion;
- PR -> merge conversion;
- reviewer minutes;
- time to first response;
- whether the seed was understandable without maintainer explanation.

### Experiment ACE-2 — First -> second contribution conversion

For first-time contributors, compare:

- generic thanks;
- one personalized bounded next-step suggestion;
- a choice of three next-step niches.

Measure verified second contribution within 30 days. Avoid manipulative messaging.

### Experiment ACE-3 — Reproduction vs extension

Compare follow-up seeds that ask contributors to reproduce a result versus extend it. Measure defect discovery, learning value, and reviewer cost.

### Experiment ACE-4 — Capacity governor

Test whether automatically reducing Growth Seed creation when review latency rises stabilizes throughput and improves contributor experience.

### Experiment ACE-5 — Strategy evolution

Run several seed strategies with a small exploration probability. Update strategy weights only from verified descendant outcomes.

---

## 17. Success criteria

ACE is useful if, over time:

- more first-time contributors become repeat contributors;
- more useful work originates without maintainer assignment;
- issues and PRs become easier to understand and review;
- community knowledge becomes more reproducible;
- contribution niches diversify;
- reviewer/maintainer concentration falls;
- review latency remains healthy as activity grows;
- useful descendant contributions per unit of human attention rises.

ACE has failed if it mainly produces more notifications, shallow issues, vanity metrics, bot-authored noise, or maintainer cleanup.

---

## 18. Relationship to IDKMesh itself

ACE is not only a community tool. It is an early instance of the IDKMesh thesis:

- events become structured evidence;
- uncertain policies are explicit experiments;
- multiple strategies compete;
- verification controls trust;
- human attention is treated as a scarce resource;
- coordination adapts to measured outcomes;
- growth is decentralized but bounded by shared rules.

If ACE works inside the IDKMesh repository, the same primitives may later become reusable for other open-source communities.

---

## 19. Immediate next steps

1. Run the v0 Growth Ledger workflow.
2. Create the `growth:spawn` label.
3. Mark only a small number of suitable merged PRs for reproduction.
4. Record descendant links explicitly with `spawned-from` markers.
5. Add a small community-metrics collector.
6. Estimate reviewer capacity from real repository data.
7. Replace hand-set event weights with evidence.
8. Add strategy fitness and replicator-mutator updates.
9. Publish negative results and disable any behavior that creates noise without verified descendants.
10. Eventually package ACE as a reusable GitHub Action if the experiment works here first.
