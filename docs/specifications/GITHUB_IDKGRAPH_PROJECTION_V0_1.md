# GitHub to IDKGraph Projection v0.1

Status: experimental, read-only

This contract deterministically joins a bounded, normalized GitHub snapshot to
IDKGraph. It covers issues, pull requests, comments, reviews, checks, commits,
security findings, evolution candidates, shared capacity observations, and
post-decision outcomes. The projector does not connect to GitHub and has no
write, execution, or merge authority.

## Boundary and stable identity

The input is an object with version 1, an owner/name repository, a collection
timestamp, and normalized records. Every record supplies a source type, stable
source ID, title, GitHub URL, timestamp, actor, and optional explicit parent or
repository-node links. Generated IDs have these forms:

    github:{owner/name}:{source_type}:{source_id}
    github:user:{login}

Edge IDs are SHA-256-derived from the typed, sorted endpoints. Input order does
not affect serialized output. A repository graph may be supplied to join
GitHub records to existing file, document, and task nodes.

## Trust and evidence rules

GitHub natural-language bodies are untrusted data. The projection retains only
their SHA-256 digest and an untrusted-text marker; it never evaluates or copies
the text into an executable surface.

Comments are provenance, not verification. A passing review from the pull
request author is not independent, bot reviews are excluded, and repeated
review/check observations with the same independence key count once. Worker
self-report is therefore separate from acceptance evidence.

ACE and repository evolution may report the same capacity observation. They
must share one observation ID: equal duplicates collapse to one value and
conflicting duplicates fail closed. This prevents two consumers from turning
one reviewer slot into two apparent slots.

## Ranking and outcomes

Evolution candidates provide all nine normalized dimensions: impact,
confidence, novelty, information gain, dependency unlock, review capacity,
cost, risk, and reversibility. Hard guards are conjunctive and precede score;
a blocked high-scoring candidate remains ineligible. Ties resolve by stable
candidate ID.

Outcome records preserve the post-merge or post-rejection measurement window
as typed evidence. The v0.1 projector does not infer success from the decision
itself.

## Disabled actuator

The output describes a future rate-limited actuator but fixes enabled to false,
with at most one public action per epoch. Activation requires protected main,
an allowed typed rule, risk budget, review capacity, duplicate suppression, and
separate human integration. Those declarations do not grant authority.

## Replay

Run the fixture twice and compare bytes:

    python tools/github_idkgraph_projection.py tests/fixtures/github_idkgraph_snapshot.json --output /tmp/github-graph-a.json
    python tools/github_idkgraph_projection.py tests/fixtures/github_idkgraph_snapshot.json --output /tmp/github-graph-b.json
    cmp /tmp/github-graph-a.json /tmp/github-graph-b.json

The focused tests also validate the embedded graph against the current
IDKGraph schema and exercise correlation, self-review, capacity conflict, hard
guard, and untrusted-text behavior.
