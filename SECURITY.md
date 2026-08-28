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

## Supported versions

IDKMesh is currently pre-release research software. There is not yet a stable supported-version matrix. Security fixes should normally target the current main branch and any explicitly maintained release branches once releases begin.

## Disclosure

The project favors coordinated disclosure: verify the issue, develop a mitigation, communicate impact accurately, then publish enough information for the community to learn from the failure without unnecessarily increasing risk before a fix exists.
