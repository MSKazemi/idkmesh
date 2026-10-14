"""Exhaustive permission matrix for the enterprise authorization kernel.

Issue #745's security section asks for a permission matrix. The HTTP surface
deliberately has no principals yet (``tests/test_api_authority_matrix.py``
pins that), so permissions live in ``idkmesh.enterprise_authz``: the
``enterprise_baseline`` policy's role/action/actor-type rules. Scenario tests
in ``tests/test_enterprise_authz.py`` cover the semantics pairwise; this
module pins the **complete decision table** as an independent oracle, so a
baseline edit that silently widens or narrows any single cell fails here and
forces a deliberate table update.

Conditions for every cell: a human actor (or the actor type under test),
authenticated and unrevoked, bound to the request scope, data classification
``internal`` within a ``confidential`` clearance, evaluated at the rule's own
risk floor, and **no approver**. Cell values are decision effects with their
codes:

- ``allow``/``authorized`` -- the role (and actor type) permit the action;
- ``deny``/``role_denied`` -- the role is not allowed for the action;
- ``requires_approval``/``distinct_approval_required`` -- permitted, but the
  rule's approval threshold is already reached at its risk floor.

Class-based on purpose: the documented test counts guard module-level
``test_*`` functions, and this file must not shift them.
"""

from __future__ import annotations

import unittest

from idkmesh.enterprise_authz import (
    ACTIONS,
    ROLES,
    ActorContext,
    AuthorizationPolicy,
    AuthorizationRequest,
    authorize,
)
from idkmesh.tenant_scope import ScopedResourceRef, TenantScope

NOW = 1790168400

ACTOR_TYPES = (
    "human",
    "github_app",
    "github_actions",
    "service",
    "provider",
    "node",
)

# Independent transcription of the expected baseline decision table.
# action -> (risk floor, expected effect+code for allowed roles, allowed roles)
ALLOWED_ROLES = {
    "read": (None, ("allow", "authorized"), ROLES),
    "claim": (
        "low",
        ("allow", "authorized"),
        frozenset({"worker", "dispatcher", "node_operator"}),
    ),
    "release": (
        "low",
        ("allow", "authorized"),
        frozenset({"worker", "dispatcher", "node_operator"}),
    ),
    "dispatch": (
        "low",
        ("allow", "authorized"),
        frozenset({"dispatcher", "admin", "owner"}),
    ),
    "execute": (
        "low",
        ("allow", "authorized"),
        frozenset({"worker", "node_operator"}),
    ),
    "verify": (
        "low",
        ("allow", "authorized"),
        frozenset({"reviewer", "auditor"}),
    ),
    "integrate": (
        "low",
        ("allow", "authorized"),
        frozenset({"integrator", "admin", "owner"}),
    ),
    "decide": (
        "low",
        ("allow", "authorized"),
        frozenset({"integrator", "admin", "owner"}),
    ),
    "manage_policy": (
        "high",
        ("requires_approval", "distinct_approval_required"),
        frozenset({"admin", "owner"}),
    ),
    "audit_export": (
        "medium",
        ("allow", "authorized"),
        frozenset({"auditor", "admin", "owner"}),
    ),
}

# action -> actor types permitted by the baseline (role gate aside).
ALLOWED_ACTOR_TYPES = {
    "read": frozenset(ACTOR_TYPES),
    "claim": frozenset(ACTOR_TYPES),
    "release": frozenset(ACTOR_TYPES),
    "dispatch": frozenset({"human", "github_app", "github_actions", "service"}),
    "execute": frozenset(ACTOR_TYPES),
    "verify": frozenset({"human", "github_app", "github_actions", "service"}),
    "integrate": frozenset({"human"}),
    "decide": frozenset({"human"}),
    "manage_policy": frozenset({"human"}),
    "audit_export": frozenset({"human", "github_app", "service"}),
}

DENY_ROLE = ("deny", "role_denied")


class BaselinePermissionMatrixTests(unittest.TestCase):
    """The full role x action decision table at the baseline's risk floors."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.policy = AuthorizationPolicy.enterprise_baseline()
        cls.scope = TenantScope("tenant-a", "project-main")

    def actor(self, *, roles, actor_type="human") -> ActorContext:
        return ActorContext(
            principal_id="github:user:alice",
            actor_type=actor_type,
            issuer="github.com",
            roles=frozenset(roles),
            scopes=(self.scope,),
            data_clearance="confidential",
            identity_revision="identity:1",
            authenticated=True,
            revoked=False,
            expires_at_epoch=None,
        )

    def request(self, actor, action: str) -> AuthorizationRequest:
        risk_floor, _effect, _roles = ALLOWED_ROLES[action]
        return AuthorizationRequest(
            request_id="request:matrix",
            scope=self.scope,
            resource=ScopedResourceRef(self.scope, "candidate", "candidate-17"),
            actor=actor,
            action=action,
            # ``None`` stands in for the natural "read"-style lowest risk;
            # every other action is exercised at its own floor.
            risk=risk_floor or "low",
            data_classification="internal",
            evaluated_at_epoch=NOW,
            # Baseline ``verify`` is strict separation of duties: the work under
            # review was executed by someone other than the actor under test.
            executor_principal_ids=("principal:executor",) if action == "verify" else (),
        )

    def cell(self, *, roles, action: str, actor_type: str = "human"):
        decision = authorize(
            self.request(self.actor(roles=roles, actor_type=actor_type), action),
            self.policy,
        )
        return decision.effect, decision.code

    def test_the_tables_cover_every_role_and_action(self) -> None:
        self.assertEqual(set(ALLOWED_ROLES), set(ACTIONS))
        self.assertEqual(set(ALLOWED_ACTOR_TYPES), set(ACTIONS))
        covered = set().union(*(set(roles) for _, _, roles in ALLOWED_ROLES.values()))
        self.assertEqual(covered, set(ROLES))

    def test_full_role_matrix_matches_the_expected_table(self) -> None:
        for action, (_floor, expected, allowed) in ALLOWED_ROLES.items():
            for role in sorted(ROLES):
                with self.subTest(action=action, role=role):
                    want = expected if role in allowed else DENY_ROLE
                    self.assertEqual(
                        self.cell(roles=(role,), action=action),
                        want,
                        f"{role} -> {action}: baseline drifted from the "
                        f"pinned matrix (expected {want})",
                    )

    def test_actor_type_matrix_matches_the_expected_table(self) -> None:
        for action, (_floor, _effect, allowed_roles) in ALLOWED_ROLES.items():
            probe_role = sorted(allowed_roles)[0]
            for actor_type in ACTOR_TYPES:
                with self.subTest(action=action, actor_type=actor_type):
                    effect, code = self.cell(
                        roles=(probe_role,),
                        action=action,
                        actor_type=actor_type,
                    )
                    if actor_type in ALLOWED_ACTOR_TYPES[action]:
                        self.assertNotEqual(code, "actor_type_denied")
                        self.assertIn(effect, ("allow", "requires_approval"))
                    else:
                        self.assertEqual(
                            (effect, code), ("deny", "actor_type_denied")
                        )

    def test_multi_role_actors_get_the_widest_cell(self) -> None:
        """Union semantics: any one allowed role is enough, and a full role
        set never fares worse than the single-role matrix predicts."""
        everything = tuple(sorted(ROLES))
        for action, (_floor, expected, _allowed) in ALLOWED_ROLES.items():
            with self.subTest(action=action):
                self.assertEqual(
                    self.cell(roles=everything, action=action), expected
                )

    def test_manage_policy_is_the_only_floor_at_its_approval_threshold(self) -> None:
        """At its own risk floor exactly one action demands approval; if the
        baseline changes that, the matrix tables need a deliberate update."""
        approval_at_floor = [
            action
            for action, (_floor, expected, allowed) in ALLOWED_ROLES.items()
            if expected[0] == "requires_approval"
        ]
        self.assertEqual(approval_at_floor, ["manage_policy"])
        for action, (_floor, expected, allowed) in ALLOWED_ROLES.items():
            if expected[0] != "requires_approval":
                continue
            with self.subTest(action=action):
                self.assertEqual(
                    self.cell(roles=(sorted(allowed)[0],), action=action),
                    expected,
                )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
