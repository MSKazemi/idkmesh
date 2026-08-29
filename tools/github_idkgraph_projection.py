#!/usr/bin/env python3
"""Deterministically project bounded GitHub metadata into IDKGraph."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

VERSION = "github-idkgraph-projection-v0.1"
NODE_TYPES = {
    "issue": "work_unit",
    "pull_request": "artifact",
    "comment": "evidence",
    "review": "evidence",
    "inline_review_comment": "evidence",
    "check_run": "evidence",
    "workflow_run": "evidence",
    "commit": "artifact",
    "release": "artifact",
    "reaction": "evidence",
    "fork": "evidence",
    "label_event": "evidence",
    "reproduction": "evidence",
    "benchmark": "evidence",
    "security_finding": "evidence",
    "evolution_candidate": "hypothesis",
    "outcome": "evidence",
    "capacity_signal": "metric",
}
ATTENTION_TYPES = {"reaction", "fork"}
COORDINATION_TYPES = {"comment", "inline_review_comment", "label_event"}
VERIFICATION_TYPES = {
    "review", "check_run", "workflow_run", "security_finding",
    "reproduction", "benchmark",
}
REQUIRED_GUARDS = {
    "protected_main",
    "typed_allowed_rule",
    "risk_budget",
    "review_capacity",
    "no_equivalent_open_candidate",
    "separate_human_integration",
}
DIMENSIONS = (
    "impact",
    "confidence",
    "novelty",
    "information_gain",
    "dependency_unlock",
    "review_capacity",
    "cost",
    "risk",
    "reversibility",
)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _node_id(repository: str, kind: str, source_id: str) -> str:
    return f"github:{repository}:{kind}:{source_id}"


def _edge_id(relation: str, sources: Iterable[str], targets: Iterable[str]) -> str:
    raw = "\0".join((relation, *sorted(sources), "->", *sorted(targets)))
    return f"edge:{hashlib.sha256(raw.encode()).hexdigest()[:24]}"


def _is_bot(login: str) -> bool:
    value = login.lower()
    return value.endswith("[bot]") or value in {"github-actions", "github-actions[bot]"}


def _rank_candidates(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    expected = set(DIMENSIONS)
    ranked: list[dict[str, Any]] = []
    for record in records:
        if record["source_type"] != "evolution_candidate":
            continue
        attributes = record.get("attributes") or {}
        dimensions = attributes.get("dimensions") or {}
        guards = attributes.get("hard_guards") or {}
        _require(isinstance(dimensions, dict) and set(dimensions) == expected,
                 "candidate dimensions must be exactly the v0.1 set")
        _require(isinstance(guards, dict), "candidate hard_guards must be an object")
        _require(REQUIRED_GUARDS <= set(guards),
                 "candidate is missing required hard guards")
        values = {key: float(value) for key, value in dimensions.items()}
        _require(all(0.0 <= value <= 1.0 for value in values.values()),
                 "candidate dimensions must be within [0, 1]")
        blocked = sorted(key for key, value in guards.items() if value is not True)
        benefit = sum(values[key] for key in DIMENSIONS if key not in {"cost", "risk"})
        score = benefit / (1.0 + values["cost"] + values["risk"])
        ranked.append({
            "candidate_id": record["id"],
            "eligible": not blocked,
            "blocked_by": blocked,
            "score": round(score, 8),
            "dimensions": values,
        })
    eligible = [row for row in ranked if row["eligible"]]
    benefits = tuple(key for key in DIMENSIONS if key not in {"cost", "risk"})
    for candidate in eligible:
        dominated_by = []
        for other in eligible:
            if other is candidate:
                continue
            no_worse = (
                all(other["dimensions"][key] >= candidate["dimensions"][key] for key in benefits)
                and all(other["dimensions"][key] <= candidate["dimensions"][key] for key in ("cost", "risk"))
            )
            strictly_better = any(
                other["dimensions"][key] > candidate["dimensions"][key] for key in benefits
            ) or any(
                other["dimensions"][key] < candidate["dimensions"][key] for key in ("cost", "risk")
            )
            if no_worse and strictly_better:
                dominated_by.append(other["candidate_id"])
        candidate["pareto_dominated_by"] = sorted(dominated_by)
        if dominated_by:
            candidate["eligible"] = False
            candidate["blocked_by"].append("pareto_dominated")
    for candidate in ranked:
        candidate.setdefault("pareto_dominated_by", [])
    return sorted(ranked, key=lambda row: (
        not row["eligible"], -float(row["score"]), str(row["candidate_id"])
    ))


def project_snapshot(
    snapshot: dict[str, Any],
    repository_graph: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Combine an existing repository graph with normalized GitHub records."""

    _require(snapshot.get("version") == 1, "snapshot version must be 1")
    repository = snapshot.get("repository")
    collected_at = snapshot.get("collected_at")
    records = snapshot.get("records")
    _require(isinstance(repository, str) and "/" in repository,
             "repository must be owner/name")
    _require(isinstance(collected_at, str) and collected_at,
             "collected_at is required")
    _require(isinstance(records, list), "records must be an array")

    base = repository_graph or {
        "graph_id": f"repository:{repository}",
        "version": "0.1",
        "nodes": [],
        "hyperedges": [],
        "events": [],
    }
    nodes = list(base.get("nodes") or [])
    edges = list(base.get("hyperedges") or [])
    events = list(base.get("events") or [])
    known_ids = {node["id"] for node in nodes}
    source_ids: dict[str, str] = {}
    normalized: list[dict[str, Any]] = []

    ordered_records = sorted(
        records,
        key=lambda row: (
            str(row.get("source_type")) if isinstance(row, dict) else "",
            str(row.get("source_id")) if isinstance(row, dict) else "",
        ),
    )
    for index, raw in enumerate(ordered_records):
        _require(isinstance(raw, dict), f"records[{index}] must be an object")
        kind, source_id = raw.get("source_type"), raw.get("source_id")
        title, url = raw.get("title"), raw.get("url")
        timestamp, actor = raw.get("timestamp"), raw.get("actor")
        _require(kind in NODE_TYPES, f"unsupported source_type: {kind}")
        _require(isinstance(source_id, str) and source_id, "source_id is required")
        _require(source_id not in source_ids, f"duplicate source_id: {source_id}")
        _require(isinstance(title, str) and title, "title is required")
        _require(isinstance(url, str) and url.startswith("https://github.com/"),
                 "GitHub URL is required")
        _require(isinstance(timestamp, str) and timestamp, "timestamp is required")
        _require(isinstance(actor, str) and actor, "actor is required")
        body = raw.get("body")
        _require(body is None or isinstance(body, str), "record body must be a string")

        node_id = _node_id(repository, kind, source_id)
        _require(node_id not in known_ids, f"duplicate generated node ID: {node_id}")
        source_ids[source_id] = node_id
        attributes = dict(raw.get("attributes") or {})
        evidence_class = (
            "attention" if kind in ATTENTION_TYPES
            else "coordination" if kind in COORDINATION_TYPES
            else "verification" if kind in VERIFICATION_TYPES
            else "worker_claim" if kind in {"pull_request", "commit"}
            else "outcome" if kind == "outcome"
            else None
        )
        attributes.update({
            "github_source_id": source_id,
            "github_source_type": kind,
            "source_url": url,
            "untrusted_text": body is not None,
        })
        if evidence_class:
            attributes["evidence_class"] = evidence_class
        if kind == "outcome":
            required_outcome = {
                "rule_version", "predicted_improvement", "decision",
                "reviewer_effort", "verification_result", "health_delta",
                "regression_or_revert",
            }
            _require(required_outcome <= set(attributes),
                     "outcome must include the complete learning record")
        if body is not None:
            attributes["body_sha256"] = hashlib.sha256(body.encode()).hexdigest()
        nodes.append({
            "id": node_id,
            "type": NODE_TYPES[kind],
            "title": title,
            "attributes": attributes,
            "provenance": {
                "actor_id": f"github:user:{actor}",
                "activity_id": source_id,
                "source": url,
                "created_at": timestamp,
                "tool": VERSION,
            },
        })
        known_ids.add(node_id)
        actor_id = f"github:user:{actor}"
        if actor_id not in known_ids:
            nodes.append({
                "id": actor_id,
                "type": "agent" if _is_bot(actor) else "contributor",
                "title": actor,
                "attributes": {"github_login": actor},
                "provenance": {"source": url, "tool": VERSION},
            })
            known_ids.add(actor_id)
        normalized.append({**raw, "id": node_id})

    for record in normalized:
        node_id = record["id"]
        actor_id = f"github:user:{record['actor']}"
        edges.append({
            "id": _edge_id("generated_by", [node_id], [actor_id]),
            "relation": "generated_by",
            "sources": [node_id],
            "targets": [actor_id],
            "attributes": {"mapping_rule": "github_actor"},
            "provenance": {"source": record["url"], "tool": VERSION},
        })
        for parent in sorted(set(record.get("parent_ids") or [])):
            _require(parent in source_ids, f"unknown parent source_id: {parent}")
            relation = (
                "verifies" if record["source_type"] in VERIFICATION_TYPES
                else "derived_from"
            )
            edges.append({
                "id": _edge_id(relation, [node_id], [source_ids[parent]]),
                "relation": relation,
                "sources": [node_id],
                "targets": [source_ids[parent]],
                "attributes": {"mapping_rule": "explicit_github_parent"},
                "provenance": {"source": record["url"], "tool": VERSION},
            })
        for target in sorted(set(record.get("repository_node_ids") or [])):
            _require(target in known_ids, f"unknown repository node: {target}")
            edges.append({
                "id": _edge_id("documents", [node_id], [target]),
                "relation": "documents",
                "sources": [node_id],
                "targets": [target],
                "attributes": {"mapping_rule": "explicit_repository_node_link"},
                "provenance": {"source": record["url"], "tool": VERSION},
            })
        events.append({
            "id": f"event:{node_id}",
            "type": (
                "EvidenceAttached"
                if NODE_TYPES[record["source_type"]] == "evidence"
                else "NodeCreated"
            ),
            "timestamp": record["timestamp"],
            "affected_ids": [node_id],
            "actor_id": actor_id,
            "attributes": {"source_url": record["url"]},
        })

    authors = {record["source_id"]: record["actor"] for record in normalized}
    independent: dict[str, set[str]] = {}
    for record in normalized:
        if record["source_type"] not in VERIFICATION_TYPES:
            continue
        attributes = record.get("attributes") or {}
        if attributes.get("outcome") != "pass" or attributes.get("self_reported") is True:
            continue
        key = attributes.get("independence_key")
        _require(isinstance(key, str) and key,
                 "passing review/check requires independence_key")
        for parent in record.get("parent_ids") or []:
            if record["source_type"] in {"review", "inline_review_comment"} and (
                _is_bot(record["actor"]) or authors.get(parent) == record["actor"]
            ):
                continue
            independent.setdefault(parent, set()).add(key)

    capacity: dict[str, dict[str, Any]] = {}
    for record in normalized:
        if record["source_type"] != "capacity_signal":
            continue
        attributes = record.get("attributes") or {}
        identity, value = attributes.get("observation_id"), attributes.get("value")
        _require(isinstance(identity, str) and identity,
                 "capacity signal observation_id is required")
        _require(isinstance(value, (int, float)) and not isinstance(value, bool),
                 "capacity signal value must be numeric")
        row = {
            "observation_id": identity,
            "value": float(value),
            "source_id": record["source_id"],
        }
        if identity in capacity:
            _require(capacity[identity]["value"] == row["value"],
                     f"conflicting capacity observation: {identity}")
        else:
            capacity[identity] = row

    unique_edges = {edge["id"]: edge for edge in edges}
    graph = {
        "graph_id": f"{base['graph_id']}+github:{repository}",
        "version": "0.1",
        "nodes": sorted(nodes, key=lambda item: item["id"]),
        "hyperedges": sorted(unique_edges.values(), key=lambda item: item["id"]),
        "events": sorted(events, key=lambda item: item["id"]),
    }
    return {
        "projection_version": VERSION,
        "policy_version": "github-evolution-policy-v0.1",
        "source": {"repository": repository, "collected_at": collected_at},
        "graph": graph,
        "independent_verification": {
            parent: {"independence_keys": sorted(keys), "count": len(keys)}
            for parent, keys in sorted(independent.items())
        },
        "capacity_observations": sorted(
            capacity.values(), key=lambda row: row["observation_id"]
        ),
        "candidate_ranking": _rank_candidates(normalized),
        "outcomes": sorted([
            record["id"] for record in normalized
            if record["source_type"] == "outcome"
        ]),
        "actuator": {
            "enabled": False,
            "max_public_actions_per_epoch": 1,
            "requires": [
                "protected_main", "typed_allowed_rule", "risk_budget",
                "review_capacity", "no_equivalent_open_candidate",
                "separate_human_integration",
            ],
        },
        "authority": {
            "github_read": False,
            "github_write": False,
            "execute_untrusted_text": False,
            "automatic_merge": False,
        },
    }


def serialize(value: dict[str, Any], pretty: bool = False) -> str:
    kwargs = {"sort_keys": True, "ensure_ascii": False}
    if pretty:
        return json.dumps(value, indent=2, **kwargs) + "\n"
    return json.dumps(value, separators=(",", ":"), **kwargs) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshot", type=Path)
    parser.add_argument("--repository-graph", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    snapshot = json.loads(args.snapshot.read_text(encoding="utf-8"))
    base = (
        json.loads(args.repository_graph.read_text(encoding="utf-8"))
        if args.repository_graph else None
    )
    rendered = serialize(project_snapshot(snapshot, base), pretty=args.pretty)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
