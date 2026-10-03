"""Local Human Control Tower UI and versioned read-only API."""

from __future__ import annotations

import html
import json
import os
import secrets
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qsl, urlsplit

from idkmesh import __version__
from idkmesh.control_tower_api import (
    API_SCHEMA_VERSION,
    API_VERSION,
    JSON_MEDIA_TYPE,
    V1_MEDIA_TYPE,
    ControlTowerInputError,
    build_snapshot,
    canonical_digest,
    error_document,
    openapi_document,
    parse_report_text,
    status_document,
    success_document,
)
from idkmesh.connector_store import DEFAULT_LIST_LIMIT, MAX_LIST_LIMIT
from idkmesh.local_ui_security import (
    HOST,
    MAX_BODY_BYTES,
    TOKEN_HEADER,
    is_loopback_host,
    new_session_token,
    send_security_headers,
)
from idkmesh.service_runtime import (
    ADMITTED,
    DEFAULT_DRAIN_TIMEOUT_SECONDS,
    DEFAULT_MAX_CONCURRENT_REQUESTS,
    DEFAULT_MAX_SSE_CLIENTS,
    DEFAULT_REQUEST_TIMEOUT_SECONDS,
    DEFAULT_RETRY_AFTER_SECONDS,
    DRAINING,
    REQUEST_ID_HEADER,
    RequestLimiter,
    SSE_HEARTBEAT_SECONDS,
    SSE_MAX_STREAM_SECONDS,
    SSE_POLL_SECONDS,
    access_logging_enabled,
    build_access_log_event,
    limits_document,
    readiness_document,
    resolve_request_id,
    service_headers,
    validate_max_concurrent_requests,
    validate_max_sse_clients,
    validate_request_timeout,
    write_access_log,
)

DEFAULT_PORT = 8770
TOKEN_ENV = "IDKMESH_CONTROL_TOWER_TOKEN"
SERVICE_NAME = "idkmesh-control-tower"
SERVICE_MODE = "local-read-only"
_TOKEN_SAFE_CHARS = frozenset(
    "abcdefghijklmnopqrstuvwxyz"
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "0123456789-._~"
)

_SAMPLE_REPORT = {
    "attempts": [
        {
            "attempt_id": "attempt-001",
            "error": None,
            "evidence_state": "supported",
            "order": 1,
            "state": "verified",
            "verifier": {
                "checks": [
                    {
                        "id": "result-manifest-schema",
                        "required": True,
                        "status": "passed",
                    },
                    {
                        "id": "independent-review",
                        "required": True,
                        "status": "passed",
                    },
                ],
                "id": "idkmesh-local-verifier",
                "recommendation": "accept_candidate",
                "status": "passed",
                "verification_semantic_digest": (
                    "sha256:04d9361f9302a165611586832a654c7b2033bb36202d4194a1b441cbc0f38e62"
                ),
            },
            "worker": {
                "id": "fixture/patch-worker",
                "result_manifest_digest": (
                    "sha256:bad853c0d3d41d79f4596315fdaf402ed3c3a073a3b76af38ce62e73fc9ce67b"
                ),
                "result_manifest_id": "verification/patch-smoke/good-attempt-1",
                "status": "succeeded",
            },
            "worker_adapter": "result-bundle",
        },
        {
            "attempt_id": "attempt-002",
            "error": None,
            "evidence_state": "rejected",
            "order": 2,
            "state": "verified",
            "verifier": {
                "checks": [
                    {
                        "id": "result-manifest-schema",
                        "required": True,
                        "status": "passed",
                    },
                    {
                        "id": "independent-review",
                        "required": True,
                        "status": "failed",
                    },
                ],
                "id": "idkmesh-local-verifier",
                "recommendation": "reject_candidate",
                "status": "failed",
                "verification_semantic_digest": (
                    "sha256:ae08b88556d6bd1805079df4946ebb62e4f615143bd2ab6db1f19f5b80730ecb"
                ),
            },
            "worker": {
                "id": "fixture/patch-worker",
                "result_manifest_digest": (
                    "sha256:505aaffee492a969c8ea6ff01b759d18937c4636a50136deac1b9e491cd2583b"
                ),
                "result_manifest_id": (
                    "verification/patch-smoke/wrong-semantic-attempt-1"
                ),
                "status": "succeeded",
            },
            "worker_adapter": "result-bundle",
        },
    ],
    "authority": {
        "automatic_candidate_selection": False,
        "canonical_state_write": False,
        "git_push": False,
        "merge": False,
    },
    "human_decision": {
        "integration_authority": "external_human_or_governance",
        "selected_attempt_id": None,
        "status": "pending",
    },
    "kind": "idkmesh-run-evidence-report",
    "orchestrator_version": "0.2",
    "run_id": "two-attempt-evaluator-plan-good-vs-bad",
    "schema_version": "0.1",
    "source_config_digest": (
        "sha256:df509d2670c2fe73c98299c6863424f0fff0629dcd03cfea3688f922c0056748"
    ),
    "source_run_digest": (
        "sha256:41ecefda10fe809fcec0acbb0d39d39d4044f26b127eb83e64d1a8c94a3bec3d"
    ),
    "source_run_kind": "idkmesh-two-attempt-run",
    "summary": {
        "attempt_count": 2,
        "control_errors": 0,
        "control_failure_present": False,
        "inconclusive": 0,
        "rejected": 1,
        "supported": 1,
        "verification_disagreement": True,
    },
    "verifier_policy_digest": (
        "sha256:e73b61280f1d52cd119da2f3b56ca4749859c823863e82d88eb84a7c63533f2a"
    ),
    "warnings": [
        (
            "Generated evidence is decision support only; this report does not "
            "select, accept, merge, or integrate a candidate."
        ),
        (
            "Independent verification recommendations disagree; preserve the "
            "disagreement for human/governance review."
        ),
    ],
    "work_unit": {
        "digest": (
            "sha256:3f8b78df3f43329fe72223018ab42300fcb19523a82769e47ba31098861c24fd"
        ),
        "id": "verification/patch-smoke",
        "version": 1,
    },
}
SAMPLE_REPORT = json.dumps(_SAMPLE_REPORT, indent=2)


def _app_html(initial_text: str | None, token: str) -> str:
    source = SAMPLE_REPORT if initial_text is None else initial_text
    page = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="dark">
<meta name="robots" content="noindex,nofollow">
<title>IDKMesh Control Tower</title>
<style>
:root{
 --bg:#070b14;--panel:#10192b;--panel2:#151f35;--line:#293754;
 --text:#eef4ff;--muted:#9ba9c1;--faint:#697891;--cyan:#8bd3ff;
 --mint:#b9ffcf;--amber:#ffd28b;--red:#ff9d9d;--violet:#c9b8ff;
 --mono:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
 --sans:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
}
*{box-sizing:border-box}
body{margin:0;background:radial-gradient(circle at 90% -10%,#14233e 0,transparent 32%),var(--bg);color:var(--text);font-family:var(--sans);line-height:1.45}
button,input,textarea{font:inherit}button{cursor:pointer}
.shell{min-height:100vh;display:grid;grid-template-columns:235px minmax(0,1fr)}
aside{position:sticky;top:0;height:100vh;padding:1.1rem;border-right:1px solid var(--line);background:rgba(8,13,24,.94)}
.brand{font-weight:850;font-size:1.05rem;letter-spacing:-.02em;margin-bottom:.25rem}
.version{font-size:.74rem;color:var(--mint);margin-bottom:1.3rem}
.nav{display:grid;gap:.35rem}
.nav button{border:0;text-align:left;border-radius:9px;padding:.65rem .75rem;background:transparent;color:var(--muted);font-weight:720}
.nav button:hover,.nav button.active{background:var(--panel2);color:var(--text)}
.nav .tool{margin-top:.7rem;border-top:1px solid var(--line);border-radius:0;padding-top:1rem}
.boundary{position:absolute;left:1.1rem;right:1.1rem;bottom:1rem;font-size:.72rem;color:var(--faint)}
main{min-width:0;padding:1.5rem 1.7rem 4rem}
.topbar{display:flex;align-items:flex-start;justify-content:space-between;gap:1rem;margin-bottom:1.25rem}
.eyebrow{text-transform:uppercase;letter-spacing:.1em;font-size:.7rem;color:var(--mint);font-weight:850}
h1{margin:.22rem 0 .35rem;font-size:clamp(1.9rem,4vw,3rem);letter-spacing:-.04em;line-height:1}
.lead{margin:0;color:var(--muted);max-width:78ch}
.local{border:1px solid var(--line);border-radius:999px;padding:.35rem .65rem;color:var(--mint);font-size:.76rem;white-space:nowrap}
.view{display:none}.view.active{display:block}
.grid{display:grid;grid-template-columns:repeat(12,minmax(0,1fr));gap:.8rem}
.card{background:linear-gradient(180deg,var(--panel),#0c1424);border:1px solid var(--line);border-radius:14px;padding:1rem;min-width:0}
.card h2,.card h3{margin:0 0 .65rem;font-size:.95rem}
.span4{grid-column:span 4}.span5{grid-column:span 5}.span6{grid-column:span 6}.span7{grid-column:span 7}.span8{grid-column:span 8}.span12{grid-column:1/-1}
.kpi{font-size:1.8rem;font-weight:850;letter-spacing:-.04em}.kpi.cyan{color:var(--cyan)}.kpi.amber{color:var(--amber)}
.label{color:var(--muted);font-size:.76rem}.small{color:var(--muted);font-size:.82rem}.mono{font-family:var(--mono);word-break:break-all}
.attention{display:grid;gap:.55rem}
.alert{border:1px solid var(--line);border-left:3px solid var(--amber);border-radius:9px;padding:.65rem .75rem}
.alert.high{border-left-color:var(--red)}.alert.action{border-left-color:var(--cyan)}
.alert strong{display:block;font-size:.84rem}.alert span{display:block;color:var(--muted);font-size:.77rem;margin-top:.16rem}
.authority{display:grid;grid-template-columns:1fr auto;gap:.4rem .8rem;font-size:.8rem}
.authority b{color:var(--mint)}.authority b.no{color:var(--red)}
.rules{margin:0;padding-left:1.2rem;color:var(--muted);font-size:.8rem}.rules li{margin:.3rem 0}
.toolbar{display:flex;gap:.45rem;flex-wrap:wrap;align-items:center;margin-bottom:.7rem}
.file,button,.button{display:inline-flex;align-items:center;justify-content:center;min-height:37px;padding:.5rem .72rem;border:1px solid var(--line);border-radius:8px;background:var(--panel2);color:var(--text);font-weight:750;font-size:.82rem;text-decoration:none}
button.primary{background:var(--text);color:var(--bg);border-color:var(--text)}
button:hover,.file:hover{border-color:var(--cyan)}
#file{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0)}
textarea{width:100%;min-height:310px;resize:vertical;background:#050912;color:#dfeaff;border:1px solid var(--line);border-radius:10px;padding:.85rem;font: .78rem/1.5 var(--mono)}
.status{min-height:1.3rem;color:var(--muted);font-size:.8rem;margin:.5rem 0}.status.error{color:var(--red)}.status.ok{color:var(--mint)}
.summary-grid{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:.55rem}
.metric{border:1px solid var(--line);border-radius:10px;padding:.65rem;background:rgba(255,255,255,.016)}
.metric .n{font-size:1.35rem;font-weight:850}.metric .t{color:var(--muted);font-size:.7rem}
.attempts{display:grid;gap:.7rem}.attempt{border:1px solid var(--line);border-radius:11px;padding:.8rem}
.attempt-head{display:flex;justify-content:space-between;gap:.5rem;align-items:center;margin-bottom:.65rem}
.badge{border:1px solid currentColor;border-radius:999px;padding:.12rem .48rem;font-size:.68rem;font-weight:850;text-transform:uppercase;color:var(--violet)}
.badge.supported{color:var(--mint)}.badge.rejected,.badge.worker_error,.badge.verification_error{color:var(--red)}.badge.inconclusive{color:var(--amber)}
.layers{display:grid;grid-template-columns:1fr 1fr 1fr;gap:.55rem}
.layer{border:1px solid var(--line);border-radius:9px;padding:.65rem;min-width:0}
.layer .tag{text-transform:uppercase;letter-spacing:.08em;font-size:.63rem;color:var(--faint);font-weight:850}
.layer strong{display:block;margin:.25rem 0;font-size:.82rem}.layer p{margin:.2rem 0;color:var(--muted);font-size:.75rem}
.checks{margin:.35rem 0 0;padding:0;list-style:none;font-size:.73rem;color:var(--muted)}
.checks li{margin:.2rem 0}.pass{color:var(--mint)}.fail{color:var(--red)}
.timeline{display:grid;gap:.15rem}.event{display:grid;grid-template-columns:40px 115px 1fr;gap:.6rem;padding:.62rem 0;border-bottom:1px solid var(--line)}
.seq{font-family:var(--mono);color:var(--faint);font-size:.73rem}.etype{text-transform:uppercase;letter-spacing:.07em;font-size:.66rem;font-weight:850;color:var(--cyan)}
.event strong{display:block;font-size:.82rem}.event p{margin:.13rem 0 0;color:var(--muted);font-size:.75rem}
.digest{margin-top:.2rem;font-family:var(--mono);font-size:.67rem;color:var(--faint);word-break:break-all}
.api-list{display:grid;gap:.5rem}.endpoint{border:1px solid var(--line);border-radius:9px;padding:.7rem}.method{color:var(--mint);font-family:var(--mono);font-size:.75rem;font-weight:850}.path{font-family:var(--mono);font-size:.78rem}
.chain{display:grid;gap:.7rem}.chain-card{border:1px solid var(--line);border-radius:11px;padding:.8rem;background:rgba(255,255,255,.012)}.chain-step{display:grid;grid-template-columns:125px 1fr;gap:.7rem;padding:.45rem 0;border-bottom:1px solid var(--line)}.chain-step:last-child{border-bottom:0}.chain-step .name{color:var(--faint);font-size:.69rem;font-weight:850;text-transform:uppercase;letter-spacing:.07em}.chain-step strong{font-size:.8rem}.chain-note{margin:.35rem 0 0;color:var(--muted);font-size:.72rem}.chain-arrow{color:var(--cyan);font-weight:850}
.empty{color:var(--muted);text-align:center;padding:2rem}
.callout{border-left:3px solid var(--cyan);background:rgba(139,211,255,.04);padding:.7rem .8rem;border-radius:8px;color:var(--muted);font-size:.8rem}
.hidden{display:none!important}
@media(max-width:1050px){.span4,.span5,.span6,.span7,.span8{grid-column:span 6}.summary-grid{grid-template-columns:repeat(3,1fr)}}
@media(max-width:760px){.shell{grid-template-columns:1fr}aside{position:static;height:auto;border-right:0;border-bottom:1px solid var(--line)}.nav{display:flex;overflow:auto}.nav button{white-space:nowrap}.nav .tool{margin:0;border:0;padding:.65rem .75rem}.boundary{display:none}main{padding:1rem}.topbar{flex-direction:column}.span4,.span5,.span6,.span7,.span8{grid-column:1/-1}.layers{grid-template-columns:1fr}.summary-grid{grid-template-columns:repeat(2,1fr)}}
</style>
</head>
<body>
<div class="shell">
<aside>
  <div class="brand">IDKMesh Control Tower</div>
  <div class="version">local · read-only · v__VERSION__</div>
  <nav class="nav" aria-label="Control Tower">
    <button class="active" data-view="overview">Overview</button>
    <button data-view="run">Run Evidence</button>
    <button data-view="provenance">Provenance</button>
    <button data-view="timeline">Audit Timeline</button>
    <button data-view="api">Local API</button>
    <button class="tool" data-view="verification">Verification tools</button>
  </nav>
  <div class="boundary">Claim ≠ evidence<br>Evidence ≠ decision<br>Decision ≠ merge</div>
</aside>

<main>
<div class="topbar">
  <div>
    <div class="eyebrow">Human supervision surface</div>
    <h1>What happened, what is proven, what needs you?</h1>
    <p class="lead">The Control Tower renders existing IDKMesh evidence. It does not run workers, select candidates, record decisions, push Git, or merge.</p>
  </div>
  <div class="local">127.0.0.1 only</div>
</div>

<section id="view-overview" class="view active">
  <div class="grid">
    <article class="card span4"><h2>Human attention</h2><div id="attention" class="attention"><div class="empty">Inspect a run to populate attention items.</div></div></article>
    <article class="card span4"><h2>Run snapshot</h2><div id="snapshot" class="empty">No run loaded.</div></article>
    <article class="card span4"><h2>Authority boundary</h2><div id="authority" class="authority"></div></article>
    <article class="card span8"><h2>Attempts</h2><div id="attempt-preview" class="attempts"><div class="empty">No attempts loaded.</div></div></article>
    <article class="card span4"><h2>Interpretation rules</h2><ul id="rules" class="rules"></ul></article>
  </div>
</section>

<section id="view-run" class="view">
  <div class="grid">
    <article class="card span5">
      <h2>Run Evidence Report v0.1</h2>
      <p class="small">Open or paste a generated report. The API recomputes counts and disagreement before presenting it.</p>
      <div class="toolbar">
        <label class="file">Open report<input id="file" type="file" accept=".json,application/json"></label>
        <button id="sample">Repository demo</button>
        <button id="format">Format</button>
        <button id="inspect" class="primary">Inspect evidence</button>
      </div>
      <textarea id="source" spellcheck="false" aria-label="Run Evidence Report JSON">__INITIAL__</textarea>
      <div id="status" class="status">Ready.</div>
    </article>
    <article class="card span7">
      <h2>Evidence summary</h2>
      <div id="run-summary" class="empty">Inspect a report to render the run.</div>
      <div id="run-attempts" class="attempts"></div>
    </article>
  </div>
</section>

<section id="view-provenance" class="view">
  <div class="grid">
    <article class="card span5">
      <h2>Evidence roots</h2>
      <p class="small">These identifiers and digests come directly from the validated Run Evidence Report. They show binding, not correctness.</p>
      <div id="provenance-root" class="chain"><div class="empty">Inspect a run to show provenance roots.</div></div>
    </article>
    <article class="card span7">
      <h2>Attempt provenance chains</h2>
      <p class="small">WorkUnit → ResultManifest → verification evidence → human authority. Identity distinction is visible; statistical or organizational independence is not inferred.</p>
      <div id="provenance-attempts" class="chain"><div class="empty">Inspect a run to show attempt chains.</div></div>
    </article>
  </div>
</section>

<section id="view-timeline" class="view">
  <article class="card">
    <h2>Semantic background activity</h2>
    <p class="small">Sequence is derived from the evidence record. No wall-clock timestamps are invented where the contract does not contain them.</p>
    <div id="timeline" class="timeline"><div class="empty">Inspect a run to build the timeline.</div></div>
  </article>
</section>

<section id="view-api" class="view">
  <div class="grid">
    <article class="card span7">
      <h2>Control Tower Local API</h2>
      <p class="small">Versioned, token-protected, loopback-only API for read-only human-facing evidence inspection.</p>
      <div id="api-list" class="api-list"></div>
    </article>
    <article class="card span5">
      <h2>Capabilities</h2>
      <div id="capabilities" class="authority"></div>
    </article>
  </div>
</section>

<section id="view-verification" class="view">
  <div class="grid">
    <article class="card span7">
      <h2>Gate Audit</h2>
      <p class="small">Gate Audit remains a specialized verification diagnostic. It measures effective independent votes, correlation, panel error and seeded-probe breaches.</p>
      <div class="callout"><strong>Run locally:</strong><br><span class="mono">idkmesh gate-audit-ui path/to/panel-votes.json</span></div>
    </article>
    <article class="card span5">
      <h2>Why it is separate</h2>
      <ul class="rules">
        <li>Control Tower explains a swarm run.</li>
        <li>Gate Audit evaluates a verifier panel against known ground truth.</li>
        <li>Neither surface grants acceptance or merge authority.</li>
      </ul>
    </article>
  </div>
</section>
</main>
</div>

<script>
(function(){
"use strict";
var token=__TOKEN__;
var sample=__SAMPLE__;
var source=document.getElementById("source");
var statusEl=document.getElementById("status");
var current=null;

function esc(v){return String(v===null||v===undefined?"":v).replace(/[&<>"']/g,function(c){return {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c];});}
function setStatus(text,kind){statusEl.textContent=text;statusEl.className="status"+(kind?" "+kind:"");}
function truth(v){return v?'<b>YES</b>':'<b class="no">NO</b>';}
function nav(name){
 document.querySelectorAll(".view").forEach(function(x){x.classList.remove("active");});
 document.querySelectorAll(".nav button").forEach(function(x){x.classList.toggle("active",x.dataset.view===name);});
 document.getElementById("view-"+name).classList.add("active");
}
document.querySelectorAll(".nav button").forEach(function(b){b.addEventListener("click",function(){nav(b.dataset.view);});});

async function request(path,opts){
 opts=opts||{};opts.headers=Object.assign({"X-IDKMesh-UI-Token":token},opts.headers||{});
 var response=await fetch(path,opts);var payload=await response.json();
 if(!response.ok||payload.ok===false){
   var err=payload.error&&payload.error.message?payload.error.message:"Request failed";
   throw new Error(err);
 }
 return payload;
}

function metric(n,t){return '<div class="metric"><div class="n">'+esc(n)+'</div><div class="t">'+esc(t)+'</div></div>';}
function checks(items){
 if(!items||!items.length)return '<p>No checks recorded.</p>';
 return '<ul class="checks">'+items.map(function(c){
   var cls=c.status==="passed"?"pass":"fail";
   return '<li><span class="'+cls+'">'+(c.status==="passed"?"✓":"✕")+'</span> '+esc(c.id)+(c.required?" · required":"")+'</li>';
 }).join("")+"</ul>";
}
function chainStep(name,title,digest,note){
 var detail='<strong>'+esc(title)+'</strong>';
 if(digest){detail+='<div class="digest">'+esc(digest)+'</div>';}
 if(note){detail+='<p class="chain-note">'+esc(note)+'</p>';}
 return '<div class="chain-step"><div class="name">'+esc(name)+'</div><div>'+detail+'</div></div>';
}
function renderProvenance(p){
 var root=document.getElementById("provenance-root");
 var attempts=document.getElementById("provenance-attempts");
 if(!p){root.innerHTML='<div class="empty">No provenance projection.</div>';attempts.innerHTML='<div class="empty">No provenance projection.</div>';return;}
 root.innerHTML='<div class="chain-card">'+
   chainStep("WorkUnit",p.work_unit.id+" v"+p.work_unit.version,p.work_unit.digest,"Bounded task contract")+
   chainStep("Run",p.run.run_id,p.run.source_run_digest,"Orchestrator "+p.run.orchestrator_version)+
   chainStep("Config","source configuration",p.run.source_config_digest,"Exact run configuration binding")+
   chainStep("Verifier policy","verification policy",p.run.verifier_policy_digest,"Policy binding; not a correctness claim")+
   '</div>';
 attempts.innerHTML=p.attempts.map(function(a){
   var html='<div class="chain-card"><div class="attempt-head"><strong>'+esc(a.attempt_id)+'</strong><span class="badge '+esc(a.evidence_state)+'">'+esc(a.evidence_state)+'</span></div>';
   html+=chainStep("WorkUnit",p.work_unit.id,p.work_unit.digest,"shared task root");
   if(a.result_manifest){
     html+=chainStep("Worker / result",a.result_manifest.worker_id+" · "+a.result_manifest.result_manifest_id,a.result_manifest.result_manifest_digest,"adapter "+a.worker_adapter+" · worker status "+a.result_manifest.worker_status);
   }else{
     html+=chainStep("Worker / result","No usable ResultManifest",null,a.error||"control-path failure");
   }
   html+='<div class="chain-step"><div class="name">Binding</div><div class="chain-arrow">↓</div></div>';
   if(a.verification){
     html+=chainStep("Verifier",a.verification.verifier_id,a.verification.verification_semantic_digest,"recommendation "+a.verification.recommendation+" · status "+a.verification.verifier_status);
     html+=chainStep("Identity relation",a.verification.identity_distinct_from_worker?"worker/verifier IDs differ":"worker/verifier identity not distinct",null,a.verification.independence_claim);
     html+='<div class="chain-step"><div class="name">Required checks</div><div>'+checks(a.verification.required_checks.map(function(x){return {id:x.id,status:x.status,required:true};}))+'</div></div>';
   }else{
     html+=chainStep("Verifier","No usable VerificationResult",null,a.error||"verification unavailable");
   }
   html+='<div class="chain-step"><div class="name">Authority</div><div><strong>Human decision '+esc(p.authority.human_decision_status)+'</strong><p class="chain-note">Integration authority: '+esc(p.authority.integration_authority)+' · auto-select '+(p.authority.automatic_candidate_selection?"YES":"NO")+' · merge '+(p.authority.merge?"YES":"NO")+'</p></div></div>';
   return html+'</div>';
 }).join("");
}

function attemptCard(a){
 var claim=a.claim?'<div class="layer"><div class="tag">Worker claim</div><strong>'+esc(a.claim.worker_id)+'</strong><p>Status: '+esc(a.claim.worker_status)+'</p><p>'+esc(a.claim.result_manifest_id)+'</p><div class="digest">'+esc(a.claim.result_manifest_digest)+'</div></div>':'<div class="layer"><div class="tag">Worker claim</div><strong>Unavailable</strong><p>'+esc(a.error||"No usable ResultManifest.")+'</p></div>';
 var evidence=a.evidence?'<div class="layer"><div class="tag">Independent evidence</div><strong>'+esc(a.evidence.verifier_id)+'</strong><p>'+esc(a.evidence.recommendation)+'</p>'+checks(a.evidence.checks)+'<div class="digest">'+esc(a.evidence.verification_digest)+'</div></div>':'<div class="layer"><div class="tag">Independent evidence</div><strong>Unavailable</strong><p>'+esc(a.error||"No usable VerificationResult.")+'</p></div>';
 var authority='<div class="layer"><div class="tag">Authority</div><strong>Human decision pending</strong><p>No automatic candidate selection.</p><p>Merge authority: NO</p></div>';
 return '<article class="attempt"><div class="attempt-head"><strong>'+esc(a.attempt_id)+'</strong><span class="badge '+esc(a.evidence_state)+'">'+esc(a.evidence_state)+'</span></div><div class="layers">'+claim+evidence+authority+'</div></article>';
}
function render(s){
 current=s;
 var att=document.getElementById("attention");
 att.innerHTML=s.attention.map(function(a){return '<div class="alert '+esc(a.severity)+'"><strong>'+esc(a.title)+'</strong><span>'+esc(a.why)+'</span></div>';}).join("");
 document.getElementById("snapshot").innerHTML='<div class="kpi cyan">'+esc(s.summary.attempt_count)+'</div><div class="label">attempts · WorkUnit '+esc(s.work_unit.id)+'</div><div class="small" style="margin-top:.7rem">Supported '+esc(s.summary.supported)+' · Rejected '+esc(s.summary.rejected)+' · Inconclusive '+esc(s.summary.inconclusive)+'</div><div class="small">Human decision: <strong>'+esc(s.human_decision.status)+'</strong></div>';
 var au=s.authority;
 document.getElementById("authority").innerHTML='<span>Canonical state write</span>'+truth(au.canonical_state_write)+'<span>Git push</span>'+truth(au.git_push)+'<span>Merge</span>'+truth(au.merge)+'<span>Auto candidate selection</span>'+truth(au.automatic_candidate_selection);
 document.getElementById("rules").innerHTML=s.interpretation_rules.map(function(x){return "<li>"+esc(x)+"</li>";}).join("");
 document.getElementById("attempt-preview").innerHTML=s.attempts.map(attemptCard).join("");
 document.getElementById("run-summary").innerHTML='<div class="summary-grid">'+metric(s.summary.attempt_count,"attempts")+metric(s.summary.supported,"supported")+metric(s.summary.rejected,"rejected")+metric(s.summary.inconclusive,"inconclusive")+metric(s.summary.control_errors,"control errors")+metric(s.summary.verification_disagreement?"YES":"NO","disagreement")+'</div><p class="small mono">'+esc(s.source.source_run_digest)+'</p>';
 document.getElementById("run-attempts").innerHTML=s.attempts.map(attemptCard).join("");
 renderProvenance(s.provenance);
 document.getElementById("timeline").innerHTML=s.timeline.map(function(e){return '<div class="event"><div class="seq">#'+esc(e.sequence)+'</div><div class="etype">'+esc(e.type)+'</div><div><strong>'+esc(e.title)+'</strong><p>'+esc(e.detail)+(e.actor?' · '+esc(e.actor):'')+'</p>'+(e.evidence_ref?'<div class="digest">'+esc(e.evidence_ref)+'</div>':'')+'</div></div>';}).join("");
}
async function inspect(){
 setStatus("Validating evidence locally…","");
 try{
  var payload=await request("/api/v1/run-evidence/inspect",{method:"POST",headers:{"Content-Type":"application/json; charset=utf-8"},body:source.value});
  render(payload.snapshot);setStatus("Evidence inspected. No candidate was selected.","ok");
 }catch(err){setStatus(err.message,"error");}
}
async function loadStatus(){
 try{
  var s=await request("/api/v1/status");
  document.getElementById("api-list").innerHTML=Object.keys(s.endpoints).map(function(k){var v=s.endpoints[k];var parts=v.split(" ");return '<div class="endpoint"><span class="method">'+esc(parts[0])+'</span> <span class="path">'+esc(parts.slice(1).join(" "))+'</span><div class="small">'+esc(k.replaceAll("_"," "))+'</div></div>';}).join("");
  document.getElementById("capabilities").innerHTML=Object.keys(s.capabilities).map(function(k){return '<span>'+esc(k.replaceAll("_"," "))+'</span>'+truth(s.capabilities[k]);}).join("");
 }catch(err){document.getElementById("api-list").textContent=err.message;}
}

document.getElementById("inspect").addEventListener("click",inspect);
document.getElementById("sample").addEventListener("click",function(){source.value=sample;setStatus("Loaded the committed two-attempt demo.","");});
document.getElementById("format").addEventListener("click",function(){try{source.value=JSON.stringify(JSON.parse(source.value),null,2);setStatus("Formatted JSON syntax. Strict evidence checks run on Inspect.","ok");}catch(err){setStatus("Invalid JSON: "+err.message,"error");}});
document.getElementById("file").addEventListener("change",function(){
 var f=this.files&&this.files[0];if(!f)return;
 if(f.size>__MAX__){setStatus("File exceeds the 2 MiB local-UI limit.","error");return;}
 var r=new FileReader();r.onload=function(){source.value=String(r.result||"");setStatus("Loaded "+f.name+".","");};r.onerror=function(){setStatus("Could not read file.","error");};r.readAsText(f,"utf-8");
});
source.addEventListener("keydown",function(e){if((e.ctrlKey||e.metaKey)&&e.key==="Enter"){e.preventDefault();inspect();}});
loadStatus();inspect();
}());
</script>
</body>
</html>"""
    return (
        page.replace("__INITIAL__", html.escape(source))
        .replace("__VERSION__", html.escape(__version__))
        .replace("__TOKEN__", json.dumps(token))
        .replace("__SAMPLE__", json.dumps(SAMPLE_REPORT))
        .replace("__MAX__", str(MAX_BODY_BYTES))
    )


def _json_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(
        payload,
        allow_nan=False,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _resolve_token() -> str:
    configured = os.environ.get(TOKEN_ENV)
    if configured is None:
        return new_session_token()
    if not (32 <= len(configured) <= 4096):
        raise ValueError(
            f"{TOKEN_ENV} must contain between 32 and 4096 characters")
    if any(ch not in _TOKEN_SAFE_CHARS for ch in configured):
        raise ValueError(
            f"{TOKEN_ENV} may contain only ASCII letters, digits, '-', '.', "
            "'_', and '~'")
    return configured


_EVENT_STREAM_PATH = f"/api/{API_VERSION}/events/stream"
_EVENT_FILTERS = ("project_id", "run_id", "work_unit_id", "event_type")
_EVENT_BATCH = 200


_SERVER_FAULT_CODES = frozenset({"store_error", "evidence_integrity_error"})


def _service_error_status(code: str, *not_found: str) -> int:
    """HTTP status for a ProductSpineRunStoreError code.

    404 for the endpoint's own not-found codes, 500 for a server-side fault
    (an unreadable store or a row that failed its integrity check), and 400 for
    everything else, which is a problem with the request.
    """
    if code in not_found:
        return 404
    if code in _SERVER_FAULT_CODES:
        return 500
    return 400


def _handler(
    initial_text: str | None,
    token: str,
    *,
    product_spine_store_path: str | None = None,
    request_timeout: float = DEFAULT_REQUEST_TIMEOUT_SECONDS,
):
    page = _app_html(initial_text, token).encode("utf-8")

    class Handler(BaseHTTPRequestHandler):
        server_version = "IDKMeshControlTower/0.1"
        # ADR-0022: socketserver applies this to the connection, so a client
        # that stalls on the request line, headers or body is dropped.
        timeout = request_timeout

        def handle_one_request(self) -> None:
            self._request_started = time.monotonic()
            self._request_id_value = None
            super().handle_one_request()

        def version_string(self) -> str:
            return self.server_version

        def log_message(self, format: str, *args: Any) -> None:
            return

        def _request_id(self) -> str:
            value = getattr(self, "_request_id_value", None)
            if value is None:
                value = resolve_request_id(
                    self.headers.get(REQUEST_ID_HEADER)
                )
                self._request_id_value = value
            return value

        def _access_path(self) -> str:
            try:
                return urlsplit(self.path).path
            except ValueError:
                return "<invalid-path>"

        def _headers(
            self,
            status: int,
            content_type: str,
            length: int | None,
            *,
            extra_headers: dict[str, str] | None = None,
        ) -> None:
            # ``length`` is None only for a close-delimited stream (SSE).
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            if length is not None:
                self.send_header("Content-Length", str(length))
            headers = service_headers(
                service=SERVICE_NAME,
                service_version=__version__,
                request_id=self._request_id(),
                read_only=True,
                api_version=API_VERSION,
            )
            if extra_headers:
                headers.update(extra_headers)
            for name, value in headers.items():
                self.send_header(name, value)
            send_security_headers(self)
            self.end_headers()
            if access_logging_enabled():
                started = getattr(
                    self, "_request_started", time.monotonic()
                )
                try:
                    write_access_log(
                        build_access_log_event(
                            service=SERVICE_NAME,
                            request_id=self._request_id(),
                            method=self.command,
                            path=self._access_path(),
                            status=status,
                            response_bytes=length or 0,
                            duration_ms=(
                                time.monotonic() - started
                            ) * 1000.0,
                        )
                    )
                except OSError:
                    # Observability failure must not turn a valid read-only
                    # response into an application failure.
                    pass

        def _response_media_type(self) -> str:
            accept = self.headers.get("Accept", "")
            for part in accept.split(","):
                media_type = part.split(";", 1)[0].strip().lower()
                if media_type == V1_MEDIA_TYPE:
                    return V1_MEDIA_TYPE
            return JSON_MEDIA_TYPE

        def _send_json(
            self,
            status: int,
            payload: dict[str, Any],
            *,
            head_only: bool = False,
            extra_headers: dict[str, str] | None = None,
        ) -> None:
            body = _json_bytes(payload)
            digest = canonical_digest(payload)
            headers = {
                "ETag": f'"{digest[7:]}"',
                "Vary": "Accept",
                "X-IDKMesh-Content-Digest": digest,
            }
            if extra_headers:
                headers.update(extra_headers)
            self._headers(
                status,
                self._response_media_type() + "; charset=utf-8",
                len(body),
                extra_headers=headers,
            )
            if not head_only and self.command != "HEAD":
                self.wfile.write(body)

        def _host_allowed(self) -> bool:
            if is_loopback_host(self.headers.get("Host")):
                return True
            self._send_json(
                403,
                error_document(
                    "invalid_host",
                    "Control Tower requests must use a loopback Host header",
                ),
            )
            return False

        def _token_allowed(self) -> bool:
            provided = self.headers.get(TOKEN_HEADER) or ""
            if secrets.compare_digest(provided, token):
                return True
            self._send_json(
                403,
                error_document(
                    "invalid_session_token",
                    "missing or invalid local UI session token",
                ),
            )
            return False

        def _accept_allowed(self) -> bool:
            accept = self.headers.get("Accept", "")
            if not accept:
                return True
            accepted = {
                "*/*",
                "application/*",
                JSON_MEDIA_TYPE,
                V1_MEDIA_TYPE,
            }
            if self._access_path() == _EVENT_STREAM_PATH:
                # ADR-0023: the SSE endpoint is the one place a client
                # legitimately asks for text/event-stream.
                accepted |= {"text/*", "text/event-stream"}
            for part in accept.split(","):
                media_type = part.split(";", 1)[0].strip().lower()
                if media_type in accepted:
                    return True
            self._send_json(
                406,
                error_document(
                    "not_acceptable",
                    (
                        "response must be accepted as application/json or "
                        f"{V1_MEDIA_TYPE}"
                    ),
                ),
            )
            return False

        def _path(self) -> tuple[str, str] | None:
            parsed = urlsplit(self.path)
            # GET /api/v1/runs and GET /api/v1/work-units (lists) are the
            # endpoints with declared, bounded query parameters (?limit=,
            # ?cursor=, and named filters; API Conventions v0.1 sections
            # 10-11). Every other /api/ endpoint keeps rejecting stray query
            # parameters outright.
            if (
                parsed.query
                and parsed.path.startswith("/api/")
                and parsed.path not in (
                    f"/api/{API_VERSION}/runs",
                    f"/api/{API_VERSION}/work-units",
                    f"/api/{API_VERSION}/events",
                    _EVENT_STREAM_PATH,
                )
            ):
                self._send_json(
                    400,
                    error_document(
                        "unexpected_query_parameters",
                        "Control Tower v1 endpoints do not accept query parameters",
                    ),
                )
                return None
            return parsed.path, parsed.query

        def _unknown_api_version(self, path: str) -> bool:
            if not path.startswith("/api/"):
                return False
            prefix = f"/api/{API_VERSION}/"
            if path.startswith(prefix):
                return False
            self._send_json(
                404,
                error_document(
                    "unsupported_api_version",
                    "unsupported Control Tower API version",
                    details={"supported_versions": [API_VERSION]},
                ),
            )
            return True

        _RUN_SUBRESOURCES = ("attempts", "evidence", "decisions")

        def _run_id_from_path(self, path: str) -> str | None:
            """Return the run_id if path is /api/v1/runs/<run_id>.

            Returns the full remainder, including a reserved sub-resource
            suffix if present -- callers that only handle the single-run
            read must check `_run_subresource_from_path` first and treat a
            match there as a different endpoint, not a run_id. See
            ADR-0019 for why `attempts`/`evidence`/`decisions` are reserved
            trailing segments rather than requiring percent-encoding.
            """
            prefix = f"/api/{API_VERSION}/runs/"
            if not path.startswith(prefix):
                return None
            remainder = path[len(prefix):]
            if not remainder:
                return None
            return remainder

        def _run_subresource_from_path(
            self, path: str
        ) -> tuple[str, str] | None:
            """Return (run_id, subresource) for a reserved sub-resource path.

            ADR-0019: a trailing "/attempts", "/evidence", or "/decisions"
            segment is always resolved as that sub-resource, independent of
            whether the derived run_id exists -- routing is a pure function
            of the path string, never a lookup outcome.
            """
            remainder = self._run_id_from_path(path)
            if remainder is None:
                return None
            for name in self._RUN_SUBRESOURCES:
                suffix = f"/{name}"
                if remainder.endswith(suffix) and len(remainder) > len(suffix):
                    return remainder[: -len(suffix)], name
            return None

        def _run_read_response(
            self, run_id: str, *, head_only: bool
        ) -> None:
            if product_spine_store_path is None:
                self._send_json(
                    503,
                    error_document(
                        "product_spine_store_not_configured",
                        "this Control Tower instance was started without a "
                        "Product Spine store; runs cannot be read",
                    ),
                    head_only=head_only,
                )
                return
            from idkmesh.connector_store import (
                LocalMetadataStore,
                LocalStoreError,
            )
            from idkmesh.product_spine_run_store import (
                ProductSpineRunStore,
                ProductSpineRunStoreError,
            )

            try:
                service = ProductSpineRunStore(
                    LocalMetadataStore(product_spine_store_path)
                )
                result = service.status(run_id)
            except ProductSpineRunStoreError as exc:
                code = getattr(exc, "code", "run_control_error")
                status = _service_error_status(code, "run_not_found")
                self._send_json(
                    status,
                    error_document(code, str(exc)),
                    head_only=head_only,
                )
                return
            except (LocalStoreError, OSError, ValueError) as exc:
                self._send_json(
                    500,
                    error_document("store_error", str(exc)),
                    head_only=head_only,
                )
                return

            payload = {
                "api_version": API_VERSION,
                "schema_version": API_SCHEMA_VERSION,
                "kind": "idkmesh-control-tower-run-response",
                "ok": True,
                **result.to_dict(),
            }
            self._send_json(200, payload, head_only=head_only)

        def _run_attempts_response(
            self, run_id: str, *, head_only: bool
        ) -> None:
            if product_spine_store_path is None:
                self._send_json(
                    503,
                    error_document(
                        "product_spine_store_not_configured",
                        "this Control Tower instance was started without a "
                        "Product Spine store; runs cannot be read",
                    ),
                    head_only=head_only,
                )
                return
            from idkmesh.connector_store import (
                LocalMetadataStore,
                LocalStoreError,
            )
            from idkmesh.product_spine_run_store import (
                ProductSpineRunStore,
                ProductSpineRunStoreError,
            )

            try:
                service = ProductSpineRunStore(
                    LocalMetadataStore(product_spine_store_path)
                )
                result = service.status(run_id)
            except ProductSpineRunStoreError as exc:
                code = getattr(exc, "code", "run_control_error")
                status = _service_error_status(code, "run_not_found")
                self._send_json(
                    status,
                    error_document(code, str(exc)),
                    head_only=head_only,
                )
                return
            except (LocalStoreError, OSError, ValueError) as exc:
                self._send_json(
                    500,
                    error_document("store_error", str(exc)),
                    head_only=head_only,
                )
                return

            payload = {
                "api_version": API_VERSION,
                "schema_version": API_SCHEMA_VERSION,
                "kind": "idkmesh-control-tower-run-attempts-response",
                "ok": True,
                "run_id": run_id,
                "attempts": [
                    attempt.to_dict() for attempt in result.run.attempts
                ],
            }
            self._send_json(200, payload, head_only=head_only)

        def _parse_list_query(
            self,
            query: str,
            allowed: set[str],
            *,
            head_only: bool,
        ) -> tuple[dict[str, str], int] | None:
            """Validate a list endpoint's bounded query string.

            Sends the 400 itself and returns None on an unknown or duplicate
            parameter or an out-of-range limit (API Conventions v0.1
            section 11: unknown filters fail explicitly).
            """
            params: dict[str, str] = {}
            for key, value in parse_qsl(query, keep_blank_values=True):
                if key not in allowed or key in params:
                    self._send_json(
                        400,
                        error_document(
                            "unexpected_query_parameters",
                            f"unsupported or duplicate query parameter: {key}",
                            details={"allowed": sorted(allowed)},
                        ),
                        head_only=head_only,
                    )
                    return None
                params[key] = value

            limit = DEFAULT_LIST_LIMIT
            if "limit" in params:
                try:
                    limit = int(params["limit"])
                except ValueError:
                    limit = -1
                if not (1 <= limit <= MAX_LIST_LIMIT):
                    self._send_json(
                        400,
                        error_document(
                            "invalid_limit",
                            f"limit must be an integer between 1 and "
                            f"{MAX_LIST_LIMIT}",
                        ),
                        head_only=head_only,
                    )
                    return None
            return params, limit

        def _work_unit_id_from_path(self, path: str) -> str | None:
            """Return the id if path is /api/v1/work-units/<id>.

            ADR-0021: WorkUnit ids share the run-id grammar and may contain
            "/", so the entire remainder is one literal id. v0.1 reserves no
            work-unit sub-resource suffix.
            """
            prefix = f"/api/{API_VERSION}/work-units/"
            if not path.startswith(prefix):
                return None
            remainder = path[len(prefix):]
            return remainder or None

        def _work_unit_store_unavailable(self, *, head_only: bool) -> bool:
            if product_spine_store_path is not None:
                return False
            self._send_json(
                503,
                error_document(
                    "product_spine_store_not_configured",
                    "this Control Tower instance was started without a "
                    "Product Spine store; work units cannot be read",
                ),
                head_only=head_only,
            )
            return True

        def _work_unit_read_response(
            self, work_unit_id: str, *, head_only: bool
        ) -> None:
            if self._work_unit_store_unavailable(head_only=head_only):
                return
            from idkmesh.connector_store import (
                LocalMetadataStore,
                LocalStoreError,
            )
            from idkmesh.product_spine_run_store import (
                ProductSpineRunStore,
                ProductSpineRunStoreError,
            )

            try:
                service = ProductSpineRunStore(
                    LocalMetadataStore(product_spine_store_path)
                )
                resource = service.get_work_unit(work_unit_id)
            except ProductSpineRunStoreError as exc:
                code = getattr(exc, "code", "run_control_error")
                status = _service_error_status(code, "work_unit_not_found")
                self._send_json(
                    status,
                    error_document(code, str(exc)),
                    head_only=head_only,
                )
                return
            except (LocalStoreError, OSError, ValueError) as exc:
                self._send_json(
                    500,
                    error_document("store_error", str(exc)),
                    head_only=head_only,
                )
                return

            self._send_json(
                200,
                {
                    "api_version": API_VERSION,
                    "schema_version": API_SCHEMA_VERSION,
                    "kind": "idkmesh-control-tower-work-unit-response",
                    "ok": True,
                    "work_unit": resource,
                },
                head_only=head_only,
            )

        def _project_id_from_path(self, path: str) -> str | None:
            """Return the id if path is /api/v1/projects/<project_id>.

            ADR-0021: the entire remainder is one literal project_id; v0.1
            reserves no project sub-resource suffix and has no project list.
            """
            prefix = f"/api/{API_VERSION}/projects/"
            if not path.startswith(prefix):
                return None
            remainder = path[len(prefix):]
            return remainder or None

        def _project_read_response(
            self, project_id: str, *, head_only: bool
        ) -> None:
            if product_spine_store_path is None:
                self._send_json(
                    503,
                    error_document(
                        "product_spine_store_not_configured",
                        "this Control Tower instance was started without a "
                        "Product Spine store; projects cannot be read",
                    ),
                    head_only=head_only,
                )
                return
            from idkmesh.connector_store import (
                LocalMetadataStore,
                LocalStoreError,
            )
            from idkmesh.product_spine_run_store import (
                ProductSpineRunStore,
                ProductSpineRunStoreError,
            )

            try:
                service = ProductSpineRunStore(
                    LocalMetadataStore(product_spine_store_path)
                )
                resource = service.get_project(project_id)
            except ProductSpineRunStoreError as exc:
                code = getattr(exc, "code", "run_control_error")
                status = _service_error_status(code, "project_not_found")
                self._send_json(
                    status,
                    error_document(code, str(exc)),
                    head_only=head_only,
                )
                return
            except (LocalStoreError, OSError, ValueError) as exc:
                self._send_json(
                    500,
                    error_document("store_error", str(exc)),
                    head_only=head_only,
                )
                return

            self._send_json(
                200,
                {
                    "api_version": API_VERSION,
                    "schema_version": API_SCHEMA_VERSION,
                    "kind": "idkmesh-control-tower-project-response",
                    "ok": True,
                    "project": resource,
                },
                head_only=head_only,
            )

        def _work_unit_list_response(
            self, query: str, *, head_only: bool
        ) -> None:
            if self._work_unit_store_unavailable(head_only=head_only):
                return
            parsed_query = self._parse_list_query(
                query,
                {"limit", "cursor", "project_id"},
                head_only=head_only,
            )
            if parsed_query is None:
                return
            params, limit = parsed_query

            from idkmesh.connector_store import (
                LocalMetadataStore,
                LocalStoreError,
            )
            from idkmesh.product_spine_run_store import (
                ProductSpineRunStore,
                ProductSpineRunStoreError,
            )

            try:
                service = ProductSpineRunStore(
                    LocalMetadataStore(product_spine_store_path)
                )
                items, next_cursor = service.list_work_units(
                    limit=limit,
                    cursor=params.get("cursor"),
                    project_id=params.get("project_id"),
                )
            except ProductSpineRunStoreError as exc:
                code = getattr(exc, "code", "run_control_error")
                self._send_json(
                    _service_error_status(code),
                    error_document(code, str(exc)),
                    head_only=head_only,
                )
                return
            except (LocalStoreError, OSError, ValueError) as exc:
                self._send_json(
                    500,
                    error_document("store_error", str(exc)),
                    head_only=head_only,
                )
                return

            self._send_json(
                200,
                {
                    "kind": "idkmesh-list",
                    "schema_version": API_SCHEMA_VERSION,
                    "items": items,
                    "page": {"next_cursor": next_cursor, "limit": limit},
                },
                head_only=head_only,
            )

        def _run_evidence_response(
            self, run_id: str, *, head_only: bool
        ) -> None:
            if product_spine_store_path is None:
                self._send_json(
                    503,
                    error_document(
                        "product_spine_store_not_configured",
                        "this Control Tower instance was started without a "
                        "Product Spine store; runs cannot be read",
                    ),
                    head_only=head_only,
                )
                return
            from idkmesh.connector_store import (
                LocalMetadataStore,
                LocalStoreError,
            )
            from idkmesh.product_spine_run_store import (
                ProductSpineRunStore,
                ProductSpineRunStoreError,
            )

            try:
                service = ProductSpineRunStore(
                    LocalMetadataStore(product_spine_store_path)
                )
                result = service.get_run_evidence(run_id)
            except ProductSpineRunStoreError as exc:
                code = getattr(exc, "code", "run_control_error")
                if code in ("run_not_found", "evidence_not_available"):
                    status = 404
                elif code in ("evidence_integrity_error", "store_error"):
                    status = 500
                else:
                    status = 400
                self._send_json(
                    status,
                    error_document(code, str(exc)),
                    head_only=head_only,
                )
                return
            except (LocalStoreError, OSError, ValueError) as exc:
                self._send_json(
                    500,
                    error_document("store_error", str(exc)),
                    head_only=head_only,
                )
                return

            payload = {
                "api_version": API_VERSION,
                "schema_version": API_SCHEMA_VERSION,
                "kind": "idkmesh-control-tower-run-evidence-response",
                "ok": True,
                "run_id": result["run_id"],
                "evidence_report_digest": result["evidence_report_digest"],
                "evidence_report": result["evidence_report"],
            }
            self._send_json(200, payload, head_only=head_only)

        def _run_list_response(self, query: str, *, head_only: bool) -> None:
            if product_spine_store_path is None:
                self._send_json(
                    503,
                    error_document(
                        "product_spine_store_not_configured",
                        "this Control Tower instance was started without a "
                        "Product Spine store; runs cannot be listed",
                    ),
                    head_only=head_only,
                )
                return

            parsed_query = self._parse_list_query(
                query,
                {"limit", "cursor", "state", "project_id"},
                head_only=head_only,
            )
            if parsed_query is None:
                return
            params, limit = parsed_query

            from idkmesh.connector_store import (
                LocalMetadataStore,
                LocalStoreError,
            )
            from idkmesh.product_spine_run_store import (
                ProductSpineRunStore,
                ProductSpineRunStoreError,
            )

            try:
                service = ProductSpineRunStore(
                    LocalMetadataStore(product_spine_store_path)
                )
                runs, next_cursor = service.list(
                    limit=limit,
                    cursor=params.get("cursor"),
                    state=params.get("state"),
                    project_id=params.get("project_id"),
                )
            except ProductSpineRunStoreError as exc:
                code = getattr(exc, "code", "run_control_error")
                self._send_json(
                    _service_error_status(code),
                    error_document(code, str(exc)),
                    head_only=head_only,
                )
                return
            except (LocalStoreError, OSError, ValueError) as exc:
                self._send_json(
                    500,
                    error_document("store_error", str(exc)),
                    head_only=head_only,
                )
                return

            payload = {
                "kind": "idkmesh-list",
                "schema_version": API_SCHEMA_VERSION,
                "items": [run.to_dict() for run in runs],
                "page": {"next_cursor": next_cursor, "limit": limit},
            }
            self._send_json(200, payload, head_only=head_only)

        def _read_json_text(self) -> str | None:
            if self.headers.get("Transfer-Encoding"):
                self._send_json(
                    400,
                    error_document(
                        "unsupported_transfer_encoding",
                        "chunked/transfer-encoded request bodies are not supported",
                    ),
                )
                return None
            content_type = self.headers.get("Content-Type", "")
            media_type = content_type.split(";", 1)[0].strip().lower()
            if media_type not in {JSON_MEDIA_TYPE, V1_MEDIA_TYPE}:
                self._send_json(
                    415,
                    error_document(
                        "unsupported_media_type",
                        (
                            "API requests must use application/json or "
                            f"{V1_MEDIA_TYPE}"
                        ),
                    ),
                )
                return None
            raw_length = self.headers.get("Content-Length")
            if raw_length is None:
                self._send_json(
                    411,
                    error_document(
                        "length_required",
                        "missing Content-Length header",
                    ),
                )
                return None
            try:
                length = int(raw_length)
            except ValueError:
                self._send_json(
                    400,
                    error_document(
                        "invalid_content_length",
                        "invalid Content-Length header",
                    ),
                )
                return None
            if length < 0:
                self._send_json(
                    400,
                    error_document(
                        "invalid_content_length",
                        "Content-Length cannot be negative",
                    ),
                )
                return None
            if length > MAX_BODY_BYTES:
                self._send_json(
                    413,
                    error_document(
                        "payload_too_large",
                        "request exceeds the 2 MiB local-UI limit",
                    ),
                )
                return None
            try:
                raw = self.rfile.read(length)
            except TimeoutError:
                self.close_connection = True
                self._send_json(
                    408,
                    error_document(
                        "request_timeout",
                        "request body was not received within the "
                        "service request timeout",
                    ),
                )
                return None
            try:
                return raw.decode("utf-8")
            except UnicodeDecodeError:
                self._send_json(
                    400,
                    error_document(
                        "invalid_utf8",
                        "request body must be UTF-8 text",
                    ),
                )
                return None

        def _method_not_allowed(
            self,
            allow: str,
            *,
            code: str = "method_not_allowed",
            message: str = "method not allowed for this endpoint",
            head_only: bool = False,
        ) -> None:
            self._send_json(
                405,
                error_document(code, message),
                head_only=head_only,
                extra_headers={"Allow": allow},
            )

        def _reject_unavailable(
            self,
            verdict: str,
            *,
            overloaded_code: str = "overloaded",
            overloaded_message: str = (
                "the service is at its concurrent request limit; retry "
                "shortly"
            ),
        ) -> None:
            """503 + Retry-After for an overloaded or draining server.

            Does no application work and closes the connection, so a rejected
            request costs a constant amount regardless of its content.
            """
            self.close_connection = True
            draining = verdict == DRAINING
            self._send_json(
                503,
                error_document(
                    "shutting_down" if draining else overloaded_code,
                    (
                        "the service is draining and not accepting new "
                        "requests"
                        if draining
                        else overloaded_message
                    ),
                    retryable=True,
                    details={"retry_after_seconds": DEFAULT_RETRY_AFTER_SECONDS},
                ),
                head_only=self.command == "HEAD",
                extra_headers={"Retry-After": str(DEFAULT_RETRY_AFTER_SECONDS)},
            )

        def _event_service(self):
            """The run-store service, or None after sending the 503."""
            if product_spine_store_path is None:
                self._send_json(
                    503,
                    error_document(
                        "product_spine_store_not_configured",
                        "this Control Tower instance was started without a "
                        "Product Spine store; events cannot be read",
                    ),
                    head_only=self.command == "HEAD",
                )
                return None
            from idkmesh.connector_store import (
                LocalMetadataStore,
                LocalStoreError,
            )
            from idkmesh.product_spine_run_store import ProductSpineRunStore

            try:
                return ProductSpineRunStore(
                    LocalMetadataStore(product_spine_store_path)
                )
            except (LocalStoreError, OSError, ValueError) as exc:
                # Opening the store runs its migration; a locked or corrupt
                # file is a server fault with an error body, not a dropped
                # connection.
                self._send_json(
                    500,
                    error_document("store_error", str(exc)),
                    head_only=self.command == "HEAD",
                )
                return None

        def _event_list_response(self, query: str, *, head_only: bool) -> None:
            parsed_query = self._parse_list_query(
                query,
                {"limit", "cursor", *_EVENT_FILTERS},
                head_only=head_only,
            )
            if parsed_query is None:
                return
            params, limit = parsed_query
            service = self._event_service()
            if service is None:
                return

            from idkmesh.connector_store import LocalStoreError
            from idkmesh.product_spine_run_store import (
                ProductSpineRunStoreError,
            )

            try:
                items, next_cursor = service.list_events(
                    limit=limit,
                    cursor=params.get("cursor"),
                    **{name: params.get(name) for name in _EVENT_FILTERS},
                )
            except ProductSpineRunStoreError as exc:
                code = getattr(exc, "code", "run_control_error")
                self._send_json(
                    _service_error_status(code),
                    error_document(code, str(exc)),
                    head_only=head_only,
                )
                return
            except (LocalStoreError, OSError, ValueError) as exc:
                self._send_json(
                    500,
                    error_document("store_error", str(exc)),
                    head_only=head_only,
                )
                return

            self._send_json(
                200,
                {
                    "kind": "idkmesh-list",
                    "schema_version": API_SCHEMA_VERSION,
                    "items": items,
                    "page": {"next_cursor": next_cursor, "limit": limit},
                },
                head_only=head_only,
            )

        @staticmethod
        def _sse_frame(event: dict[str, Any]) -> bytes:
            data = json.dumps(
                event, sort_keys=True, separators=(",", ":"), ensure_ascii=False
            )
            return (
                f"id: {event['sequence']}\n"
                f"event: {event['event_type']}\n"
                f"data: {data}\n\n"
            ).encode("utf-8")

        def _sse_write(self, payload: bytes) -> None:
            self.wfile.write(payload)
            self.wfile.flush()

        def _event_stream_response(self, query: str) -> None:
            """Read-only, bounded, resumable SSE stream (ADR-0023)."""
            parsed_query = self._parse_list_query(
                query, set(_EVENT_FILTERS), head_only=False
            )
            if parsed_query is None:
                return
            params, _limit = parsed_query

            raw_id = self.headers.get("Last-Event-ID")
            resume_from: int | None = None
            if raw_id is not None:
                text = raw_id.strip()
                if not (text.isascii() and text.isdecimal() and len(text) <= 18):
                    self._send_json(
                        400,
                        error_document(
                            "invalid_last_event_id",
                            "Last-Event-ID must be a non-negative integer "
                            "event sequence",
                        ),
                    )
                    return
                resume_from = int(text)

            service = self._event_service()
            if service is None:
                return

            from idkmesh.connector_store import LocalStoreError
            from idkmesh.product_spine_run_store import (
                ProductSpineRunStoreError,
            )

            filters = {name: params.get(name) for name in _EVENT_FILTERS}
            try:
                # Validates the filters (invalid_event_type) before any
                # stream byte is sent, and fixes the live-tail position.
                service.list_events(limit=1, **filters)
                latest = service.latest_event_sequence()
            except ProductSpineRunStoreError as exc:
                code = getattr(exc, "code", "run_control_error")
                self._send_json(
                    _service_error_status(code), error_document(code, str(exc))
                )
                return
            except (LocalStoreError, OSError, ValueError) as exc:
                self._send_json(500, error_document("store_error", str(exc)))
                return
            if resume_from is not None and resume_from > latest:
                # A client cannot have seen an event this stream has not
                # committed. Accepting it would silently skip every event
                # between the stream head and that id (ADR-0023 decision 8).
                self._send_json(
                    400,
                    error_document(
                        "invalid_last_event_id",
                        "Last-Event-ID is beyond the newest event of this "
                        "stream; it did not come from this store",
                        details={"latest_sequence": latest},
                    ),
                )
                return
            last_seq = resume_from if resume_from is not None else latest

            limits = self.server.limits
            heartbeat = float(limits["sse_heartbeat_seconds"])
            max_stream = float(limits["sse_max_stream_seconds"])
            poll = float(self.server.sse_poll_seconds)
            # The request timeout guards a stalled request; an idle healthy
            # stream is allowed to outlive it up to the heartbeat interval.
            self.connection.settimeout(max(self.timeout or 0.0, heartbeat + 5.0))
            self.close_connection = True
            self._headers(
                200,
                "text/event-stream; charset=utf-8",
                None,
                extra_headers={
                    "Connection": "close",
                    "X-Accel-Buffering": "no",
                },
            )

            limiter = self.server.sse_limiter
            stop = self.server.stream_stop
            started = last_write = time.monotonic()
            try:
                self._sse_write(b"retry: 3000\n\n")
                while True:
                    if limiter.draining or stop.is_set():
                        self._sse_write(b": stream-ended reason=shutdown\n\n")
                        return
                    if time.monotonic() - started >= max_stream:
                        self._sse_write(
                            b": stream-ended reason=max-duration\n\n"
                        )
                        return
                    try:
                        batch = service.events_after(
                            last_seq, limit=_EVENT_BATCH, **filters
                        )
                    except (
                        ProductSpineRunStoreError,
                        LocalStoreError,
                        OSError,
                        ValueError,
                    ):
                        self._sse_write(b": stream-ended reason=store-error\n\n")
                        return
                    for event in batch:
                        self._sse_write(self._sse_frame(event))
                        last_seq = event["sequence"]
                        last_write = time.monotonic()
                    if len(batch) >= _EVENT_BATCH:
                        continue
                    if time.monotonic() - last_write >= heartbeat:
                        self._sse_write(b": keepalive\n\n")
                        last_write = time.monotonic()
                    stop.wait(poll)
            except (BrokenPipeError, ConnectionResetError, TimeoutError, OSError):
                # The client went away or stalled; nothing to report.
                return

        def _handle_get(self, *, head_only: bool) -> None:
            if not self._host_allowed():
                return
            parsed = self._path()
            if parsed is None:
                return
            path, query = parsed
            if path in ("/", "/index.html"):
                self._headers(
                    200,
                    "text/html; charset=utf-8",
                    len(page),
                )
                if not head_only:
                    self.wfile.write(page)
                return
            if path == "/healthz":
                body = b"ok\n"
                self._headers(
                    200,
                    "text/plain; charset=utf-8",
                    len(body),
                )
                if not head_only:
                    self.wfile.write(body)
                return
            if path == "/readyz":
                self._send_json(
                    200,
                    readiness_document(
                        service=SERVICE_NAME,
                        service_version=__version__,
                        mode=SERVICE_MODE,
                        api_version=API_VERSION,
                    ),
                    head_only=head_only,
                )
                return
            if self._unknown_api_version(path):
                return
            if path.startswith(f"/api/{API_VERSION}/"):
                if not self._token_allowed() or not self._accept_allowed():
                    return
            if path == f"/api/{API_VERSION}/status":
                self._send_json(
                    200,
                    status_document(limits=self.server.limits),
                    head_only=head_only,
                )
                return
            if path == f"/api/{API_VERSION}/openapi.json":
                self._send_json(
                    200,
                    openapi_document(),
                    head_only=head_only,
                )
                return
            if path == f"/api/{API_VERSION}/run-evidence/inspect":
                self._method_not_allowed("POST", head_only=head_only)
                return
            if path == f"/api/{API_VERSION}/runs":
                self._run_list_response(query, head_only=head_only)
                return
            if path == f"/api/{API_VERSION}/work-units":
                self._work_unit_list_response(query, head_only=head_only)
                return
            if path == f"/api/{API_VERSION}/events":
                self._event_list_response(query, head_only=head_only)
                return
            if path == _EVENT_STREAM_PATH:
                if head_only:
                    self._method_not_allowed("GET", head_only=True)
                    return
                self._event_stream_response(query)
                return
            work_unit_id = self._work_unit_id_from_path(path)
            if work_unit_id is not None:
                self._work_unit_read_response(
                    work_unit_id, head_only=head_only
                )
                return
            project_id = self._project_id_from_path(path)
            if project_id is not None:
                self._project_read_response(project_id, head_only=head_only)
                return
            subresource = self._run_subresource_from_path(path)
            if subresource is not None:
                run_id, name = subresource
                if name == "attempts":
                    self._run_attempts_response(run_id, head_only=head_only)
                    return
                if name == "evidence":
                    self._run_evidence_response(run_id, head_only=head_only)
                    return
                self._send_json(
                    404,
                    error_document("not_found", "endpoint not found"),
                    head_only=head_only,
                )
                return
            run_id = self._run_id_from_path(path)
            if run_id is not None:
                self._run_read_response(run_id, head_only=head_only)
                return
            self._send_json(
                404,
                error_document("not_found", "endpoint not found"),
                head_only=head_only,
            )

        def do_GET(self) -> None:
            self._handle_get(head_only=False)

        def do_HEAD(self) -> None:
            self._handle_get(head_only=True)

        def do_OPTIONS(self) -> None:
            if not self._host_allowed():
                return
            parsed = self._path()
            if parsed is None:
                return
            path, _query = parsed
            allow = "GET, HEAD"
            if path == f"/api/{API_VERSION}/run-evidence/inspect":
                allow = "POST"
            elif path == _EVENT_STREAM_PATH:
                allow = "GET"
            self._method_not_allowed(
                allow,
                code="preflight_not_supported",
                message="cross-origin preflight is not supported",
            )

        def do_POST(self) -> None:
            if not self._host_allowed():
                return
            parsed = self._path()
            if parsed is None:
                return
            path, _query = parsed
            if self._unknown_api_version(path):
                return
            if path.startswith(f"/api/{API_VERSION}/"):
                if not self._token_allowed() or not self._accept_allowed():
                    return
            if path in (
                "/",
                "/index.html",
                "/healthz",
                "/readyz",
                f"/api/{API_VERSION}/status",
                f"/api/{API_VERSION}/openapi.json",
                f"/api/{API_VERSION}/runs",
                f"/api/{API_VERSION}/work-units",
                f"/api/{API_VERSION}/events",
            ):
                self._method_not_allowed("GET, HEAD")
                return
            if path == _EVENT_STREAM_PATH:
                self._method_not_allowed("GET")
                return
            if (
                self._run_id_from_path(path) is not None
                or self._work_unit_id_from_path(path) is not None
                or self._project_id_from_path(path) is not None
            ):
                self._method_not_allowed("GET, HEAD")
                return
            if path != f"/api/{API_VERSION}/run-evidence/inspect":
                self._send_json(
                    404,
                    error_document("not_found", "endpoint not found"),
                )
                return
            body = self._read_json_text()
            if body is None:
                return
            try:
                report = parse_report_text(
                    body,
                    source="Control Tower API input",
                )
                snapshot = build_snapshot(report)
            except ControlTowerInputError as exc:
                self._send_json(
                    400,
                    error_document("invalid_run_evidence", str(exc)),
                )
                return
            self._send_json(200, success_document(snapshot))

        def _unsupported_write_method(self) -> None:
            if not self._host_allowed():
                return
            parsed = self._path()
            if parsed is None:
                return
            path, _query = parsed
            if self._unknown_api_version(path):
                return
            if path.startswith(f"/api/{API_VERSION}/"):
                if not self._token_allowed() or not self._accept_allowed():
                    return
            if path == f"/api/{API_VERSION}/run-evidence/inspect":
                self._method_not_allowed("POST")
                return
            if path == _EVENT_STREAM_PATH:
                self._method_not_allowed("GET")
                return
            if path in (
                "/",
                "/index.html",
                "/healthz",
                f"/api/{API_VERSION}/status",
                f"/api/{API_VERSION}/openapi.json",
                f"/api/{API_VERSION}/runs",
                f"/api/{API_VERSION}/work-units",
                f"/api/{API_VERSION}/events",
            ) or (
                self._run_id_from_path(path) is not None
                or self._work_unit_id_from_path(path) is not None
                or self._project_id_from_path(path) is not None
            ):
                self._method_not_allowed("GET, HEAD")
                return
            self._send_json(
                404,
                error_document("not_found", "endpoint not found"),
            )

        do_PUT = _unsupported_write_method
        do_PATCH = _unsupported_write_method
        do_DELETE = _unsupported_write_method
        do_TRACE = _unsupported_write_method
        do_CONNECT = _unsupported_write_method

    def _limited(method):
        """Admit a request through the server's RequestLimiter (ADR-0022).

        ``GET /healthz`` is exempt so liveness stays cheap under saturation;
        everything else, including ``/readyz``, is admitted or rejected.
        """

        def wrapper(self):
            if self._access_path() == "/healthz":
                return method(self)
            if (
                self._access_path() == _EVENT_STREAM_PATH
                and self.command == "GET"
            ):
                # ADR-0023: streams hold a connection for minutes, so they
                # use their own cap and never starve the request cap. Other
                # methods on the stream path go through the normal cap and
                # get their 405.
                limiter = self.server.sse_limiter
                reject = {
                    "overloaded_code": "too_many_streams",
                    "overloaded_message": (
                        "the service is at its open event stream limit; "
                        "retry shortly"
                    ),
                }
            else:
                limiter = self.server.limiter
                reject = {}
            verdict = limiter.admit()
            if verdict != ADMITTED:
                self._reject_unavailable(verdict, **reject)
                return None
            try:
                return method(self)
            finally:
                limiter.release()

        wrapper.__name__ = method.__name__
        return wrapper

    for _name in (
        "do_GET", "do_HEAD", "do_OPTIONS", "do_POST", "do_PUT",
        "do_PATCH", "do_DELETE", "do_TRACE", "do_CONNECT",
    ):
        setattr(Handler, _name, _limited(getattr(Handler, _name)))

    return Handler

class ControlTowerServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True
    # ADR-0022: an explicit, small listen backlog bounds queued connections.
    request_queue_size = 16

    ui_token: str
    limiter: RequestLimiter
    sse_limiter: RequestLimiter
    stream_stop: threading.Event
    sse_poll_seconds: float
    limits: dict[str, Any]

    def drain(self, timeout: float = DEFAULT_DRAIN_TIMEOUT_SECONDS) -> bool:
        """Stop admitting requests and wait for in-flight ones to finish.

        Open event streams are told to end (``reason=shutdown``) and count as
        in-flight until they do. Returns False if ``timeout`` elapsed with
        requests or streams still running. Every endpoint is read-only, so
        abandoning one cannot leave a partially committed mutation
        (ADR-0022, ADR-0023).
        """
        deadline = time.monotonic() + timeout
        self.limiter.begin_drain()
        self.sse_limiter.begin_drain()
        self.stream_stop.set()
        idle = self.limiter.wait_idle(timeout)
        remaining = max(0.0, deadline - time.monotonic())
        return self.sse_limiter.wait_idle(remaining) and idle


def create_server(
    initial_text: str | None = None,
    *,
    port: int = DEFAULT_PORT,
    product_spine_store_path: str | None = None,
    request_timeout: float = DEFAULT_REQUEST_TIMEOUT_SECONDS,
    max_concurrent_requests: int = DEFAULT_MAX_CONCURRENT_REQUESTS,
    max_sse_clients: int = DEFAULT_MAX_SSE_CLIENTS,
) -> ControlTowerServer:
    """Create, but do not start, the loopback-only Control Tower server.

    ``product_spine_store_path``, when given, is the SQLite path an existing
    ``idkmesh run create/status/cancel`` invocation already writes to (see
    ``idkmesh/product_spine_run_store.py``). It enables ``GET
    /api/v1/runs/{run_id}``, read-only, over that same durable state; when
    omitted, that endpoint returns 503 rather than being absent.
    """
    request_timeout = validate_request_timeout(request_timeout)
    max_concurrent_requests = validate_max_concurrent_requests(
        max_concurrent_requests
    )
    max_sse_clients = validate_max_sse_clients(max_sse_clients)
    token = _resolve_token()
    server = ControlTowerServer(
        (HOST, port),
        _handler(
            initial_text,
            token,
            product_spine_store_path=product_spine_store_path,
            request_timeout=request_timeout,
        ),
    )
    server.ui_token = token
    server.limiter = RequestLimiter(max_concurrent_requests)
    server.sse_limiter = RequestLimiter(max_sse_clients)
    server.stream_stop = threading.Event()
    server.sse_poll_seconds = SSE_POLL_SECONDS
    server.limits = limits_document(
        request_timeout_seconds=request_timeout,
        max_concurrent_requests=max_concurrent_requests,
        max_request_body_bytes=MAX_BODY_BYTES,
        max_sse_clients=max_sse_clients,
        sse_heartbeat_seconds=SSE_HEARTBEAT_SECONDS,
        sse_max_stream_seconds=SSE_MAX_STREAM_SECONDS,
    )
    return server


def serve_control_tower(
    initial_text: str | None = None,
    *,
    port: int = DEFAULT_PORT,
    open_browser: bool = True,
    product_spine_store_path: str | None = None,
    request_timeout: float = DEFAULT_REQUEST_TIMEOUT_SECONDS,
    max_concurrent_requests: int = DEFAULT_MAX_CONCURRENT_REQUESTS,
    max_sse_clients: int = DEFAULT_MAX_SSE_CLIENTS,
) -> None:
    """Serve the local Control Tower until interrupted, then drain."""
    server = create_server(
        initial_text,
        port=port,
        product_spine_store_path=product_spine_store_path,
        request_timeout=request_timeout,
        max_concurrent_requests=max_concurrent_requests,
        max_sse_clients=max_sse_clients,
    )
    url = f"http://{HOST}:{server.server_port}/"
    print(f"IDKMesh Control Tower: {url}")
    print(
        "Read-only evidence view; no worker execution, push, or merge authority. "
        "Press Ctrl+C to stop."
    )
    if open_browser:
        try:
            opened = webbrowser.open(url)
        except webbrowser.Error:
            opened = False
        if not opened:
            print("Browser did not open automatically; open the URL above.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        if not server.drain():
            print(
                "Control Tower: in-flight requests did not finish within "
                f"{DEFAULT_DRAIN_TIMEOUT_SECONDS:g}s; closing anyway."
            )
        server.server_close()
