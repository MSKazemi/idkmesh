# OpenHands development pilot

IDKMesh is adding **OpenHands** as the next heterogeneous coding worker after Google Jules. The first integration is deliberately manual and narrow so it cannot silently fan the same `agent-ready` issue out to two agents.

## Why OpenHands

OpenHands is open-source agent software and supports hosted as well as local/self-hosted execution. That makes it useful for two IDKMesh goals:

1. add a materially different issue-to-candidate worker beside Jules;
2. later test a zero-project-spend local worker path with an allowed local/free model endpoint.

Open-source software does **not** mean hosted model inference is always free. The hosted control surface and the model/runtime cost must be treated separately.

## Bootstrap flow

```text
maintainer reviews issue
        |
        v
   agent-ready
        |
        v
manual "OpenHands Manual Pilot" workflow
        |
        v
validate open issue + veto labels
        |
        v
OpenHands conversation at protected default branch
        |
        v
candidate work / candidate PR
        |
        v
normal IDKMesh CI + review + human integration
```

The existing automatic `agent-ready` path belongs to Jules. The OpenHands pilot therefore has **no issue event or schedule trigger**.

## One-time owner setup

1. Create/sign in to an OpenHands account and create an API key for the hosted API, or later replace the hosted route with an explicitly reviewed self-hosted endpoint.
2. In GitHub, add the key as the Actions repository secret `OPENHANDS_API_KEY`.
3. Ensure the OpenHands account/integration can access `MSKazemi/idkmesh`. Do not place the API key in repository variables, issue text, workflow inputs, commits, or logs.

The workflow itself receives only `contents: read` and `issues: read`. Repository mutation is not granted through the workflow token.

## Running the first pilot

Choose a low-risk, bounded issue that already has `agent-ready` and none of:

- `blocked`;
- `do-not-automate`;
- `human-required`;
- `needs-decomposition`;
- `research-evidence`;
- `security-sensitive`.

Then run **Actions → OpenHands Manual Pilot → Run workflow** and enter the numeric issue number.

The preparation step fetches the issue through the GitHub API, validates the approval/veto labels, and writes a bounded prompt. The third-party OpenHands action is pinned to an immutable commit SHA rather than a floating tag.

## Evidence and authority

The workflow summary retains:

- selected issue number;
- source/default branch;
- OpenHands conversation ID;
- provider status;
- conversation URL when available.

This is operational provenance, not verification.

```text
OpenHands says complete != candidate accepted
candidate PR green != independent verification
verification recommendation != merge authority
```

Normal protected-main CI and explicit human integration still apply.

## Why manual first

The current Jules dispatcher consumes `agent-ready` automatically. Reusing the same event for OpenHands would create an accidental fan-out race. The provider-neutral target is:

```text
agent-ready = approved for bounded agent work
agent:jules / agent:openhands = explicit worker selection
```

That routing change should land through the shared connector/GitHub-dispatch control plane, not as a second ad-hoc automatic dispatcher.

## Next slices

Tracked by issue #641:

1. prove one low-risk OpenHands candidate run;
2. record exact conversation/source/candidate provenance;
3. add explicit `agent:openhands` routing after the common connector contracts stabilize;
4. normalize the resulting PR/head SHA into the canonical candidate/ResultManifest path;
5. add restart-safe idempotency/recovery;
6. test local/self-hosted OpenHands with an allowed zero-spend model/runtime route.

## Implementation surfaces

- workflow: `.github/workflows/openhands-pilot.yml`
- validator/prompt builder: `tools/openhands_pilot.py`
- tests: `tests/test_openhands_pilot.py`
- tracker: issue #641

The pilot never auto-merges and must not be used for security-sensitive, governance, secret-handling, human-observation, or independent-research tasks.
