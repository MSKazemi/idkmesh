"""Guard the checked-in compute authorization itself, against the real clock.

Why this file exists separately from ``test_resource_compute_admission.py``:
that suite proves the admission *algorithm* on synthetic fixtures, and
``.github/workflows/free-resource-plan.yml`` runs the real files but pins
``--today 2026-08-28`` so its example assertion stays reproducible. Pinning is
correct for a determinism check and wrong for an expiry check: between them,
nothing ever evaluates ``config/resource-compute-bindings.json`` against the
date the project is actually living in.

The gap is not hypothetical. Every binding carries ``reviewed_at`` plus
``max_age_days`` precisely so an authorization goes *unauthorized* when nobody
re-reviews it, and admission implements that. With CI frozen in August, the only
bound compute path in the project can stop authorizing without a single red
check.

So the freshness assertions below deliberately fail on a date change with no
code change. That is the mechanism working, not a flaky test: an expired
authorization must block, and `AGENTS.md` requires current evidence rather than
evidence that was current once. The fix when one fires is to re-verify the
source and move the date, never to widen the window to cover the gap.

The structural assertions are time-independent and guard the boundary the
architecture is built on: a hosted *agent* is not direct compute, and no
binding may point at a resource holding repository-write or merge authority.
"""
from __future__ import annotations

import datetime as dt
import json
import sys
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import resource_compute_admission as admission  # noqa: E402

BINDINGS_PATH = ROOT / "config/resource-compute-bindings.json"
REGISTRY_PATH = ROOT / "examples/resources/free-resource-registry-v0.1.json"
POOL_PATH = ROOT / "examples/compute-offers/free-pool.example.json"


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


class LiveBindingContractTests(unittest.TestCase):
    """The real checked-in authorization, not a fixture."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.bindings = _load(BINDINGS_PATH)
        cls.registry = _load(REGISTRY_PATH)
        cls.resources = {offer["id"]: offer for offer in cls.registry["offers"]}
        cls.enabled = [b for b in cls.bindings["bindings"] if b["enabled"]]

    def test_real_files_pass_their_own_validators(self) -> None:
        admission.validate_bindings(self.bindings)
        admission.validate_registry(self.registry)
        admission.validate_pool(_load(POOL_PATH))

    def test_every_binding_resolves_to_a_registry_resource(self) -> None:
        # A binding naming a resource that no longer exists fails closed at
        # admission, which reads as "no capacity" rather than "broken config".
        for binding in self.bindings["bindings"]:
            with self.subTest(binding=binding["id"]):
                self.assertIn(binding["resource_id"], self.resources)

    def test_no_enabled_binding_points_at_a_hosted_agent(self) -> None:
        # The architectural boundary: hosted agents and agent orchestrators are
        # external actors, not capacity. Binding one through the compute bridge
        # would hand an external data processor a routable execution path.
        # Widening DIRECT_COMPUTE_KINDS to make the LLM offers routable is the
        # specific mistake this test exists to stop.
        for binding in self.enabled:
            resource = self.resources[binding["resource_id"]]
            with self.subTest(binding=binding["id"]):
                self.assertIn(
                    resource.get("kind"),
                    admission.DIRECT_COMPUTE_KINDS,
                    f"{binding['id']} binds kind={resource.get('kind')!r}",
                )

    def test_no_enabled_binding_grants_repository_authority(self) -> None:
        for binding in self.enabled:
            resource = self.resources[binding["resource_id"]]
            security = resource.get("security", {})
            with self.subTest(binding=binding["id"]):
                self.assertIs(security.get("repo_write_authority"), False)
                self.assertIs(security.get("merge_authority"), False)

    def test_no_enabled_binding_exceeds_the_zero_cost_policy(self) -> None:
        policy = _load(ROOT / "config/compute-policy.json")
        allowed = set(policy["allowed_cost_classes"])
        for binding in self.enabled:
            with self.subTest(binding=binding["id"]):
                self.assertEqual(
                    set(binding["allowed_cost_classes"]) - allowed,
                    set(),
                    "binding authorizes a cost class the project policy forbids",
                )

    def test_enabled_bindings_affirm_terms_eligibility(self) -> None:
        for binding in self.enabled:
            with self.subTest(binding=binding["id"]):
                self.assertTrue(binding["terms_eligible"])


class LiveFreshnessTests(unittest.TestCase):
    """Evaluated against today, which is the whole point.

    These are the assertions the pinned workflow date cannot make.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.bindings = _load(BINDINGS_PATH)
        cls.registry = _load(REGISTRY_PATH)
        cls.resources = {offer["id"]: offer for offer in cls.registry["offers"]}
        cls.today = dt.datetime.now(dt.timezone.utc).date()

    def test_no_enabled_binding_review_has_expired(self) -> None:
        for binding in (b for b in self.bindings["bindings"] if b["enabled"]):
            fresh, age = admission._fresh(
                binding["reviewed_at"], binding["max_age_days"], self.today
            )
            with self.subTest(binding=binding["id"]):
                self.assertTrue(
                    fresh,
                    f"{binding['id']} reviewed_at={binding['reviewed_at']} is "
                    f"{age} days old against max_age_days="
                    f"{binding['max_age_days']}. Re-verify the provider terms "
                    f"and move reviewed_at; do not widen max_age_days.",
                )

    def test_evidence_behind_every_enabled_binding_is_current(self) -> None:
        # A fresh local review resting on a stale reading of the provider's
        # terms is the failure max_age_days exists to prevent.
        for binding in (b for b in self.bindings["bindings"] if b["enabled"]):
            resource = self.resources[binding["resource_id"]]
            source = resource["source"]
            fresh, age = admission._fresh(
                source["checked_at"], source["max_age_days"], self.today
            )
            with self.subTest(binding=binding["id"], resource=resource["id"]):
                self.assertTrue(
                    fresh,
                    f"{resource['id']} source.checked_at={source['checked_at']} "
                    f"is {age} days old against max_age_days="
                    f"{source['max_age_days']}. Re-read {source['url']} and "
                    f"move checked_at only on a real re-read.",
                )

    def test_the_project_still_has_at_least_one_authorized_compute_path(self) -> None:
        # The failure this whole file was written for: on an expiry date, real
        # admission quietly drops to zero admitted offers while the pinned
        # workflow stays green and reports nothing.
        admitted, report = admission.admit(
            self.registry, self.bindings, _load(POOL_PATH), self.today
        )
        self.assertGreater(
            len(admitted["offers"]),
            0,
            "no concrete compute offer survives admission today; the free "
            f"resource mesh has no authorized capacity. Report: {report['rejected']}",
        )


if __name__ == "__main__":
    unittest.main()
