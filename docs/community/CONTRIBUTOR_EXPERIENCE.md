# Contributor Experience Guidelines

**Status:** practical community-design guidance.
**Authority:** none by itself; this document does not authorize outreach, automated messaging, or contributor decisions.

These are the norms IDKMesh tries to follow so that a curious visitor can become a capable, recurring contributor without being nudged, pressured, or gamified into it.

## 1. Offer real choices

The contributor front door should always expose several different lanes, for example:

- no-code newcomer observation;
- Python tests;
- documentation;
- reproducibility/research;
- security/review;
- external-platform testing.

Do not funnel every newcomer into the same task.

**Repository rule:** keep multiple live starter tasks with different skill profiles.

## 2. Make first tasks winnable

A first task should make it possible to know "I did this correctly."

Good first tasks therefore need:

- a bounded deliverable;
- a concrete test or acceptance condition;
- a short expected effort;
- only the minimum required context;
- permission to report a negative or failed result.

This reduces uncertainty and lets the contributor build confidence from evidence rather than praise alone.

## 3. Make the review path visible

A contributor should know that someone will notice useful work.

Every newcomer-facing task should make the review path clear. Where practical, identify the current review contact or the expected review surface.

Do not promise instant responses or pretend an automated queue is human mentorship.

## 4. Show a legible path forward

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

## 5. Recognize craftsmanship, not volume

Recognition should reinforce craftsmanship and responsibility.

Useful examples:

- mention a contributor in release notes for a meaningful change;
- credit experiment reproduction and negative results;
- acknowledge high-quality review and documentation;
- invite recurring contributors to review a narrow area they understand.

Avoid leaderboards for raw commits, comments, PR count, or AI-generated volume.

## 6. Give before you ask

The strongest contributor-acquisition mechanism is value-first interaction.

When IDKMesh engages an adjacent open-source project:

1. find a genuine problem IDKMesh can help with;
2. contribute useful work under that project's rules;
3. only after a legitimate technical interaction, mention a relevant IDKMesh task when appropriate.

Do not submit promotional-only PRs or mass invitations.

## 7. Coordinate scope openly

For a bounded issue, asking a contributor to comment with the scope they intend to take reduces accidental duplicated effort when the task is not explicitly parallel.

This is coordination, not a commitment device. A contributor can stop at any time without penalty.

## 8. Frame tasks around real open questions

Concrete unresolved questions are more motivating than abstract slogans.

Prefer:

- "Can you reproduce this count from the raw data?"
- "Does this command work on Windows?"
- "Which instruction made you stop?"
- "Can this verifier fail on this boundary case?"

over:

- "Help build the future of AI."

Tasks should come from a real technical uncertainty, not manufactured mystery.

## 9. Belonging is earned by contribution, not branding

The project should communicate:

> You belong here when you make the work clearer, safer, more reproducible, or more useful.

Belonging must not depend on prestige, follower count, geography, employer, or ability to donate compute.

## 10. Practices we do not use

Do not use:

- fake urgency or artificial scarcity;
- deceptive social proof;
- repeated unsolicited mentions or DMs;
- guilt for not contributing;
- profiling individuals to target persuasion;
- dark patterns that make opting out difficult;
- exaggerated claims that IDKMesh is more mature or popular than it is.

Use aggregate funnel measurements to improve the repository, not to pressure individuals.

## How we know onboarding is working

Useful measurements include:

- visitor -> starter-task interaction;
- starter-task interaction -> first contribution;
- first contribution -> second contribution;
- second contribution -> reviewer/steward;
- median time to first useful response;
- contributor-reported confusion;
- maintainer/reviewer attention per retained contributor.

Stars, forks, impressions, comments, and raw PR volume are discovery/activity signals, not the objective.

The current live front door for newcomers is the [Contributor Quickstart](CONTRIBUTOR_QUICKSTART.md).
