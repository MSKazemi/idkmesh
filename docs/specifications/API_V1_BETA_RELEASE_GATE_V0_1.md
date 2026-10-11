---
description: "The release gate for the first IDKMesh API v1 beta: the required evidence, how each item is verified, what a beta release note must state, and the tool that evaluates it."
---
# API v1 Beta Release Gate v0.1

**Status:** experimental; the gate exists and currently reports *not ready*  
**Issue:** #747 (API-12), parent #713  
**Authority:** a readiness report is evidence for a human release decision; it tags, publishes and merges nothing.

## Purpose

"API v1 beta" must name a reproducible, tagged contract and a qualification
report, not merely the existence of endpoints. This document fixes the evidence
a beta release needs, how each item is checked, and what the release note must
say. The item list and the live status of each item are owned by
`tools/api_beta_readiness.py`; this document deliberately does not copy the
table, so the two cannot disagree.

```bash
make qualify-api STRICT=1 BASE=<previous-tag>   # produce the qualification report
make beta-readiness                              # evaluate the gate (exit 1 until ready)
python tools/api_beta_readiness.py --json        # machine-readable
```

## How an item is decided

Each required item has a declared status — `satisfied`, `partial` or `unmet` —
a statement of what is missing when it is not satisfied, and the repository
files that back it. The tool then applies four rules:

1. **Evidence must exist.** If a named evidence file is missing, the item is
   `unverified`, whatever it declares. Renaming or deleting a document cannot
   leave an item green.
2. **Measured items are not taken on faith.** Items that the API release
   qualification run measures (`contract`, `fuzz`, `security`, `reliability`,
   `client`) are `satisfied` only if `results/api-qualification/report.json`
   exists, was taken at the current git revision on a clean tree, and every
   check in the relevant groups passed. Otherwise they are `unverified` with the
   reason.
3. **The tag item is decided by git.** It is `satisfied` only when `HEAD` carries
   an `api-v1-beta*` tag and the working tree is clean. Tag last.
4. **Declared status is a maintainer's claim, kept honest by tests.**
   `tests/test_api_beta_readiness.py` pins that a `satisfied` item records no
   gap, every item that is not satisfied says what is missing, every evidence
   file exists, and the list still has the fourteen items the issue requires.
   A maintainer changes a declared status in the same change that closes the
   gap.

The release is `ready` only when every item is `satisfied`.

## Required evidence

The fourteen items of issue #747, in the tool's order: tagged source revision;
API surface inventory; schema-frozen objects; OpenAPI/runtime/schema
conformance; compatibility report; declared security profile; identity and
authority matrix; mutation idempotency evidence; persistence and replay
semantics; reliability and load qualification; SLO and observability proof;
published SDK and docs; migration and deprecation policy; clean install and
reproducible demo.

At the time of writing the gate reports **not ready**. The gaps it records are
the real ones: the Human Decision API and its sub-resources are unbuilt (#740),
the network/multi-user security profile and an API-level authority matrix do not
exist (#743, #670), the Python client is unpublished (#769) and the typed web
client is unbuilt (#746), there is no beta migration guide, and there is no
automated clean-install demo for the API. Recording them is the point; closing
them is the work of those issues.

## What the beta release note must state

- what is stable;
- what remains experimental;
- localhost versus multi-user support;
- authority limitations;
- known limits and unsupported operations.

The tool prints this list with every report so it is never forgotten, but
writing the note is a maintainer's task: it must describe the actual tagged
revision, and it cannot be generated before the gate is ready.

## Non-goals

This gate does not tag a release, publish a package, or decide that a gap is
acceptable. Accepting a known limit in a beta is a human decision recorded in
the release note, not a status the tool can grant.
