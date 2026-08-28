# Growth Acceleration Audit — 2026-08-28

## User direction

The repository has been running intensely for several hours. The user asked whether IDKMesh had actually found free compute, agents, influence/discovery endpoints, or contributors, and asked the project to move in a direction that grows faster rather than merely producing more internal activity.

## Observed state

At the time of this continuation:

- the repository was approximately 4.5 hours old;
- public metadata reported no description, topics, Pages, Discussions, stars, or forks;
- ACE reported zero distinct external participants, zero claimed Growth Seeds, zero candidate external PRs, and zero verified descendants;
- repository-internal activity was already very high, including hundreds of ACE-observed events and many merged implementation/research changes;
- GitHub Actions public runners were already a zero-project-cost compute lane;
- the Free Resource Mesh also listed conditional Gemini, Jules, volunteer local-model, Codespaces, and Cloudflare lanes;
- Hugging Face ZeroGPU was identified as an additional candidate that can combine bounded shared GPU compute with a public ML-community discovery surface.

## Decision

Treat the immediate bottleneck as **external discovery and first-contact conversion**, not implementation throughput.

The response therefore created:

1. issue #173, an owner/admin task to activate GitHub-native discovery surfaces;
2. a concise `docs/index.md` suitable for a future GitHub Pages front door;
3. `docs/findings/2026-08-28-fast-growth-and-free-compute-audit.md` documenting the diagnosis, free resources, ZeroGPU candidate, and a short-window growth-control model.

## Growth invariant

Internal owner/bot activity must not count as external community growth evidence.

The next meaningful community milestone is:

```text
one external non-bot person
 -> discovers IDKMesh
 -> understands one bounded action
 -> asks/claims/submits something inspectable
```

Then measure whether that becomes an independently verified useful result and whether the contributor returns.

## Safety / integrity

Faster growth must not mean spam. The project should not mass-mention strangers, scrape contact information, send unsolicited automated messages, manufacture engagement, or grant public demos repository integration authority.

The preferred growth mechanism is permissionless discoverability plus extremely low-friction bounded contribution paths.
