import copy
import importlib.util
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

TOOLS = Path(__file__).parents[1] / "tools"

shadow_spec = importlib.util.spec_from_file_location(
    "adaptive_policy_shadow",
    TOOLS / "adaptive_policy_shadow.py",
)
shadow = importlib.util.module_from_spec(shadow_spec)
sys.modules[shadow_spec.name] = shadow
assert shadow_spec.loader is not None
shadow_spec.loader.exec_module(shadow)

adapter_spec = importlib.util.spec_from_file_location(
    "ave_shadow_adapter",
    TOOLS / "ave_shadow_adapter.py",
)
adapter = importlib.util.module_from_spec(adapter_spec)
sys.modules[adapter_spec.name] = adapter
assert adapter_spec.loader is not None
adapter_spec.loader.exec_module(adapter)


SOURCE = "1" * 40
CAPTURED = "2026-09-22T12:00:00Z"


def work_unit(risk="low", minimum=1, validators=None):
    validators = validators or ["schema-check"]
    return {
        "schema_version": "0.2",
        "id": "test/work-unit",
        "version": 1,
        "kind": "testing",
        "security": {
            "risk_class": risk,
        },
        "budget": {
            "project_spend_usd_max": 0,
            "paid_fallback_allowed": False,
        },
        "verification_policy": {
            "strategy": "all_required",
            "independent_from_worker": True,
            "minimum_independent_verifiers": minimum,
        },
        "validators": [
            {
                "id": validator_id,
                "type": "test",
                "required": True,
            }
            for validator_id in validators
        ],
        "provenance": {
            "source_revision": SOURCE,
        },
    }


def evaluator_plan(wu, verifier_id="baseline-verifier"):
    return {
        "schema_version": "0.4",
        "id": "verification/test-plan",
        "binding": {
            "work_unit_id": wu["id"],
            "work_unit_version": wu["version"],
            "work_unit_digest": adapter.canonical_digest(wu),
            "source_revision": SOURCE,
        },
        "verifier": {
            "id": verifier_id,
            "type": "system",
            "adapter": "test-adapter",
            "adapter_version": "1",
        },
        "required_validator_ids": [
            item["id"]
            for item in wu["validators"]
            if item["required"]
        ],
        "policy": {
            "require_verifier_distinct_from_worker": True,
        },
    }


def candidate(
    verifier_id,
    family,
    *,
    validators=("schema-check",),
    basis="live_outcomes",
    alpha=8,
    beta=2,
    samples=10,
    domain="testing",
    observed_at="2026-09-21T12:00:00Z",
    shift=False,
    probe_trials=0,
    probe_breaches=0,
    review=1.0,
    queue=0.0,
    available=True,
    independent=True,
    shared_model=False,
    shared_runtime=False,
):
    return {
        "id": verifier_id,
        "family": family,
        "provider_family": None,
        "available": available,
        "supported_validator_ids": list(validators),
        "review_units": review,
        "queue_load": queue,
        "independence": {
            "independent_from_worker": independent,
            "shared_model_family": shared_model,
            "shared_runtime": shared_runtime,
        },
        "reliability": {
            "basis": basis,
            "alpha": alpha,
            "beta": beta,
            "sample_count": samples,
            "domain": domain,
            "observed_at": observed_at,
            "shift_warning": shift,
            "source_refs": [],
            "known_bad_probe_trials": probe_trials,
            "known_bad_probe_breaches": probe_breaches,
        },
    }


def pool(wu, candidates, *, domain="testing", max_age=30):
    return {
        "schema_version": "0.1",
        "kind": "idkmesh-verifier-observation-pool",
        "repository": "MSKazemi/idkmesh",
        "source_revision": SOURCE,
        "captured_at": CAPTURED,
        "work_unit_id": wu["id"],
        "task_domain": domain,
        "worker_id": "worker-1",
        "reliability_max_age_days": max_age,
        "verifier_candidates": candidates,
        "limitations": [
            "test fixture only",
        ],
    }


def selected_ids(plan):
    selected = plan["recommendation"]["selected_choice_id"]
    if selected is None:
        return []
    assert selected.startswith("portfolio:")
    return selected.removeprefix("portfolio:").split("+")


def build(wu, candidates, *, plan=None, pool_overrides=None):
    verifier_pool = pool(wu, candidates)
    if pool_overrides:
        verifier_pool.update(pool_overrides)
    return adapter.build_ave_shadow_plan(
        repository="MSKazemi/idkmesh",
        work_unit=wu,
        evaluator_plan=plan or evaluator_plan(wu),
        verifier_pool=verifier_pool,
        maturity="N2",
        input_refs=["fixture:test"],
    )


def test_exact_binding_selects_when_all_gates_pass():
    wu = work_unit()
    result = build(
        wu,
        [
            candidate("v1", "family-a"),
            candidate("v2", "family-b", alpha=6, beta=4),
        ],
    )
    assert result["recommendation"]["selected_choice_id"] is not None
    assert all(
        gate["status"] == "pass"
        for gate in result["hard_gates"]
    )
    assert result["authority"]["dispatch"] is False
    assert result["authority"]["modify_required_verification"] is False


def test_work_unit_digest_mismatch_forces_shadow_abstention():
    wu = work_unit()
    plan = evaluator_plan(wu)
    plan["binding"]["work_unit_digest"] = "sha256:" + "0" * 64
    result = build(wu, [candidate("v1", "family-a")], plan=plan)
    assert result["recommendation"]["selected_choice_id"] is None
    gate = next(
        value
        for value in result["hard_gates"]
        if value["id"] == "exact-work-unit-digest"
    )
    assert gate["status"] == "fail"


def test_source_revision_mismatch_forces_shadow_abstention():
    wu = work_unit()
    result = build(
        wu,
        [candidate("v1", "family-a")],
        pool_overrides={"source_revision": "2" * 40},
    )
    assert result["recommendation"]["selected_choice_id"] is None
    gate = next(
        value
        for value in result["hard_gates"]
        if value["id"] == "source-revision-binding"
    )
    assert gate["status"] == "fail"


def test_required_validator_coverage_is_preserved_at_portfolio_level():
    wu = work_unit(
        risk="medium",
        validators=["schema-check", "security-check"],
    )
    result = build(
        wu,
        [
            candidate(
                "v-schema",
                "family-a",
                validators=("schema-check",),
            ),
            candidate(
                "v-security",
                "family-b",
                validators=("security-check",),
            ),
            candidate(
                "v-unused",
                "family-c",
                validators=("schema-check",),
            ),
        ],
    )
    assert set(selected_ids(result)) == {"v-schema", "v-security"}


def test_risk_target_never_weakens_work_unit_minimum():
    wu = work_unit(risk="low", minimum=3)
    assert adapter._risk_target(wu) == 3
    medium = work_unit(risk="medium", minimum=1)
    assert adapter._risk_target(medium) == 2
    high = work_unit(risk="high", minimum=1)
    assert adapter._risk_target(high) == 3


def test_family_diversity_beats_same_family_high_reliability():
    wu = work_unit(risk="medium")
    result = build(
        wu,
        [
            candidate("a1", "family-a", alpha=20, beta=1),
            candidate("a2", "family-a", alpha=20, beta=1),
            candidate("b1", "family-b", alpha=6, beta=4),
        ],
    )
    ids = set(selected_ids(result))
    assert "b1" in ids
    assert len(ids.intersection({"a1", "a2"})) == 1


def test_high_risk_abstains_without_three_distinct_families():
    wu = work_unit(risk="high")
    result = build(
        wu,
        [
            candidate("a1", "family-a"),
            candidate("a2", "family-a"),
            candidate("b1", "family-b"),
            candidate("b2", "family-b"),
        ],
    )
    assert result["recommendation"]["selected_choice_id"] is None
    assert any(
        "family-diverse" in reason
        for reason in result["recommendation"]["reasons"]
    )


def test_probe_only_success_is_neutral_not_positive_trust():
    wu = work_unit()
    result = build(
        wu,
        [
            candidate(
                "probe-star",
                "family-a",
                basis="known_bad_probes",
                alpha=100,
                beta=1,
                samples=99,
                probe_trials=99,
                probe_breaches=0,
            ),
            candidate(
                "live",
                "family-b",
                basis="live_outcomes",
                alpha=6,
                beta=4,
                samples=10,
            ),
        ],
    )
    assert selected_ids(result) == ["live"]
    probe = next(
        choice
        for choice in result["eligible_choices"]
        if choice["id"] == "portfolio:probe-star"
    )
    assert probe["metrics"]["live_supported_count"] == 0
    assert probe["metrics"]["mean_reliability"] == 0.5


def test_known_bad_probe_breach_vetoes_ave_selection():
    wu = work_unit()
    result = build(
        wu,
        [
            candidate(
                "breached",
                "family-a",
                alpha=50,
                beta=1,
                probe_trials=5,
                probe_breaches=1,
            ),
            candidate("clean", "family-b", alpha=6, beta=4),
        ],
    )
    assert selected_ids(result) == ["clean"]
    assert not any(
        choice["id"] == "portfolio:breached"
        for choice in result["eligible_choices"]
    )


def test_shift_warning_neutralizes_learned_reliability():
    wu = work_unit()
    result = build(
        wu,
        [
            candidate(
                "shifted",
                "family-a",
                alpha=99,
                beta=1,
                samples=100,
                shift=True,
            ),
            candidate(
                "stable",
                "family-b",
                alpha=6,
                beta=4,
                samples=10,
            ),
        ],
    )
    assert selected_ids(result) == ["stable"]


def test_stale_live_reliability_is_neutral():
    wu = work_unit()
    stale_time = (
        datetime(2026, 9, 22, tzinfo=timezone.utc)
        - timedelta(days=90)
    ).isoformat().replace("+00:00", "Z")
    result = build(
        wu,
        [
            candidate(
                "stale",
                "family-a",
                alpha=99,
                beta=1,
                samples=100,
                observed_at=stale_time,
            ),
            candidate(
                "fresh",
                "family-b",
                alpha=6,
                beta=4,
                samples=10,
            ),
        ],
        pool_overrides={"reliability_max_age_days": 30},
    )
    assert selected_ids(result) == ["fresh"]


def test_wrong_domain_live_reliability_is_neutral():
    wu = work_unit()
    result = build(
        wu,
        [
            candidate(
                "other-domain",
                "family-a",
                alpha=99,
                beta=1,
                samples=100,
                domain="security",
            ),
            candidate(
                "same-domain",
                "family-b",
                alpha=6,
                beta=4,
                samples=10,
                domain="testing",
            ),
        ],
    )
    assert selected_ids(result) == ["same-domain"]


def test_pool_rejects_impossible_probe_counts():
    wu = work_unit()
    bad = pool(
        wu,
        [
            candidate(
                "bad",
                "family-a",
                probe_trials=1,
                probe_breaches=2,
            )
        ],
    )
    try:
        adapter.validate_verifier_pool(bad)
    except adapter.AVEShadowAdapterError as exc:
        assert "probe counts" in str(exc)
    else:
        raise AssertionError("invalid probe counts were accepted")


def test_future_dated_reliability_is_rejected():
    wu = work_unit()
    bad = pool(
        wu,
        [
            candidate(
                "future",
                "family-a",
                observed_at="2026-09-23T12:00:00Z",
            )
        ],
    )
    try:
        adapter.validate_verifier_pool(bad)
    except adapter.AVEShadowAdapterError as exc:
        assert "future-dated" in str(exc)
    else:
        raise AssertionError("future evidence was accepted")


def test_output_is_deterministic_across_candidate_order():
    wu = work_unit(risk="medium")
    candidates = [
        candidate("a", "family-a"),
        candidate("b", "family-b"),
        candidate("c", "family-c"),
    ]
    first = build(wu, candidates)
    second = build(wu, list(reversed(candidates)))
    assert first == second


def test_baseline_is_named_even_when_not_in_observation_pool():
    wu = work_unit()
    result = build(
        wu,
        [candidate("v1", "family-a")],
        plan=evaluator_plan(wu, verifier_id="canonical-existing-verifier"),
    )
    baseline_id = result["recommendation"]["baseline_choice_id"]
    assert baseline_id.startswith("baseline:evaluator-plan:")
    baseline = next(
        choice
        for choice in result["eligible_choices"]
        if choice["id"] == baseline_id
    )
    assert "baseline-verifier-not-present-in-observation-pool" in baseline["reasons"]
