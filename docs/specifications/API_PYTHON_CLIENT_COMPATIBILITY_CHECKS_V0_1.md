# Python API client integration check matrix

**Issue:** #746. **Status:** test design, no client behavior modified.

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
| POST inspection | never retry implicitly; does not record human decision |

## Graduation evidence
Exercise each fixture against a deterministic fake HTTP server, not a live
credentialed provider. Verify response metadata and stable exception types,
and retain exact source revision plus test command/output in the PR.
Regenerate typed web client only after API v1 schema/read surface is stable.

**Remaining:** TypeScript client, actual documentation publication and
human-decision method after authorized server implementation.
