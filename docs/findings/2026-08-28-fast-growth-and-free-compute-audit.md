# Fast Growth and Free Compute Audit — 2026-08-28

## Executive finding

IDKMesh is not currently compute-starved or implementation-starved. It is **external-attention and first-contact starved**.

At approximately 19:05 CEST on 2026-08-28, the repository was only about 4.5 hours old but had already generated hundreds of internal GitHub events, many pull requests, many merges, a large issue surface, multiple deterministic observatories, a Free Resource Mesh, and live experiments.

At the same time, public repository metadata still reported:

- description: empty;
- topics: none;
- GitHub Discussions: disabled;
- GitHub Pages: disabled;
- homepage: unset;
- stars: 0;
- forks: 0.

The ACE Bootstrap Cohort Observatory reported:

- distinct external participants: 0;
- claimed Growth Seeds: 0;
- candidate community PRs: 0;
- verified descendant PRs: 0.

The correct diagnosis is therefore not "build more internal machinery faster." It is:

```text
internal production >> external discovery >> first-contact conversion
```

The next growth iteration should spend scarce maintainer/agent effort on increasing the probability that a qualified external person discovers one clear project thesis and one bounded action.

## Why no contributors appeared yet

Four explanations are consistent with the evidence.

### 1. The repository is extremely young

A few hours is too short to infer that the project cannot attract contributors. Search indexing, social propagation, word of mouth, and contributor scheduling all have latency.

### 2. The strongest GitHub-native discovery fields are not active

The repository currently lacks a description and topics. Discussions and Pages are disabled. The README is substantial, but it mostly helps **after** somebody reaches the repository.

### 3. Internal activity does not automatically create an external audience

Commits, PRs, Actions runs, issue updates, and self-evolution artifacts can improve a repository, but GitHub does not guarantee that high internal event volume will be distributed to relevant external developers. A self-growing system therefore needs explicit public discovery surfaces rather than assuming activity becomes reach.

### 4. The project intentionally avoids spammy outbound behavior

IDKMesh should not mass-mention strangers, scrape emails, auto-DM people, or manufacture engagement. The repository needs permissionless public surfaces that make useful work discoverable without unsolicited outreach.

## Free compute and agent resources already found

The existing registry already records useful zero-project-cost lanes:

1. GitHub Actions public-repository hosted runners — currently the strongest immediately usable deterministic compute lane.
2. Gemini API free-tier capacity — conditional, secret-backed advisory/agent lane.
3. Google Jules bounded free plan — manual hosted coding-agent lane.
4. Volunteer Ollama / goose / OpenHands configurations — conditional contributor-controlled compute.
5. Personal GitHub Codespaces included usage — manual contributor compute.
6. Cloudflare Workers free control-plane capacity — useful for a future lightweight broker, not coding-agent compute.

These should remain opportunistic resources rather than protocol constants. Every external service must be re-observed for quota/security changes before activation.

## Newly identified candidate: Hugging Face ZeroGPU

A useful new resource/discovery candidate is **Hugging Face Spaces ZeroGPU**.

Observed from Hugging Face documentation on 2026-08-28:

- ZeroGPU is shared GPU infrastructure for public Spaces;
- existing ZeroGPU Spaces can be used for free;
- a free personal account in good standing can host up to two ZeroGPU Spaces;
- hosting eligibility requires a verified email and an account older than 30 days;
- free accounts have a bounded daily GPU quota;
- ZeroGPU hosting is currently Gradio-focused and PyTorch-oriented;
- public Spaces expose source code and a public app surface, so they can act as both a compute experiment and a discovery/demo surface.

Authoritative sources:

- https://huggingface.co/docs/hub/spaces-zerogpu
- https://huggingface.co/docs/hub/en/spaces-overview

### Why ZeroGPU is unusually interesting for IDKMesh

Most free resources improve only compute. A public Space can improve two dimensions at once:

```text
small bounded GPU experiment
        +
public interactive demonstration
        ->
compute evidence + discovery surface
```

A first Space should **not** become a privileged IDKMesh worker or GitHub writer. It should be a read-only/public demonstration, for example:

- paste/select a bounded public Work Unit;
- visualize Work Unit -> worker attempts -> independent verification -> Evidence Report;
- run a small open model only when a GPU is available;
- emit an untrusted candidate/advice artifact;
- link back to the canonical GitHub task and contribution instructions.

No repository token, merge authority, private data, or canonical-write authority should be present in the Space.

## Immediate 24-hour growth strategy

The repository should optimize a simple conversion funnel:

```text
Discovery D
 -> comprehension C
 -> bounded-action selection A
 -> contribution/claim Q
 -> independently verified useful result V
 -> return/help-another R
```

The current failure is near `D` and `C`, not `V`.

### Priority 0 — activate GitHub-native discovery metadata

Repository owner/admin action:

1. add a concise description;
2. add 5–10 focused topics;
3. enable Discussions;
4. enable Pages after the landing page is ready;
5. set the homepage to the Pages/primary demo URL when useful.

Tracked in issue #173.

### Priority 1 — make one 15-minute action unavoidable

The public front door should expose exactly three paths above the fold:

1. **New here?** Run the 15-minute newcomer audit.
2. **Engineer/researcher?** Pick one bounded `help wanted` task.
3. **Expert reviewer?** Perform one independent evidence/security review.

Do not show dozens of internal architecture links before these actions.

### Priority 2 — create one public live demonstration

Candidate ordering:

1. GitHub Pages static front door — lowest risk, no external account required beyond GitHub;
2. Hugging Face public Static/ZeroGPU Space — discovery + optional bounded open-model demo;
3. optional Jules/Gemini experiments only after explicit owner setup.

### Priority 3 — treat external first contact as the next growth milestone

Do not evaluate growth from commits, PR count, comments, stars, or workflow runs.

First milestone:

```text
one non-owner, non-bot external person
 -> reaches a public front door
 -> asks a concrete question OR claims a bounded task OR submits a bounded candidate
```

Second milestone:

```text
that first contact becomes an independently verified useful contribution
```

Third milestone:

```text
that contributor returns or helps another contributor
```

This creates a causal growth lineage rather than an activity metric.

## A faster growth control law

Define a short-window growth vector:

```text
x_t = [external_visitors_proxy, external_contacts, claims, verified_descendants, returns]
```

For each public growth experiment `i`, estimate a Beta posterior for conversion success:

```text
p_i ~ Beta(alpha_i, beta_i)
```

Update only from externally attributable outcomes, then allocate the next small growth action using Thompson sampling or UCB with a diversity floor.

Example strategies:

- GitHub topics/description;
- GitHub Pages front door;
- Hugging Face demo;
- improved `good first issue` wording;
- independent-review call;
- release/research-preview artifact.

Fitness should be approximately:

```text
verified external descendants + qualified first contacts
--------------------------------------------------------
1 + maintainer_minutes + reviewer_minutes + public_noise
```

Hard rule:

```text
internal owner/bot activity cannot count as external growth evidence
```

### Exploration budget

Use a small number of simultaneous surfaces rather than one surface or dozens:

```text
70% attention -> best current conversion surface
20% -> second-best / diversity-preserving surface
10% -> new experiment
```

This is an engineering hypothesis to test, not a proven optimal allocation.

## What should not happen

Do not accelerate growth by:

- mass @mentions;
- unsolicited DMs/email scraping;
- fake stars/forks/comments;
- recursive issue spam;
- automatic posting to unrelated projects;
- claiming agents are independent external contributors;
- granting public demos repository write or merge authority;
- maximizing raw GitHub activity.

## Next evidence to collect

Within the next real external-contact window, record:

- which public surface the person used, when observable without invasive tracking;
- time from first contact to first bounded action;
- whether the task was understandable without maintainer explanation;
- reviewer/maintainer minutes;
- whether the result was independently verified;
- whether the contributor returned.

That evidence is more valuable for community growth than another hundred owner-generated repository events.
