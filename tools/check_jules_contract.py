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
        len({manual_queue, automatic_queue, dispatch_label, attention_label}) == 4,
        "manual queue, automatic queue, dispatch, and attention labels must be distinct",
    )

    for label_name, role in (
        (manual_queue, "manual queue"),
        (automatic_queue, "automatic queue"),
        (dispatch_label, "dispatch status"),
        (attention_label, "attention"),
    ):
        _require(
            errors,
            label_name in definitions,
            f"{role} label {label_name!r} is missing from label_definitions",
        )

    _require(
        errors,
        attention_label in blocked,
        "attention label must be a hard dispatch veto",
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
    _require(
        errors,
        max_per_sweep <= effective_cap,
        "max_dispatch_per_sweep cannot exceed effective provider/repository capacity",
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
        "actions: write" not in router_workflow,
        "router no longer needs actions:write when using workflow_call",
    )
    _require(
        errors,
        'dispatch_policy["automatic_queue_label"]' in router_workflow,
        "router workflow must derive the automatic queue label from dispatch policy",
    )
    _require(
        errors,
        "python tools/check_jules_contract.py" in pr_gate,
        "required PR Gate must execute the Jules contract guard",
    )

    _require(
        errors,
        "inputs.issue_number" in dispatcher_workflow,
        "dispatcher must consume the typed issue_number input",
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

    if errors:
        print("Jules automation contract check failed:", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1

    print(
        "Jules automation contract OK: "
        f"manual={manual_queue}, automatic={automatic_queue}, "
        f"repo_cap={max_in_flight}, provider_cap={provider_max}, "
        f"effective_cap={effective_cap}, sweep_cap={max_per_sweep}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
