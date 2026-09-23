# IDKMesh API Threat Model v0.1

**Status:** planning baseline  
**Date:** 2026-09-23  
**Program:** #713  
**Network security owner:** #743  
**Qualification owner:** #745

## Purpose

This threat model defines the security questions the API program must answer
before exposing IDKMesh beyond a local loopback development profile.

It does not claim all mitigations are implemented.

## Protected assets

The API must protect:

1. **authority integrity** — no actor gains dispatch, decision, repository-write,
   push, merge, secret, or integration authority implicitly;
2. **evidence integrity** — WorkUnit, ResultManifest, VerificationResult, Run
   Evidence Report, Human Decision Record, event, and digest bindings cannot be
   silently substituted;
3. **identity integrity** — actor/service identity, tenant/project scope, and
   authorization revision cannot be forged or reused after revocation;
4. **secret confidentiality** — provider credentials and secret material never
   become ordinary API payloads or logs;
5. **tenant/project isolation** — one project/principal cannot read or mutate
   another without explicit policy;
6. **availability** — malformed/slow/high-volume clients cannot consume
   unbounded memory, threads, event streams, or downstream provider capacity;
7. **audit integrity** — security-relevant state changes remain attributable,
   immutable, and replayable.

## Deployment profiles and trust boundaries

### Local profile

```text
same-machine browser/client
 -> loopback HTTP
 -> local session token
 -> read-only Control Tower service
 -> local evidence projection
```

Assumptions:

- machine/OS account is not already compromised;
- no public network binding;
- session token is not a user identity;
- browser page and API are same-origin local surfaces.

Threats still considered:

- cross-origin browser request attempts;
- malicious local web page probing localhost;
- Host-header manipulation;
- malformed JSON;
- token injection/leakage;
- memory/thread exhaustion;
- unsafe logging.

### GitHub-first profile

```text
GitHub actor/event
 -> GitHub Actions / app boundary
 -> #598 role/authority
 -> #607 governance/secret controls
 -> Product Spine / connector services
 -> #597 durable GitHub ledger
```

GitHub metadata is evidence about an actor/event only after trusted adapter
validation. Issue text, labels, comments, model output, and PR content are
untrusted data.

### Network/multi-user profile

```text
client/browser/service
 -> TLS termination / trusted proxy
 -> authentication adapter
 -> ActorContext
 -> authorization policy
 -> production HTTP adapter
 -> application service
 -> durable stores / connector adapters
```

This profile requires #670 + #743 before mutating operations are enabled.

## Threat actors

Consider:

- unauthenticated Internet client;
- authenticated but unauthorized user;
- authorized user attempting privilege escalation;
- malicious/compromised worker agent;
- malicious/compromised verifier;
- malicious connector/provider response;
- malicious GitHub issue/PR/webhook content;
- compromised browser origin;
- compromised reverse proxy configuration;
- replaying client;
- concurrent legitimate clients causing races;
- accidental operator misconfiguration;
- compromised dependency/build artifact.

## Threat matrix

| Threat | Example | Required mitigation/owner |
| --- | --- | --- |
| authority confusion | verifier recommendation treated as merge approval | ADR-0013, #738, #740 |
| auth bypass | network mutation accepts localhost token | #743 + #670 |
| horizontal access | project A reads project B run | #743, scoped resource model #739 |
| vertical escalation | worker calls integration action | #670/#743 scope matrix |
| self-approval | worker and required approver collapse to same actor | #670/#598 separation of duties |
| stale authority | revoked identity still authorized from cache | #670 freshness/revision |
| replay | duplicate run/decision request creates second effect | #616/#597/#740 idempotency |
| race/lost update | two clients mutate same resource concurrently | #736 concurrency + #742 |
| evidence substitution | human decision points at swapped report | #740 digest binding |
| digest ambiguity | different JSON encodings hash differently unexpectedly | canonical digest rules #736/#737 |
| malicious JSON | duplicate keys/NaN/deep/pathological body | #735/#745 parser/fuzz/limits |
| request smuggling | proxy/backend interpret request differently | #743 production transport tests |
| Host-header attack | local service accepts non-loopback Host | local runtime boundary #735 |
| cross-origin local attack | public page calls localhost API | same-origin/preflight rejection; #735 |
| CSRF | browser credential automatically sent to mutation | #743 explicit CSRF/origin design |
| CORS overexposure | wildcard origin exposes evidence | #743 deny/default allowlist |
| secret exfiltration | API returns raw connector key | #580/#607 secret-reference boundary |
| secret logging | token/body appears in access log | #677/#744 bounded telemetry |
| SSRF | connector URL causes internal network fetch | connector-specific validation #570/#743 |
| webhook forgery | unauthenticated event triggers run | #580/#607 trusted webhook boundary |
| provider confusion | powerful model assumed authorized | #570/#670 authority policy |
| event forgery | client writes arbitrary audit event | #741 append authority + provenance |
| event stream leak | SSE exposes another tenant | #741/#743 scoped auth |
| storage tamper | durable evidence rewritten/corrupted | #597/#750 immutable digest checks |
| retention loss | essential evidence expires with CI logs | #597/#750 retention matrix |
| resource exhaustion | slow/body-heavy clients exhaust server | #742 limits/timeouts/concurrency |
| provider spend abuse | repeated dispatch consumes paid quota | zero-spend policy + #580 admission |
| supply-chain compromise | server dependency/action replaced | #667/#745 + pinned/reviewed dependencies |
| UI policy bypass | browser hides warning/authority limit | server/domain authority; UI non-authoritative |

## Security rules for public objects

Authority-sensitive objects should:

- reject unknown authority-changing fields;
- use explicit schema version;
- carry stable identity/digests;
- be validated server-side;
- never trust browser-side validation as the security boundary.

## Authentication versus authorization

Authentication answers:

> Who/what is the principal?

Authorization answers:

> May this principal perform this action on this resource now?

They are separate.

A valid identity does not imply:

- project membership;
- reviewer independence;
- dispatch authority;
- secret access;
- human-decision authority;
- integration authority.

## Local session token rules

The local token:

- is ephemeral unless explicitly configured for local automation;
- is sent only to loopback API surfaces;
- is compared safely;
- should not appear in logs;
- is not a multi-user principal;
- must not be accepted as network enterprise authorization.

## Network credential rules

The network profile should prefer:

- short-lived credentials;
- trusted issuer/audience validation;
- revocation/expiry;
- narrow scopes;
- explicit project/tenant claims.

Long-lived provider secrets stay behind secret-reference resolvers rather than
becoming API bearer identity.

## Browser mutation rules

Before adding browser mutations:

- decide whether credentials use Authorization headers or cookies;
- if cookies are used, define SameSite/Secure/HttpOnly behavior;
- enforce CSRF protection;
- validate Origin for sensitive same-origin operations;
- define CORS allowlist explicitly;
- require idempotency for retried state changes;
- require re-authorization/confirmation where high-risk policy says so.

## Proxy rules

The production service must define exactly which proxy is trusted.

Do not trust arbitrary incoming:

- `X-Forwarded-For`;
- `X-Forwarded-Proto`;
- forwarded host;
- user/role headers.

Proxy-normalized request boundaries must be security-tested for ambiguity and
smuggling.

## Webhook rules

Webhook ingress is a separate untrusted boundary.

Required:

- provider signature verification where available;
- replay/event-ID handling;
- exact repository/project binding;
- event type allowlist;
- body-size limits;
- no issue/comment content authority;
- idempotent downstream handling.

## Connector and SSRF boundary

Connector configuration can create outbound network capability.

Before arbitrary endpoints are supported:

- driver owns allowed URL forms;
- block unreviewed loopback/link-local/metadata destinations where applicable;
- resolve redirects under the same policy;
- enforce timeout/body limits;
- never send a secret to a destination that was not authorized for it.

## Denial-of-service model

The service must bound:

- headers;
- body;
- parse depth/complexity where relevant;
- concurrent requests;
- worker threads/tasks;
- downstream calls;
- event-stream clients;
- buffered event backlog;
- log volume.

Overload must degrade explicitly through 429/503 rather than uncontrolled memory
growth.

## Audit/security events

Security-relevant events should include safe references for:

- auth failure classes;
- authorization deny/requires-approval;
- idempotency conflict;
- decision creation;
- dispatch/cancel;
- secret materialization attempt/result class;
- break-glass grant/use;
- integration handoff.

Do not put secrets or raw evidence bodies in audit telemetry.

## Security qualification

#745 should include:

- auth bypass matrix;
- tenant isolation tests;
- scope/role negative matrix;
- stale/revoked identity tests;
- self-approval tests;
- parser/header/media fuzz;
- body/header boundary tests;
- CSRF/CORS tests for mutations;
- request-smuggling/proxy tests for production transport;
- webhook replay/signature tests;
- idempotency replay/race tests;
- secret/log redaction tests;
- storage corruption/substitution tests;
- load/slow-client tests.

## Security release gates

### Local beta

May ship without enterprise identity only if:

- loopback binding is enforced;
- local token boundary is tested;
- surface is explicitly documented as local;
- mutating authority is limited to the declared local contract.

### Network beta

Must not ship until:

- #670 trusted identity/policy integration is active;
- #743 threat/deployment profile is reviewed;
- TLS/proxy model is defined;
- tenant/project scope tests pass;
- mutation idempotency/concurrency exists;
- #745 security qualification passes for the declared scope.

## Open questions

Tracked, not silently assumed:

- exact first production HTTP adapter;
- exact network identity provider(s);
- whether browser network auth uses cookies or bearer/OIDC-derived tokens;
- tenant isolation persistence strategy;
- metrics/tracing backend choices;
- external security review timing.

These choices should be delayed until their owning issues need them, while the
security invariants above remain stable.
