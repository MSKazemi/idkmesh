---
description: "The fail-closed security profile a non-loopback or multi-user IDKMesh API must satisfy, the enforcement library that implements its checks, and exactly what is and is not enforced by a served listener."
---
# Network API Security Profile v0.1

**Status:** library and validation implemented; **not wired into any served listener**  
**Issue:** #743 (API-8); parent #713; identity owner #670  
**Code:** `idkmesh/network_api_profile.py`, `tests/test_network_api_profile.py`  
**Authority:** declares and checks policy. It authenticates nobody by itself, grants no authority and starts no server.

## What this is, and is not

The Control Tower served today is a loopback, read-only service whose session token
is a local boundary, not an identity ([Control Tower Local API](CONTROL_TOWER_LOCAL_API_V0_1.md),
[API Authority Matrix](API_AUTHORITY_MATRIX_V0_1.md)). **No localhost session token
is, or may be treated as, authentication for a public or multi-user service.**

This document and `idkmesh.network_api_profile` define the checks a network
listener must run before it may serve a non-loopback request. The module is a
dependency-free library. Nothing in the repository binds a non-loopback socket,
terminates TLS, resolves an `ActorContext` from a credential, or calls these
checks per request. Enabling a network-facing endpoint on the strength of this
module alone would be wrong; the missing pieces are listed under
[Not implemented](#not-implemented).

## Declared profile (`parse_network_profile`)

A profile is a strict JSON object (`kind: idkmesh-network-api-profile`,
`schema_version: "0.1"`); unknown or missing fields are errors. Validation is
fail-closed and raises `NetworkProfileError` with a stable `code`.

| Requirement | Loopback bind | Non-loopback bind |
|---|---|---|
| bind host | `127.0.0.0/8`, `::1`, `localhost` | any other IP, wildcard (`0.0.0.0`, `::`) or host name (names are never resolved, so they are non-loopback) |
| TLS | `loopback_plaintext` or `trusted_proxy_terminated` | **`trusted_proxy_terminated` only** (`tls_required`); in-process TLS is not implemented and is refused |
| trusted proxies | only with `trusted_proxy_terminated` | at least one CIDR/IP; a range covering the whole address space is refused |
| authentication adapter | `local_session_token` allowed | `oidc`, `mtls`, `github_app` or `service_token`; `local_session_token` is refused by name (`session_token_not_authentication`) |
| credential transport | `authorization_header` only | `authorization_header` only (ambient cookies would need a CSRF-token design and are refused) |
| Host allowlist | optional | **required**, exact lowercase DNS names, no wildcards |
| CORS origins | default none | default none; each entry an exact `https://host[:port]`; `*`, `null`, `http:` and paths refused |
| secrets | no literal secrets | token registry given only as a reference (`env:`, `github_actions:`, `vault:`, `external_secret_manager:`); a literal value is refused |
| body and rate limits | required, bounded (body at most 8 MiB; rates and key table capped) | same |
| audit | `record_denials` must be `true` | same |
| break-glass | cannot be enabled | cannot be enabled (not implemented) |

A valid profile is declared input. It is not evidence that a proxy, certificate or
identity provider exists.

## Per-request checks

`NetworkRequestGuard` (stateless, built from one validated profile):

- **Peer trust.** With a TLS-terminating proxy, a direct connection from outside the
  trusted proxy ranges is refused (`untrusted_peer`), so TLS cannot be bypassed.
- **Client address.** `X-Forwarded-For` is honoured only from a trusted proxy and is
  walked right to left; the first non-proxy hop is the client, so a client cannot
  prepend a forged address. Malformed addresses and chains over 16 hops are refused.
- **Host header.** Exact match against the allowlist; unnormalized, list-valued or
  missing values are refused.
- **Origin / CORS / CSRF.** Cross-origin access is denied unless the Origin is
  allowlisted; `Origin: null`, plain `http` and a declared `cross-site` fetch without
  an allowed Origin are refused. Allowed responses name the exact origin with
  `Vary: Origin`, never `*`, and never `Allow-Credentials`. Credentials travel only
  in the `Authorization` header, so a browser cannot attach them ambiently.
- **Framing (request-smuggling assumptions).** The backend rejects, rather than
  reinterprets, every `Transfer-Encoding`, a repeated or list-valued
  `Content-Length`, signs, whitespace, non-ASCII digits and over-limit sizes. A
  front proxy must forward only one well-formed `Content-Length` and no
  `Transfer-Encoding`; the backend does not rely on that.

## Credentials (`ServiceTokenVerifier`)

- Only SHA-256 digests are stored; tokens come from `new_service_token()`
  (`secrets.token_urlsafe(32)`), and at least 32 characters are required on the wire.
- Verification compares the presented digest against **every** record with
  `hmac.compare_digest` and no early exit, then judges the match, so timing does not
  depend on which record matched. Unknown and malformed credentials share one error
  (`invalid_credentials`).
- Each record has a validity window and the verifier enforces the profile's maximum
  lifetime. **Rotation** is an overlap of two records for one principal; **revocation**
  returns a new verifier with the record marked revoked and takes effect on the next
  `authenticate` call. Distributing a revoked verifier to every process is the
  deployer's responsibility and is not implemented.
- A successful result is a `TokenAuthentication` (token id, principal id, expiry). It
  holds no token material and is **not** an `ActorContext`; roles, scopes and
  identity revision must come from the trusted identity adapter (#670).

## Rate limiting (`RateLimiter`)

Token buckets, keyed `p:<principal>` for authenticated callers and `ip:<client
address>` otherwise (`rate_limit_key`), with a stricter anonymous quota. The key table
is capped. When it is full, only fully refilled buckets are evicted; if none are, a
new key is refused (`rate_limiter_saturated`), so flooding distinct source addresses
cannot reset another caller's limit. The caller supplies the clock. State is
per-process: it is not shared across replicas.

## Authorization and audit

`SCOPE_ACTIONS` maps the endpoint scope vocabulary onto the enterprise authorization
kernel. `authorize_scope` evaluates a mapped scope through `enterprise_authz.authorize`
(tenant/project binding, role, actor type, revocation, expiry and separation of duties
all stay in the kernel). `append_authorization_audit` writes every decision, denials
included, to the tamper-evident `LocalEnterpriseAuditLedger`.

| Scope | Kernel action |
|---|---|
| `evidence:read`, `runs:read`, `connectors:read` | `read` |
| `connectors:dispatch` | `dispatch` |
| `decisions:write` | none: the kernel has no such action (#740); denied (`scope_not_defined`) |
| `integration:propose`, `integration:execute` | none: ambiguous between the kernel's `execute` and `integrate`; denied rather than guessed |

## Not implemented

These remain open on #743 and are not claimed:

- a listener that calls these checks, and a production HTTP adapter;
- an authentication adapter that turns a verified credential into an `ActorContext`
  (OIDC/mTLS/GitHub App) and propagates it to application services;
- real TLS termination, certificate management and proxy hardening; the profile only
  records the assumption, and the framing checks only bound the backend's side;
- distribution of revocation and rate-limit state across processes;
- break-glass and the human adoption decision for the
  [proposed authority matrix](API_AUTHORITY_MATRIX_V0_1.md);
- `decisions:write` and `integration:*` kernel actions;
- tenant partitioning of the store and per-tenant event streams.
