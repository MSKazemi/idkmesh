#!/usr/bin/env python3
"""E048: the temporal-holdout runner registered by PREREG_AGENT_VALUE_FORECAST_V2.

It fetches only submissions that were not present at the commit E045-E047 used,
then runs the *frozen* E046 analysis (`agent_value_forecast.py`, imported
unchanged) and the E047 one-per-model population on them. It adds no new
statistics, so the only things this file can change are which submissions are
selected and which population is primary.

Usage::

    python experiments/temporal_holdout.py list  --commit <new upstream commit>
    python experiments/temporal_holdout.py fetch --commit <new upstream commit> --cache .cache/e048
    python experiments/temporal_holdout.py analyze .cache/e048/lite .cache/e048/verified --out experiments/results/E048-temporal-holdout.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

sys.path.insert(0, str(Path(__file__).resolve().parent))
import agent_value_forecast as frozen  # noqa: E402
import submission_provenance as provenance  # noqa: E402

BASELINE_COMMIT = "40f164d5b8f1d249bf95a6df8b74b577fd8e519d"
SPLITS = ("lite", "verified", "test", "multilingual", "multimodal")


def _names(split: str, commit: str) -> set[str]:
    url = f"https://api.github.com/repos/{frozen.UPSTREAM_REPO}/contents/evaluation/{split}?ref={commit}"
    with frozen._ipv4_only():
        return {e["name"] for e in json.loads(frozen._get(url)) if e["type"] == "dir"}


def new_submissions(split: str, commit: str) -> list[str]:
    """Submissions present at ``commit`` but not at the baseline commit."""
    return sorted(_names(split, commit) - _names(split, BASELINE_COMMIT))


def fetch(cache_root: Path, commit: str) -> dict[str, int]:
    counts = {}
    for split in SPLITS:
        fresh = new_submissions(split, commit)
        counts[split] = len(fresh)
        if not fresh:
            continue
        cache = cache_root / split
        raw = f"https://raw.githubusercontent.com/{frozen.UPSTREAM_REPO}/{commit}/evaluation/{split}"
        for kind, rel in (("r", "results/results.json"), ("p", "per_instance_details.json"), ("m", "metadata.yaml")):
            (cache / kind).mkdir(parents=True, exist_ok=True)
            with frozen._ipv4_only():
                for name in fresh:
                    try:
                        payload = frozen._get(f"{raw}/{name}/{rel}")
                    except OSError:
                        continue
                    suffix = "yaml" if kind == "m" else "json"
                    (cache / kind / f"{name}.{suffix}").write_bytes(payload)
        (cache / "COMMIT").write_text(commit + "\n", encoding="utf-8")
        (cache / "SPLIT").write_text(split + "\n", encoding="utf-8")
    return counts


def analyze(caches: Sequence[Path]) -> dict:
    out: dict = {"experiment": "E048", "frozen_e046_sha256": frozen.hashlib.sha256(Path(frozen.__file__).read_bytes()).hexdigest(), "splits": {}}
    for cache in caches:
        name = (cache / "SPLIT").read_text(encoding="utf-8").strip()
        rows, universe, _ = frozen.load_split(cache)
        competent = frozen.competent(rows, len(universe))
        out["splits"][name] = {
            "new_submissions": len(rows),
            "competent_new_submissions": len(competent),
            "all_agents_analysis": frozen.analyze_split(rows, universe),
            "one_per_model_analysis": provenance.analyze(cache),
        }
    out["decision"] = frozen.combine({n: s["all_agents_analysis"] for n, s in out["splits"].items()})
    return out


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("list", "fetch"):
        p = sub.add_parser(name)
        p.add_argument("--commit", required=True)
        if name == "fetch":
            p.add_argument("--cache", type=Path, required=True)
    a = sub.add_parser("analyze")
    a.add_argument("caches", type=Path, nargs="+")
    a.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    if args.command == "list":
        print(json.dumps({s: len(new_submissions(s, args.commit)) for s in SPLITS}, indent=1))
        return 0
    if args.command == "fetch":
        print(json.dumps(fetch(args.cache, args.commit), indent=1))
        return 0
    text = json.dumps(analyze(args.caches), indent=2) + "\n"
    if args.out:
        args.out.write_text(text, encoding="utf-8")
    sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
