"""Gate audit: measure what a verifier panel's verdicts are actually worth.

A review gate that reports "N verifiers approved" implies N independent pieces
of evidence. E017 measured a real 25-verifier panel (accuracy 0.7956, pairwise
error correlation +0.5873) whose majority vote was worth about one verifier,
and E015 showed the standard ``N / (1 + (N-1) rho)`` heuristic is optimistic in
exactly the accurate-verifier regime where such panels operate. This module
turns those retained results into a diagnostic: given a verdict matrix with
ground truth, it reports per-verifier accuracy, pairwise error correlation,
measured effective votes, the accuracy-dependent effective-vote ceiling, and
the breach rate on seeded known-bad probe candidates.

The audit consumes verdicts; it never runs a gate, selects candidates, or
grants acceptance authority. Collecting verdicts is the caller's job, and the
input must declare its evidence class (synthetic vs observed) so a report can
never silently launder fixture data into an observed claim.

Mathematical provenance: ``effective_n``, ``effective_n_ceiling`` and
``heuristic_effective_n`` follow ``sim/e015_analyze.py``; ``phi`` follows
``sim/e016_analyze.py``. ``tests/test_gate_audit.py`` asserts parity with those
modules so the packaged copies cannot drift from the research record.
"""

from __future__ import annotations

import hashlib
import itertools
import json
import math
import statistics
from pathlib import Path
from typing import Any

SCHEMA_ID = "gate-audit-report-v0.1"
VERDICTS = ("accept", "reject")
EVIDENCE_CLASSES = ("synthetic", "observed")


class GateAuditInputError(ValueError):
    """The verdict-matrix input violates the documented contract."""


# ---------------------------------------------------------------------------
# Panel mathematics (parity-tested against sim/e015_analyze.py and
# sim/e016_analyze.py).
# ---------------------------------------------------------------------------


def phi(x: list[int], y: list[int]) -> float:
    """Pearson correlation of two binary vectors (the phi coefficient).

    Returns ``nan`` when either vector has zero variance: a verifier that is
    always right (or always wrong) on the audited set carries no correlation
    information, and pretending otherwise would bias the panel mean.
    """
    n = len(x)
    if n == 0 or len(y) != n:
        return float("nan")
    mx = sum(x) / n
    my = sum(y) / n
    vx = sum((a - mx) ** 2 for a in x)
    vy = sum((b - my) ** 2 for b in y)
    if vx == 0.0 or vy == 0.0:
        return float("nan")
    cov = sum((a - mx) * (b - my) for a, b in zip(x, y))
    return cov / math.sqrt(vx * vy)


def majority_error_independent(n: int, acc: float, quorum: float = 0.5) -> float:
    """Error probability of n independent verifiers under quorum voting.

    The panel is wrong when the fraction of correct votes fails to exceed
    ``quorum``. This is the independent baseline that measured panel error is
    compared against to obtain effective votes.
    """
    need = math.floor(quorum * n) + 1  # correct votes required
    wrong = 0.0
    for k in range(0, need):
        wrong += math.comb(n, k) * (acc**k) * ((1 - acc) ** (n - k))
    return wrong


def effective_n(measured_err: float, acc: float, quorum: float = 0.5,
                nmax: int = 201) -> float:
    """Smallest independent panel size reproducing ``measured_err``.

    Interpolates linearly between the bracketing odd sizes, exactly as
    ``sim/e015_analyze.py`` does, so audit numbers stay comparable with the
    published E015/E017 results.
    """
    if acc <= 0.5:
        return float("nan")
    sizes = [n for n in range(1, nmax, 2)]
    errs = [majority_error_independent(n, acc, quorum) for n in sizes]
    if measured_err >= errs[0]:
        return 1.0
    if measured_err <= errs[-1]:
        return float(sizes[-1])
    for i in range(len(sizes) - 1):
        hi, lo = errs[i], errs[i + 1]
        if lo <= measured_err <= hi:
            if hi == lo:
                return float(sizes[i])
            frac = (hi - measured_err) / (hi - lo)
            return sizes[i] + frac * (sizes[i + 1] - sizes[i])
    return float("nan")


def heuristic_effective_n(n: int, correlation: float) -> float:
    """The classic ``N / (1 + (N-1) rho)`` heuristic, reported for contrast.

    E015 falsified it as a sizing rule: it converges to ``1/rho`` regardless
    of verifier accuracy, so it overstates panels of accurate verifiers. It is
    included in reports only so readers can see the gap.
    """
    return n / (1.0 + (n - 1) * correlation)


def effective_n_ceiling(acc: float, correlation: float,
                        nmax: int = 201) -> float:
    """Largest effective size ANY panel at ``acc``/``correlation`` can reach.

    Under the shared-shock mixture, panel error floors at ``rho * (1 - acc)``
    no matter how many verifiers are added, so effective size floors with it.
    If this ceiling is below a target, adding reviewers is wasted spend; the
    only moves are raising accuracy or lowering correlation.
    """
    if acc <= 0.5:
        return float("nan")
    if correlation <= 0.0:
        return float("inf")
    return effective_n(correlation * (1.0 - acc), acc, 0.5, nmax=nmax)


# ---------------------------------------------------------------------------
# Input contract.
# ---------------------------------------------------------------------------


def validate_input(data: Any) -> dict[str, Any]:
    """Validate a verdict-matrix document; raise GateAuditInputError otherwise.

    The contract is strict on purpose: a missing verdict is refused rather
    than imputed, because every imputation rule silently changes the measured
    correlation structure the audit exists to report.
    """
    if not isinstance(data, dict):
        raise GateAuditInputError("input must be a JSON object")

    gate_id = data.get("gate_id")
    if not isinstance(gate_id, str) or not gate_id:
        raise GateAuditInputError("'gate_id' must be a non-empty string")

    evidence_class = data.get("evidence_class")
    if evidence_class not in EVIDENCE_CLASSES:
        raise GateAuditInputError(
            "'evidence_class' must be declared as 'synthetic' or 'observed'; "
            "an audit report must never guess its own evidence status")

    quorum = data.get("quorum", 0.5)
    if not isinstance(quorum, (int, float)) or not (0.0 <= quorum < 1.0):
        raise GateAuditInputError("'quorum' must be a number in [0, 1)")

    candidates = data.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        raise GateAuditInputError("'candidates' must be a non-empty list")
    seen_c: set[str] = set()
    for cand in candidates:
        if not isinstance(cand, dict):
            raise GateAuditInputError("each candidate must be an object")
        cid = cand.get("id")
        if not isinstance(cid, str) or not cid:
            raise GateAuditInputError("candidate 'id' must be a non-empty string")
        if cid in seen_c:
            raise GateAuditInputError(f"duplicate candidate id: {cid!r}")
        seen_c.add(cid)
        if cand.get("ground_truth") not in VERDICTS:
            raise GateAuditInputError(
                f"candidate {cid!r}: 'ground_truth' must be 'accept' or 'reject'")
        probe = cand.get("probe", False)
        if not isinstance(probe, bool):
            raise GateAuditInputError(f"candidate {cid!r}: 'probe' must be boolean")
        if probe and cand.get("ground_truth") != "reject":
            raise GateAuditInputError(
                f"candidate {cid!r}: probes are seeded KNOWN-BAD candidates and "
                "must carry ground_truth 'reject'")
        if probe and "probe_kind" in cand and (
                not isinstance(cand["probe_kind"], str) or not cand["probe_kind"]):
            raise GateAuditInputError(
                f"candidate {cid!r}: 'probe_kind' must be a non-empty string")

    verifiers = data.get("verifiers")
    if not isinstance(verifiers, list) or not verifiers:
        raise GateAuditInputError("'verifiers' must be a non-empty list")
    seen_v: set[str] = set()
    for ver in verifiers:
        if not isinstance(ver, dict):
            raise GateAuditInputError("each verifier must be an object")
        vid = ver.get("id")
        if not isinstance(vid, str) or not vid:
            raise GateAuditInputError("verifier 'id' must be a non-empty string")
        if vid in seen_v:
            raise GateAuditInputError(f"duplicate verifier id: {vid!r}")
        seen_v.add(vid)
        verdicts = ver.get("verdicts")
        if not isinstance(verdicts, dict):
            raise GateAuditInputError(f"verifier {vid!r}: 'verdicts' must be an object")
        missing = seen_c - set(verdicts)
        if missing:
            raise GateAuditInputError(
                f"verifier {vid!r} is missing verdicts for candidates "
                f"{sorted(missing)}; the matrix must be complete")
        extra = set(verdicts) - seen_c
        if extra:
            raise GateAuditInputError(
                f"verifier {vid!r} has verdicts for unknown candidates "
                f"{sorted(extra)}")
        for cid, verdict in verdicts.items():
            if verdict not in VERDICTS:
                raise GateAuditInputError(
                    f"verifier {vid!r}, candidate {cid!r}: verdict must be "
                    "'accept' or 'reject'")
    return data


# ---------------------------------------------------------------------------
# The audit itself.
# ---------------------------------------------------------------------------


def _panel_accepts(accept_votes: int, total: int, quorum: float) -> bool:
    """Strictly-greater-than-quorum acceptance; a tie at the default 0.5 rejects."""
    return accept_votes > quorum * total


def _finite_or_none(value: float) -> float | None:
    return value if math.isfinite(value) else None


def audit(data: dict[str, Any]) -> dict[str, Any]:
    """Compute a gate-audit report from a validated verdict matrix.

    Headline panel statistics use only non-probe candidates so that the seeded
    probe set cannot inflate or deflate the measured accuracy/correlation it
    is supposed to stress-test. Probes get their own section.
    """
    validate_input(data)

    quorum = float(data.get("quorum", 0.5))
    candidates = data["candidates"]
    verifiers = data["verifiers"]
    non_probe = [c for c in candidates if not c.get("probe", False)]
    probes = [c for c in candidates if c.get("probe", False)]
    truth = {c["id"]: c["ground_truth"] for c in candidates}

    warnings: list[str] = []
    if len(non_probe) < 2:
        raise GateAuditInputError(
            "at least two non-probe candidates are required; panel statistics "
            "from fewer are not meaningful")

    # Per-verifier accuracy and error vectors over non-probe candidates.
    verifier_rows = []
    error_vectors: dict[str, list[int]] = {}
    for ver in verifiers:
        errors = [
            0 if ver["verdicts"][c["id"]] == truth[c["id"]] else 1
            for c in non_probe
        ]
        error_vectors[ver["id"]] = errors
        accuracy = 1.0 - sum(errors) / len(errors)
        verifier_rows.append({
            "id": ver["id"],
            "accuracy": accuracy,
            "errors": sum(errors),
        })
        if accuracy <= 0.5:
            warnings.append(
                f"verifier {ver['id']!r} does not discriminate above chance "
                f"(accuracy {accuracy:.4f}); its vote adds no evidence (E016)")

    mean_accuracy = statistics.fmean(row["accuracy"] for row in verifier_rows)

    # Pairwise error correlation.
    pair_values: list[float] = []
    skipped_pairs = 0
    for a, b in itertools.combinations(error_vectors, 2):
        value = phi(error_vectors[a], error_vectors[b])
        if math.isnan(value):
            skipped_pairs += 1
        else:
            pair_values.append(value)
    mean_rho = statistics.fmean(pair_values) if pair_values else None
    if len(verifiers) >= 2 and not pair_values:
        warnings.append(
            "no verifier pair had variance in both error vectors; pairwise "
            "correlation is unmeasurable on this candidate set")

    # Panel decision per non-probe candidate.
    n_verifiers = len(verifiers)
    false_accepts = 0
    false_rejects = 0
    n_bad = sum(1 for c in non_probe if c["ground_truth"] == "reject")
    n_good = len(non_probe) - n_bad
    for cand in non_probe:
        accept_votes = sum(
            1 for ver in verifiers if ver["verdicts"][cand["id"]] == "accept")
        accepted = _panel_accepts(accept_votes, n_verifiers, quorum)
        if accepted and cand["ground_truth"] == "reject":
            false_accepts += 1
        if not accepted and cand["ground_truth"] == "accept":
            false_rejects += 1
    panel_error = (false_accepts + false_rejects) / len(non_probe)

    # Effective votes: measured, heuristic, and ceiling.
    measured_eff = effective_n(panel_error, mean_accuracy, quorum)
    if math.isnan(measured_eff):
        warnings.append(
            "mean verifier accuracy is at or below 0.5; effective votes are "
            "undefined because the panel does not discriminate")
    heuristic = (heuristic_effective_n(n_verifiers, mean_rho)
                 if mean_rho is not None and mean_rho > 0.0 else None)
    ceiling = (effective_n_ceiling(mean_accuracy, mean_rho)
               if mean_rho is not None else None)
    if (heuristic is not None and ceiling is not None
            and math.isfinite(ceiling) and heuristic > ceiling):
        warnings.append(
            f"the N/(1+(N-1)rho) heuristic promises {heuristic:.2f} effective "
            f"votes but the accuracy-dependent ceiling is {ceiling:.2f}; the "
            "heuristic is optimistic for this panel (E015)")

    # Probe section: seeded known-bad candidates run through the same rule.
    probe_section = None
    if probes:
        by_kind: dict[str, dict[str, int]] = {}
        breached = 0
        for cand in probes:
            accept_votes = sum(
                1 for ver in verifiers if ver["verdicts"][cand["id"]] == "accept")
            hit = _panel_accepts(accept_votes, n_verifiers, quorum)
            kind = cand.get("probe_kind", "unspecified")
            bucket = by_kind.setdefault(kind, {"total": 0, "breached": 0})
            bucket["total"] += 1
            if hit:
                bucket["breached"] += 1
                breached += 1
        probe_section = {
            "total": len(probes),
            "breached": breached,
            "breach_rate": breached / len(probes),
            "by_kind": {k: by_kind[k] for k in sorted(by_kind)},
        }
        if breached:
            warnings.append(
                f"{breached}/{len(probes)} seeded known-bad probes were "
                "accepted by the panel")

    canonical = json.dumps(data, sort_keys=True, separators=(",", ":"))
    report = {
        "schema": SCHEMA_ID,
        "gate_id": data["gate_id"],
        "evidence_class": data["evidence_class"],
        "inputs": {
            "candidates": len(candidates),
            "non_probe_candidates": len(non_probe),
            "probe_candidates": len(probes),
            "verifiers": n_verifiers,
            "known_good": n_good,
            "known_bad": n_bad,
        },
        "verifiers": verifier_rows,
        "panel": {
            "quorum": quorum,
            "nominal_votes": n_verifiers,
            "mean_verifier_accuracy": mean_accuracy,
            "mean_pairwise_error_correlation": mean_rho,
            "skipped_correlation_pairs": skipped_pairs,
            "error": panel_error,
            "false_accept_rate": (false_accepts / n_bad) if n_bad else None,
            "false_reject_rate": (false_rejects / n_good) if n_good else None,
            "effective_votes": _finite_or_none(measured_eff),
            "heuristic_n_eff": heuristic,
            "effective_votes_ceiling": (
                None if ceiling is None else
                ("unbounded" if math.isinf(ceiling) else ceiling)),
        },
        "probes": probe_section,
        "warnings": warnings,
        "provenance": {
            "tool": "idkmesh gate-audit",
            "tool_version": _tool_version(),
            "input_digest_sha256": hashlib.sha256(
                canonical.encode("utf-8")).hexdigest(),
        },
    }
    return report


def _tool_version() -> str:
    from idkmesh import __version__

    return __version__


# ---------------------------------------------------------------------------
# Rendering.
# ---------------------------------------------------------------------------


def _fmt(value: Any, digits: int = 4) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, str):
        return value
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def render_markdown(report: dict[str, Any]) -> str:
    """Render a report as the human summary posted next to the JSON evidence."""
    panel = report["panel"]
    lines = [
        f"# Gate audit: {report['gate_id']}",
        "",
        f"Evidence class: **{report['evidence_class']}** · "
        f"input digest `sha256:{report['provenance']['input_digest_sha256'][:12]}…` · "
        f"idkmesh {report['provenance']['tool_version']}",
        "",
        f"**{panel['nominal_votes']} verifiers ≈ "
        f"{_fmt(panel['effective_votes'], 2)} effective independent votes.**",
        "",
        "| Panel metric | Value |",
        "|---|---|",
        f"| Mean verifier accuracy | {_fmt(panel['mean_verifier_accuracy'])} |",
        f"| Mean pairwise error correlation | "
        f"{_fmt(panel['mean_pairwise_error_correlation'])} |",
        f"| Panel error (quorum {panel['quorum']}) | {_fmt(panel['error'])} |",
        f"| False-accept rate | {_fmt(panel['false_accept_rate'])} |",
        f"| False-reject rate | {_fmt(panel['false_reject_rate'])} |",
        f"| Effective votes (measured) | {_fmt(panel['effective_votes'], 2)} |",
        f"| Effective-vote ceiling at this accuracy/correlation | "
        f"{_fmt(panel['effective_votes_ceiling'], 2)} |",
        f"| N/(1+(N-1)ρ) heuristic (for contrast; unreliable) | "
        f"{_fmt(panel['heuristic_n_eff'], 2)} |",
    ]
    probes = report["probes"]
    if probes is not None:
        lines += [
            "",
            "## Seeded probes",
            "",
            f"{probes['breached']}/{probes['total']} known-bad probes were "
            f"accepted (breach rate {_fmt(probes['breach_rate'])}).",
        ]
        if probes["by_kind"]:
            lines += ["", "| Probe kind | Breached / total |", "|---|---|"]
            for kind, bucket in probes["by_kind"].items():
                lines.append(
                    f"| {kind} | {bucket['breached']} / {bucket['total']} |")
    if report["warnings"]:
        lines += ["", "## Warnings", ""]
        lines += [f"- {w}" for w in report["warnings"]]
    lines += [
        "",
        "---",
        "",
        "This report is decision support, not acceptance authority: "
        "worker success ≠ acceptance, verification recommendation ≠ merge "
        "authority.",
        "",
    ]
    return "\n".join(lines)


def audit_file(input_path: str | Path) -> dict[str, Any]:
    """Load, validate, and audit one verdict-matrix JSON file."""
    path = Path(input_path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise GateAuditInputError(f"{path}: not valid JSON ({exc})") from exc
    return audit(data)
