"""In-process enterprise conformance harness for E9 (#676).

The harness runs destructive failure-mode scenarios against the *real* E2/E3/E4
primitives (tenant scope, authorization kernel, audit ledger, run-idempotency
store, secret boundary) using temporary directories and in-process fakes only.
It contacts no provider, GitHub, network service, or real secret store.

Each scenario states the safe state it expects, runs the attack or fault, and
records what it observed. The result is PASS / WARN / FAIL / UNKNOWN:

* PASS    every check held and no known gap applies;
* WARN    every executed check held, but a named gap means the scenario does not
          yet cover the whole failure mode;
* FAIL    at least one expected safe state did not hold (or the scenario raised);
* UNKNOWN the harness has no scenario for it yet. This is never a pass.

A passing report demonstrates behaviour of the IDKMesh baseline primitives. It
is readiness evidence and is **not** a SOC 2, ISO 27001, FedRAMP, or any other
certification claim, and it does not prove a deployed service enforces these
primitives.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
import json
import io
from pathlib import Path
import sqlite3
import tempfile
from typing import Any, Callable

from idkmesh.connector_profiles import parse_connector_profile_document
from idkmesh.connector_secrets import (
    SecretReferenceError,
    materialize_config_secret,
    mint_secret_access_grant,
)
from idkmesh.connector_store import LocalMetadataStore, LocalStoreConflict
from idkmesh.connector_errors import connector_error
from idkmesh.enterprise_authz_cache import AuthorizationDecisionCache
from idkmesh.enterprise_data_policy import (
    DataPolicyDecision, decide_credential, decide_egress, decide_external_processing,
)
from idkmesh.github_public_evidence import (
    GitHubPublicEvidenceError, GitHubPublicEvidencePolicy,
    build_github_public_evidence_projection, render_github_public_evidence_json,
)
from idkmesh.local_ui_security import is_loopback_host, token_matches
from idkmesh.product_spine import ProductSpineRun
from idkmesh.task_claims import ClaimBinding, LocalTaskClaims, TaskClaimError, TaskClaimPolicy
from idkmesh.enterprise_audit import (
    AuditEventInput,
    EnterpriseAuditError,
    JsonLinesAuditSink,
    LocalEnterpriseAuditLedger,
)
from idkmesh.enterprise_authz import (
    ActorContext,
    AuthorizationDecision,
    AuthorizationPolicy,
    AuthorizationRequest,
    authorize,
)
from idkmesh.tenant_scope import (
    ScopedMemoryStore,
    ScopedResourceRef,
    TenantIsolationError,
    TenantScope,
    scoped_idempotency_key,
)

REPORT_KIND = "idkmesh-enterprise-conformance-report"
REPORT_VERSION = "0.1"
STATUSES = ("PASS", "WARN", "FAIL", "UNKNOWN")
DISCLAIMER = (
    "Readiness evidence for the IDKMesh baseline primitives only. This is not "
    "a SOC 2, ISO 27001, FedRAMP, or other certification claim, and it does "
    "not prove that any deployed service enforces these primitives."
)

# Fixed clock and revisions keep every run deterministic.
_NOW = 1_791_406_800
_REVISION = "a" * 40
_DIGEST_A = "sha256:" + "a" * 64
_DIGEST_B = "sha256:" + "b" * 64
_SECRET = "conformance-secret-value-do-not-leak"


@dataclass(frozen=True)
class Scenario:
    scenario_id: str
    title: str
    expected_safe_state: str
    evidence: tuple[str, ...]
    run: Callable[["_Context"], None] | None = None
    unknown_reason: str | None = None


@dataclass
class _Context:
    """Per-scenario recorder plus an isolated temp directory."""

    workdir: Path
    checks: list[dict[str, Any]] = field(default_factory=list)
    gaps: list[str] = field(default_factory=list)

    def expect(self, name: str, condition: bool) -> None:
        self.checks.append({"name": name, "ok": bool(condition)})

    def gap(self, text: str) -> None:
        self.gaps.append(text)


# --------------------------------------------------------------------------
# shared fixtures
# --------------------------------------------------------------------------

_SCOPE_A = TenantScope("tenant-a", "project-main")
_SCOPE_B = TenantScope("tenant-b", "project-main")


def _actor(
    principal: str,
    *,
    roles: tuple[str, ...],
    actor_type: str = "human",
    scopes: tuple[TenantScope, ...] = (_SCOPE_A,),
    revision: str = "identity:1",
    authenticated: bool = True,
    revoked: bool = False,
    expires_at_epoch: int | None = None,
) -> ActorContext:
    return ActorContext(
        principal_id=principal,
        actor_type=actor_type,
        issuer="idkmesh.conformance",
        roles=frozenset(roles),
        scopes=scopes,
        data_clearance="restricted",
        identity_revision=revision,
        authenticated=authenticated,
        revoked=revoked,
        expires_at_epoch=expires_at_epoch,
    )


def _request(
    request_id: str,
    actor: ActorContext,
    action: str,
    *,
    scope: TenantScope = _SCOPE_A,
    resource: ScopedResourceRef | None = None,
    risk: str = "low",
    approver: ActorContext | None = None,
    at: int = _NOW,
) -> AuthorizationRequest:
    return AuthorizationRequest(
        request_id=request_id,
        scope=scope,
        resource=resource or ScopedResourceRef(scope, "candidate", "candidate-17"),
        actor=actor,
        action=action,
        risk=risk,
        data_classification="internal",
        evaluated_at_epoch=at,
        approver=approver,
        approval_reference=None if approver is None else "approval:conformance",
    )


_POLICY = AuthorizationPolicy.enterprise_baseline()
_SERVICE = _actor(
    "service:audit-writer",
    roles=(),
    actor_type="service",
    revision="identity:service:1",
)


def _audit_input(
    actor: ActorContext,
    decision: AuthorizationDecision,
    outcome: str,
) -> AuditEventInput:
    return AuditEventInput(
        occurred_at_epoch=_NOW + 1,
        actor=actor,
        service=_SERVICE,
        decision=decision,
        resource_revision=_REVISION,
        outcome=outcome,
        run_id="run-conformance",
        evidence_digest=_DIGEST_A,
    )


def _seed_ledger(path: Path, count: int) -> LocalEnterpriseAuditLedger:
    ledger = LocalEnterpriseAuditLedger(path)
    worker = _actor("github:user:alice", roles=("worker",))
    for index in range(count):
        decision = authorize(
            _request(f"req-seed-{index}", worker, "claim"), _POLICY
        )
        ledger.append(_audit_input(worker, decision, "succeeded"))
    return ledger


# --------------------------------------------------------------------------
# scenarios
# --------------------------------------------------------------------------


def _unauthorized_actor(ctx: _Context) -> None:
    outsider = _actor("github:user:mallory", roles=("owner",), scopes=(_SCOPE_B,))
    reviewer = _actor("github:user:rita", roles=("reviewer",))
    anonymous = _actor("github:user:anon", roles=("owner",), authenticated=False)

    cases = (
        ("outsider_scope", outsider, "dispatch", "actor_scope_denied"),
        ("wrong_role", reviewer, "dispatch", "role_denied"),
        ("unauthenticated", anonymous, "dispatch", "actor_unauthenticated"),
    )
    denied: list[AuthorizationDecision] = []
    for label, actor, action, code in cases:
        decision = authorize(_request(f"req-{label}", actor, action), _POLICY)
        ctx.expect(f"{label}: denied with {code}", decision.effect == "deny" and decision.code == code)
        ctx.expect(
            f"{label}: decision grants no execute/write/merge authority",
            decision.to_dict()["authority"]
            == {"executes_action": False, "canonical_state_write": False, "merge": False},
        )
        denied.append(decision)

    path = ctx.workdir / "audit.sqlite3"
    with LocalEnterpriseAuditLedger(path) as ledger:
        event = ledger.append(_audit_input(outsider, denied[0], "denied"))
        ctx.expect("denied attempt is retained in the audit ledger", event["outcome"] == "denied")
        ctx.expect("ledger still verifies after the denial", ledger.verify().ok)
        try:
            ledger.append(_audit_input(outsider, denied[0], "succeeded"))
        except EnterpriseAuditError as exc:
            ctx.expect("a denied decision cannot be recorded as executed", exc.code == "outcome_decision_mismatch")
        else:
            ctx.expect("a denied decision cannot be recorded as executed", False)


def _cross_tenant_reference(ctx: _Context) -> None:
    store = ScopedMemoryStore()
    ref_a = store.put(_SCOPE_A, "candidate", "candidate-17", {"owner": "tenant-a"})

    try:
        store.get_ref(_SCOPE_B, ref_a)
    except TenantIsolationError as exc:
        ctx.expect("foreign scope cannot dereference tenant-a reference", exc.code == "scope_mismatch")
    else:
        ctx.expect("foreign scope cannot dereference tenant-a reference", False)

    try:
        store.delete_ref(_SCOPE_B, ref_a)
    except TenantIsolationError:
        ctx.expect("foreign scope cannot delete tenant-a reference", True)
    else:
        ctx.expect("foreign scope cannot delete tenant-a reference", False)
    ctx.expect(
        "tenant-a value survives the delete attempt",
        store.get_ref(_SCOPE_A, ref_a) == {"owner": "tenant-a"},
    )

    ctx.expect(
        "same type/id under tenant-b resolves to nothing",
        store.get(_SCOPE_B, "candidate", "candidate-17") is None,
    )
    ctx.expect("tenant-b keyspace is empty", store.keys_for_scope(_SCOPE_B) == ())

    for hostile in ("candidate-17/../../tenant-a", "../tenant-a", "a b"):
        try:
            TenantScope(hostile, "project-main")
        except TenantIsolationError:
            ctx.expect(f"path-like tenant id rejected: {hostile!r}", True)
        else:
            ctx.expect(f"path-like tenant id rejected: {hostile!r}", False)

    admin_b = _actor("github:user:bob", roles=("owner",), scopes=(_SCOPE_B,))
    substituted = authorize(
        _request("req-substitute", admin_b, "read", scope=_SCOPE_B, resource=ref_a),
        _POLICY,
    )
    ctx.expect(
        "authorization denies a tenant-a resource presented under tenant-b",
        substituted.effect == "deny" and substituted.code == "scope_mismatch",
    )

    key_a = scoped_idempotency_key(_SCOPE_A, operation="dispatch", logical_key="k1", payload_digest=_DIGEST_A)
    key_b = scoped_idempotency_key(_SCOPE_B, operation="dispatch", logical_key="k1", payload_digest=_DIGEST_A)
    ctx.expect("identical logical key yields different keys per tenant", key_a != key_b)


def _duplicate_event(ctx: _Context) -> None:
    store = LocalMetadataStore(ctx.workdir / "runs.sqlite3")
    args = dict(
        run_id="run-dup-1",
        idempotency_key="github-webhook:org/repo:delivery-1",
        request_digest=_DIGEST_A,
        state="proposed",
        metadata={"kind": "conformance"},
        created_at="2026-10-12T00:00:00Z",
    )
    first, created = store.admit_run(**args)
    replay, replay_created = LocalMetadataStore(ctx.workdir / "runs.sqlite3").admit_run(**args)
    ctx.expect("first delivery creates the run", created is True)
    ctx.expect("replayed delivery is not created again", replay_created is False)
    ctx.expect("replay returns the original run", replay.run_id == first.run_id)
    ctx.expect("exactly one run exists after the replay", len(store.list_runs(limit=10)[0]) == 1)

    conflict = dict(args, request_digest=_DIGEST_B, run_id="run-dup-2")
    try:
        store.admit_run(**conflict)
    except LocalStoreConflict:
        ctx.expect("same key with different content fails closed", True)
    else:
        ctx.expect("same key with different content fails closed", False)
    ctx.expect("conflicting replay did not add a run", len(store.list_runs(limit=10)[0]) == 1)


def _coordinator_crash_after_dispatch(ctx: _Context) -> None:
    path = ctx.workdir / "runs.sqlite3"
    args = dict(
        run_id="run-crash-1",
        idempotency_key="dispatch:candidate-17",
        request_digest=_DIGEST_A,
        state="proposed",
        metadata={"kind": "conformance"},
        created_at="2026-10-12T00:00:00Z",
    )
    before = LocalMetadataStore(path)
    first, created = before.admit_run(**args)
    del before  # simulate the coordinator process dying; only the file survives

    after = LocalMetadataStore(path)
    retry, retry_created = after.admit_run(**args)
    ctx.expect("admission survives a coordinator restart", first.run_id == retry.run_id)
    ctx.expect("the post-restart retry does not create a second run", created and not retry_created)
    ctx.gap(
        "no provider-side dispatch record or lease/fencing primitive exists "
        "in-process, so reconciliation of an already-accepted external "
        "dispatch (#675/#673) is not exercised"
    )


def _secret_missing_or_revoked(ctx: _Context) -> None:
    config = parse_connector_profile_document(
        {
            "api_version": "idkmesh.io/v1alpha1",
            "id": "secret-target",
            "kind": "agent",
            "driver": "fake",
            "enabled": True,
            "auth": {"secret_ref": "env:PROVIDER_KEY"},
        }
    )[0]
    grant = mint_secret_access_grant(config, admitted=True, admission_id="admission-1")

    live = {"PROVIDER_KEY": _SECRET}
    value = materialize_config_secret(config, grant, environ=live)
    ctx.expect(
        "secret wrapper never renders its value",
        _SECRET not in repr(value) and _SECRET not in str(value),
    )

    for label, environ in (("missing", {}), ("revoked_empty", {"PROVIDER_KEY": ""})):
        try:
            materialize_config_secret(config, grant, environ=environ)
        except SecretReferenceError as exc:
            ctx.expect(f"{label}: fails closed with missing_secret", exc.code == "missing_secret")
            ctx.expect(f"{label}: error text carries no secret value", _SECRET not in str(exc))
        else:
            ctx.expect(f"{label}: fails closed with missing_secret", False)

    try:
        mint_secret_access_grant(config, admitted=False, admission_id="admission-2")
    except SecretReferenceError as exc:
        ctx.expect("no grant is minted without admission", exc.code == "secret_access_not_admitted")
    else:
        ctx.expect("no grant is minted without admission", False)
    ctx.gap(
        "only the environment-variable secret scheme exists; rotation and "
        "revocation of a secret already held by an in-flight run are not modelled"
    )


class _FailingSink:
    """Sink that accepts one event and then becomes unavailable."""

    def __init__(self) -> None:
        self.accepted = 0

    def write_event(self, event: Any) -> None:
        if self.accepted >= 1:
            raise OSError("audit exporter unavailable")
        self.accepted += 1


def _audit_exporter_unavailable(ctx: _Context) -> None:
    with _seed_ledger(ctx.workdir / "audit.sqlite3", 3) as ledger:
        before = ledger.checkpoint()
        sink = _FailingSink()
        try:
            ledger.export_to_sink(sink, tenant_id=_SCOPE_A.tenant_id)
        except OSError:
            ctx.expect("exporter outage surfaces instead of being swallowed", True)
        else:
            ctx.expect("exporter outage surfaces instead of being swallowed", False)

        ctx.expect("ledger is unchanged by the outage", ledger.checkpoint() == before)
        ctx.expect("ledger still verifies after the outage", ledger.verify().ok)

        stream = io.StringIO()
        receipt = ledger.export_to_sink(
            JsonLinesAuditSink(stream), tenant_id=_SCOPE_A.tenant_id
        )
        ctx.expect("a retry exports every retained event", receipt.exported_count == 3)
        ctx.expect(
            "retry receipt ends at the ledger head",
            receipt.last_digest == before.head_digest,
        )
    ctx.gap(
        "export is at-least-once: the partially delivered prefix is re-sent "
        "on retry, and no durable per-sink cursor exists to resume from"
    )


def _ledger_restore(ctx: _Context) -> None:
    source_path = ctx.workdir / "audit.sqlite3"
    with _seed_ledger(source_path, 3) as ledger:
        checkpoint = ledger.checkpoint()

    def copy(name: str) -> Path:
        target = ctx.workdir / name
        src = sqlite3.connect(source_path)
        dst = sqlite3.connect(target)
        try:
            src.backup(dst)
        finally:
            dst.close()
            src.close()
        return target

    restored = copy("restored.sqlite3")
    with LocalEnterpriseAuditLedger(restored) as ledger:
        ctx.expect(
            "restored ledger verifies against the pre-backup checkpoint",
            ledger.verify(expected_checkpoint=checkpoint).ok,
        )

    edited = copy("edited.sqlite3")
    conn = sqlite3.connect(edited)
    try:
        try:
            conn.execute("UPDATE enterprise_audit_events SET event_json = '{}' WHERE sequence = 2")
        except sqlite3.DatabaseError:
            ctx.expect("append-only trigger blocks an in-place edit", True)
        else:
            ctx.expect("append-only trigger blocks an in-place edit", False)
        conn.execute("DROP TRIGGER enterprise_audit_no_update")
        conn.execute(
            "UPDATE enterprise_audit_events SET event_json = replace(event_json, 'alice', 'carol') "
            "WHERE sequence = 2"
        )
        conn.commit()
    finally:
        conn.close()
    with LocalEnterpriseAuditLedger(edited) as ledger:
        ctx.expect("a restored copy with an edited event is detected", not ledger.verify().ok)

    truncated = copy("truncated.sqlite3")
    conn = sqlite3.connect(truncated)
    try:
        conn.execute("DROP TRIGGER enterprise_audit_no_delete")
        conn.execute("DELETE FROM enterprise_audit_events WHERE sequence = 3")
        conn.commit()
    finally:
        conn.close()
    with LocalEnterpriseAuditLedger(truncated) as ledger:
        ctx.expect(
            "a restore that silently drops the newest event is detected by checkpoint",
            not ledger.verify(expected_checkpoint=checkpoint).ok,
        )
    # A second, separate SQLite durability port must also survive restart.
    local_path = ctx.workdir / "local-runs.sqlite3"
    local = LocalMetadataStore(local_path)
    args = dict(
        run_id="run-restored-17", idempotency_key="restore:example-17",
        request_digest=_DIGEST_A, state="proposed",
        metadata={"kind": "conformance"}, created_at="2026-10-12T00:00:00Z",
    )
    initial, initial_created = local.admit_run(**args)
    backup_path = local.backup_to(ctx.workdir / "local-runs-backup.sqlite3")
    restored_local = LocalMetadataStore(backup_path)
    copy_run = restored_local.get_run("run-restored-17")
    ctx.expect(
        "online backup retains the exact local run and digest",
        initial_created and copy_run is not None
        and copy_run.request_digest == initial.request_digest,
    )
    replay, replay_created = restored_local.admit_run(**args)
    ctx.expect(
        "restored local store cannot re-admit the same work",
        not replay_created and replay.run_id == initial.run_id,
    )
    ctx.gap(
        "the audit checkpoint must be retained outside the restored database; "
        "no network storage adapter, encrypted-backup owner or measured RPO/RTO "
        "drill exists (#673/#750)"
    )



# An immutable, credential-free policy fixture derived from the committed G2
# example. Keep this embedded: conformance must run from the installed wheel
# where repository examples/ are not installed.
_G2_DATA_PROFILE = json.loads("{\"kind\":\"idkmesh-enterprise-control-profile\",\"schema_version\":\"0.1\",\"profile_id\":\"example-g2-self-hosted\",\"semantics\":{\"profile_role\":\"policy_input_only\",\"control_evidence\":\"declared_not_observed\",\"grants_runtime_authority\":false},\"deployment\":{\"profile\":\"g2_self_hosted_team\",\"tenant_scope\":\"single_org\",\"remote_api_enabled\":true,\"coordinator_lifecycle\":\"long_lived_service\",\"canonical_code_authority\":\"github_protected_integration\"},\"identity\":{\"human_source\":\"oidc\",\"service_source\":\"oidc\",\"high_risk_distinct_approval\":true,\"break_glass_enabled\":true},\"authority\":{\"worker_can_merge\":false,\"verifier_can_merge\":false,\"worker_can_modify_policy\":false,\"integration_authority\":\"github_protected_integration\"},\"data\":{\"default_classification\":\"internal\",\"allowed_classifications\":[\"public\",\"internal\",\"confidential\",\"restricted\"],\"external_processing\":{\"public\":true,\"internal\":false,\"confidential\":false,\"restricted\":false},\"egress_default\":\"deny\"},\"secrets\":{\"backend\":\"oidc_workload_identity\",\"long_lived_cloud_keys_allowed\":false,\"raw_secret_material_in_work_units\":false,\"raw_secret_material_in_evidence\":false},\"audit\":{\"enabled\":true,\"tamper_evident_required\":true,\"retention_days\":730,\"export\":\"siem\"},\"reliability\":{\"availability_target\":0.995,\"rpo_minutes\":15,\"rto_minutes\":60,\"backups_required\":true,\"restore_test_required\":true},\"supply_chain\":{\"immutable_action_pins_required\":true,\"sbom_required\":true,\"provenance_required\":true,\"vulnerability_response_sla_hours\":24},\"change_management\":{\"protected_integration_required\":true,\"policy_change_approval_required\":true,\"break_glass_reason_required\":true},\"enforcement\":{\"mode\":\"enforce\",\"unknown_control_behavior\":\"fail\",\"startup_profile_validation\":true}}")


def _stale_claim_retry(ctx: _Context) -> None:
    clock = [_NOW]
    path = ctx.workdir / "claims.sqlite3"
    task = ScopedResourceRef(_SCOPE_A, "task", "claim-1")
    dispatcher = _actor("github:user:dispatcher", roles=("dispatcher",))
    owner = _actor("github:user:alice", roles=("worker",))
    replacement_owner = _actor("github:user:bob", roles=("worker",))
    policy = TaskClaimPolicy(
        max_attempts=2, ack_seconds=5, lease_seconds=15,
        progress_seconds=30, hard_seconds=60,
    )
    binding = ClaimBinding(_DIGEST_A, _REVISION, _DIGEST_B)
    claims = LocalTaskClaims(
        LocalMetadataStore(path), _POLICY, clock=lambda: clock[0]
    )
    ctx.expect(
        "trusted dispatcher configures the bounded task",
        claims.configure_task(task, dispatcher, policy) is True,
    )
    first, created = claims.claim(
        task, owner, request_id="first-claim", binding=binding
    )
    ctx.expect("one initial epoch is admitted", created and first.epoch == 1)
    clock[0] += policy.ack_seconds

    # A restarted process reads the durable clock and epoch; it cannot
    # interpret expiry as fresh execution authority.
    recovered = LocalTaskClaims(
        LocalMetadataStore(path), _POLICY, clock=lambda: clock[0]
    )
    states = recovered.snapshot(task, dispatcher)
    ctx.expect("expired claim is retained after restart", len(states) == 1 and states[0].state == "expired")
    replay, replay_created = recovered.claim(
        task, owner, request_id="first-claim", binding=binding
    )
    ctx.expect(
        "replayed request neither renews nor creates an attempt",
        not replay_created and replay.epoch == first.epoch and replay.state == "expired",
    )
    try:
        recovered.update_owner(
            task, owner, request_id=first.request_id,
            epoch=first.epoch, operation="release",
        )
    except TaskClaimError as exc:
        ctx.expect("expired owner is fenced from state changes", exc.code == "stale_claim")
    else:
        ctx.expect("expired owner is fenced from state changes", False)

    successor, successor_created = recovered.claim(
        task, replacement_owner, request_id="second-claim", binding=binding
    )
    ctx.expect(
        "a distinct owner receives a higher epoch, not the old grant",
        successor_created and successor.epoch == first.epoch + 1,
    )
    ctx.gap(
        "only local SQLite claim fencing is observed; real provider-side "
        "cancellation, tenant-wide leases and execution admission are not exercised"
    )


def _provider_outage_quota(ctx: _Context) -> None:
    expected = (
        ("rate_limited", True),
        ("quota_exhausted", False),
        ("provider_unavailable", True),
        ("authentication_error", False),
    )
    for code, retryable in expected:
        error = connector_error(
            code, "synthetic connector failure",
            details={"Authorization": "Bearer " + _SECRET, "retry_after_seconds": 10},
        )
        envelope = error.to_envelope()["error"]
        ctx.expect(
            f"{code}: normalized without false success",
            envelope["code"] == code and error.is_retryable is retryable,
        )
        ctx.expect(
            f"{code}: metadata redacts Authorization and exception omits details",
            envelope["details"]["Authorization"] == "[REDACTED]"
            and _SECRET not in str(error)
            and _SECRET not in json.dumps(envelope),
        )
    ctx.gap(
        "the real provider adapter, retry scheduler, cancellation and "
        "attempt ledger are not exercised; retryable does not mean an "
        "unbounded automatic retry is authorized"
    )


def _external_data_and_egress(ctx: _Context) -> None:
    profile = _G2_DATA_PROFILE
    approved = ("example-provider",)
    restricted = decide_external_processing(
        profile, data_class="restricted", provider_id="example-provider",
        approved_provider_ids=approved,
    )
    ctx.expect(
        "restricted data cannot leave even for an approved provider",
        not restricted.allowed and restricted.code == "external_processing_forbidden",
    )
    public = decide_external_processing(
        profile, data_class="public", provider_id="example-provider",
        approved_provider_ids=approved,
    )
    ctx.expect("public processing still requires a listed provider", public.allowed)
    unapproved = decide_external_processing(
        profile, data_class="public", provider_id="unknown-provider",
        approved_provider_ids=approved,
    )
    ctx.expect("a non-allowlisted provider is refused", not unapproved.allowed)
    for destination in ("evil.example", "trusted.example.evil", "trusted.example:443"):
        decision = decide_egress(
            profile, destination_host=destination, allowlist=("trusted.example",)
        )
        ctx.expect(f"egress is denied for {destination}", not decision.allowed)
    trusted = decide_egress(
        profile, destination_host="trusted.example", allowlist=("trusted.example",)
    )
    ctx.expect("the exact allowlisted hostname is permitted", trusted.allowed)
    ctx.expect(
        "long-lived cloud keys remain blocked under workload identity",
        not decide_credential(profile, credential_kind="long_lived_cloud_key").allowed,
    )
    for decision in (restricted, public, unapproved, trusted):
        ctx.expect(
            "policy decisions grant no execution or merge authority",
            not decision.to_dict()["authority"]["executes_action"]
            and not decision.to_dict()["authority"]["merge"],
        )
    ctx.gap(
        "pure policy decisions are not live worker network isolation, DLP, "
        "secret brokerage or provider dispatch enforcement"
    )


def _local_http_boundary(ctx: _Context) -> None:
    ctx.expect("loopback Host is accepted", is_loopback_host("127.0.0.1:8770"))
    ctx.expect("local hostname is accepted", is_loopback_host("localhost:8770"))
    for host in (
        "example.org", "localhost.example.org", "127.0.0.1@evil.example",
        "localhost:65536", "127.0.0.1,evil.example", "[::1]",
    ):
        ctx.expect(f"non-local or malformed Host {host!r} is rejected", not is_loopback_host(host))
    token = "local-session-test-only-token"
    ctx.expect("matching local session token works", token_matches(token, token))
    ctx.expect("missing token is denied", not token_matches(None, token))
    ctx.expect("modified token is denied", not token_matches(token + "x", token))
    ctx.expect(
        "non-ASCII header bytes cannot bypass token check",
        not token_matches("séssion", token),
    )
    ctx.gap(
        "loopback session tokens are NOT enterprise authentication; "
        "TLS, reverse-proxy trust, tenant-scoped remote API and browser "
        "mutation CSRF controls are not exercised"
    )


def _public_evidence_and_authority(ctx: _Context) -> None:
    run = ProductSpineRun(
        run_id="run-public-17",
        request_digest=_DIGEST_A,
        project_id="MSKazemi/idkmesh",
        work_unit_id="work-public-17",
        work_unit_version=2,
        work_unit_digest=_DIGEST_B,
        source_revision=_REVISION,
        authority_mode="human_required",
        routing_policy_version="conformance:1",
    )
    policy = GitHubPublicEvidencePolicy("MSKazemi/idkmesh", "public", True)
    projection = build_github_public_evidence_projection(run, policy=policy)
    rendered = render_github_public_evidence_json(projection)
    ctx.expect(
        "public projection retains exact source/digest binding",
        projection["run"]["source_revision"] == _REVISION
        and projection["run"]["work_unit_digest"] == _DIGEST_B,
    )
    ctx.expect(
        "publishing does not turn a proposed run into human approval",
        projection["human_decision_status"] == "not_recorded"
        and all(value is False for value in projection["authority"].values()),
    )
    ctx.expect("projection never includes a raw credential", _SECRET not in rendered)
    injected = dict(projection, provider_log=_SECRET)
    try:
        render_github_public_evidence_json(injected)
    except GitHubPublicEvidenceError:
        ctx.expect("unlisted provider fields fail the strict publication whitelist", True)
    else:
        ctx.expect("unlisted provider fields fail the strict publication whitelist", False)
    elevated = dict(projection, authority=dict(projection["authority"], merge=True))
    try:
        render_github_public_evidence_json(elevated)
    except GitHubPublicEvidenceError:
        ctx.expect("an attempted merge-authority flag is rejected", True)
    else:
        ctx.expect("an attempted merge-authority flag is rejected", False)
    for classification in ("internal", "confidential", "restricted"):
        try:
            build_github_public_evidence_projection(
                run,
                policy=GitHubPublicEvidencePolicy("MSKazemi/idkmesh", classification, True),
            )
        except GitHubPublicEvidenceError:
            ctx.expect(f"{classification} run cannot be publicly projected", True)
        else:
            ctx.expect(f"{classification} run cannot be publicly projected", False)
    ctx.gap(
        "this is a synthetic Product Spine projection; live GitHub Pages "
        "publication, an actual Human Decision Record and protected merge are not run"
    )


def _stale_identity_policy_cache(ctx: _Context) -> None:
    alice = _actor("github:user:alice", roles=("worker",))
    cache = AuthorizationDecisionCache(max_age_seconds=30, max_entries=8)
    first = cache.authorize(_request("req-cached", alice, "claim"), _POLICY)
    ctx.expect("live identity is allowed before revocation", first.effect == "allow")
    hit = cache.authorize(
        _request("req-cached-hit", alice, "claim", at=_NOW + 1), _POLICY
    )
    ctx.expect(
        "the valid cached decision is re-stamped but not an execution grant",
        cache.hits == 1 and hit.request_id == "req-cached-hit"
        and hit.to_dict()["authority"]["executes_action"] is False,
    )
    revoked = replace(alice, revoked=True)  # deliberately unchanged revision
    decision = cache.authorize(
        _request("req-revoked", revoked, "claim", at=_NOW + 2), _POLICY
    )
    ctx.expect(
        "same-revision revocation cannot reuse cached ALLOW",
        decision.effect == "deny" and decision.code == "actor_revoked"
        and cache.hits == 1,
    )
    after = authorize(
        _request("req-direct-revoked", revoked, "claim", at=_NOW + 2), _POLICY
    )
    ctx.expect("direct authorization agrees with cached revocation", after.code == "actor_revoked")
    expired = replace(alice, expires_at_epoch=_NOW + 3)
    cache.authorize(_request("req-expiry-prime", expired, "claim", at=_NOW + 2), _POLICY)
    expiry = cache.authorize(_request("req-expiry", expired, "claim", at=_NOW + 3), _POLICY)
    ctx.expect("expiry instant does not reuse a cached ALLOW", expiry.code == "actor_expired")
    ctx.expect("revocation feed can invalidate an active principal", cache.invalidate_principal(alice.principal_id) > 0)
    ctx.gap(
        "the cache is in-process only; no live API identity-revocation feed "
        "or policy-store integration is exercised"
    )


def _high_risk_sod_violation(ctx: _Context) -> None:
    dispatcher = _actor("github:user:dana", roles=("dispatcher",))

    def attempt(label: str, approver: ActorContext | None) -> AuthorizationDecision:
        return authorize(
            _request(f"req-sod-{label}", dispatcher, "dispatch", risk="high", approver=approver),
            _POLICY,
        )

    cases = (
        ("no_approver", None, "distinct_approval_required"),
        ("self_approval", dispatcher, "self_approval_forbidden"),
        ("wrong_role", _actor("github:user:wes", roles=("worker",)), "approver_role_denied"),
        (
            "service_approver",
            _actor("service:bot", roles=("admin",), actor_type="service"),
            "approver_type_denied",
        ),
        (
            "foreign_tenant",
            _actor("github:user:fay", roles=("admin",), scopes=(_SCOPE_B,)),
            "approver_scope_denied",
        ),
        (
            "revoked_approver",
            _actor("github:user:gus", roles=("admin",), revoked=True),
            "approver_revoked",
        ),
    )
    blocked: list[AuthorizationDecision] = []
    for label, approver, code in cases:
        decision = attempt(label, approver)
        ctx.expect(
            f"{label}: not allowed ({code})",
            decision.effect == "requires_approval" and decision.code == code,
        )
        blocked.append(decision)

    control = attempt("valid", _actor("github:user:hana", roles=("admin",)))
    ctx.expect(
        "positive control: a distinct authorised human approver is allowed",
        control.effect == "allow" and control.code == "authorized_with_distinct_approval",
    )

    try:
        _audit_input(dispatcher, blocked[1], "succeeded")
    except EnterpriseAuditError as exc:
        ctx.expect(
            "a blocked self-approval cannot be audited as executed",
            exc.code == "outcome_decision_mismatch",
        )
    else:
        ctx.expect("a blocked self-approval cannot be audited as executed", False)


_AUTHZ = ("idkmesh/enterprise_authz.py", "tests/test_enterprise_authz.py")
_TENANT = ("idkmesh/tenant_scope.py", "tests/test_tenant_scope.py")
_AUDIT = ("idkmesh/enterprise_audit.py", "tests/test_enterprise_audit.py")
_STORE = ("idkmesh/connector_store.py", "tests/test_connector_store.py")
_SECRETS = ("idkmesh/connector_secrets.py", "tests/test_connector_secrets.py")
_SELF = ("idkmesh/enterprise_conformance.py", "tests/test_enterprise_conformance.py")
_CLAIMS = ("idkmesh/task_claims.py", "tests/test_task_claims.py")
_CACHE = ("idkmesh/enterprise_authz_cache.py", "tests/test_enterprise_authz_cache.py")
_DATA = ("idkmesh/enterprise_data_policy.py", "tests/test_enterprise_data_policy.py")
_ERRORS = ("idkmesh/connector_errors.py", "tests/test_connector_errors.py")
_LOCAL_API = ("idkmesh/local_ui_security.py", "tests/test_api_security_matrix.py")
_PUBLIC = ("idkmesh/github_public_evidence.py", "tests/test_github_public_evidence.py")
_SPINE = ("idkmesh/product_spine.py", "tests/test_product_spine.py")


SCENARIOS: tuple[Scenario, ...] = (
    Scenario(
        "unauthorized_actor",
        "Unauthorized actor",
        "Out-of-scope, wrong-role and unauthenticated actors are denied, the "
        "denial is retained in the audit ledger, and no authority is granted.",
        _AUTHZ + _AUDIT + _SELF,
        _unauthorized_actor,
    ),
    Scenario(
        "cross_tenant_reference",
        "Cross-tenant reference substitution",
        "A reference minted under one tenant cannot be read, deleted or "
        "authorised under another, and hostile identifiers are rejected.",
        _TENANT + _AUTHZ + _SELF,
        _cross_tenant_reference,
    ),
    Scenario(
        "duplicate_event",
        "Duplicate or replayed event",
        "A replayed delivery returns the original run, and the same key with "
        "different content fails closed without creating a second run.",
        _STORE + _SELF,
        _duplicate_event,
    ),
    Scenario(
        "coordinator_crash_after_dispatch",
        "Coordinator crash after external dispatch",
        "After a restart a retry rejoins the admitted run instead of creating "
        "a second dispatch.",
        _STORE + _SELF,
        _coordinator_crash_after_dispatch,
    ),
    Scenario(
        "stale_claim_retry",
        "Stale claim or retry",
        "Expired claims and replayed request IDs cannot renew an owner grant; "
        "a new actor obtains a higher fencing epoch after restart.",
        _CLAIMS + _STORE + _SELF,
        _stale_claim_retry,
    ),
    Scenario(
        "provider_outage_quota",
        "Provider outage or quota failure",
        "Normalized provider errors carry the intended retryability and "
        "never copy credentials into diagnostic output.",
        _ERRORS + _SELF,
        _provider_outage_quota,
    ),
    Scenario(
        "secret_missing_or_revoked",
        "Secret missing or revoked",
        "A missing, emptied or unadmitted secret fails closed and no error or "
        "repr ever contains the secret value.",
        _SECRETS + _SELF,
        _secret_missing_or_revoked,
    ),
    Scenario(
        "external_data_and_egress",
        "Data classification and destination egress",
        "Restricted data does not leave the trust boundary; an allowlisted "
        "provider/host has no implied secret, execution or merge authority.",
        _DATA + _SELF,
        _external_data_and_egress,
    ),
    Scenario(
        "local_http_boundary",
        "Local-only HTTP security boundary",
        "Host validation and a process-local token refuse nonlocal/malformed "
        "requests; no network/multi-user authentication is inferred.",
        _LOCAL_API + _SELF,
        _local_http_boundary,
    ),
    Scenario(
        "public_evidence_authority",
        "Public evidence and Product Spine authority boundary",
        "Public output is strictly whitelisted; internal evidence and raw "
        "provider data cannot be published or converted to merge approval.",
        _PUBLIC + _SPINE + _SELF,
        _public_evidence_and_authority,
    ),
    Scenario(
        "audit_exporter_unavailable",
        "Audit exporter unavailable",
        "An exporter outage is surfaced, leaves the ledger intact and "
        "verifiable, and a retry delivers every retained event.",
        _AUDIT + _SELF,
        _audit_exporter_unavailable,
    ),
    Scenario(
        "ledger_restore",
        "Database or ledger restore",
        "A restored ledger verifies against the pre-backup checkpoint, and an "
        "edited or truncated restore is detected.",
        _AUDIT + _SELF,
        _ledger_restore,
    ),
    Scenario(
        "stale_identity_policy_cache",
        "Stale identity or policy cache",
        "A decision made before revocation is not reusable: re-evaluation "
        "denies, and every decision names the identity and policy revisions "
        "it was made under.",
        _AUTHZ + _SELF,
        _stale_identity_policy_cache,
    ),
    Scenario(
        "high_risk_sod_violation",
        "High-risk separation-of-duties violation",
        "A high-risk action is never allowed without a distinct, in-scope, "
        "authorised, unrevoked human approver.",
        _AUTHZ + _AUDIT + _SELF,
        _high_risk_sod_violation,
    ),
    Scenario(
        "release_provenance",
        "Release provenance verification",
        "A release artifact without verifiable provenance is not accepted.",
        (),
        unknown_reason=(
            "supply-chain provenance (E7, #674) has no verifier in this repo "
            "to exercise"
        ),
    ),
)


# --------------------------------------------------------------------------
# runner
# --------------------------------------------------------------------------


def _run_scenario(scenario: Scenario, base: Path) -> dict[str, Any]:
    result: dict[str, Any] = {
        "id": scenario.scenario_id,
        "title": scenario.title,
        "expected_safe_state": scenario.expected_safe_state,
        "evidence": list(scenario.evidence),
        "checks": [],
        "gaps": [],
    }
    if scenario.run is None:
        result["status"] = "UNKNOWN"
        result["observed"] = "not exercised: " + str(scenario.unknown_reason)
        return result

    workdir = base / scenario.scenario_id
    workdir.mkdir(parents=True, exist_ok=True)
    ctx = _Context(workdir=workdir)
    try:
        scenario.run(ctx)
    except Exception as exc:  # a crashing scenario is a failed safe state
        ctx.expect(f"scenario ran to completion (raised {type(exc).__name__})", False)

    failed = [c["name"] for c in ctx.checks if not c["ok"]]
    result["checks"] = ctx.checks
    result["gaps"] = list(ctx.gaps)
    if failed:
        result["status"] = "FAIL"
        result["observed"] = "expected safe state did not hold: " + "; ".join(failed)
    elif ctx.gaps:
        result["status"] = "WARN"
        result["observed"] = (
            f"{len(ctx.checks)} checks held; coverage gap: " + "; ".join(ctx.gaps)
        )
    else:
        result["status"] = "PASS"
        result["observed"] = f"all {len(ctx.checks)} checks held"
    return result


def overall_status(statuses: list[str]) -> str:
    for status in ("FAIL", "UNKNOWN", "WARN"):
        if status in statuses:
            return status
    return "PASS"


def run_conformance(
    *,
    scenario_ids: tuple[str, ...] | None = None,
    workdir: str | Path | None = None,
) -> dict[str, Any]:
    """Run the conformance scenarios and return a deterministic report."""

    selected = SCENARIOS
    if scenario_ids is not None:
        known = {s.scenario_id for s in SCENARIOS}
        unknown = sorted(set(scenario_ids) - known)
        if unknown:
            raise ValueError("unknown scenario id: " + ", ".join(unknown))
        selected = tuple(s for s in SCENARIOS if s.scenario_id in scenario_ids)

    def build(base: Path) -> list[dict[str, Any]]:
        return [_run_scenario(s, base) for s in selected]

    if workdir is None:
        with tempfile.TemporaryDirectory(prefix="idkmesh-conformance-") as tmp:
            results = build(Path(tmp))
    else:
        base = Path(workdir)
        base.mkdir(parents=True, exist_ok=True)
        results = build(base)

    statuses = [r["status"] for r in results]
    return {
        "kind": REPORT_KIND,
        "schema_version": REPORT_VERSION,
        "status": overall_status(statuses),
        "counts": {name: statuses.count(name) for name in STATUSES},
        "scenarios": results,
        "certification_claim": "none",
        "disclaimer": DISCLAIMER,
    }
