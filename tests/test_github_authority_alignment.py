"""C10 (#598): binding table vs C5 dispatch trusted-list alignment audit.

Offline, synthetic numeric GitHub actor ids only. The audit is read-only and
grants no authority; these tests pin that it flags every divergence in which
one configuration cannot back the other's authority, and that it stays quiet
for a genuinely aligned pair.
"""

from __future__ import annotations

import copy
from dataclasses import replace
import json
import unittest

from idkmesh.enterprise_authz import AuthorizationPolicy
from idkmesh.enterprise_identity_github import parse_identity_binding_table
from idkmesh.github_authority_alignment import (
    ALIGNMENT_REPORT_KIND,
    AlignmentFinding,
    AuthorityAlignmentError,
    audit_dispatch_authority_alignment,
)
from idkmesh.github_dispatch_authorization import (
    GitHubDispatchAuthorizationPolicy,
    TrustedGitHubActor,
)
from idkmesh.tenant_scope import TenantScope

SCOPE = TenantScope("tenant-a", "project-main")
OTHER_SCOPE = TenantScope("tenant-b", "project-other")
ALICE, BOB, BOT = 1001, 1002, 2001


def _item(actor_id, login, roles, actor_type="human", **extra):
    item = {
        "actor_id": actor_id,
        "login": login,
        "actor_type": actor_type,
        "issuer": "github.com",
        "roles": roles,
        "scopes": [{"tenant_id": "tenant-a", "project_id": "project-main"}],
        "data_clearance": "confidential",
        "identity_revision": "github-identity:1",
        "revoked": False,
        "expires_at_epoch": None,
    }
    item.update(extra)
    return item


def _document(*items):
    return {
        "kind": "idkmesh-enterprise-github-identity-binding-table",
        "schema_version": "0.1",
        "bindings": list(items),
    }


def _table(*items):
    return parse_identity_binding_table(_document(*items))


def _policy(*actors, allowed_roles=frozenset({"owner", "maintainer"})):
    return GitHubDispatchAuthorizationPolicy(
        repository="MSKazemi/idkmesh",
        dispatch_labels=frozenset({"agent-ready"}),
        trusted_actors=tuple(actors),
        allowed_roles=allowed_roles,
    )


def _codes(report):
    return [(f.actor_id, f.code) for f in report.findings]


class AlignedConfigurationTests(unittest.TestCase):
    def test_aligned_pair_is_clean_and_grants_no_authority(self):
        table = _table(
            _item(ALICE, "alice", ["owner"]),
            _item(BOB, "bob", ["worker"]),
        )
        policy = _policy(TrustedGitHubActor(ALICE, "alice", "owner"))
        report = audit_dispatch_authority_alignment(
            table, policy, scope=SCOPE, now_epoch=1_000
        )
        self.assertEqual(report.findings, ())
        self.assertTrue(report.aligned)
        self.assertTrue(report.clean)
        document = report.to_dict()
        self.assertEqual(document["kind"], ALIGNMENT_REPORT_KIND)
        self.assertIs(document["grants_authority"], False)
        self.assertEqual(document["dispatch_actors_checked"], 1)
        self.assertEqual(document["bindings_checked"], 2)
        json.dumps(document)  # JSON-serialisable

    def test_automation_actor_bound_as_github_app_is_aligned(self):
        table = _table(
            _item(ALICE, "alice", ["owner"]),
            _item(BOT, "idk-bot[bot]", ["dispatcher"], actor_type="github_app"),
        )
        policy = _policy(
            TrustedGitHubActor(ALICE, "alice", "owner"),
            TrustedGitHubActor(BOT, "idk-bot[bot]", "automation"),
            allowed_roles=frozenset({"owner", "automation"}),
        )
        self.assertTrue(
            audit_dispatch_authority_alignment(table, policy).clean
        )

    def test_report_is_deterministic(self):
        table = _table(_item(ALICE, "alice", ["worker"]), _item(BOB, "bob", ["worker"]))
        policy = _policy(
            TrustedGitHubActor(BOB, "bob", "owner"),
            TrustedGitHubActor(ALICE, "alice", "owner"),
        )
        first = audit_dispatch_authority_alignment(table, policy).to_dict()
        second = audit_dispatch_authority_alignment(table, policy).to_dict()
        self.assertEqual(first, second)
        self.assertEqual(
            [f["actor_id"] for f in first["findings"]], sorted(
                f["actor_id"] for f in first["findings"]
            )
        )


class DivergenceTests(unittest.TestCase):
    def test_dispatch_actor_without_binding_is_an_error(self):
        table = _table(_item(BOB, "bob", ["worker"]))
        policy = _policy(TrustedGitHubActor(ALICE, "alice", "owner"))
        report = audit_dispatch_authority_alignment(table, policy)
        self.assertEqual(_codes(report), [(ALICE, "dispatch_actor_unbound")])
        self.assertFalse(report.aligned)

    def test_login_mismatch_is_an_error_but_case_is_not(self):
        table = _table(_item(ALICE, "alice", ["owner"]))
        renamed = _policy(TrustedGitHubActor(ALICE, "alice-renamed", "owner"))
        report = audit_dispatch_authority_alignment(table, renamed)
        self.assertEqual(
            _codes(report), [(ALICE, "dispatch_actor_login_mismatch")]
        )
        recased = _policy(TrustedGitHubActor(ALICE, "ALICE", "owner"))
        self.assertTrue(audit_dispatch_authority_alignment(table, recased).clean)

    def test_actor_that_crosses_gate_without_kernel_dispatch_role_is_an_error(self):
        # The label gate trusts alice as owner, but the kernel binding only
        # makes her a worker: a label could dispatch what authorize() denies.
        table = _table(_item(ALICE, "alice", ["worker"]))
        policy = _policy(TrustedGitHubActor(ALICE, "alice", "owner"))
        report = audit_dispatch_authority_alignment(table, policy)
        self.assertEqual(
            _codes(report), [(ALICE, "dispatch_actor_lacks_kernel_dispatch_role")]
        )
        self.assertFalse(report.aligned)

    def test_trusted_actor_with_role_the_gate_refuses_is_not_an_error(self):
        # triager is trusted but not in allowed_roles: the gate itself refuses
        # them, so the kernel need not back dispatch authority.
        policy = _policy(
            TrustedGitHubActor(ALICE, "alice", "owner"),
            TrustedGitHubActor(BOB, "bob", "triager"),
        )
        table = _table(_item(ALICE, "alice", ["owner"]), _item(BOB, "bob", ["worker"]))
        self.assertTrue(audit_dispatch_authority_alignment(table, policy).clean)

    def test_human_role_bound_to_a_bot_identity_is_an_error(self):
        table = _table(_item(BOT, "idk-bot[bot]", ["dispatcher"], actor_type="github_app"))
        policy = _policy(TrustedGitHubActor(BOT, "idk-bot[bot]", "maintainer"))
        report = audit_dispatch_authority_alignment(table, policy)
        self.assertEqual(_codes(report), [(BOT, "dispatch_actor_kind_mismatch")])

    def test_automation_role_bound_to_a_human_identity_is_an_error(self):
        table = _table(_item(ALICE, "alice", ["owner"]))
        policy = _policy(
            TrustedGitHubActor(ALICE, "alice", "automation"),
            allowed_roles=frozenset({"automation"}),
        )
        report = audit_dispatch_authority_alignment(table, policy)
        self.assertIn((ALICE, "dispatch_actor_kind_mismatch"), _codes(report))

    def test_revoked_binding_is_an_error(self):
        table = _table(_item(ALICE, "alice", ["owner"], revoked=True))
        policy = _policy(TrustedGitHubActor(ALICE, "alice", "owner"))
        report = audit_dispatch_authority_alignment(table, policy)
        self.assertEqual(
            _codes(report), [(ALICE, "dispatch_actor_binding_revoked")]
        )

    def test_expiry_is_checked_only_with_an_explicit_clock(self):
        table = _table(_item(ALICE, "alice", ["owner"], expires_at_epoch=500))
        policy = _policy(TrustedGitHubActor(ALICE, "alice", "owner"))
        self.assertTrue(audit_dispatch_authority_alignment(table, policy).clean)
        before = audit_dispatch_authority_alignment(table, policy, now_epoch=499)
        self.assertTrue(before.clean)
        at = audit_dispatch_authority_alignment(table, policy, now_epoch=500)
        self.assertEqual(_codes(at), [(ALICE, "dispatch_actor_binding_expired")])

    def test_scope_is_checked_only_when_supplied(self):
        table = _table(_item(ALICE, "alice", ["owner"]))
        policy = _policy(TrustedGitHubActor(ALICE, "alice", "owner"))
        self.assertTrue(
            audit_dispatch_authority_alignment(table, policy, scope=SCOPE).clean
        )
        report = audit_dispatch_authority_alignment(
            table, policy, scope=OTHER_SCOPE
        )
        self.assertEqual(_codes(report), [(ALICE, "dispatch_actor_scope_missing")])

    def test_kernel_dispatcher_outside_gate_is_a_warning_not_an_error(self):
        table = _table(
            _item(ALICE, "alice", ["owner"]),
            _item(BOB, "bob", ["dispatcher"]),
        )
        policy = _policy(TrustedGitHubActor(ALICE, "alice", "owner"))
        report = audit_dispatch_authority_alignment(table, policy)
        self.assertEqual(
            _codes(report), [(BOB, "kernel_dispatcher_not_dispatch_gate_trusted")]
        )
        self.assertEqual(report.findings[0].severity, "warning")
        self.assertTrue(report.aligned)
        self.assertFalse(report.clean)

    def test_revoked_kernel_dispatcher_outside_gate_is_not_reported(self):
        table = _table(
            _item(ALICE, "alice", ["owner"]),
            _item(BOB, "bob", ["dispatcher"], revoked=True),
        )
        policy = _policy(TrustedGitHubActor(ALICE, "alice", "owner"))
        self.assertTrue(audit_dispatch_authority_alignment(table, policy).clean)

    def test_policy_without_a_dispatch_rule_leaves_gate_actors_unbacked(self):
        baseline = AuthorizationPolicy.enterprise_baseline()
        no_dispatch = replace(
            baseline,
            rules=tuple(r for r in baseline.rules if r.action != "dispatch"),
        )
        table = _table(_item(ALICE, "alice", ["owner"]))
        policy = _policy(TrustedGitHubActor(ALICE, "alice", "owner"))
        report = audit_dispatch_authority_alignment(
            table, policy, authorization_policy=no_dispatch
        )
        self.assertEqual(
            _codes(report), [(ALICE, "dispatch_actor_lacks_kernel_dispatch_role")]
        )

    def test_multiple_findings_per_actor_are_all_reported_sorted(self):
        table = _table(_item(ALICE, "alice", ["worker"], revoked=True))
        policy = _policy(TrustedGitHubActor(ALICE, "other-login", "owner"))
        report = audit_dispatch_authority_alignment(table, policy)
        self.assertEqual(
            _codes(report),
            [
                (ALICE, "dispatch_actor_binding_revoked"),
                (ALICE, "dispatch_actor_lacks_kernel_dispatch_role"),
                (ALICE, "dispatch_actor_login_mismatch"),
            ],
        )


class InputValidationTests(unittest.TestCase):
    def setUp(self):
        self.table = _table(_item(ALICE, "alice", ["owner"]))
        self.policy = _policy(TrustedGitHubActor(ALICE, "alice", "owner"))

    def test_wrong_types_fail_closed(self):
        for kwargs in (
            {"table": {}, "dispatch_policy": self.policy},
            {"table": self.table, "dispatch_policy": object()},
            {
                "table": self.table,
                "dispatch_policy": self.policy,
                "authorization_policy": "baseline",
            },
            {"table": self.table, "dispatch_policy": self.policy, "scope": "x"},
            {"table": self.table, "dispatch_policy": self.policy, "now_epoch": -1},
            {"table": self.table, "dispatch_policy": self.policy, "now_epoch": True},
            {"table": self.table, "dispatch_policy": self.policy, "now_epoch": 1.5},
        ):
            with self.subTest(kwargs=sorted(kwargs)):
                with self.assertRaises(AuthorityAlignmentError):
                    audit_dispatch_authority_alignment(**kwargs)

    def test_finding_rejects_unknown_code_severity_and_actor(self):
        with self.assertRaises(AuthorityAlignmentError):
            AlignmentFinding("nope", "error", 1, "m")
        with self.assertRaises(AuthorityAlignmentError):
            AlignmentFinding("dispatch_actor_unbound", "info", 1, "m")
        with self.assertRaises(AuthorityAlignmentError):
            AlignmentFinding("dispatch_actor_unbound", "error", 0, "m")

    def test_audit_does_not_mutate_its_inputs(self):
        before = copy.deepcopy(self.table.bindings[0].context.to_dict())
        audit_dispatch_authority_alignment(self.table, self.policy)
        self.assertEqual(self.table.bindings[0].context.to_dict(), before)

    def test_findings_never_echo_login_text(self):
        table = _table(_item(ALICE, "alice", ["worker"]))
        policy = _policy(TrustedGitHubActor(ALICE, "alice", "owner"))
        rendered = json.dumps(
            audit_dispatch_authority_alignment(table, policy).to_dict()
        )
        self.assertNotIn("alice", rendered)


if __name__ == "__main__":
    unittest.main()
