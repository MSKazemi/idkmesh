#!/usr/bin/env python3
"""T1 (#974): provenance for public SWE-bench submissions, and E047's provenance-aware re-analysis.

E045 and E046 treated every leaderboard submission as an exchangeable agent.
Many submissions share a model, a model organisation or a scaffold. This module:

1. downloads each submission's ``metadata.yaml`` at the pinned commit (never vendored);
2. parses the provenance fields in that file (model, model organisation, submitting
   organisation, scaffold, attempts), using a small standard-library YAML subset reader;
3. re-runs the *frozen* E046 functions, unchanged and imported, on a population
   with one submission per primary model. The representative is chosen blind to
   outcomes: the lexicographically first submission name. This tests whether H1
   survives once duplicate models are removed.
4. adds the declared-diversity selector that the preregistration deferred to T1:
   the k most accurate submissions with at most one per model organisation.

Every split analysed here was opened before this code was written, so all E047
output is **exploratory**. It tests robustness to a known threat; it is not a
new confirmatory result.
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
from pathlib import Path
from typing import Mapping, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parent))
import agent_value_forecast as frozen  # noqa: E402

SEED = 20261010
FIELDS = ("model", "model_display", "model_org", "org", "agent", "agent_org", "attempts", "os_model")


# --------------------------------------------------------------------------- parse


def _scalar(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
        value = value[1:-1]
    return value


def parse_metadata(text: str) -> dict:
    """Read the provenance fields of a SWE-bench ``metadata.yaml``.

    It handles only the shapes these files use: nested mappings by two-space
    indentation, ``key: value`` scalars, and ``- item`` lists. ``attempts`` is
    nested under ``tags.system``. Unknown or missing fields come back as None.
    """
    result: dict = {field: None for field in FIELDS}
    stack: list[tuple[int, str]] = []
    pending_list: tuple[int, str] | None = None
    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        line = raw.strip()
        if line.startswith("- ") and pending_list is not None and indent >= pending_list[0]:
            path = pending_list[1]
            if path == "tags.model":
                result["model"] = (result["model"] or []) + [_scalar(line[2:])]
            continue
        pending_list = None
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        while stack and stack[-1][0] >= indent:
            stack.pop()
        path = ".".join([name for _, name in stack] + [key])
        if value.strip() == "":
            stack.append((indent, key))
            pending_list = (indent, path)
            continue
        scalar = _scalar(value)
        if path == "tags.model":
            result["model"] = [scalar] if scalar not in ("null", "") else None
        elif path in ("tags.model_display", "tags.model_org", "tags.org", "tags.agent", "tags.agent_org", "tags.os_model"):
            result[path.split(".")[1]] = None if scalar in ("null", "") else scalar
        elif path == "tags.system.attempts":
            result["attempts"] = None if scalar in ("null", "") else scalar
    return result


def primary_model(record: Mapping) -> str | None:
    """The first listed model, else the display name; None when undisclosed."""
    models = record.get("model") or []
    name = models[0] if models else (record.get("model_display") or "")
    name = name.strip().lower().rsplit("/", 1)[-1]
    name = re.sub(r"[\s_.]+", "-", name)
    name = re.sub(r"-(\d{8}|\d{4}-\d{2}-\d{2}|latest)$", "", name)
    if name in ("", "[]", "undisclosed", "unknown", "multiple", "mixed-models"):
        return None
    # Token order varies between submitters (claude-4-5-opus / claude-opus-4-5).
    return "-".join(sorted(token for token in name.split("-") if token))


# --------------------------------------------------------------------------- fetch


def fetch_metadata(cache: Path, split: str, commit: str) -> int:
    names = sorted({p.stem for kind in ("r", "p") for p in (cache / kind).glob("*.json")})
    (cache / "m").mkdir(parents=True, exist_ok=True)
    raw = f"https://raw.githubusercontent.com/{frozen.UPSTREAM_REPO}/{commit}/evaluation/{split}"
    stored = 0
    with frozen._ipv4_only():
        for name in names:
            try:
                payload = frozen._get(f"{raw}/{name}/metadata.yaml")
            except OSError:
                continue
            (cache / "m" / f"{name}.yaml").write_bytes(payload)
            stored += 1
    return stored


def load_provenance(cache: Path) -> dict[str, dict]:
    return {p.stem: parse_metadata(p.read_text(encoding="utf-8")) for p in sorted((cache / "m").glob("*.yaml"))}


# ------------------------------------------------------------------------ analysis


def one_per_model(agents: Sequence[str], provenance: Mapping[str, Mapping]) -> tuple[list[str], int]:
    """Keep the lexicographically first submission per primary model (outcome-blind).

    Submissions with no recorded model are kept, since each is its own unknown
    group. Returns (kept agents, number of submissions without a model).
    """
    chosen: dict[str, str] = {}
    unknown: list[str] = []
    for agent in sorted(agents):
        model = primary_model(provenance.get(agent, {}))
        if model is None:
            unknown.append(agent)
        elif model not in chosen:
            chosen[model] = agent
    return sorted(list(chosen.values()) + unknown), len(unknown)


def select_top_k_one_per_org(rows: Mapping, agents: Sequence[str], calibration: frozenset, k: int, provenance: Mapping[str, Mapping]) -> list[str]:
    """Top-k by calibration accuracy, at most one per model organisation.

    A submission with no recorded organisation counts as its own organisation,
    which makes this selector *more* permissive than a strict one-per-org rule.
    """
    chosen: list[str] = []
    orgs: set[str] = set()
    for agent in sorted(agents, key=lambda a: (-len(rows[a] & calibration), a)):
        org = (provenance.get(agent, {}).get("model_org") or f"unknown:{agent}").strip().lower()
        if org in orgs:
            continue
        chosen.append(agent)
        orgs.add(org)
        if len(chosen) == k:
            break
    return chosen


def diversity_selector_comparison(rows: Mapping, agents: Sequence[str], tasks: Sequence[str], provenance: Mapping[str, Mapping]) -> dict:
    calibration = frozenset(t for t in tasks if frozen.calibration_half(t))
    held_out = frozenset(tasks) - calibration
    out = {}
    for k in frozen.SELECTION_SIZES:
        greedy = frozen.select_greedy(rows, agents, calibration, k)
        diverse = select_top_k_one_per_org(rows, agents, calibration, k, provenance)
        if len(diverse) < k:
            out[str(k)] = {"infeasible": f"only {len(diverse)} distinct model organisations"}
            continue
        g = frozenset().union(*(rows[a] for a in greedy)) & held_out
        d = frozenset().union(*(rows[a] for a in diverse)) & held_out
        b, c = len(g - d), len(d - g)
        out[str(k)] = {
            "greedy_held_out_coverage": round(len(g) / len(held_out), 4),
            "one_per_model_org_held_out_coverage": round(len(d) / len(held_out), 4),
            "greedy_only_tasks": b,
            "diverse_only_tasks": c,
            "mcnemar_p": round(frozen.exact_mcnemar(b, c), 6),
            "distinct_model_orgs_chosen": len({(provenance.get(a, {}).get("model_org") or a).lower() for a in diverse}),
        }
    return out


def provenance_summary(agents: Sequence[str], provenance: Mapping[str, Mapping]) -> dict:
    models = [primary_model(provenance.get(a, {})) for a in agents]
    orgs = [(provenance.get(a, {}).get("model_org") or "").strip().lower() or None for a in agents]
    multi = [a for a in agents if str(provenance.get(a, {}).get("attempts") or "1").strip() not in ("1", "")]
    return {
        "submissions": len(agents),
        "with_metadata": sum(1 for a in agents if a in provenance),
        "distinct_primary_models": len({m for m in models if m}),
        "without_model": sum(1 for m in models if m is None),
        "distinct_model_orgs": len({o for o in orgs if o}),
        "multi_attempt_submissions": len(multi),
    }


def analyze(cache: Path, seed: int = SEED) -> dict:
    rows, universe, _ = frozen.load_split(cache)
    provenance = load_provenance(cache)
    n = len(universe)
    agents = frozen.competent(rows, n)
    deduplicated, unknown = one_per_model(agents, provenance)
    report: dict = {
        "provenance": provenance_summary(agents, provenance),
        "provenance_table": {
            agent: {
                "primary_model": primary_model(provenance.get(agent, {})),
                "model_org": provenance.get(agent, {}).get("model_org"),
                "agent": provenance.get(agent, {}).get("agent"),
                "attempts": provenance.get(agent, {}).get("attempts"),
            }
            for agent in agents
        },
        "deduplicated_population": len(deduplicated),
        "kept_without_model": unknown,
    }
    collapsed_rows = {a: rows[a] for a in deduplicated}
    rerun = frozen.analyze_split(collapsed_rows, universe, seed=seed)
    report["frozen_analysis_on_one_per_model"] = {
        key: rerun.get(key)
        for key in ("feasible", "reason", "competent_agents", "blind_spot_floor", "mean_pairwise_phi", "h1_verdict", "h1_bootstrap")
    }
    if rerun.get("feasible"):
        report["frozen_analysis_on_one_per_model"]["curve_mae"] = rerun["primary"]["curve_mae"]
        report["frozen_analysis_on_one_per_model"]["population_coverage_mae"] = rerun["primary"]["population_coverage_mae"]
        report["frozen_analysis_on_one_per_model"]["h3_verdict"] = rerun["h3"]["verdict"]
    report["greedy_vs_one_per_model_org"] = diversity_selector_comparison(rows, agents, sorted(universe), provenance)
    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    f = sub.add_parser("fetch-metadata")
    f.add_argument("--cache", type=Path, required=True)
    f.add_argument("--split", required=True)
    f.add_argument("--commit", required=True)
    a = sub.add_parser("analyze")
    a.add_argument("caches", type=Path, nargs="+")
    a.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    if args.command == "fetch-metadata":
        print(f"stored {fetch_metadata(args.cache, args.split, args.commit)} metadata files")
        return 0
    out = {
        "experiment": "E047",
        "evidence_class": "exploratory: every split was opened before this analysis was written",
        "frozen_e046_sha256": frozen.hashlib.sha256(Path(frozen.__file__).read_bytes()).hexdigest(),
        "seed": SEED,
        "splits": {},
    }
    for cache in args.caches:
        name = (cache / "SPLIT").read_text(encoding="utf-8").strip() if (cache / "SPLIT").exists() else cache.name
        out["splits"][name] = analyze(cache)
    text = json.dumps(out, indent=2) + "\n"
    if args.out:
        args.out.write_text(text, encoding="utf-8")
    sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
