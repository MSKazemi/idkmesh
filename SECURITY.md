# Security Policy

IDKMesh may eventually execute work from untrusted participants on heterogeneous machines, so security and supply-chain integrity are foundational project concerns.

## Reporting a vulnerability

Please **do not open a public GitHub issue for an undisclosed vulnerability**.

Preferred reporting path:

1. Use GitHub's private vulnerability reporting / Security tab for this repository if the option is available.
2. If private vulnerability reporting is unavailable, contact the repository maintainer privately through the contact information available on the maintainer's GitHub profile.
3. Share only the information needed to reproduce and assess the issue until a coordinated disclosure plan is agreed.

As the maintainer team grows, IDKMesh should establish a dedicated security team and documented private security contact independent of any single individual.

## What to include

A useful report includes:

- affected component or document;
- impact;
- reproduction steps or proof of concept where safe;
- assumptions required for exploitation;
- suggested mitigation if known;
- whether the issue has been disclosed elsewhere.

## Security priorities

High-priority areas include:

- remote code execution on volunteer worker machines;
- sandbox escapes;
- malicious Work Units;
- malicious or forged worker results;
- dependency and supply-chain compromise;
- artifact/provenance tampering;
- credential/token leakage;
- privilege escalation;
- unsafe automatic merging or deployment;
- model/tool prompt injection that crosses trust boundaries;
- Sybil/collusion attacks on reputation or verification;
- privacy leakage in distributed workloads.

## Vulnerability response targets

These are response **targets**, not guarantees or claims that every report is
valid. Severity is assigned after triage using exploitability, impact, affected
deployment profiles, and exposure.

| Severity | Initial acknowledgement | Triage target | Remediation / mitigation target |
| --- | --- | --- | --- |
| Critical | 1 business day | 2 business days | 7 calendar days |
| High | 2 business days | 5 business days | 14 calendar days |
| Medium | 5 business days | 10 business days | 30 calendar days |
| Low | 10 business days | 20 business days | next planned release or 90 days |

A credible actively exploited issue may trigger an emergency release outside
the normal dependency/update cadence. If a complete fix cannot safely meet the
target, maintainers should document a temporary mitigation, affected versions,
and the next review date in the private security record before public
disclosure.

Routine dependency updates do not automatically receive release authority.
Major-version changes and security-sensitive build/release changes require
focused compatibility and trust-boundary review.

## Automated repository checks

GitHub secret scanning and push protection are enabled in repository settings.
The pinned `.github/workflows/codeql.yml` workflow analyzes Python changes on
pull requests, pushes to `main`, and a weekly schedule. `.github/dependabot.yml`
checks GitHub Actions and Python dependency declarations weekly with a bounded
open-PR limit. Routine update automation excludes semantic major versions;
major migrations require a focused compatibility and trust-boundary review. A
pinned weekly OpenSSF Scorecard workflow uploads SARIF to GitHub code scanning
and retains a five-day diagnostic artifact. It deliberately does not publish
results to the external Scorecard service or request an OIDC token.

Every third-party GitHub Action is pinned to an immutable commit SHA rather
than a floating tag. A tag resolves at run time to whatever it points at then,
so whoever controls it can change what executes in CI without any change landing
in this repository. `tests/test_workflow_action_pinning.py` enforces this: it
fails with the offending file and line if a tag reappears, and also fails if one
version comment maps to two different SHAs, which would mean one of them is
stale.

The PyPI release workflow additionally emits checksums, an SPDX 2.3 SBOM, an
exact source/workflow identity manifest, and GitHub build-provenance
attestations for release distributions. See
`docs/specifications/RELEASE_SUPPLY_CHAIN_V0_1.md` for generation and consumer
verification. These controls supplement review; a valid signature, checksum,
SBOM, or attestation does not establish that a candidate, dependency update, or
release is correct or vulnerability-free.

## Supported versions

IDKMesh is currently pre-release research software. There is not yet a stable supported-version matrix. Security fixes should normally target the current main branch and any explicitly maintained release branches once releases begin.

## Disclosure

The project favors coordinated disclosure: verify the issue, develop a mitigation, communicate impact accurately, then publish enough information for the community to learn from the failure without unnecessarily increasing risk before a fix exists.
