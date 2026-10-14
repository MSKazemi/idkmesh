"""Machine-readable SLO contract and offline evaluators for the local API.

Issue #744. ``API_OBSERVABILITY_V0_1.md`` documents the local-profile SLO and
alert targets in prose; this module pins the same numbers as data
(:func:`default_slo_contract`), validates a contract fail-closed
(:func:`validate_slo_contract`) and applies it to results of the existing
same-process interval evaluator
(:func:`idkmesh.otel_metrics.evaluate_api_metrics_interval`).

Everything here is a pure function: no clock reads, no network I/O, no state,
no alert delivery. The targets are *operational targets* for the local
single-token profile, not measured product claims. An interval that cannot be
trusted (restart, regression, too short, malformed) is ``unknown``, and
``unknown`` is never read as "met".
"""

from __future__ import annotations

import math
from typing import Any, Mapping, Sequence

from idkmesh.otel_metrics import (
    OtlpMetricsInputError,
    validate_api_metrics_document,
)

SLO_SCHEMA_VERSION = "0.1"
SLO_KIND = "idkmesh-api-slo-contract"
SLO_PROFILE = "local_single_token"

_OBJECTIVE_IDS = (
    "server_error_fraction",
    "latency_within_1000ms_fraction",
    "overload_rejections",
)
_SATURATION_IDS = ("api_concurrency_hot", "sse_saturation")
_MAX_CONSECUTIVE = 16
_MAX_WINDOW_SECONDS = 86_400
_AUTHORITY_FLAGS = ("canonical_state_write", "git_push", "merge", "pages_deploy")


class SloContractError(ValueError):
    """The SLO contract is malformed or relaxes a fixed safety property."""


def default_slo_contract() -> dict[str, Any]:
    """Return a fresh copy of the documented local-profile SLO contract."""
    return {
        "schema_version": SLO_SCHEMA_VERSION,
        "kind": SLO_KIND,
        "profile": SLO_PROFILE,
        "claim": "operational_target_not_measured_result",
        "window_seconds": 300,
        "objectives": [
            {
                "id": "server_error_fraction",
                "comparison": "less_than",
                "threshold": 0.01,
            },
            {
                "id": "latency_within_1000ms_fraction",
                "comparison": "at_least",
                "threshold": 0.95,
                "latency_bound_ms": 1000.0,
            },
            {
                "id": "overload_rejections",
                "comparison": "at_most",
                "threshold": 0,
                "alert_after_consecutive_intervals": 2,
            },
        ],
        "saturation_alerts": [
            {
                "id": "api_concurrency_hot",
                "comparison": "at_least",
                "threshold": 0.8,
                "for_seconds": 300,
            },
            {
                "id": "sse_saturation",
                "comparison": "at_least",
                "threshold": 1.0,
                "for_seconds": 0,
            },
        ],
        "authority": {flag: False for flag in _AUTHORITY_FLAGS},
    }


def _exact_keys(obj: Any, keys: set[str], field: str) -> Mapping[str, Any]:
    if not isinstance(obj, Mapping):
        raise SloContractError(f"{field} must be an object")
    if set(obj) != keys:
        raise SloContractError(f"{field} has unexpected or missing fields")
    return obj


def _int(value: Any, field: str, *, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise SloContractError(f"{field} must be an integer")
    if not minimum <= value <= maximum:
        raise SloContractError(f"{field} must be in [{minimum}, {maximum}]")
    return value


def _fraction(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SloContractError(f"{field} must be a number")
    if not math.isfinite(float(value)) or not 0.0 <= float(value) <= 1.0:
        raise SloContractError(f"{field} must be in [0, 1]")
    return float(value)


def validate_slo_contract(contract: Any) -> dict[str, Any]:
    """Validate a contract and return a normalized deep copy.

    The set of objective and alert ids is closed because each id is bound to a
    specific indicator computed by this module; a contract cannot introduce an
    indicator, a label, or any authority.
    """
    top = _exact_keys(
        contract,
        {
            "schema_version", "kind", "profile", "claim", "window_seconds",
            "objectives", "saturation_alerts", "authority",
        },
        "contract",
    )
    if top["schema_version"] != SLO_SCHEMA_VERSION:
        raise SloContractError(f"schema_version must be {SLO_SCHEMA_VERSION!r}")
    if top["kind"] != SLO_KIND:
        raise SloContractError(f"kind must be {SLO_KIND!r}")
    if top["profile"] != SLO_PROFILE:
        raise SloContractError(f"profile must be {SLO_PROFILE!r}")
    if top["claim"] != "operational_target_not_measured_result":
        raise SloContractError(
            "claim must be 'operational_target_not_measured_result'"
        )
    window = _int(
        top["window_seconds"], "window_seconds",
        minimum=1, maximum=_MAX_WINDOW_SECONDS,
    )

    authority = _exact_keys(top["authority"], set(_AUTHORITY_FLAGS), "authority")
    for flag in _AUTHORITY_FLAGS:
        if authority[flag] is not False:
            raise SloContractError(f"authority.{flag} must be false")

    raw_objectives = top["objectives"]
    if not isinstance(raw_objectives, list):
        raise SloContractError("objectives must be a list")
    if [o.get("id") if isinstance(o, Mapping) else None for o in raw_objectives] != list(
        _OBJECTIVE_IDS
    ):
        raise SloContractError(
            f"objectives must be exactly {list(_OBJECTIVE_IDS)} in order"
        )
    objectives: list[dict[str, Any]] = []
    error = _exact_keys(
        raw_objectives[0], {"id", "comparison", "threshold"}, "objectives[0]"
    )
    if error["comparison"] != "less_than":
        raise SloContractError("server_error_fraction comparison must be less_than")
    err_threshold = _fraction(error["threshold"], "objectives[0].threshold")
    if err_threshold <= 0.0:
        raise SloContractError("server_error_fraction threshold must be > 0")
    objectives.append(
        {"id": error["id"], "comparison": "less_than", "threshold": err_threshold}
    )

    latency = _exact_keys(
        raw_objectives[1],
        {"id", "comparison", "threshold", "latency_bound_ms"},
        "objectives[1]",
    )
    if latency["comparison"] != "at_least":
        raise SloContractError(
            "latency_within_1000ms_fraction comparison must be at_least"
        )
    lat_threshold = _fraction(latency["threshold"], "objectives[1].threshold")
    if lat_threshold <= 0.0:
        raise SloContractError("latency threshold must be > 0")
    bound = latency["latency_bound_ms"]
    # The interval evaluator only reports the fixed 1000 ms bucket.
    if isinstance(bound, bool) or not isinstance(bound, (int, float)) or float(bound) != 1000.0:
        raise SloContractError("latency_bound_ms must be 1000.0")
    objectives.append(
        {
            "id": latency["id"],
            "comparison": "at_least",
            "threshold": lat_threshold,
            "latency_bound_ms": 1000.0,
        }
    )

    overload = _exact_keys(
        raw_objectives[2],
        {"id", "comparison", "threshold", "alert_after_consecutive_intervals"},
        "objectives[2]",
    )
    if overload["comparison"] != "at_most":
        raise SloContractError("overload_rejections comparison must be at_most")
    over_threshold = _int(
        overload["threshold"], "objectives[2].threshold", minimum=0, maximum=1_000_000
    )
    consecutive = _int(
        overload["alert_after_consecutive_intervals"],
        "objectives[2].alert_after_consecutive_intervals",
        minimum=1, maximum=_MAX_CONSECUTIVE,
    )
    objectives.append(
        {
            "id": overload["id"],
            "comparison": "at_most",
            "threshold": over_threshold,
            "alert_after_consecutive_intervals": consecutive,
        }
    )

    raw_alerts = top["saturation_alerts"]
    if not isinstance(raw_alerts, list):
        raise SloContractError("saturation_alerts must be a list")
    if [a.get("id") if isinstance(a, Mapping) else None for a in raw_alerts] != list(
        _SATURATION_IDS
    ):
        raise SloContractError(
            f"saturation_alerts must be exactly {list(_SATURATION_IDS)} in order"
        )
    alerts: list[dict[str, Any]] = []
    for index, raw in enumerate(raw_alerts):
        alert = _exact_keys(
            raw,
            {"id", "comparison", "threshold", "for_seconds"},
            f"saturation_alerts[{index}]",
        )
        if alert["comparison"] != "at_least":
            raise SloContractError("saturation alert comparison must be at_least")
        threshold = _fraction(
            alert["threshold"], f"saturation_alerts[{index}].threshold"
        )
        if threshold <= 0.0:
            raise SloContractError("saturation alert threshold must be > 0")
        for_seconds = _int(
            alert["for_seconds"], f"saturation_alerts[{index}].for_seconds",
            minimum=0, maximum=_MAX_WINDOW_SECONDS,
        )
        alerts.append(
            {
                "id": alert["id"],
                "comparison": "at_least",
                "threshold": threshold,
                "for_seconds": for_seconds,
            }
        )

    return {
        "schema_version": SLO_SCHEMA_VERSION,
        "kind": SLO_KIND,
        "profile": SLO_PROFILE,
        "claim": "operational_target_not_measured_result",
        "window_seconds": window,
        "objectives": objectives,
        "saturation_alerts": alerts,
        "authority": {flag: False for flag in _AUTHORITY_FLAGS},
    }


def _unknown(reason: str) -> dict[str, Any]:
    return {"status": "unknown", "reason": reason, "authority": "none"}


def _interval_fields(interval: Any) -> tuple[int, int, int, float, float] | None:
    """Return validated interval fields, or None if the interval is unusable."""
    if not isinstance(interval, Mapping) or interval.get("status") != "measured":
        return None
    if interval.get("authority") != "none":
        return None

    def count(key: str) -> int | None:
        value = interval.get(key)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            return None
        return value

    def frac(key: str) -> float | None:
        value = interval.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None
        if not math.isfinite(float(value)) or not 0.0 <= float(value) <= 1.0:
            return None
        return float(value)

    requests = count("requests")
    overload = count("overload_rejections")
    nanos = count("interval_nanoseconds")
    errors = frac("server_error_fraction")
    fast = frac("within_1000ms_fraction")
    if None in (requests, overload, nanos, errors, fast) or not requests or not nanos:
        return None
    assert requests is not None and overload is not None and nanos is not None
    assert errors is not None and fast is not None
    return requests, overload, nanos, errors, fast


def evaluate_slo_interval(
    interval: Mapping[str, Any],
    contract: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Judge one measured interval against the SLO objectives.

    ``interval`` is the output of ``evaluate_api_metrics_interval()``. Anything
    that is not a well-formed ``measured`` result, or that covers less than the
    contract window, is ``unknown``. An invalid *contract* raises
    :class:`SloContractError` (a caller bug, not a runtime condition).
    """
    normalized = validate_slo_contract(
        default_slo_contract() if contract is None else contract
    )
    fields = _interval_fields(interval)
    if fields is None:
        return _unknown("interval_not_measured")
    requests, overload, nanos, error_fraction, fast_fraction = fields
    window_nanos = normalized["window_seconds"] * 1_000_000_000
    if nanos < window_nanos:
        return _unknown("interval_shorter_than_window")

    error_obj, latency_obj, overload_obj = normalized["objectives"]
    results = [
        {
            "id": error_obj["id"],
            "state": "met" if error_fraction < error_obj["threshold"] else "breached",
            "observed": error_fraction,
            "threshold": error_obj["threshold"],
        },
        {
            "id": latency_obj["id"],
            "state": "met" if fast_fraction >= latency_obj["threshold"] else "breached",
            "observed": fast_fraction,
            "threshold": latency_obj["threshold"],
        },
        {
            "id": overload_obj["id"],
            "state": "met" if overload <= overload_obj["threshold"] else "breached",
            "observed": overload,
            "threshold": overload_obj["threshold"],
        },
    ]
    return {
        "status": "evaluated",
        "authority": "none",
        "requests": requests,
        "interval_seconds": nanos / 1_000_000_000,
        "objectives": results,
        "all_met": all(item["state"] == "met" for item in results),
    }


def evaluate_overload_alert(
    intervals: Sequence[Mapping[str, Any]],
    contract: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Fire only if the latest N consecutive intervals all breached overload.

    ``intervals`` are ``evaluate_api_metrics_interval()`` results, oldest
    first. Fewer than N intervals, or any of the latest N being unknown, is
    ``unknown`` rather than "not firing".
    """
    normalized = validate_slo_contract(
        default_slo_contract() if contract is None else contract
    )
    needed = normalized["objectives"][2]["alert_after_consecutive_intervals"]
    if isinstance(intervals, (str, bytes)) or not isinstance(intervals, Sequence):
        return _unknown("intervals_not_a_sequence")
    if len(intervals) < needed:
        return _unknown("not_enough_intervals")
    states = []
    for interval in intervals[-needed:]:
        judged = evaluate_slo_interval(interval, normalized)
        if judged["status"] != "evaluated":
            return _unknown(judged["reason"])
        states.append(judged["objectives"][2]["state"])
    return {
        "status": "evaluated",
        "authority": "none",
        "alert": "api_overloaded",
        "firing": all(state == "breached" for state in states),
        "consecutive_intervals": needed,
    }


def evaluate_saturation_conditions(
    document: Mapping[str, Any],
    contract: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Evaluate point-in-time saturation from one canonical metrics snapshot.

    Sustained duration (``for_seconds``) is reported but *not* evaluated: one
    snapshot cannot show how long a gauge stayed high, so a collector must
    apply the duration. ``condition_met`` is therefore necessary, not
    sufficient, for the documented alert to fire.
    """
    normalized = validate_slo_contract(
        default_slo_contract() if contract is None else contract
    )
    try:
        canonical = validate_api_metrics_document(document)
    except OtlpMetricsInputError:
        # Never reflect malformed fields: they may contain private payloads.
        return _unknown("invalid_snapshot")
    concurrency = canonical["concurrency"]
    observed = {
        "api_concurrency_hot": (
            concurrency["in_flight_requests"] / concurrency["max_concurrent_requests"]
        ),
        "sse_saturation": (
            concurrency["event_stream_clients"]
            / concurrency["max_event_stream_clients"]
        ),
    }
    conditions = [
        {
            "id": alert["id"],
            "condition_met": observed[alert["id"]] >= alert["threshold"],
            "observed_fraction": observed[alert["id"]],
            "threshold": alert["threshold"],
            "for_seconds": alert["for_seconds"],
            "duration_evaluated": False,
        }
        for alert in normalized["saturation_alerts"]
    ]
    return {"status": "evaluated", "authority": "none", "conditions": conditions}
