# Python API client integration check matrix

**Issue:** #746. **Status:** bounded multi-page run helper implemented; further test fixtures and web client pending.

The dependency-free ControlTowerClient supports local-only read and inspection.
The human-decision mutation is intentionally absent pending issue #740.
A caller must not infer remote or multi-user authorization from a local token.

## Required compatibility fixtures
| Scenario | Required result |
| --- | --- |
| loopback URI | explicit timeouts, one request per method |
| non-loopback URI | fail before network or credential disclosure |
| redirect response | do not follow; surface protocol error |
| invalid content digest | integrity error; never return trusted evidence |
| malformed JSON / duplicate key | protocol error |
| wrong resource ID in response | protocol error |
| unsupported OpenAPI marker | protocol error |
| cursor returned by server | caller echoes opaque cursor; never decodes |
| missing server request ID | protocol error |
| server HTTP error envelope | stable response taxonomy with request ID |
| POST inspection | never retry, even under a `RetryPolicy`; does not record human decision |
| retry policy | opt-in only; idempotent GET; transport and `retryable` 429/502/503/504 only; bounded, deterministic, no jitter |
| redirect to another host | not followed; the token is never sent to the redirect target (real two-server test) |

## Graduation evidence
Exercise each fixture against a deterministic fake HTTP server, not a live
credentialed provider. Verify response metadata and stable exception types,
and retain exact source revision plus test command/output in the PR.
Regenerate typed web client only after API v1 schema/read surface is stable.

**Remaining:** TypeScript client, actual documentation publication and
human-decision method after authorized server implementation.


## Bounded run pagination (implemented)

`ControlTowerClient.collect_run_pages(max_pages=3, limit=50, state=None, project_id=None)`
collects multiple `list_runs` pages using **opaque cursors**. Its mandatory
page cap is validated before I/O (maximum 100). Each result retains its own
request ID and response digest. Repeated cursors, exhausted budgets, invalid
parameters or server errors raise typed exceptions rather than returning
misleading partial success; the helper never retries or writes.

`iter_run_pages(...)` and `iter_runs(...)` are the lazy forms of the same walk:
one HTTP read per page, nothing fetched until iterated, the same page cap and
replay refusal, and pages already yielded stay valid if a later page raises.
`collect_run_pages` is the all-or-nothing tuple over `iter_run_pages`.

**Important:** this is not a transactional snapshot. Concurrent changes may
affect later pages. Single-page reads should still use `list_runs` directly.
Three-page HTTP, cap, replay and pre-network validation regression tests are
part of this slice. No TypeScript SDK or human-decision write API is claimed.
