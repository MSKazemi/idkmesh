#!/usr/bin/env python3
"""Fail closed when the IDKMesh router/dispatcher Jules contract drifts.

This guard is intentionally stdlib-only so PR Gate can run it before installing
dependencies. The dispatcher policy is the execution-side source of truth; the
routing policy and GitHub workflow handoff must agree with it.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def _load_json(relative: str) -> dict[str, Any]:
    value = json.loads((ROOT / relative).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{relative} must contain a JSON object")
    return value


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def _indented_block(text: str, header: str) -> str:
    """Return the YAML block nested below an exact stripped header."""
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if line.strip() != header:
            continue
        base_indent = len(line) - len(line.lstrip())
        collected: list[str] = []
        for candidate in lines[index + 1 :]:
            if not candidate.strip():
                collected.append(candidate)
                continue
            indent = len(candidate) - len(candidate.lstrip())
            if indent <= base_indent:
                break
            collected.append(candidate)
        return "\n".join(collected)
    return ""


def _require(errors: list[str], condition: bool, message: str) -> None:
    if not condition:
        errors.append(message)


def main() -> int:
    errors: list[str] = []

    dispatch_policy = _load_json("config/jules-dispatch.json")
    routing_policy = _load_json("config/llm-routing-policy.json")
    dispatcher_workflow = _read(".github/workflows/jules-dispatch.yml")
    router_workflow = _read(".github/workflows/issue-model-router.yml")
    pr_gate = _read(".github/workflows/pr-gate.yml")
    router_code = _read("scripts/issue_model_router.py")
    dispatcher_code = _read("tools/jules_dispatcher.py")

    manual_queue = str(dispatch_policy.get("queue_label") or "")
    automatic_queue = str(dispatch_policy.get("automatic_queue_label") or "")
    dispatch_label = str(dispatch_policy.get("dispatch_label") or "")
    attention_label = str(dispatch_policy.get("attention_label") or "")
    completion_label = str(dispatch_policy.get("completion_label") or "")
    definitions = dispatch_policy.get("label_definitions") or {}
    blocked = {str(value) for value in dispatch_policy.get("blocked_labels") or []}
    trusted = {
        str(value).upper()
        for value in dispatch_policy.get("trusted_author_associations") or []
    }

    _require(errors, bool(manual_queue), "dispatch policy is missing queue_label")
    _require(
        errors,
        bool(automatic_queue),
        "dispatch policy is missing automatic_queue_label",
    )
    _require(errors, bool(dispatch_label), "dispatch policy is missing dispatch_label")
    _require(
        errors,
        bool(attention_label),
        "dispatch policy is missing attention_label",
    )
    _require(
        errors,
        bool(completion_label),
        "dispatch policy is missing completion_label",
    )
    _require(
        errors,
        len({
            manual_queue,
            automatic_queue,
            dispatch_label,
            attention_label,
            completion_label,
        }) == 5,
        "manual queue, automatic queue, dispatch, attention, and completion labels must be distinct",
    )

    for label_name, role in (
        (manual_queue, "manual queue"),
        (automatic_queue, "automatic queue"),
        (dispatch_label, "dispatch status"),
        (attention_label, "attention"),
        (completion_label, "completion"),
    ):
        _require(
            errors,
            label_name in definitions,
            f"{role} label {label_name!r} is missing from label_definitions",
        )

    for label_name, definition in definitions.items():
        _require(
            errors,
            isinstance(definition, dict),
            f"label definition {label_name!r} must be an object",
        )
        if isinstance(definition, dict):
            description = str(definition.get("description") or "")
            _require(
                errors,
                len(description) <= 100,
                f"label {label_name!r} description exceeds GitHub's 100-character limit",
            )

    _require(
        errors,
        attention_label in blocked,
        "attention label must be a hard dispatch veto",
    )
    _require(
        errors,
        completion_label in blocked,
        "completion label must be a hard dispatch veto",
    )
    _require(
        errors,
        {"OWNER", "MEMBER", "COLLABORATOR"}.issubset(trusted),
        "automatic Jules routing must remain restricted to trusted author associations",
    )

    max_in_flight = int(dispatch_policy.get("max_in_flight", 0))
    max_per_sweep = int(dispatch_policy.get("max_dispatch_per_sweep", 0))
    provider = dispatch_policy.get("provider_concurrency") or {}
    provider_max = (
        provider.get("max_concurrent_tasks")
        if isinstance(provider, dict)
        else None
    )
    provider_max_valid = (
        isinstance(provider_max, int)
        and not isinstance(provider_max, bool)
        and provider_max > 0
    )
    effective_cap = min(
        max_in_flight,
        provider_max if provider_max_valid else 0,
    )

    _require(errors, max_in_flight > 0, "max_in_flight must be positive")
    _require(errors, max_per_sweep > 0, "max_dispatch_per_sweep must be positive")
    _require(
        errors,
        provider_max_valid,
        "provider_concurrency.max_concurrent_tasks must be a positive integer",
    )
    _require(
        errors,
        isinstance(provider, dict)
        and str(provider.get("source") or "").startswith(
            "https://jules.google/docs/usage-limits"
        ),
        "provider concurrency must cite the official Jules limits page",
    )
    _require(
        errors,
        isinstance(provider, dict) and bool(str(provider.get("checked_at") or "").strip()),
        "provider concurrency must record checked_at",
    )
    terminal_states = (
        provider.get("terminal_session_states", [])
        if isinstance(provider, dict)
        else []
    )
    normalized_terminal = {
        str(value).upper()
        for value in terminal_states
        if str(value).strip()
    }
    _require(
        errors,
        isinstance(terminal_states, list)
        and {"COMPLETED", "FAILED"}.issubset(normalized_terminal),
        "provider terminal_session_states must include COMPLETED and FAILED",
    )
    _require(
        errors,
        isinstance(provider, dict)
        and str(provider.get("session_state_source") or "").startswith(
            "https://jules.google/docs/api/reference/"
        ),
        "provider terminal states must cite the official Jules API reference",
    )
    _require(
        errors,
        max_per_sweep <= effective_cap,
        "max_dispatch_per_sweep cannot exceed effective provider/repository capacity",
    )

    ci_backpressure = dispatch_policy.get("ci_backpressure") or {}
    _require(
        errors,
        isinstance(ci_backpressure, dict)
        and isinstance(ci_backpressure.get("enabled"), bool),
        "ci_backpressure.enabled must be a boolean",
    )
    for field in ("max_queued_runs", "max_in_progress_runs"):
        value = (
            ci_backpressure.get(field)
            if isinstance(ci_backpressure, dict)
            else None
        )
        _require(
            errors,
            isinstance(value, int) and not isinstance(value, bool) and value >= 0,
            f"ci_backpressure.{field} must be an integer >= 0",
        )
    _require(
        errors,
        isinstance(ci_backpressure, dict)
        and str(ci_backpressure.get("source") or "").startswith(
            "https://docs.github.com/en/rest/actions/workflow-runs"
        ),
        "CI backpressure must cite the official GitHub workflow-runs API",
    )
    _require(
        errors,
        isinstance(ci_backpressure, dict)
        and bool(str(ci_backpressure.get("checked_at") or "").strip()),
        "CI backpressure must record checked_at",
    )

    jules_routing = (
        routing_policy.get("provider_examples", {})
        .get("jules", {})
    )
    _require(
        errors,
        jules_routing.get("queue_label") == automatic_queue,
        "routing-policy Jules queue_label must equal dispatch automatic_queue_label",
    )
    _require(
        errors,
        jules_routing.get("execution_status_label") == dispatch_label,
        "routing-policy execution_status_label must equal dispatch_label",
    )
    _require(
        errors,
        jules_routing.get("attention_label") == attention_label,
        "routing-policy attention_label must equal dispatcher attention_label",
    )
    _require(
        errors,
        jules_routing.get("manual_fallback_label") in dispatch_policy.get(
            "legacy_dispatch_labels", []
        ),
        "routing-policy manual fallback must be a legacy dispatcher label",
    )

    workflow_call = _indented_block(dispatcher_workflow, "workflow_call:")
    workflow_dispatch = _indented_block(dispatcher_workflow, "workflow_dispatch:")
    workflow_run = _indented_block(dispatcher_workflow, "workflow_run:")
    router_push = _indented_block(router_workflow, "push:")
    for name, block in (
        ("workflow_call", workflow_call),
        ("workflow_dispatch", workflow_dispatch),
    ):
        _require(errors, bool(block), f"Jules workflow must declare {name}")
        _require(
            errors,
            "issue_number:" in block,
            f"{name} must declare issue_number",
        )
        _require(
            errors,
            "bootstrap_labels:" in block,
            f"{name} must declare bootstrap_labels",
        )
    _require(
        errors,
        "fill_capacity:" in workflow_call,
        "workflow_call must declare typed fill_capacity intent",
    )
    _require(
        errors,
        bool(workflow_run),
        "Jules workflow must declare workflow_run capacity recovery",
    )
    _require(
        errors,
        'workflows: ["PR Gate"]' in workflow_run,
        "Jules workflow_run recovery must be sourced only from PR Gate",
    )
    _require(
        errors,
        "types: [completed]" in workflow_run,
        "Jules workflow_run recovery must run only after completion",
    )

    _require(
        errors,
        "uses: ./.github/workflows/jules-dispatch.yml" in router_workflow,
        "router must call Jules through the local reusable workflow",
    )
    _require(
        errors,
        "issue_number: ${{ needs.route.outputs.routed_issue_number }}" in router_workflow,
        "router reusable-workflow call must pass routed_issue_number",
    )
    _require(
        errors,
        "secrets: inherit" in router_workflow,
        "router reusable-workflow call must inherit the Jules repository secret",
    )
    _require(
        errors,
        "gh workflow run jules-dispatch.yml" not in router_workflow,
        "router must not use a stringly-typed gh workflow run handoff",
    )
    _require(
        errors,
        "actions: read" in router_workflow,
        "router must pass Actions read permission to reusable Jules dispatch",
    )
    _require(
        errors,
        "actions: write" not in router_workflow,
        "router must never grant Actions write to Jules automation",
    )
    _require(
        errors,
        'dispatch_policy["automatic_queue_label"]' in router_workflow,
        "router workflow must derive the automatic queue label from dispatch policy",
    )
    _require(
        errors,
        "--dispatch-policy config/jules-dispatch.json" in router_workflow,
        "router classifier must consume the dispatcher policy for hard vetoes",
    )
    _require(
        errors,
        "python tools/check_jules_contract.py" in pr_gate,
        "required PR Gate must execute the Jules contract guard",
    )
    _require(
        errors,
        "python tools/check_jules_contract.py" in router_workflow,
        "production Issue Model Router must self-check the Jules contract",
    )
    _require(
        errors,
        "python tools/check_jules_contract.py" in dispatcher_workflow,
        "production Jules Dispatcher must self-check the Jules contract",
    )
    _require(
        errors,
        bool(router_push),
        "router must own the control-plane push recovery trigger",
    )
    for required_path in (
        ".github/workflows/issue-model-router.yml",
        ".github/workflows/jules-dispatch.yml",
        "config/jules-dispatch.json",
        "tools/jules_dispatcher.py",
        "tools/check_jules_contract.py",
    ):
        _require(
            errors,
            required_path in router_push,
            f"router control-plane push recovery must watch {required_path}",
        )
    _require(
        errors,
        "dispatch-after-control-plane-change:" in router_workflow,
        "router must retain immediate dispatch after control-plane changes",
    )
    _require(
        errors,
        "bootstrap_labels: true" in router_workflow,
        "control-plane recovery must bootstrap any newly introduced policy labels",
    )
    _require(
        errors,
        "fill_capacity: true" in router_workflow,
        "router recovery/backfill calls must explicitly request capacity fill",
    )
    _require(
        errors,
        "\n  push:\n" not in dispatcher_workflow,
        "dispatcher must not duplicate router-owned control-plane push recovery",
    )

    _require(
        errors,
        "inputs.issue_number" in dispatcher_workflow,
        "dispatcher must consume the typed issue_number input",
    )
    _require(
        errors,
        "inputs.fill_capacity" in dispatcher_workflow,
        "dispatcher must consume typed reusable capacity-fill intent",
    )
    _require(
        errors,
        automatic_queue in dispatcher_workflow,
        "dispatcher workflow must retain the automatic queue label event path",
    )
    _require(
        errors,
        manual_queue in dispatcher_workflow,
        "dispatcher workflow must retain the manual approval label event path",
    )
    _require(
        errors,
        "actions: read" in dispatcher_workflow,
        "dispatcher must have read-only Actions capacity visibility",
    )
    _require(
        errors,
        "github.event.workflow_run.conclusion == 'success'" in dispatcher_workflow,
        "PR Gate capacity recovery must be success-only",
    )
    _require(
        errors,
        "github.event_name == 'workflow_run'" in dispatcher_workflow
        and "--reconcile --dispatch" in dispatcher_workflow,
        "successful PR Gate completion must reuse Jules reconciliation/dispatch",
    )
    _require(
        errors,
        "actions: write" not in dispatcher_workflow,
        "dispatcher must not gain Actions write authority",
    )
    _require(
        errors,
        "pull-requests: write" not in dispatcher_workflow,
        "dispatcher must not gain pull-request write authority",
    )
    _require(
        errors,
        "pull_request_target:" not in dispatcher_workflow,
        "dispatcher must not run with pull_request_target privileges",
    )

    _require(
        errors,
        automatic_queue not in router_code,
        "router code must derive the Jules queue label from routing policy, not hard-code it",
    )
    _require(
        errors,
        "_jules_queue_label(policy)" in router_code,
        "router code must use the routing-policy Jules queue label",
    )
    _require(
        errors,
        "_jules_veto_hits" in router_code
        and 'dispatch_policy.get("blocked_labels")' in router_code,
        "router code must suppress Jules eligibility from dispatcher blocked_labels",
    )
    _require(
        errors,
        '"automationMode": "AUTO_CREATE_PR"' in dispatcher_code,
        "dispatcher must continue requesting Jules AUTO_CREATE_PR",
    )
    _require(
        errors,
        '"requirePlanApproval": False' in dispatcher_code,
        "dispatcher must keep unattended bounded tasks free of a provider plan gate",
    )
    _require(
        errors,
        "provider_active_session_count" in dispatcher_code,
        "dispatcher must account provider concurrency from session state",
    )
    _require(
        errors,
        "available_dispatch_capacity" in dispatcher_code,
        "dispatcher must compute independent repository/provider slot budgets",
    )
    _require(
        errors,
        "count_workflow_runs" in dispatcher_code,
        "dispatcher must read repository Actions backlog before new work",
    )
    _require(
        errors,
        "ci_backpressure_reason" in dispatcher_code,
        "dispatcher must enforce configured CI backpressure",
    )
    dispatch_block = dispatcher_code.split("def dispatch(", 1)[-1].split(
        "def build_parser(", 1
    )[0]
    backpressure_call = dispatch_block.find("ci_backpressure_reason(api, policy)")
    issue_snapshot = dispatch_block.find("issues = open_issues")
    _require(
        errors,
        "def dispatch(" in dispatcher_code
        and backpressure_call >= 0
        and issue_snapshot >= 0
        and backpressure_call < issue_snapshot,
        "dispatcher must check CI backpressure before selecting/reserving issues",
    )
    _require(
        errors,
        "repository review capacity full" in dispatcher_code,
        "dispatcher must report repository review capacity separately",
    )
    _require(
        errors,
        "non-terminal account sessions" in dispatcher_code,
        "dispatcher must report provider-active session capacity separately",
    )
    _require(
        errors,
        "effective_in_flight_limit(policy)" in dispatcher_code,
        "dispatcher must enforce the stricter repository/provider concurrency cap",
    )
    _require(
        errors,
        "is_provider_backpressure(exc)" in dispatcher_code,
        "dispatcher must explicitly handle rejected provider backpressure",
    )
    _require(
        errors,
        "FAILED_PRECONDITION" in dispatcher_code
        and "RESOURCE_EXHAUSTED" in dispatcher_code,
        "dispatcher must recognize Jules precondition/quota backpressure statuses",
    )
    _require(
        errors,
        "def get_session(" in dispatcher_code
        and "session_pull_request_urls" in dispatcher_code,
        "dispatcher must inspect full completed Jules Session outputs",
    )
    _require(
        errors,
        "get_pull_request_from_url" in dispatcher_code,
        "dispatcher must bind Jules pull-request outputs back to same-repository GitHub state",
    )
    _require(
        errors,
        'policy["completion_label"]' in dispatcher_code,
        "dispatcher must implement the terminal completion lifecycle from policy",
    )

    if errors:
        print("Jules automation contract check failed:", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1

    print(
        "Jules automation contract OK: "
        f"manual={manual_queue}, automatic={automatic_queue}, "
        f"completion={completion_label}, "
        f"repo_cap={max_in_flight}, provider_cap={provider_max}, "
        f"effective_cap={effective_cap}, sweep_cap={max_per_sweep}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
