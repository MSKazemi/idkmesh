"""Verifier != executor separation of duties in the authorization kernel (#598).

One human holding both the worker and reviewer roles must not be able to verify
work they executed. The rule mirrors ``distinct_approval_at_risk``: a per-rule
risk threshold, strict in the baseline, that a project can relax explicitly.
"""

from __future__ import annotations

from dataclasses import replace
import unittest

from idkmesh.enterprise_authz import (
    MAX_EXECUTOR_PRINCIPALS,
    RISKS,
    ActorContext,
    AuthorizationContractError,
    AuthorizationPolicy,
    AuthorizationRequest,
    PolicyRule,
    authorize,
)
from idkmesh.enterprise_authz_cache import (
    AuthorizationDecisionCache,
    decision_cache_key,
    policy_digest,
)
from idkmesh.tenant_scope import ScopedResourceRef, TenantScope

NOW = 1790168400
SCOPE = TenantScope("tenant-a", "project-main")
RESOURCE = ScopedResourceRef(SCOPE, "candidate", "candidate-17")
WORKER = "github:user:worker"
REVIEWER = "github:user:reviewer"
BOTH = "github:user:both"


def actor(principal: str, *roles: str, **overrides) -> ActorContext:
    fields = dict(
        principal_id=principal,
        actor_type="human",
        issuer="github.com",
        roles=frozenset(roles),
        scopes=(SCOPE,),
        data_clearance="confidential",
        identity_revision="identity:1",
    )
    fields.update(overrides)
    return ActorContext(**fields)


def verify_request(who: ActorContext, *, risk="low", executors=(), **overrides):
    fields = dict(
        request_id="request:1",
        scope=SCOPE,
        resource=RESOURCE,
        actor=who,
        action="verify",
        risk=risk,
        data_classification="internal",
        evaluated_at_epoch=NOW,
        executor_principal_ids=executors,
    )
    fields.update(overrides)
    return AuthorizationRequest(**fields)


def relaxed_policy(threshold: str | None) -> AuthorizationPolicy:
    """The baseline with the verify rule's executor threshold replaced."""

    baseline = AuthorizationPolicy.enterprise_baseline()
    rules = tuple(
        replace(rule, executor_distinct_at_risk=threshold)
        if rule.action == "verify"
        else rule
        for rule in baseline.rules
    )
    return replace(baseline, rules=rules, revision="0.1-relaxed")


class BaselineSeparationTests(unittest.TestCase):
    policy = AuthorizationPolicy.enterprise_baseline()
    reviewer = actor(REVIEWER, "reviewer")
    both = actor(BOTH, "worker", "reviewer")

    def test_baseline_verify_rule_is_strict_from_the_lowest_risk(self) -> None:
        rule = self.policy.rule_for("verify")
        self.assertEqual(rule.executor_distinct_at_risk, "low")
        others = [r.action for r in self.policy.rules if r.executor_distinct_at_risk]
        self.assertEqual(others, ["verify"])

    def test_a_distinct_verifier_is_allowed_at_every_risk(self) -> None:
        for risk in RISKS:
            with self.subTest(risk=risk):
                decision = authorize(
                    verify_request(self.reviewer, risk=risk, executors=(WORKER,)),
                    self.policy,
                )
                self.assertEqual((decision.effect, decision.code), ("allow", "authorized"))

    def test_the_executor_cannot_verify_their_own_work_at_any_risk(self) -> None:
        for risk in RISKS:
            with self.subTest(risk=risk):
                decision = authorize(
                    verify_request(self.both, risk=risk, executors=(BOTH,)),
                    self.policy,
                )
                self.assertEqual(
                    (decision.effect, decision.code),
                    ("deny", "self_verification_forbidden"),
                )

    def test_taking_part_in_a_multi_party_execution_is_enough_to_disqualify(self) -> None:
        decision = authorize(
            verify_request(self.both, executors=(WORKER, BOTH)), self.policy
        )
        self.assertEqual(decision.code, "self_verification_forbidden")

    def test_an_unknown_executor_fails_closed_at_every_risk(self) -> None:
        # A rule the caller could switch off by omitting a field is not a control.
        for risk in RISKS:
            with self.subTest(risk=risk):
                decision = authorize(verify_request(self.reviewer, risk=risk), self.policy)
                self.assertEqual(
                    (decision.effect, decision.code),
                    ("deny", "executor_identity_required"),
                )

    def test_an_approver_cannot_waive_it(self) -> None:
        approver = actor("github:user:owner", "owner")
        decision = authorize(
            verify_request(
                self.both,
                risk="high",
                executors=(BOTH,),
                approver=approver,
                approval_reference="review:1",
            ),
            self.policy,
        )
        self.assertEqual((decision.effect, decision.code), ("deny", "self_verification_forbidden"))

    def test_earlier_denials_still_win(self) -> None:
        # A principal with no verify role is told so, not told about executors.
        worker_only = actor(WORKER, "worker")
        decision = authorize(verify_request(worker_only, executors=(WORKER,)), self.policy)
        self.assertEqual(decision.code, "role_denied")

    def test_other_actions_ignore_the_executor_field(self) -> None:
        worker = actor(WORKER, "worker")
        request = verify_request(worker, action="execute", executors=(WORKER,))
        self.assertEqual(authorize(request, self.policy).effect, "allow")


class ExplicitRelaxationTests(unittest.TestCase):
    """The issue: same human, low-risk roles, only when policy explicitly permits."""

    both = actor(BOTH, "worker", "reviewer")

    def test_a_project_can_permit_low_risk_self_verification_explicitly(self) -> None:
        policy = relaxed_policy("medium")
        low = authorize(verify_request(self.both, risk="low", executors=(BOTH,)), policy)
        self.assertEqual((low.effect, low.code), ("allow", "authorized"))
        # An omitted executor is also tolerated below the threshold...
        self.assertEqual(authorize(verify_request(self.both, risk="low"), policy).effect, "allow")
        # ...but the threshold itself and everything above it stays distinct.
        for risk in ("medium", "high", "critical"):
            with self.subTest(risk=risk):
                denied = authorize(
                    verify_request(self.both, risk=risk, executors=(BOTH,)), policy
                )
                self.assertEqual(denied.code, "self_verification_forbidden")

    def test_the_rule_can_be_switched_off_only_in_the_policy(self) -> None:
        policy = relaxed_policy(None)
        decision = authorize(verify_request(self.both, risk="critical", executors=(BOTH,)), policy)
        self.assertEqual(decision.effect, "allow")

    def test_an_unknown_threshold_is_rejected(self) -> None:
        with self.assertRaises(AuthorizationContractError):
            PolicyRule(
                "verify",
                frozenset({"reviewer"}),
                frozenset({"human"}),
                executor_distinct_at_risk="severe",
            )


class RequestFieldTests(unittest.TestCase):
    reviewer = actor(REVIEWER, "reviewer")

    def test_ids_are_normalized_to_a_sorted_unique_tuple(self) -> None:
        request = verify_request(self.reviewer, executors=(WORKER, BOTH, WORKER))
        self.assertEqual(request.executor_principal_ids, tuple(sorted({WORKER, BOTH})))
        frozen = verify_request(self.reviewer, executors=frozenset({WORKER, BOTH}))
        self.assertEqual(frozen.executor_principal_ids, request.executor_principal_ids)

    def test_malformed_values_are_rejected(self) -> None:
        for bad in ([WORKER], WORKER, {WORKER: 1}, (1,), ("",), ("bad id",), (None,)):
            with self.subTest(value=repr(bad)), self.assertRaises(AuthorizationContractError):
                verify_request(self.reviewer, executors=bad)

    def test_the_principal_count_is_bounded(self) -> None:
        many = tuple(f"github:user:u{i}" for i in range(MAX_EXECUTOR_PRINCIPALS))
        self.assertEqual(
            len(verify_request(self.reviewer, executors=many).executor_principal_ids),
            MAX_EXECUTOR_PRINCIPALS,
        )
        with self.assertRaises(AuthorizationContractError):
            verify_request(self.reviewer, executors=(*many, "github:user:extra"))


class DecisionCacheTests(unittest.TestCase):
    """A cached ALLOW must never be replayed for a self-verification."""

    policy = AuthorizationPolicy.enterprise_baseline()
    both = actor(BOTH, "worker", "reviewer")

    def test_cache_key_covers_the_executor_set(self) -> None:
        keys = {
            decision_cache_key(verify_request(self.both, executors=executors), self.policy)
            for executors in ((), (WORKER,), (BOTH,), (WORKER, BOTH))
        }
        self.assertEqual(len(keys), 4)
        reordered = decision_cache_key(
            verify_request(self.both, executors=(BOTH, WORKER)), self.policy
        )
        self.assertEqual(
            reordered,
            decision_cache_key(verify_request(self.both, executors=(WORKER, BOTH)), self.policy),
        )

    def test_policy_digest_covers_the_threshold(self) -> None:
        digests = {policy_digest(relaxed_policy(t)) for t in (None, "low", "medium", "high")}
        self.assertEqual(len(digests), 4)

    def test_cached_allow_is_not_replayed_when_the_actor_is_the_executor(self) -> None:
        cache = AuthorizationDecisionCache(max_age_seconds=300)
        allowed = cache.authorize(
            verify_request(self.both, executors=(WORKER,)), self.policy
        )
        self.assertEqual(allowed.effect, "allow")
        replay = cache.authorize(
            verify_request(self.both, executors=(BOTH,), request_id="request:2"), self.policy
        )
        self.assertEqual((replay.effect, replay.code), ("deny", "self_verification_forbidden"))
        self.assertEqual(cache.hits, 0)
        # And the identical request still hits.
        again = cache.authorize(
            verify_request(self.both, executors=(WORKER,), request_id="request:3"), self.policy
        )
        self.assertEqual((again.effect, cache.hits), ("allow", 1))


if __name__ == "__main__":
    unittest.main()
