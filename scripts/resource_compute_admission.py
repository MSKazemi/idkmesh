#!/usr/bin/env python3
"""Admit concrete zero-cost compute offers through the Free Resource Mesh.

The bridge is deliberately subtractive: it never invents CPU/GPU capacity and
never dispatches work. A concrete compute offer survives only when all of these
are true:

1. the offer is already present in a live Compute Offer Pool;
2. an enabled checked-in binding explicitly authorizes its provider/cost class;
3. the bound Free Resource Mesh entry is current, zero-cost, direct-compute,
   and carries no repository write/merge authority;
4. both external evidence and local binding review are current and not future-dated;
5. the bound resource still exposes the broad discovery capabilities required by
   the binding;
6. the concrete offer does not exceed the binding's separate runtime-capability
   allowlist.

Discovery/resource capability names and concrete runtime capability names are
intentionally separate vocabularies. The checked-in binding is the reviewed
materialization boundary between them; admission does not infer string equality
between the two layers.

The output is another Compute Offer Pool, suitable for the existing
``free_compute_router.py``. Correctness and execution authority remain outside
this bridge.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from typing import Any

REGISTRY_VERSION = 1
BINDINGS_VERSION = 1
DIRECT_COMPUTE_KINDS = {"compute", "volunteer_compute"}
ALLOWED_REGISTRY_STATUS = {"available", "conditional"}


class AdmissionError(RuntimeError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AdmissionError(message)


def _load(path: str | Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    _require(isinstance(value, dict), f"{path}: expected JSON object")
    return value


def _parse_date(raw: str) -> dt.date:
    try:
        return dt.date.fromisoformat(raw)
    except (TypeError, ValueError) as exc:
        raise AdmissionError(f"invalid ISO date: {raw!r}") from exc


def _fresh(checked_at: str, max_age_days: int, today: dt.date) -> tuple[bool, int]:
    _require(isinstance(max_age_days, int) and max_age_days > 0, "max_age_days must be positive")
    age = (today - _parse_date(checked_at)).days
    return 0 <= age <= max_age_days, age


def validate_registry(registry: dict[str, Any]) -> None:
    _require(registry.get("version") == REGISTRY_VERSION, "registry version must be 1")
    _parse_date(registry.get("observed_at"))
    offers = registry.get("offers")
    _require(isinstance(offers, list) and offers, "registry.offers must be a non-empty list")
    seen: set[str] = set()
    for offer in offers:
        _require(isinstance(offer, dict), "registry offer must be an object")
        resource_id = offer.get("id")
        _require(isinstance(resource_id, str) and resource_id, "registry offer id required")
        _require(resource_id not in seen, f"duplicate registry offer: {resource_id}")
        seen.add(resource_id)
        capabilities = offer.get("capabilities")
        _require(isinstance(capabilities, list), f"{resource_id}: capabilities must be a list")
        _require(
            all(isinstance(value, str) and value for value in capabilities),
            f"{resource_id}: invalid capability",
        )
        _require(len(capabilities) == len(set(capabilities)), f"{resource_id}: capabilities must be unique")
        _require(offer.get("project_cost_usd") == 0, f"{resource_id}: project cost must be zero")
        security = offer.get("security")
        _require(isinstance(security, dict), f"{resource_id}: security object required")
        _require(security.get("repo_write_authority") is False, f"{resource_id}: repo write authority forbidden")
        _require(security.get("merge_authority") is False, f"{resource_id}: merge authority forbidden")
        source = offer.get("source")
        _require(isinstance(source, dict), f"{resource_id}: source required")
        _require(isinstance(source.get("checked_at"), str), f"{resource_id}: source.checked_at required")
        _parse_date(source["checked_at"])
        _require(
            isinstance(source.get("max_age_days"), int) and source["max_age_days"] > 0,
            f"{resource_id}: source.max_age_days must be positive",
        )


def validate_pool(pool: dict[str, Any]) -> None:
    _require(pool.get("schema_version") == "0.1", "compute pool schema_version must be 0.1")
    offers = pool.get("offers")
    _require(isinstance(offers, list), "compute pool offers must be a list")
    seen: set[str] = set()
    for offer in offers:
        _require(isinstance(offer, dict), "compute offer must be an object")
        offer_id = offer.get("id")
        _require(isinstance(offer_id, str) and offer_id, "compute offer id required")
        _require(offer_id not in seen, f"duplicate compute offer: {offer_id}")
        seen.add(offer_id)
        _require(isinstance(offer.get("provider"), str) and offer["provider"], f"{offer_id}: provider required")
        capabilities = offer.get("capabilities")
        _require(isinstance(capabilities, list), f"{offer_id}: capabilities must be a list")
        _require(
            all(isinstance(value, str) and value for value in capabilities),
            f"{offer_id}: invalid capability",
        )
        _require(len(capabilities) == len(set(capabilities)), f"{offer_id}: capabilities must be unique")


def validate_bindings(bindings: dict[str, Any]) -> None:
    _require(bindings.get("version") == BINDINGS_VERSION, "bindings version must be 1")
    values = bindings.get("bindings")
    _require(isinstance(values, list), "bindings.bindings must be a list")
    seen: set[str] = set()
    for binding in values:
        _require(isinstance(binding, dict), "binding must be an object")
        binding_id = binding.get("id")
        _require(isinstance(binding_id, str) and binding_id, "binding.id required")
        _require(binding_id not in seen, f"duplicate binding id: {binding_id}")
        seen.add(binding_id)
        for key in ("resource_id", "provider", "authorization_scope", "reviewed_at"):
            _require(isinstance(binding.get(key), str) and binding[key], f"{binding_id}: {key} required")
        _parse_date(binding["reviewed_at"])
        _require(
            isinstance(binding.get("max_age_days"), int) and binding["max_age_days"] > 0,
            f"{binding_id}: max_age_days must be positive",
        )
        _require(isinstance(binding.get("enabled"), bool), f"{binding_id}: enabled must be boolean")
        _require(
            binding.get("terms_eligible") is True or binding.get("terms_eligible") is False,
            f"{binding_id}: terms_eligible must be boolean",
        )
        cost_classes = binding.get("allowed_cost_classes")
        _require(isinstance(cost_classes, list) and cost_classes, f"{binding_id}: allowed_cost_classes required")
        _require(all(isinstance(x, str) and x for x in cost_classes), f"{binding_id}: invalid cost class")
        _require(len(cost_classes) == len(set(cost_classes)), f"{binding_id}: allowed_cost_classes must be unique")
        required_resource_capabilities = binding.get("required_resource_capabilities")
        _require(
            isinstance(required_resource_capabilities, list) and required_resource_capabilities,
            f"{binding_id}: required_resource_capabilities required",
        )
        _require(
            all(isinstance(x, str) and x for x in required_resource_capabilities),
            f"{binding_id}: invalid required resource capability",
        )
        _require(
            len(required_resource_capabilities) == len(set(required_resource_capabilities)),
            f"{binding_id}: required_resource_capabilities must be unique",
        )
        capabilities = binding.get("allowed_capabilities")
        _require(isinstance(capabilities, list) and capabilities, f"{binding_id}: allowed_capabilities required")
        _require(all(isinstance(x, str) and x for x in capabilities), f"{binding_id}: invalid capability")
        _require(len(capabilities) == len(set(capabilities)), f"{binding_id}: allowed_capabilities must be unique")
        prefix = binding.get("offer_id_prefix")
        _require(prefix is None or (isinstance(prefix, str) and prefix), f"{binding_id}: invalid offer_id_prefix")


def _registry_index(registry: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {offer["id"]: offer for offer in registry["offers"]}


def _binding_matches(binding: dict[str, Any], offer: dict[str, Any]) -> bool:
    if binding["provider"] != offer["provider"]:
        return False
    if offer.get("cost_class") not in binding["allowed_cost_classes"]:
        return False
    prefix = binding.get("offer_id_prefix")
    return prefix is None or offer["id"].startswith(prefix)


def _freshness_reason(label: str, fresh: bool, age: int) -> str | None:
    if fresh:
        return None
    if age < 0:
        return f"{label} future-dated ({-age} days ahead)"
    return f"{label} stale ({age} days)"


def _binding_reason(
    binding: dict[str, Any],
    resource: dict[str, Any] | None,
    offer: dict[str, Any],
    today: dt.date,
) -> list[str]:
    reasons: list[str] = []
    if not binding["enabled"]:
        reasons.append("binding disabled")
    if not binding["terms_eligible"]:
        reasons.append("binding terms eligibility not affirmed")
    binding_fresh, binding_age = _fresh(binding["reviewed_at"], binding["max_age_days"], today)
    binding_freshness = _freshness_reason("binding review", binding_fresh, binding_age)
    if binding_freshness:
        reasons.append(binding_freshness)
    if resource is None:
        reasons.append("bound resource missing from registry")
        return reasons
    if resource.get("kind") not in DIRECT_COMPUTE_KINDS:
        reasons.append("bound resource is not a direct compute class")
    if resource.get("status") not in ALLOWED_REGISTRY_STATUS:
        reasons.append("bound resource status is not executable")
    source = resource["source"]
    resource_fresh, resource_age = _fresh(source["checked_at"], source["max_age_days"], today)
    resource_freshness = _freshness_reason("resource evidence", resource_fresh, resource_age)
    if resource_freshness:
        reasons.append(resource_freshness)
    if resource.get("project_cost_usd") != 0:
        reasons.append("resource is not zero-project-cost")
    security = resource.get("security", {})
    if security.get("repo_write_authority") is not False or security.get("merge_authority") is not False:
        reasons.append("resource authority invariant violated")
    missing_resource_capabilities = sorted(
        set(binding["required_resource_capabilities"]) - set(resource.get("capabilities", []))
    )
    if missing_resource_capabilities:
        reasons.append(
            "resource evidence missing required capabilities: " + ", ".join(missing_resource_capabilities)
        )
    if offer.get("project_cost_usd") != 0:
        reasons.append("concrete offer is not zero-project-cost")
    if offer.get("available") is not True:
        reasons.append("concrete offer unavailable")
    unexpected = sorted(set(offer.get("capabilities", [])) - set(binding["allowed_capabilities"]))
    if unexpected:
        reasons.append("capability exceeds binding allowlist: " + ", ".join(unexpected))
    return reasons


def admit(
    registry: dict[str, Any],
    bindings: dict[str, Any],
    pool: dict[str, Any],
    today: dt.date,
) -> tuple[dict[str, Any], dict[str, Any]]:
    validate_registry(registry)
    validate_bindings(bindings)
    validate_pool(pool)
    observed_at = _parse_date(registry["observed_at"])
    _require(
        observed_at <= today,
        f"registry observed_at future-dated ({(observed_at - today).days} days ahead)",
    )
    resources = _registry_index(registry)
    admitted: list[dict[str, Any]] = []
    admitted_report: list[dict[str, str]] = []
    rejected: list[dict[str, Any]] = []

    for offer in pool["offers"]:
        matches = [binding for binding in bindings["bindings"] if _binding_matches(binding, offer)]
        if not matches:
            rejected.append({"offer_id": offer["id"], "reasons": ["no matching local binding"]})
            continue
        if len(matches) > 1:
            rejected.append({"offer_id": offer["id"], "reasons": ["ambiguous matching bindings"]})
            continue
        binding = matches[0]
        resource = resources.get(binding["resource_id"])
        reasons = _binding_reason(binding, resource, offer, today)
        if reasons:
            rejected.append({"offer_id": offer["id"], "binding_id": binding["id"], "reasons": reasons})
            continue
        admitted.append(offer)
        admitted_report.append(
            {
                "offer_id": offer["id"],
                "binding_id": binding["id"],
                "resource_id": binding["resource_id"],
                "authorization_scope": binding["authorization_scope"],
            }
        )

    return (
        {"schema_version": "0.1", "offers": admitted},
        {
            "schema_version": "0.1",
            "bridge": "resource-compute-admission-v0.1",
            "today": today.isoformat(),
            "admitted": admitted_report,
            "rejected": rejected,
            "authority": "filtering only; no discovery, dispatch, repository write, merge, or correctness authority",
        },
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", required=True)
    parser.add_argument("--bindings", required=True)
    parser.add_argument("--pool", required=True)
    parser.add_argument("--today", help="ISO date; defaults to UTC today")
    parser.add_argument("--output", required=True, help="Admitted Compute Offer Pool JSON")
    parser.add_argument("--report", required=True, help="Admission report JSON")
    args = parser.parse_args()

    today = _parse_date(args.today) if args.today else dt.datetime.now(dt.timezone.utc).date()
    admitted, report = admit(_load(args.registry), _load(args.bindings), _load(args.pool), today)
    Path(args.output).write_text(json.dumps(admitted, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    Path(args.report).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"admitted={len(admitted['offers'])} rejected={len(report['rejected'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
