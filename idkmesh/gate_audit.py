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


_JSON_TYPE_NAMES = {
    dict: "an object", list: "an array", str: "a string", bool: "a boolean",
    int: "a number", float: "a number", type(None): "null",
}


def _type_name(value: Any) -> str:
    """Name a value's JSON type, so an error can say what arrived instead.

    An empty string gets its own wording: "must be a non-empty string, got a
    string" is a riddle rather than a diagnosis.
    """
    if isinstance(value, str) and not value:
        return "an empty string"
    return _JSON_TYPE_NAMES.get(type(value), type(value).__name__)


def _required(container: dict[str, Any], key: str, hint: str,
              where: str = "") -> Any:
    """Fetch a required key, distinguishing "absent" from "present but wrong".

    A first malformed matrix is almost always a missing or misspelled key, and
    a bare "'gate_id' must be a non-empty string" does not say which of the
    two happened.
    """
    if key not in container:
        prefix = f"{where}: " if where else ""
        raise GateAuditInputError(
            f"{prefix}missing required key {key!r}; {hint}")
    return container[key]


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


def effective_n_table_max(nmax: int = 201) -> int:
    """Largest panel size ``effective_n`` compares against.

    ``effective_n`` interpolates within a table of odd sizes below ``nmax``.
    A measured error at or below the table's smallest entry pins the answer
    only as "at least this", so reports have to say which of the two they are
    carrying.
    """
    return max(n for n in range(1, nmax, 2))


def resolved_effective_votes(measured: float, nominal: int) -> float | None:
    """Clamp an effective-vote estimate to the votes actually cast.

    ``effective_n`` answers "what independent panel size reproduces this
    error". For a near-independent panel that made no errors on the audited
    set the answer runs off the top of its table, and a 50-verifier panel
    came back as 199 effective independent votes -- a table edge presented as
    a measurement, in the one sentence the report exists to say. A panel is
    never worth more independent votes than it cast, so the headline is capped
    at the nominal count and the raw estimate is described in a warning.
    """
    if not math.isfinite(measured):
        return None
    return min(measured, float(nominal))


# ---------------------------------------------------------------------------
# Input contract.
# ---------------------------------------------------------------------------


def validate_input(data: Any) -> dict[str, Any]:
    """Validate a verdict-matrix document; raise GateAuditInputError otherwise.

    The contract is strict on purpose: a missing verdict is refused rather
    than imputed, because every imputation rule silently changes the measured
    correlation structure the audit exists to report. Every rule the
    specification lists is checked here, so a caller using this function as a
    pre-flight check sees exactly what the audit would refuse.
    """
    if not isinstance(data, dict):
        raise GateAuditInputError(
            f"input must be a JSON object, got {_type_name(data)}")

    gate_id = _required(
        data, "gate_id", "a non-empty string naming the audited gate")
    if not isinstance(gate_id, str) or not gate_id:
        raise GateAuditInputError(
            f"'gate_id' must be a non-empty string, got {_type_name(gate_id)}")

    if "evidence_class" not in data:
        raise GateAuditInputError(
            "missing required key 'evidence_class'; declare 'synthetic' or "
            "'observed' - an audit report must never guess its own evidence "
            "status")
    if data["evidence_class"] not in EVIDENCE_CLASSES:
        raise GateAuditInputError(
            "'evidence_class' must be declared as 'synthetic' or 'observed'; "
            "an audit report must never guess its own evidence status")

    quorum = data.get("quorum", 0.5)
    # ``bool`` is a subclass of ``int``, so an unguarded isinstance check let
    # ``"quorum": false`` through as the quorum 0.0 - a rule under which one
    # accept vote carries the panel.
    if isinstance(quorum, bool) or not isinstance(quorum, (int, float)):
        raise GateAuditInputError(
            f"'quorum' must be a number in [0, 1), got {_type_name(quorum)}")
    if not math.isfinite(quorum) or not (0.0 <= quorum < 1.0):
        raise GateAuditInputError(
            f"'quorum' must be a number in [0, 1), got {quorum!r}")

    candidates = _required(
        data, "candidates",
        "a non-empty list of candidate objects, each with 'id' and "
        "'ground_truth'")
    if not isinstance(candidates, list) or not candidates:
        raise GateAuditInputError(
            f"'candidates' must be a non-empty list, got "
            f"{_type_name(candidates)}")
    seen_c: set[str] = set()
    non_probe_count = 0
    for index, cand in enumerate(candidates):
        # Positional labels matter: in a matrix with hundreds of rows, an error
        # about an absent 'id' has no id to name itself with.
        where = f"candidate #{index + 1}"
        if not isinstance(cand, dict):
            raise GateAuditInputError(
                f"{where} must be a JSON object, got {_type_name(cand)}")
        cid = _required(
            cand, "id", "a non-empty string identifying the candidate", where)
        if not isinstance(cid, str) or not cid:
            raise GateAuditInputError(
                f"{where}: 'id' must be a non-empty string, got "
                f"{_type_name(cid)}")
        if cid in seen_c:
            raise GateAuditInputError(f"duplicate candidate id: {cid!r}")
        seen_c.add(cid)
        ground_truth = _required(
            cand, "ground_truth",
            "it must be 'accept' or 'reject' - the audit measures a panel "
            "against known answers, so a candidate with no ground truth "
            "cannot be audited",
            f"candidate {cid!r}")
        if ground_truth not in VERDICTS:
            raise GateAuditInputError(
                f"candidate {cid!r}: 'ground_truth' must be 'accept' or "
                "'reject'")
        probe = cand.get("probe", False)
        if not isinstance(probe, bool):
            raise GateAuditInputError(
                f"candidate {cid!r}: 'probe' must be boolean, got "
                f"{_type_name(probe)}")
        if probe and ground_truth != "reject":
            raise GateAuditInputError(
                f"candidate {cid!r}: probes are seeded KNOWN-BAD candidates and "
                "must carry ground_truth 'reject'")
        if "probe_kind" in cand:
            if not probe:
                # Refusing this is the point: accepted silently, the candidate
                # joined the headline statistics and the breach report came
                # back empty, which reads as "no probes breached".
                raise GateAuditInputError(
                    f"candidate {cid!r}: 'probe_kind' labels a probe, but this "
                    'candidate is not one; add "probe": true or drop '
                    "'probe_kind'")
            if not isinstance(cand["probe_kind"], str) or not cand["probe_kind"]:
                raise GateAuditInputError(
                    f"candidate {cid!r}: 'probe_kind' must be a non-empty "
                    "string")
        if not probe:
            non_probe_count += 1

    if non_probe_count < 2:
        raise GateAuditInputError(
            "at least two non-probe candidates are required; panel statistics "
            f"from fewer are not meaningful (got {non_probe_count} of "
            f"{len(candidates)} candidates)")

    verifiers = _required(
        data, "verifiers",
        "a non-empty list of verifier objects, each with 'id' and 'verdicts'")
    if not isinstance(verifiers, list) or not verifiers:
        raise GateAuditInputError(
            f"'verifiers' must be a non-empty list, got "
            f"{_type_name(verifiers)}")
    seen_v: set[str] = set()
    for index, ver in enumerate(verifiers):
        where = f"verifier #{index + 1}"
        if not isinstance(ver, dict):
            raise GateAuditInputError(
                f"{where} must be a JSON object, got {_type_name(ver)}")
        vid = _required(
            ver, "id", "a non-empty string identifying the verifier", where)
        if not isinstance(vid, str) or not vid:
            raise GateAuditInputError(
                f"{where}: 'id' must be a non-empty string, got "
                f"{_type_name(vid)}")
        if vid in seen_v:
            raise GateAuditInputError(f"duplicate verifier id: {vid!r}")
        seen_v.add(vid)
        verdicts = _required(
            ver, "verdicts",
            "an object mapping every candidate id to 'accept' or 'reject'",
            f"verifier {vid!r}")
        if not isinstance(verdicts, dict):
            raise GateAuditInputError(
                f"verifier {vid!r}: 'verdicts' must be an object, got "
                f"{_type_name(verdicts)}")
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


def _ceiling_field(ceiling: float | None) -> float | str | None:
    """Render the effective-vote ceiling for JSON, never as a bare ``NaN``.

    ``effective_n_ceiling`` returns NaN for a panel that does not discriminate
    (mean accuracy <= 0.5). Passing that straight into the report produced a
    document containing the bare token ``NaN``: not JSON at all outside
    Python's own permissive parser, and invalid against
    ``gate-audit-report-v0.1``, which admits only a number, ``"unbounded"`` or
    ``null``. ``null`` is the honest value - the same one ``effective_votes``
    already carries for such a panel.
    """
    if ceiling is None or math.isnan(ceiling):
        return None
    return "unbounded" if math.isinf(ceiling) else ceiling


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
    table_max = effective_n_table_max()
    if math.isfinite(measured_eff) and measured_eff >= table_max:
        warnings.append(
            f"measured panel error ({panel_error:.4g}) is at or below what "
            f"{table_max} independent verifiers would achieve, so effective "
            "votes are a lower bound, not a measurement; this candidate set "
            "cannot resolve the panel's independence any further")
    effective_votes = resolved_effective_votes(measured_eff, n_verifiers)
    if effective_votes is not None and measured_eff > effective_votes:
        warnings.append(
            f"the effective-vote estimate ({measured_eff:.2f}) exceeded the "
            f"{n_verifiers} votes actually cast and is reported as "
            f"{n_verifiers}: a panel is never worth more independent votes "
            "than it has verifiers")
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
            "effective_votes": effective_votes,
            "heuristic_n_eff": heuristic,
            "effective_votes_ceiling": _ceiling_field(ceiling),
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


def render_json(report: dict[str, Any], pretty: bool = False) -> str:
    """Serialize a report as strict JSON.

    ``allow_nan=False`` is deliberate. Python's default emits bare ``NaN`` and
    ``Infinity`` tokens that no other JSON parser accepts, so any non-finite
    number that ever reached a report would produce a file the rest of the
    world cannot read. Failing loudly beats shipping that silently.
    """
    return json.dumps(
        report, indent=2 if pretty else None, sort_keys=False,
        allow_nan=False)


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


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """Refuse duplicate object keys instead of silently keeping the last.

    Implementations disagree on duplicates -- last wins, first wins, or a hard
    error -- so a document carrying them has no single meaning, and the input
    digest cannot promise what it says it promises. It is not a cosmetic
    problem: a repeated candidate id inside one ``verdicts`` object silently
    rewrote the verifier accuracy the audit exists to measure.
    """
    seen: dict[str, Any] = {}
    for key, value in pairs:
        if key in seen:
            raise GateAuditInputError(
                f"duplicate JSON key {key!r} in one object; implementations "
                "disagree on which value wins, so the document has no single "
                "meaning")
        seen[key] = value
    return seen


def _reject_json_constant(token: str) -> Any:
    """Refuse Python's JSON extensions (``NaN``, ``Infinity``, ``-Infinity``).

    ``json.loads`` accepts them by default, but no other implementation does.
    Since ``provenance.input_digest_sha256`` promises that a report is bound to
    a reproducible canonicalization of its input, an input only Python can read
    is a digest nobody else can recompute.
    """
    raise GateAuditInputError(
        f"input uses {token}, which is a Python extension and not valid JSON; "
        "a verdict matrix must be standard JSON so its digest is reproducible "
        "by other implementations")


def audit_file(input_path: str | Path) -> dict[str, Any]:
    """Load, validate, and audit one verdict-matrix JSON file.

    Raises ``GateAuditInputError`` for anything wrong with the document's
    encoding, syntax or contract, with the path named so a CI log says which
    file was rejected. Failures to *reach* the file (missing, a directory, not
    readable) stay ``OSError``, which is what they are.

    The text is decoded as ``utf-8-sig`` so a byte-order mark is tolerated:
    Windows editors and PowerShell redirection add one, and the previous
    behaviour was to reject the file with Python's own advice to "decode using
    utf-8-sig" - a remark about the reader, not about the caller's file.
    """
    path = Path(input_path)
    try:
        text = path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError as exc:
        raise GateAuditInputError(
            f"{path}: not UTF-8 text ({exc.reason} at byte {exc.start}); save "
            "the verdict matrix as UTF-8. UTF-16, the default for PowerShell "
            "output redirection, is not readable as JSON") from exc
    try:
        data = json.loads(
            text, parse_constant=_reject_json_constant,
            object_pairs_hook=_reject_duplicate_keys)
    except json.JSONDecodeError as exc:
        raise GateAuditInputError(f"{path}: not valid JSON ({exc})") from exc
    except GateAuditInputError as exc:
        raise GateAuditInputError(f"{path}: {exc}") from exc
    try:
        return audit(data)
    except GateAuditInputError as exc:
        raise GateAuditInputError(f"{path}: {exc}") from exc
