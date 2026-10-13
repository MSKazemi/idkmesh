# Interactive Reviewer Lab: no-install beginner demonstration (2026-10-13)

## Owner request

Continue improving IDKMesh's introductory documentation for visitors without specialist AI or software-engineering experience. Follow the completed [beginner clarity work](2026-10-11-beginner-clarity-first-run.md) with an interactive experience, while saving work in this repository.

## Decision

Add an optional browser-only page under `docs/labs/reviewer-lab.html`, using a short first-contact walkthrough: inspect the failed `p01` known-bad probe, see overlapping mistakes on `c10`, select a subset of reviewers, and change the strict approval threshold. No model account, Python installation, credential, server, provider call, external script, analytics or user-data upload is required. Keep the other static documentation pages unchanged in execution behavior; the lab is an explicit exception to the no-JavaScript **presentational site** default.

## Source of truth

The lab embeds the complete, unchanged `examples/gate-audit/panel-votes.example.json` synthetic fixture; tests compare both documents structurally and check the actual browser calculator for every non-empty reviewer subset (31) against three quorum values (93 cases). The strict threshold mirrors `idkmesh/gate_audit.py`: accept when `accept_votes > quorum * number_of_selected_reviewers`, ties reject. The page intentionally counts ordinary-candidate false approvals and false rejections separately from breached probes. It displays pairwise **overlapping mistakes**, not correlation, statistical independence or effective votes; those belong to the real Python `gate-audit` implementation.

Default (all five; quorum 0.5): 1 false approval (c10), 1 false rejection (c03), 2/3 probe breaches (p01 and p03). At 0.67: 0 false approvals, 2 false rejections, 0 probes breached. At 0.8: 0 false approvals, 4 false rejections, 0 probes breached. All are properties of the **synthetic** sample and do not support real-world reviewer quality claims.

## Navigation and maintenance

Promote the lab from the README, beginner guide, published Start page and docs navigation. Include the new HTML URL in the GitHub Pages sitemap while preserving its generated structure; keep canonical/OG structured metadata and published-page constraints aligned. A dedicated Python test checks the exact fixture, UI accessibility markers, offline code boundary and Node parity when Node is available.

## Boundaries

- A browser voting lesson is **not** a hosted AI reviewer, a live audit, an independent verification result, a measure of independence, or a merge authorization surface.
- The source fixture is invented and labelled `synthetic`; changing the voting rule does not change recorded reviewer decisions or ground truth.
- A strict threshold can trade fewer false approvals for more false rejections; it cannot replace independent evaluation.
- The browser page is distinct from the local `idkmesh gate-audit-ui` service and the read-only Human Control Tower.

## Community impact and evidence

A curious visitor can experience a meaningful, falsifiable behavior before cloning the repository. No traffic, accessibility study, or external-user comprehension improvement is claimed without measurement. The intended next evaluation is to ask first-time visitors to distinguish recorded verdicts, known correct answers and acceptance authority.

AI/tool provenance: authored with ChatGPT GPT-6 through the connected GitHub interface, source-matched to the committed fixture and Python audit rule. No independent human review is asserted.
