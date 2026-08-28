#!/usr/bin/env python3
"""Deterministic zero-project-cost resource planner for IDKMesh.

This tool DOES NOT dispatch work, call external services, mutate GitHub, or grant
worker authority. It filters a versioned discovery registry against a bounded
task request and emits an evidence-oriented candidate plan.

Important contract boundary: planner selections are discovery/control-plane
candidates, NOT executable runtime compute offers. A provider-specific adapter
or live capability probe must materialize an eligible resource into
``schemas/compute-offer-pool-v0.1.schema.json`` before
``experiments/free_compute_router.py`` can select it under
``config/compute-policy.json``. The planner must never become a second execution
router or infer concrete CPU/RAM/GPU capacity from catalog metadata.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
from pathlib import Path
from typing import Any

REGISTRY_VERSION = 1
TASK_VERSION = 1
DISCOVERY_CONTRACT = "schemas/resource-offer-registry-v0.1.schema.json"
RUNTIME_CONTRACT = "schemas/compute-offer-pool-v0.1.schema.json"
RUNTIME_ROUTER = "experiments/free_compute_router.py"
REPOSITORY_COMPUTE_POLICY = "config/compute-policy.json"


def _require(cond: bool, msg: str) -> None:
    if not cond:
        raise ValueError(msg)


def _load(path: str | Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    _require(isinstance(value, dict), f"{path}: expected JSON object")
    return value


def _parse_date(raw: str) -> dt.date:
    return dt.date.fromisoformat(raw)


def validate_registry(registry: dict[str, Any]) -> None:
    _require(registry.get("version") == REGISTRY_VERSION, "registry version must be 1")
    observed = registry.get("observed_at")
    _require(isinstance(observed, str), "observed_at must be ISO date")
    _parse_date(observed)
    offers = registry.get("offers")
    _require(isinstance(offers, list) and offers, "offers must be a non-empty list")
    ids: set[str] = set()
    for offer in offers:
        _require(isinstance(offer, dict), "each offer must be an object")
        oid = offer.get("id")
        _require(isinstance(oid, str) and oid, "offer.id must be non-empty")
        _require(oid not in ids, f"duplicate offer id: {oid}")
        ids.add(oid)
        _require(offer.get("status") in {"available", "conditional", "manual", "excluded"}, f"{oid}: invalid status")
        _require(offer.get("project_cost_usd") == 0, f"{oid}: v0 registry only accepts zero-project-cost offers")
        roles = offer.get("task_classes")
        _require(isinstance(roles, list) and roles, f"{oid}: task_classes required")
        _require(all(isinstance(x, str) and x for x in roles), f"{oid}: invalid task_classes")
        caps = offer.get("capabilities")
        _require(isinstance(caps, list), f"{oid}: capabilities must be a list")
        source = offer.get("source")
        _require(isinstance(source, dict), f"{oid}: source required")
        _require(isinstance(source.get("url"), str) and source["url"].startswith("https://"), f"{oid}: HTTPS source URL required")
        _require(isinstance(source.get("checked_at"), str), f"{oid}: checked_at required")
        _parse_date(source["checked_at"])
        _require(isinstance(source.get("max_age_days"), int) and source["max_age_days"] > 0, f"{oid}: positive max_age_days required")
        sec = offer.get("security")
        _require(isinstance(sec, dict), f"{oid}: security required")
        _require(sec.get("merge_authority") is False, f"{oid}: merge_authority must be false")
        _require(sec.get("repo_write_authority") is False, f"{oid}: repo_write_authority must be false in v0")


def validate_task(task: dict[str, Any]) -> None:
    _require(task.get("version") == TASK_VERSION, "task version must be 1")
    _require(isinstance(task.get("id"), str) and task["id"], "task.id required")
    _require(task.get("task_class") in {"observer", "researcher", "coder", "verifier", "compute", "control_plane"}, "invalid task_class")
    _require(task.get("max_project_cost_usd") == 0, "v0 planner requires zero project cost")
    _require(task.get("data_sensitivity") == "public", "v0 planner handles public data only")
    _require(task.get("requires_repo_write") is False, "v0 planner does not schedule repository-write tasks")
    for name in ("required_capabilities", "preferred_capabilities"):
        value = task.get(name, [])
        _require(isinstance(value, list) and all(isinstance(x, str) for x in value), f"{name} must be a string array")


def _freshness(offer: dict[str, Any], today: dt.date) -> tuple[bool, int]:
    source = offer["source"]
    age = (today - _parse_date(source["checked_at"])).days
    return age <= source["max_age_days"], age


def _eligible(offer: dict[str, Any], task: dict[str, Any], today: dt.date) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if offer["status"] == "excluded":
        reasons.append("offer status is excluded")
    fresh, age = _freshness(offer, today)
    if not fresh:
        reasons.append(f"offer evidence is stale ({age} days)")
    if task["task_class"] not in offer["task_classes"]:
        reasons.append("task class unsupported")
    required = set(task.get("required_capabilities", []))
    missing = sorted(required - set(offer.get("capabilities", [])))
    if missing:
        reasons.append("missing capabilities: " + ", ".join(missing))
    if task.get("requires_llm") and "llm" not in offer.get("capabilities", []):
        reasons.append("LLM required")
    if task.get("requires_docker") and "docker" not in offer.get("capabilities", []):
        reasons.append("Docker required")
    if offer.get("human_interaction_required") and not task.get("human_interactive_ok", False):
        reasons.append("offer requires human interaction")
    if offer.get("requires_repository_secret") and not task.get("repository_secret_ok", False):
        reasons.append("offer requires repository secret")
    if offer.get("external_data_processor") and not task.get("external_processing_ok", False):
        reasons.append("offer sends public task data to external processor")
    return not reasons, reasons


def _score(offer: dict[str, Any], task: dict[str, Any]) -> float:
    preferred = set(task.get("preferred_capabilities", []))
    caps = set(offer.get("capabilities", []))
    fit = 1.0 + 0.12 * len(preferred & caps)
    availability = float(offer.get("availability_weight", 0.5))
    independence = 1.12 if "independent_verification" in caps else 1.0
    no_secret = 1.08 if not offer.get("requires_repository_secret") else 0.92
    no_external = 1.05 if not offer.get("external_data_processor") else 0.95
    human_cost = float(offer.get("human_setup_cost", 0.5))
    scarcity = float(offer.get("scarcity", 0.5))
    risk = float(offer.get("security_risk", 0.5))
    raw = availability * fit * independence * no_secret * no_external / (1.0 + human_cost + scarcity + 2.0 * risk)
    _require(math.isfinite(raw) and raw >= 0, f"invalid score for {offer['id']}")
    return round(raw, 6)


def plan(registry: dict[str, Any], task: dict[str, Any], limit: int, today: dt.date) -> dict[str, Any]:
    validate_registry(registry)
    validate_task(task)
    candidates = []
    rejected = []
    for offer in registry["offers"]:
        ok, reasons = _eligible(offer, task, today)
        if ok:
            candidates.append({
                "resource_id": offer["id"],
                "score": _score(offer, task),
                "status": offer["status"],
                "task_classes": offer["task_classes"],
                "capabilities": offer["capabilities"],
                "activation": offer.get("activation"),
                "authority": "candidate/evidence only; no repository write or merge authority",
            })
        else:
            rejected.append({"resource_id": offer["id"], "reasons": reasons})
    candidates.sort(key=lambda x: (-x["score"], x["resource_id"]))
    return {
        "schema_version": "0.1",
        "task_id": task["id"],
        "planner": "free-resource-planner-v0.1",
        "policy": {
            "max_project_cost_usd": 0,
            "public_data_only": True,
            "repo_write_authority": False,
            "merge_authority": False,
            "fresh_external_evidence_required": True,
        },
        "runtime_materialization": {
            "required_before_execution": True,
            "planner_output_is_executable_compute_offer": False,
            "discovery_contract": DISCOVERY_CONTRACT,
            "runtime_contract": RUNTIME_CONTRACT,
            "runtime_router": RUNTIME_ROUTER,
            "repository_compute_policy": REPOSITORY_COMPUTE_POLICY,
            "rule": "materialize live provider capacity before runtime routing; discovery metadata cannot grant execution capacity or financial authority",
        },
        "selected": candidates[:limit],
        "rejected": rejected,
        "human_integration_decision_required": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    v = sub.add_parser("validate")
    v.add_argument("registry")
    p = sub.add_parser("plan")
    p.add_argument("registry")
    p.add_argument("task")
    p.add_argument("--limit", type=int, default=5)
    p.add_argument("--today", default=None, help="ISO date; defaults to UTC today")
    args = parser.parse_args()
    registry = _load(args.registry)
    if args.cmd == "validate":
        validate_registry(registry)
        print("OK: free resource registry valid")
        return 0
    task = _load(args.task)
    today = _parse_date(args.today) if args.today else dt.datetime.now(dt.timezone.utc).date()
    print(json.dumps(plan(registry, task, args.limit, today), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
