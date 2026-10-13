# API observability interval validation v0.1

**Issue:** #744. **Scope:** operator guidance only; interval diagnostic implemented; no alert daemon or live measurements.

The currently implemented ApiMetrics counters cover the lifetime of one API
process. A telemetry consumer must not calculate error rate or latency by
subtracting cumulative counters across restarts. An interval is comparable
only with a collector-trusted shared process identity, exact service/schema
and ordered scrape timestamps.

## Safe interval algorithm

1. Validate both metrics snapshots against their frozen schema and privacy
   boundary before using them.
2. Reject missing process identity, inconsistent bucket boundaries, decreased
   counters, inverted timestamps and changed service identity as UNKNOWN.
3. Derive requests, 5xx and overload increments by subtraction.
4. Obtain the <=1000ms latency count from the cumulative histogram bucket.
5. If the request increment is zero, error and slow fractions are UNKNOWN.
6. Otherwise derive the 5xx fraction and slow fraction over exactly the same
   observation interval, and compare with the nonbinding operational targets
   in docs/specifications/API_OBSERVABILITY_V0_1.md.
7. Require multiple valid consecutive windows before announcing sustained
   degradation. A 4xx alone is not an internal server error.
8. Record metric coverage gaps separately rather than declaring the API healthy.

## Privacy and no-authority guarantee
Do not export caller-controlled paths, query strings, IDs, auth headers,
prompts, raw evidence or secrets as metric labels. The decision is an
operator alert, never a WorkUnit routing/dispatch or integration decision.

## Missing implementation
The API does not yet publish a guaranteed collector-attested process identity nor ship an alert daemon. A future implementation must provide
them and test counter resets, histogram changes, missing scrapes, zero traffic
and malformed snapshots before claiming a working alert.


## Pure interval diagnostic

`idkmesh.otel_metrics.evaluate_api_metrics_interval(before, after, before_process_identity=..., after_process_identity=..., before_time_unix_nano=..., after_time_unix_nano=...)` compares two already-collected, validated metrics snapshots. It reports counted requests, 5xx fraction, fraction of requests no slower than 1000 ms and overload rejections. It returns a fixed reason code and status `unknown` for restarts, invalid documents, regressed counters, zero traffic or timestamp inconsistencies, never false-green success. The caller must supply a trusted process identity; the local service does **not** currently expose one. An alerting collector and rolling-window policy remain unimplemented.
