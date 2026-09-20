# Ethical Contributor Psychology

**Status:** practical community-design guidance.  
**Authority:** none by itself; this document does not authorize outreach, automated messaging, or contributor decisions.

IDKMesh can use well-established human-motivation principles to make useful participation easier and more rewarding **without manipulating people**.

The goal is not to maximize attention. It is to help a curious visitor become a capable, autonomous, recurring contributor.

## The behavioral loop

```text
curiosity
  -> low-risk choice
  -> small successful action
  -> fast useful feedback
  -> visible impact
  -> belonging / recognition
  -> slightly deeper next task
  -> reviewer / steward identity
```

## 1. Autonomy: offer real choices

People engage more readily when they can choose a path that fits their interests.

The contributor front door should always expose several different lanes, for example:

- no-code newcomer observation;
- Python tests;
- documentation;
- reproducibility/research;
- security/review;
- external-platform testing.

Do not funnel every newcomer into the same task.

**Repository rule:** keep multiple live starter tasks with different skill profiles.

## 2. Competence: engineer an early win

A first task should make it possible to know "I did this correctly."

Good first tasks therefore need:

- a bounded deliverable;
- a concrete test or acceptance condition;
- a short expected effort;
- only the minimum required context;
- permission to report a negative or failed result.

This reduces uncertainty and lets the contributor build confidence from evidence rather than praise alone.

## 3. Relatedness: make a real person visible

A contributor should know that someone will notice useful work.

Every newcomer-facing task should make the review path clear. Where practical, identify the current review contact or the expected review surface.

Do not promise instant responses or pretend an automated queue is human mentorship.

## 4. Progress: make the path legible

The project should show a visible progression:

```text
first small contribution
  -> second related contribution
  -> recurring contributor
  -> reviewer
  -> steward
  -> maintainer
```

The next step should be close enough to feel achievable, not a jump from typo fix to "own the architecture."

After a verified first contribution, prefer one personalized follow-up task related to what the person already demonstrated.

## 5. Recognition: reward useful identity, not volume

Recognition should reinforce craftsmanship and responsibility.

Useful examples:

- mention a contributor in release notes for a meaningful change;
- credit experiment reproduction and negative results;
- acknowledge high-quality review and documentation;
- invite recurring contributors to review a narrow area they understand.

Avoid leaderboards for raw commits, comments, PR count, or AI-generated volume.

## 6. Reciprocity: contribute before recruiting

The strongest contributor-acquisition mechanism is value-first interaction.

When IDKMesh engages an adjacent open-source project:

1. find a genuine problem IDKMesh can help with;
2. contribute useful work under that project's rules;
3. only after a legitimate technical interaction, expose a relevant IDKMesh task when appropriate.

Do not submit promotional-only PRs or mass invitations.

## 7. Commitment and continuity

A small public commitment can reduce accidental duplicated effort and make follow-through easier.

For a bounded issue, asking a contributor to comment with the scope they intend to take is useful when the task is not explicitly parallel.

This is coordination, not pressure. A contributor can stop at any time without penalty.

## 8. Curiosity: expose real unanswered questions

Concrete unresolved questions are more motivating than abstract slogans.

Prefer:

- "Can you reproduce this count from the raw data?"
- "Does this command work on Windows?"
- "Which instruction made you stop?"
- "Can this verifier fail on this boundary case?"

over:

- "Help build the future of AI."

Curiosity should come from a real technical uncertainty, not manufactured mystery.

## 9. Belonging through contribution, not branding

The project should communicate:

> You belong here when you make the work clearer, safer, more reproducible, or more useful.

Belonging must not depend on prestige, follower count, geography, employer, or ability to donate compute.

## 10. Anti-manipulation constraints

Do not use:

- fake urgency or artificial scarcity;
- deceptive social proof;
- repeated unsolicited mentions or DMs;
- guilt for not contributing;
- hidden behavioral targeting;
- dark patterns that make opting out difficult;
- exaggerated claims that IDKMesh is more mature or popular than it is;
- personal psychological profiling for persuasion.

Use aggregate funnel measurements to improve the repository, not to pressure individuals.

## Metrics

Useful measurements include:

- visitor -> starter-task interaction;
- starter-task interaction -> first contribution;
- first contribution -> second contribution;
- second contribution -> reviewer/steward;
- median time to first useful response;
- contributor-reported confusion;
- maintainer/reviewer attention per retained contributor.

Stars, forks, impressions, comments, and raw PR volume are discovery/activity signals, not the objective.

## Current experiment

The immediate hypothesis is:

> A choice-rich, low-risk first task plus fast useful feedback and one skill-matched follow-up will produce more recurring external contributors per maintainer-review minute than a generic "please contribute" invitation.

The current live front door is [Contributor Quickstart](CONTRIBUTOR_QUICKSTART.md), and the value-first acquisition experiment is tracked in issue #412.
