# IDKGraph T2 link-integrity convergence

**Date:** 2026-08-28  
**Repository:** `MSKazemi/idkmesh`

## Owner instruction

Continue strengthening IDKMesh so the repository becomes more solid, smart, and internally consistent while preserving public project memory.

## Convergence event

Focused T1 PR #129 merged a deterministic Markdown document/heading identity contract:

- canonical implementation: `tools/idkgraph_markdown_index.py`;
- document and heading IDs are deterministic SHA-256-derived identities;
- setext and ATX headings are recognized;
- repeated headings receive stable occurrence-aware identities;
- source line is metadata, not identity.

A broader observatory prototype in PR #130 had independently implemented another Markdown identity system with different hash framing/length and heading parsing. Although its CI was green, merging both would have created two incompatible identities for the same repository objects.

PR #130 was therefore preserved as prototype/design evidence but closed unmerged. Issue #20 was updated with the convergence rule:

> one canonical identity contract, multiple observatory layers.

## T2 design

T2 is implemented as `tools/idkgraph_link_check.py` and **consumes T1** rather than redefining identity.

It deterministically:

1. loads the canonical T1 Markdown index;
2. scans inline Markdown links outside fenced and inline code;
3. ignores external links and non-Markdown routes such as GitHub issue paths;
4. resolves repository-local `.md` links and fragment-only links;
5. maps navigation anchors to canonical T1 heading IDs;
6. distinguishes missing file, missing anchor, repository escape, and ambiguous repository-absolute Markdown links;
7. detects duplicate canonical T1 IDs defensively;
8. emits a deterministic JSON report.

GitHub-style anchors are explicitly navigation locators, **not graph identities**.

## Safety and authority

T2 has no repository-write, GitHub-mutation, semantic-inference, repair, approval, or merge authority.

Repository-wide findings are initially observation evidence. A real repository may contain historical link debt, so CI first proves parser behavior and byte determinism rather than failing all PRs on pre-existing findings. A later baseline/policy change can promote selected categories to required gates after the debt is measured and intentionally handled.

## Verification plan

The focused test suite covers:

- cross-document anchor resolution;
- fragment-only same-document resolution;
- binding to exact canonical T1 document/heading IDs;
- setext-heading resolution inherited from T1;
- duplicate heading anchors;
- missing Markdown files;
- missing anchors;
- repository-root escape attempts;
- ambiguous root-absolute Markdown paths;
- external/non-Markdown link exclusion;
- fenced and inline-code false-positive avoidance;
- byte-for-byte deterministic replay;
- read-only/identity-neutral authority invariants.

The GitHub workflow runs T1 + T2 tests on Python 3.11 and 3.13, scans the real repository twice, compares the output bytes, and retains the T2 observation artifact.

## Architectural principle

```text
T1 identity
    -> T2 link integrity
    -> T3 typed structural mapping
    -> T4 executable dependency projection
    -> T5 composed observatory/report
```

Each layer may add evidence, but later layers must not silently redefine identities owned by earlier canonical layers.
