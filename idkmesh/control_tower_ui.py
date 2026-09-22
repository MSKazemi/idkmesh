"""Local Human Control Tower UI and versioned read-only API."""

from __future__ import annotations

import html
import json
import os
import secrets
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlsplit

from idkmesh import __version__
from idkmesh.control_tower_api import (
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
from idkmesh.local_ui_security import (
    HOST,
    MAX_BODY_BYTES,
    TOKEN_HEADER,
    is_loopback_host,
    new_session_token,
    send_security_headers,
)

DEFAULT_PORT = 8770
TOKEN_ENV = "IDKMESH_CONTROL_TOWER_TOKEN"

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
    if len(configured) < 32 or any(ch.isspace() for ch in configured):
        raise ValueError(
            f"{TOKEN_ENV} must contain at least 32 non-whitespace characters")
    return configured


def _handler(initial_text: str | None, token: str):
    page = _app_html(initial_text, token).encode("utf-8")

    class Handler(BaseHTTPRequestHandler):
        server_version = "IDKMeshControlTower/0.1"

        def version_string(self) -> str:
            return self.server_version

        def log_message(self, format: str, *args: Any) -> None:
            return

        def _headers(
            self,
            status: int,
            content_type: str,
            length: int,
            *,
            extra_headers: dict[str, str] | None = None,
        ) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(length))
            if extra_headers:
                for name, value in extra_headers.items():
                    self.send_header(name, value)
            send_security_headers(self)
            self.end_headers()

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
                "X-IDKMesh-API-Version": API_VERSION,
                "X-IDKMesh-Content-Digest": digest,
                "X-IDKMesh-Read-Only": "true",
            }
            if extra_headers:
                headers.update(extra_headers)
            self._headers(
                status,
                self._response_media_type() + "; charset=utf-8",
                len(body),
                extra_headers=headers,
            )
            if not head_only:
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
            if parsed.query and parsed.path.startswith("/api/"):
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
            raw = self.rfile.read(length)
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

        def _handle_get(self, *, head_only: bool) -> None:
            if not self._host_allowed():
                return
            parsed = self._path()
            if parsed is None:
                return
            path, _query = parsed
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
                    extra_headers={"X-IDKMesh-Read-Only": "true"},
                )
                if not head_only:
                    self.wfile.write(body)
                return
            if self._unknown_api_version(path):
                return
            if path.startswith(f"/api/{API_VERSION}/"):
                if not self._token_allowed() or not self._accept_allowed():
                    return
            if path == f"/api/{API_VERSION}/status":
                self._send_json(
                    200,
                    status_document(),
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
                f"/api/{API_VERSION}/status",
                f"/api/{API_VERSION}/openapi.json",
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
            if path in (
                "/",
                "/index.html",
                "/healthz",
                f"/api/{API_VERSION}/status",
                f"/api/{API_VERSION}/openapi.json",
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

    return Handler

class ControlTowerServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    ui_token: str


def create_server(
    initial_text: str | None = None,
    *,
    port: int = DEFAULT_PORT,
) -> ControlTowerServer:
    """Create, but do not start, the loopback-only Control Tower server."""
    token = _resolve_token()
    server = ControlTowerServer(
        (HOST, port),
        _handler(initial_text, token),
    )
    server.ui_token = token
    return server


def serve_control_tower(
    initial_text: str | None = None,
    *,
    port: int = DEFAULT_PORT,
    open_browser: bool = True,
) -> None:
    """Serve the local Control Tower until interrupted."""
    server = create_server(initial_text, port=port)
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
        server.server_close()
