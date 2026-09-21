"""Guard the real-node/two-attempt E2E tools' external candidate reference.

`tools/real_node_verifier_e2e.py` and `tools/real_two_attempt_e2e.py` drive a
REAL exact-SHA git checkout and subprocess execution of the `idkmesh-node`
worker. That worker tree intentionally never merged onto `main` (PR #91 stays
closed by design -- see `docs/acceptance/PR91_CONTROLLED_DOCKER_GATE.md`), so
`node/examples/work-unit.canonical-smoke.json` cannot exist in this
repository's own tree: it lives only in the frozen `CANDIDATE_SHA` checkout
that a caller must supply through `--candidate`. That is by design, not a
gap, and this suite cannot fetch that external checkout (no network/docker in
the fast tiers), so it cannot re-run the real E2E itself.

What this suite *can* guard offline is the failure mode that actually bit the
project: five separate tool files hardcode the same 40-character
`CANDIDATE_SHA`/`SOURCE_SHA` pair. A future candidate acceptance that updates
one file and misses another would silently point half the E2E tools at a
`node/` tree that may not even contain a matching WorkUnit fixture -- exactly
the "hardcoded demo SHA pair" gap this test suite closes.

It also guards that the local-run runbook
(`docs/acceptance/REAL_NODE_TWO_ATTEMPT_E2E_LOCAL_RUN.md`) stays in sync with
the pinned SHAs and is the doc the tools' own SHA-drift error message points
readers at, so the discoverability gap this suite was added for cannot regress
silently either.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
RUNBOOK = ROOT / "docs" / "acceptance" / "REAL_NODE_TWO_ATTEMPT_E2E_LOCAL_RUN.md"
RUNBOOK_RELATIVE = "docs/acceptance/REAL_NODE_TWO_ATTEMPT_E2E_LOCAL_RUN.md"

# Tools bound to the CURRENT runtime-accepted node candidate. `CANDIDATE_SHA`
# must be identical across all of them.
CURRENT_CANDIDATE_TOOLS = (
    "real_node_verifier_e2e.py",
    "real_two_attempt_e2e.py",
    "real_two_attempt_evidence_e2e.py",
    "real_mixed_outcome_e2e.py",
)

# `node_verifier_e2e.py` is the reusable historical harness, deliberately left
# bound to an earlier candidate; `node_verifier_e2e_current.py` re-binds it to
# the current candidate via a monkeypatched `e2e.CANDIDATE_SHA` assignment
# instead of its own top-level constant.
CURRENT_CANDIDATE_PATCH_TOOL = "node_verifier_e2e_current.py"

# Tools whose SOURCE_SHA (the immutable source repository revision the
# WorkUnit fixture is pinned to) must never silently drift, regardless of
# which node candidate they target.
SOURCE_SHA_TOOLS = (
    "node_verifier_e2e.py",
    "real_node_verifier_e2e.py",
    "real_two_attempt_e2e.py",
    "real_two_attempt_evidence_e2e.py",
    "real_mixed_outcome_e2e.py",
)

SHA_RE = re.compile(r"\b[0-9a-f]{40}\b")


def _constant(text: str, name: str) -> str:
    match = re.search(rf'^{name}\s*=\s*"([0-9a-f]{{40}})"', text, re.MULTILINE)
    assert match, f"expected a top-level {name} = \"<40-hex-char sha>\" assignment"
    return match.group(1)


def test_current_candidate_sha_identical_across_real_e2e_tools() -> None:
    shas = {
        name: _constant((TOOLS / name).read_text(encoding="utf-8"), "CANDIDATE_SHA")
        for name in CURRENT_CANDIDATE_TOOLS
    }
    assert len(set(shas.values())) == 1, (
        "CANDIDATE_SHA drifted between the current real-node E2E tools: "
        f"{shas}"
    )

    patch_text = (TOOLS / CURRENT_CANDIDATE_PATCH_TOOL).read_text(encoding="utf-8")
    patch_match = re.search(
        r'e2e\.CANDIDATE_SHA\s*=\s*"([0-9a-f]{40})"', patch_text
    )
    assert patch_match, (
        f"{CURRENT_CANDIDATE_PATCH_TOOL} no longer rebinds e2e.CANDIDATE_SHA "
        "to the current candidate"
    )
    current_sha = next(iter(shas.values()))
    assert patch_match.group(1) == current_sha, (
        f"{CURRENT_CANDIDATE_PATCH_TOOL} rebinds to {patch_match.group(1)}, "
        f"which no longer matches the current candidate {current_sha}"
    )


def test_source_sha_identical_across_node_e2e_tools() -> None:
    shas = {
        name: _constant((TOOLS / name).read_text(encoding="utf-8"), "SOURCE_SHA")
        for name in SOURCE_SHA_TOOLS
    }
    assert len(set(shas.values())) == 1, (
        "SOURCE_SHA (the immutable source revision the WorkUnit fixture is "
        f"pinned to) drifted between node E2E tools: {shas}"
    )

    frozen_text = (TOOLS / "node_runtime_acceptance.py").read_text(encoding="utf-8")
    frozen_source_sha = _constant(frozen_text, "FROZEN_SOURCE_SHA")
    current_source_sha = next(iter(shas.values()))
    assert frozen_source_sha == current_source_sha, (
        "node_runtime_acceptance.py's FROZEN_SOURCE_SHA "
        f"({frozen_source_sha}) no longer matches the current SOURCE_SHA "
        f"({current_source_sha}); the source revision the fixture is pinned "
        "to is not supposed to change across candidate acceptances"
    )


def test_plan_template_fixture_referenced_by_real_e2e_tools_exists() -> None:
    for name in ("real_node_verifier_e2e.py", "real_two_attempt_e2e.py"):
        text = (TOOLS / name).read_text(encoding="utf-8")
        match = re.search(r'PLAN_TEMPLATE\s*=\s*"([^"]+)"', text)
        assert match, f"{name} no longer defines PLAN_TEMPLATE"
        fixture_path = ROOT / match.group(1)
        assert fixture_path.is_file(), (
            f"{name} references PLAN_TEMPLATE={match.group(1)!r}, which does "
            "not exist"
        )


def test_local_run_runbook_exists_and_matches_current_pinned_shas() -> None:
    assert RUNBOOK.is_file(), (
        f"{RUNBOOK_RELATIVE} is missing; this is the documented local "
        "reproduction of the CI checkout steps in "
        ".github/workflows/real-node-verifier-e2e.yml and "
        ".github/workflows/real-two-attempt-e2e.yml"
    )
    runbook_text = RUNBOOK.read_text(encoding="utf-8")

    current_sha = _constant(
        (TOOLS / "real_node_verifier_e2e.py").read_text(encoding="utf-8"),
        "CANDIDATE_SHA",
    )
    source_sha = _constant(
        (TOOLS / "real_node_verifier_e2e.py").read_text(encoding="utf-8"),
        "SOURCE_SHA",
    )
    assert current_sha in runbook_text, (
        f"{RUNBOOK_RELATIVE} does not mention the current CANDIDATE_SHA "
        f"({current_sha}); update the runbook when the accepted candidate "
        "changes"
    )
    assert source_sha in runbook_text, (
        f"{RUNBOOK_RELATIVE} does not mention the current SOURCE_SHA "
        f"({source_sha}); update the runbook when the source revision "
        "changes"
    )


def test_sha_drift_error_message_points_readers_at_the_runbook() -> None:
    for name in ("real_node_verifier_e2e.py", "real_two_attempt_e2e.py"):
        text = (TOOLS / name).read_text(encoding="utf-8")
        assert RUNBOOK_RELATIVE in text, (
            f"{name}'s candidate SHA-drift error message no longer points "
            f"readers at {RUNBOOK_RELATIVE}"
        )


def test_current_workflows_check_out_the_same_candidate_sha() -> None:
    workflows_dir = ROOT / ".github" / "workflows"
    current_sha = _constant(
        (TOOLS / "real_node_verifier_e2e.py").read_text(encoding="utf-8"),
        "CANDIDATE_SHA",
    )
    for name in ("real-node-verifier-e2e.yml", "real-two-attempt-e2e.yml"):
        text = (workflows_dir / name).read_text(encoding="utf-8")
        assert current_sha in text, (
            f".github/workflows/{name} checks out a candidate SHA that no "
            f"longer matches the current CANDIDATE_SHA ({current_sha})"
        )
