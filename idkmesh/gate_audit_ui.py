"""Local, dependency-free browser UI for idkmesh gate-audit.

The UI is intentionally a loopback-only tool rather than a hosted service.
Review verdicts can be sensitive, so the browser talks only to the Python
process bound to 127.0.0.1 and every audit delegates to idkmesh.gate_audit
rather than reimplementing panel mathematics in JavaScript.
"""

from __future__ import annotations

import html
import json
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from idkmesh import __version__
from idkmesh.gate_audit import GateAuditInputError, audit_text, render_markdown
from idkmesh.local_ui_security import (
    HOST,
    MAX_BODY_BYTES,
    TOKEN_HEADER,
    is_loopback_host,
    new_session_token,
    send_security_headers,
)

DEFAULT_PORT = 8765

_SAMPLE = {
    "gate_id": "local-demo",
    "evidence_class": "synthetic",
    "candidates": [
        {"id": "good-1", "ground_truth": "accept"},
        {"id": "good-2", "ground_truth": "accept"},
        {"id": "bad-1", "ground_truth": "reject"},
        {"id": "bad-2", "ground_truth": "reject"},
        {
            "id": "probe-1",
            "ground_truth": "reject",
            "probe": True,
            "probe_kind": "seeded-defect",
        },
    ],
    "verifiers": [
        {
            "id": "reviewer-a",
            "verdicts": {
                "good-1": "accept",
                "good-2": "accept",
                "bad-1": "reject",
                "bad-2": "accept",
                "probe-1": "accept",
            },
        },
        {
            "id": "reviewer-b",
            "verdicts": {
                "good-1": "accept",
                "good-2": "reject",
                "bad-1": "reject",
                "bad-2": "reject",
                "probe-1": "reject",
            },
        },
        {
            "id": "reviewer-c",
            "verdicts": {
                "good-1": "accept",
                "good-2": "accept",
                "bad-1": "accept",
                "bad-2": "reject",
                "probe-1": "accept",
            },
        },
    ],
}
SAMPLE_INPUT = json.dumps(_SAMPLE, indent=2)


def _app_html(initial_text: str | None, token: str) -> str:
    source = SAMPLE_INPUT if initial_text is None else initial_text
    safe_source = html.escape(source)
    page = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="color-scheme" content="dark">
  <meta name="robots" content="noindex,nofollow">
  <title>IDKMesh Gate Audit</title>
  <style>
    :root {
      --bg:#070b14; --bg2:#0b1220; --panel:#10192b; --panel2:#152039;
      --line:#2a3857; --line2:#3a4b70; --text:#eef4ff; --muted:#9aa9c3;
      --faint:#6f7e99; --cyan:#8bd3ff; --mint:#b9ffcf; --amber:#ffd28b;
      --red:#ff9d9d; --violet:#c9b8ff; --shadow:0 24px 70px rgba(0,0,0,.28);
      --mono:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
      --sans:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
    }
    * { box-sizing:border-box; }
    html { scroll-behavior:smooth; }
    body {
      margin:0; min-height:100vh; color:var(--text); font-family:var(--sans); line-height:1.5;
      background:
        radial-gradient(1000px 620px at 92% -5%, rgba(139,211,255,.12), transparent 62%),
        radial-gradient(860px 520px at -5% 30%, rgba(185,255,207,.08), transparent 58%),
        var(--bg);
    }
    button,input,textarea { font:inherit; }
    button,a { -webkit-tap-highlight-color:transparent; }
    a { color:var(--cyan); }
    .wrap { width:min(1280px,calc(100% - 2rem)); margin:auto; }
    .skip { position:absolute; left:-9999px; top:0; z-index:30; background:var(--text); color:var(--bg); padding:.65rem 1rem; }
    .skip:focus { left:0; }
    header {
      position:sticky; top:0; z-index:20; border-bottom:1px solid rgba(42,56,87,.85);
      background:rgba(7,11,20,.88); backdrop-filter:blur(12px) saturate(140%);
    }
    .top { min-height:64px; display:flex; align-items:center; gap:1rem; }
    .brand { display:flex; gap:.65rem; align-items:center; font-weight:850; letter-spacing:-.02em; }
    .brand svg { width:28px; height:28px; flex:none; }
    .pill { margin-left:auto; border:1px solid var(--line); border-radius:999px; padding:.28rem .7rem; color:var(--mint); font-size:.79rem; font-weight:750; }
    main { padding:2rem 0 4.5rem; }
    .hero {
      display:grid; grid-template-columns:minmax(0,1.25fr) minmax(300px,.75fr);
      gap:1.3rem; align-items:end; margin-bottom:1.25rem;
    }
    .eyebrow { color:var(--mint); font-size:.74rem; font-weight:850; letter-spacing:.11em; text-transform:uppercase; }
    h1 { font-size:clamp(2.15rem,5vw,3.8rem); line-height:.98; margin:.3rem 0 .75rem; letter-spacing:-.04em; max-width:15ch; }
    h1 span { background:linear-gradient(100deg,var(--cyan),var(--mint)); -webkit-background-clip:text; background-clip:text; color:transparent; }
    .lead { margin:0; color:var(--muted); font-size:1.02rem; max-width:72ch; }
    .privacy {
      border:1px solid var(--line); border-left:3px solid var(--mint); border-radius:12px;
      padding:.85rem .95rem; color:var(--muted); background:rgba(185,255,207,.035); font-size:.9rem;
    }
    .privacy strong { color:var(--text); }
    .workspace { display:grid; grid-template-columns:minmax(0,1.02fr) minmax(380px,.98fr); gap:1rem; align-items:start; }
    .panel {
      background:linear-gradient(180deg,rgba(16,25,43,.98),rgba(11,18,32,.98));
      border:1px solid var(--line); border-radius:17px; padding:1rem; box-shadow:var(--shadow);
    }
    .panel-head { display:flex; gap:.75rem; align-items:center; justify-content:space-between; flex-wrap:wrap; margin-bottom:.8rem; }
    .panel h2 { margin:0; font-size:1rem; }
    .panel-sub { margin:.15rem 0 0; color:var(--faint); font-size:.8rem; }
    .toolbar { display:flex; gap:.45rem; flex-wrap:wrap; }
    .file-label,button,.download {
      display:inline-flex; align-items:center; justify-content:center; gap:.35rem;
      border:1px solid var(--line); background:var(--panel2); color:var(--text);
      padding:.52rem .72rem; min-height:38px; border-radius:9px; cursor:pointer;
      text-decoration:none; font-weight:750; font-size:.86rem;
    }
    button.primary { background:var(--text); color:var(--bg); border-color:var(--text); }
    button.ghost { background:transparent; color:var(--muted); }
    button:disabled { cursor:not-allowed; opacity:.45; }
    button:not(:disabled):hover,.file-label:hover,.download:hover { border-color:var(--cyan); }
    button.primary:not(:disabled):hover { background:var(--cyan); border-color:var(--cyan); }
    :focus-visible { outline:2px solid var(--cyan); outline-offset:2px; }
    #file { position:absolute; width:1px; height:1px; overflow:hidden; clip:rect(0 0 0 0); white-space:nowrap; }
    .editor-shell { position:relative; }
    textarea {
      display:block; width:100%; min-height:560px; resize:vertical; border:1px solid var(--line);
      border-radius:12px; background:#050913; color:#dfeaff; padding:1rem; font-family:var(--mono);
      font-size:.81rem; line-height:1.55; tab-size:2; caret-color:var(--mint);
    }
    .input-meta { display:flex; gap:.4rem; flex-wrap:wrap; margin:.7rem 0 0; min-height:1.4rem; }
    .chip {
      display:inline-flex; align-items:center; border:1px solid var(--line); border-radius:999px;
      padding:.15rem .52rem; color:var(--muted); font-size:.74rem; font-weight:700;
    }
    .chip.ok { color:var(--mint); border-color:rgba(185,255,207,.38); }
    .chip.warn { color:var(--amber); border-color:rgba(255,210,139,.4); }
    .status { min-height:1.45rem; margin:.58rem 0 0; color:var(--muted); font-size:.86rem; }
    .status.error { color:var(--red); }
    .status.success { color:var(--mint); }
    .hint { color:var(--faint); font-size:.76rem; margin:.55rem 0 0; }
    .result-empty { min-height:260px; display:grid; place-items:center; text-align:center; color:var(--muted); padding:2rem .8rem; }
    .result-empty strong { display:block; color:var(--text); margin-bottom:.3rem; }
    .result-top { display:flex; gap:.65rem; align-items:flex-start; justify-content:space-between; flex-wrap:wrap; }
    .result-title { font-size:1.25rem; font-weight:850; letter-spacing:-.02em; }
    .result-meta { color:var(--muted); font-size:.82rem; margin-top:.18rem; }
    .badge { display:inline-block; border:1px solid currentColor; border-radius:999px; padding:.15rem .55rem; font-size:.71rem; font-weight:850; letter-spacing:.05em; text-transform:uppercase; color:var(--violet); }
    .summary {
      border:1px solid var(--line); border-radius:12px; padding:.9rem 1rem; margin:.8rem 0;
      background:linear-gradient(100deg,rgba(139,211,255,.06),rgba(185,255,207,.035));
      font-size:.92rem;
    }
    .summary .headline { font-size:1.05rem; font-weight:800; color:var(--text); margin-bottom:.25rem; }
    .summary strong { color:var(--mint); }
    .metrics { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:.6rem; margin:.75rem 0; }
    .metric { min-width:0; border:1px solid var(--line); border-radius:11px; padding:.72rem .75rem; background:rgba(255,255,255,.018); }
    .metric .v { font-size:clamp(1.25rem,2.4vw,1.7rem); font-weight:850; letter-spacing:-.03em; font-variant-numeric:tabular-nums; overflow-wrap:anywhere; }
    .metric .k { color:var(--muted); font-size:.72rem; margin-top:.16rem; }
    .metric.eff .v { color:var(--cyan); }
    .metric.probe .v { color:var(--amber); }
    .metric.bad .v { color:var(--red); }
    .section { border-top:1px solid var(--line); padding-top:.9rem; margin-top:.95rem; }
    .section h3 { font-size:.9rem; margin:0 0 .6rem; }
    .bars { display:grid; gap:.5rem; }
    .bar-row { display:grid; grid-template-columns:125px 1fr 65px; gap:.65rem; align-items:center; font-size:.78rem; color:var(--muted); }
    .bar-row strong { color:var(--text); font-weight:700; }
    progress { width:100%; height:10px; appearance:none; border:0; border-radius:999px; overflow:hidden; background:#050913; }
    progress::-webkit-progress-bar { background:#050913; border-radius:999px; }
    progress::-webkit-progress-value { background:linear-gradient(90deg,var(--cyan),var(--mint)); border-radius:999px; }
    progress::-moz-progress-bar { background:linear-gradient(90deg,var(--cyan),var(--mint)); border-radius:999px; }
    .table-wrap { overflow:auto; border:1px solid var(--line); border-radius:10px; }
    table { width:100%; border-collapse:collapse; font-size:.79rem; min-width:420px; }
    th,td { padding:.55rem .65rem; border-bottom:1px solid var(--line); text-align:left; }
    th { color:var(--faint); font-size:.69rem; letter-spacing:.06em; text-transform:uppercase; background:rgba(255,255,255,.018); }
    tr:last-child td { border-bottom:0; }
    td.num { font-variant-numeric:tabular-nums; white-space:nowrap; }
    .warnings { margin:.25rem 0 0; padding-left:1.2rem; color:var(--amber); font-size:.83rem; }
    .warnings li { margin:.35rem 0; }
    .all-clear { color:var(--muted); font-size:.82rem; margin:0; }
    .provenance { display:grid; grid-template-columns:auto 1fr; gap:.35rem .7rem; font-size:.76rem; color:var(--muted); }
    .provenance dt { color:var(--faint); }
    .provenance dd { margin:0; font-family:var(--mono); overflow-wrap:anywhere; }
    details { border-top:1px solid var(--line); margin-top:.95rem; padding-top:.8rem; }
    summary { cursor:pointer; color:var(--muted); font-weight:750; font-size:.82rem; }
    pre { white-space:pre-wrap; word-break:break-word; background:#050913; border:1px solid var(--line); border-radius:10px; padding:.8rem; max-height:360px; overflow:auto; font:.76rem/1.5 var(--mono); }
    footer { color:var(--faint); font-size:.79rem; margin-top:1rem; text-align:center; }
    .hidden { display:none !important; }
    @media (max-width:1080px) { .metrics { grid-template-columns:repeat(2,minmax(0,1fr)); } }
    @media (max-width:920px) {
      header { position:static; }
      .hero,.workspace { grid-template-columns:1fr; }
      textarea { min-height:400px; }
    }
    @media (max-width:560px) {
      .wrap { width:min(calc(100% - 1rem),1280px); }
      main { padding-top:1.3rem; }
      h1 { font-size:clamp(2rem,12vw,3rem); }
      .panel { padding:.75rem; border-radius:13px; }
      .toolbar { width:100%; }
      .toolbar > * { flex:1 1 auto; }
      .metrics { grid-template-columns:1fr 1fr; }
      .bar-row { grid-template-columns:105px 1fr 55px; gap:.4rem; }
    }
    @media (prefers-reduced-motion:reduce) { html { scroll-behavior:auto; } }
  </style>
</head>
<body>
<a class="skip" href="#main">Skip to audit workspace</a>
<header>
  <div class="wrap top">
    <div class="brand">
      <svg viewBox="0 0 32 32" aria-hidden="true">
        <circle cx="16" cy="6" r="3" fill="#8bd3ff"></circle>
        <circle cx="6" cy="23" r="3" fill="#b9ffcf"></circle>
        <circle cx="26" cy="23" r="3" fill="#c9b8ff"></circle>
        <circle cx="16" cy="16" r="2.2" fill="#eef4ff"></circle>
        <g stroke="#3a4b70" stroke-width="1.5"><path d="M16 9v4.8"></path><path d="M8.6 21.2l5.5-3.5"></path><path d="M23.4 21.2l-5.5-3.5"></path></g>
      </svg>
      IDKMesh Gate Audit
    </div>
    <span class="pill">local-only · v__VERSION__</span>
  </div>
</header>
<main id="main" class="wrap">
  <section class="hero" aria-labelledby="page-title">
    <div>
      <div class="eyebrow">Review-panel diagnostic</div>
      <h1 id="page-title">Measure the panel, not the <span>head-count.</span></h1>
      <p class="lead">Load verdicts with known ground truth and see effective independent votes, error correlation, false accepts and rejects, seeded-probe breaches, and verifier-level accuracy.</p>
    </div>
    <div class="privacy"><strong>Your data stays local.</strong> The browser sends the matrix only to this Python process on 127.0.0.1. A per-session token protects the audit endpoint, and no hosted IDKMesh service receives the verdicts.</div>
  </section>

  <div class="workspace">
    <section class="panel" aria-labelledby="input-title">
      <div class="panel-head">
        <div>
          <h2 id="input-title">Verdict matrix</h2>
          <p class="panel-sub">Paste JSON or open a file. Press Ctrl/Cmd + Enter to audit.</p>
        </div>
        <div class="toolbar">
          <label class="file-label">Open JSON<input id="file" type="file" accept=".json,application/json"></label>
          <button id="sample" type="button">Example</button>
          <button id="format" type="button">Format</button>
          <button id="clear" class="ghost" type="button">Clear</button>
          <button id="run" class="primary" type="button">Audit panel</button>
        </div>
      </div>
      <div class="editor-shell">
        <textarea id="source" spellcheck="false" autocomplete="off" aria-label="Verdict matrix JSON">__INITIAL__</textarea>
      </div>
      <div id="input-meta" class="input-meta" aria-live="polite"></div>
      <div id="status" class="status" role="status" aria-live="polite">Ready. The strict server-side contract is checked when you audit.</div>
      <p class="hint">The local preview checks ordinary JSON syntax; the audit endpoint additionally rejects duplicate keys, incomplete verdict matrices, invalid evidence classes, and other Gate Audit v0.1 contract violations.</p>
    </section>

    <section class="panel" aria-labelledby="result-title">
      <div class="panel-head">
        <div>
          <h2 id="result-title">Audit result</h2>
          <p class="panel-sub">Decision support only; this does not grant acceptance authority.</p>
        </div>
        <div id="result-actions" class="toolbar hidden">
          <button id="copy-json" type="button">Copy JSON</button>
          <button id="copy-md" type="button">Copy Markdown</button>
          <a id="download-json" class="download" href="#" download="gate-audit-report.json">JSON ↓</a>
          <a id="download-md" class="download" href="#" download="gate-audit-report.md">Markdown ↓</a>
        </div>
      </div>
      <div id="result" class="result-empty"><div><strong>No audit yet.</strong>Load the example or your verdict matrix, then choose Audit panel.</div></div>
    </section>
  </div>
  <footer>Worker success ≠ acceptance · verification recommendation ≠ merge authority · local GUI ≠ hosted service</footer>
</main>
<script>
(function () {
  "use strict";
  var source = document.getElementById("source");
  var file = document.getElementById("file");
  var status = document.getElementById("status");
  var inputMeta = document.getElementById("input-meta");
  var result = document.getElementById("result");
  var actions = document.getElementById("result-actions");
  var run = document.getElementById("run");
  var sampleText = __SAMPLE_JSON__;
  var uiToken = __UI_TOKEN__;
  var maxBodyBytes = __MAX_BODY_BYTES__;
  var currentJson = "";
  var currentMarkdown = "";
  var jsonUrl = "";
  var mdUrl = "";
  var inputTimer = 0;

  function esc(value) {
    return String(value).replace(/[&<>"']/g, function (ch) {
      return {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[ch];
    });
  }
  function fmt(value, digits) {
    if (value === null || value === undefined) return "n/a";
    if (typeof value === "number") return value.toFixed(digits === undefined ? 3 : digits);
    return String(value);
  }
  function pct(value) {
    return value === null || value === undefined ? "n/a" : (100 * value).toFixed(1) + "%";
  }
  function effectiveLabel(value) {
    if (value === null || value === undefined) return "n/a";
    return Number(value) >= 199 ? "≥" + Number(value).toFixed(0) : Number(value).toFixed(2);
  }
  function setStatus(message, kind) {
    status.textContent = message;
    status.className = "status" + (kind ? " " + kind : "");
  }
  function setInputMeta(items) {
    inputMeta.innerHTML = items.map(function (item) {
      return '<span class="chip ' + esc(item.kind || "") + '">' + esc(item.text) + "</span>";
    }).join("");
  }
  function previewInput() {
    window.clearTimeout(inputTimer);
    inputTimer = window.setTimeout(function () {
      var text = source.value.trim();
      if (!text) {
        setInputMeta([{text:"empty editor",kind:"warn"}]);
        return;
      }
      try {
        var data = JSON.parse(text);
        var candidates = Array.isArray(data.candidates) ? data.candidates.length : 0;
        var verifiers = Array.isArray(data.verifiers) ? data.verifiers.length : 0;
        var evidence = typeof data.evidence_class === "string" ? data.evidence_class : "undeclared";
        setInputMeta([
          {text:"JSON syntax OK",kind:"ok"},
          {text:candidates + " candidates"},
          {text:verifiers + " verifiers"},
          {text:"evidence: " + evidence}
        ]);
      } catch (err) {
        setInputMeta([{text:"JSON syntax needs attention",kind:"warn"}]);
      }
    }, 180);
  }
  function metric(value, label, cls) {
    return '<div class="metric ' + (cls || "") + '"><div class="v">' + esc(value) +
      '</div><div class="k">' + esc(label) + "</div></div>";
  }
  function table(headers, rows) {
    if (!rows.length) return '<p class="all-clear">No rows to show.</p>';
    return '<div class="table-wrap"><table><thead><tr>' +
      headers.map(function (h) { return "<th>" + esc(h) + "</th>"; }).join("") +
      "</tr></thead><tbody>" +
      rows.map(function (row) {
        return "<tr>" + row.map(function (cell, i) {
          return '<td class="' + (i ? "num" : "") + '">' + esc(cell) + "</td>";
        }).join("") + "</tr>";
      }).join("") + "</tbody></table></div>";
  }
  function barChart(panel) {
    var values = [
      ["Nominal", panel.nominal_votes],
      ["Measured", panel.effective_votes],
      ["Heuristic", panel.heuristic_n_eff],
      ["Ceiling", typeof panel.effective_votes_ceiling === "number" ? panel.effective_votes_ceiling : null]
    ];
    var numeric = values.map(function (v) { return Number(v[1]); }).filter(function (v) { return Number.isFinite(v) && v >= 0; });
    var max = numeric.length ? Math.max.apply(null, numeric) : 1;
    if (max <= 0) max = 1;
    return '<div class="bars">' + values.map(function (item) {
      var raw = item[1];
      var num = Number(raw);
      var has = Number.isFinite(num) && num >= 0;
      var shown = item[0] === "Measured" ? effectiveLabel(raw) : fmt(raw, 2);
      if (raw === "unbounded") shown = "unbounded";
      return '<div class="bar-row"><strong>' + esc(item[0]) + '</strong>' +
        '<progress max="' + esc(max) + '" value="' + esc(has ? num : 0) + '"></progress>' +
        '<span>' + esc(shown) + "</span></div>";
    }).join("") + "</div>";
  }
  function render(report) {
    var p = report.panel;
    var probes = report.probes;
    var eff = effectiveLabel(p.effective_votes);
    var probeText = probes ? probes.breached + " / " + probes.total : "none";
    var warningHtml = report.warnings.length
      ? '<ul class="warnings">' + report.warnings.map(function (w) { return "<li>" + esc(w) + "</li>"; }).join("") + "</ul>"
      : '<p class="all-clear">No audit warnings on this candidate set.</p>';
    var verifierRows = report.verifiers.map(function (v) {
      return [v.id, pct(v.accuracy), String(v.errors)];
    });
    var probeRows = probes ? Object.keys(probes.by_kind).map(function (kind) {
      var bucket = probes.by_kind[kind];
      return [kind, String(bucket.breached), String(bucket.total), pct(bucket.total ? bucket.breached / bucket.total : 0)];
    }) : [];
    var digest = report.provenance.input_digest_sha256 || "";
    var ratio = p.nominal_votes && p.effective_votes !== null
      ? Number(p.effective_votes) / Number(p.nominal_votes)
      : null;
    var ratioText = ratio === null ? "n/a" : ratio.toFixed(2) + "× nominal";
    result.className = "";
    result.innerHTML =
      '<div class="result-top"><div><span class="badge">' + esc(report.evidence_class) +
      '</span><div class="result-title">' + esc(report.gate_id) + '</div>' +
      '<div class="result-meta">' + esc(report.inputs.candidates) + " candidates · " +
      esc(report.inputs.verifiers) + " verifiers · quorum " + esc(fmt(p.quorum, 2)) + "</div></div></div>" +
      '<div class="summary"><div class="headline">' + esc(p.nominal_votes) +
      " nominal votes → <strong>" + esc(eff) + " effective independent votes</strong></div>" +
      "Measured from panel error on the non-probe candidate set. Effective size can exceed nominal head-count on a finite sample; a value at ≥199 is censored by the comparison table, not resolved exactly.</div>" +
      '<div class="metrics">' +
      metric(eff, "effective votes", "eff") +
      metric(String(p.nominal_votes), "nominal votes", "") +
      metric(pct(p.mean_verifier_accuracy), "mean verifier accuracy", "") +
      metric(fmt(p.mean_pairwise_error_correlation, 3), "error correlation", "") +
      metric(pct(p.error), "panel error", p.error > 0 ? "bad" : "") +
      metric(pct(p.false_accept_rate), "false-accept rate", p.false_accept_rate > 0 ? "bad" : "") +
      metric(pct(p.false_reject_rate), "false-reject rate", p.false_reject_rate > 0 ? "bad" : "") +
      metric(probeText, "seeded probes breached", probes && probes.breached ? "probe" : "") +
      "</div>" +
      '<div class="section"><h3>Panel-size comparison</h3>' + barChart(p) +
      '<p class="hint">Measured effective votes are the audit estimand. The N/(1+(N-1)ρ) heuristic is shown only for contrast; the research record documents regimes where it is optimistic.</p></div>' +
      '<div class="section"><h3>Warnings</h3>' + warningHtml + "</div>" +
      '<div class="section"><h3>Verifier detail</h3>' +
      table(["Verifier","Accuracy","Errors"], verifierRows) + "</div>" +
      '<div class="section"><h3>Seeded probes by kind</h3>' +
      (probes ? table(["Probe kind","Breached","Total","Rate"], probeRows) :
        '<p class="all-clear">No seeded probes were included in this matrix.</p>') + "</div>" +
      '<div class="section"><h3>Advanced panel metrics</h3>' +
      table(["Metric","Value"], [
        ["Measured / nominal", ratioText],
        ["Heuristic effective N", fmt(p.heuristic_n_eff, 3)],
        ["Effective-vote ceiling", fmt(p.effective_votes_ceiling, 3)],
        ["Skipped correlation pairs", String(p.skipped_correlation_pairs)],
        ["Known good candidates", String(report.inputs.known_good)],
        ["Known bad candidates", String(report.inputs.known_bad)]
      ]) + "</div>" +
      '<div class="section"><h3>Provenance</h3><dl class="provenance">' +
      "<dt>Tool</dt><dd>" + esc(report.provenance.tool + " " + report.provenance.tool_version) + "</dd>" +
      "<dt>Input SHA-256</dt><dd>" + esc(digest) + "</dd>" +
      "<dt>Evidence class</dt><dd>" + esc(report.evidence_class) + "</dd></dl></div>" +
      '<details><summary>Raw report JSON</summary><pre>' + esc(currentJson) + "</pre></details>";
    actions.classList.remove("hidden");
  }
  function revokeDownloads() {
    if (jsonUrl) URL.revokeObjectURL(jsonUrl);
    if (mdUrl) URL.revokeObjectURL(mdUrl);
    jsonUrl = "";
    mdUrl = "";
  }
  function setDownloads() {
    revokeDownloads();
    jsonUrl = URL.createObjectURL(new Blob([currentJson + "\n"], {type:"application/json"}));
    mdUrl = URL.createObjectURL(new Blob([currentMarkdown], {type:"text/markdown"}));
    document.getElementById("download-json").href = jsonUrl;
    document.getElementById("download-md").href = mdUrl;
  }
  function resetResult() {
    currentJson = "";
    currentMarkdown = "";
    actions.classList.add("hidden");
    revokeDownloads();
    result.className = "result-empty";
    result.innerHTML = "<div><strong>No audit yet.</strong>Load the example or your verdict matrix, then choose Audit panel.</div>";
  }
  async function runAudit() {
    var bytes = new TextEncoder().encode(source.value).length;
    if (!source.value.trim()) {
      setStatus("The editor is empty. Load or paste a verdict matrix first.", "error");
      return;
    }
    if (bytes > maxBodyBytes) {
      setStatus("This matrix is larger than the 2 MiB local-UI limit. Use idkmesh gate-audit from the CLI.", "error");
      return;
    }
    run.disabled = true;
    actions.classList.add("hidden");
    result.className = "result-empty";
    result.textContent = "Auditing locally…";
    setStatus("Running the strict Gate Audit v0.1 checks locally…", "");
    try {
      var response = await fetch("/api/audit", {
        method:"POST",
        headers:{
          "Content-Type":"application/json; charset=utf-8",
          "X-IDKMesh-UI-Token":uiToken
        },
        body:source.value
      });
      var payload = await response.json();
      if (!response.ok || !payload.ok) throw new Error(payload.error || "Audit failed.");
      currentJson = JSON.stringify(payload.report, null, 2);
      currentMarkdown = payload.markdown || "";
      render(payload.report);
      setDownloads();
      setStatus("Audit complete. The report is bound to the input digest shown in Provenance.", "success");
    } catch (err) {
      resetResult();
      setStatus(err && err.message ? err.message : String(err), "error");
    } finally {
      run.disabled = false;
    }
  }
  async function copyText(text, label) {
    try {
      await navigator.clipboard.writeText(text);
      setStatus(label + " copied.", "success");
    } catch (err) {
      setStatus("Clipboard access was blocked. Use the download button instead.", "error");
    }
  }

  file.addEventListener("change", function () {
    if (!file.files || !file.files[0]) return;
    var chosen = file.files[0];
    if (chosen.size > maxBodyBytes) {
      setStatus("That file is larger than the 2 MiB local-UI limit. Use the CLI for larger matrices.", "error");
      return;
    }
    var reader = new FileReader();
    reader.onload = function () {
      source.value = String(reader.result || "");
      previewInput();
      resetResult();
      setStatus("Loaded " + chosen.name + ". Ready to audit.", "");
    };
    reader.onerror = function () { setStatus("Could not read that file.", "error"); };
    reader.readAsText(chosen, "utf-8");
  });
  source.addEventListener("input", function () {
    previewInput();
    if (currentJson) resetResult();
  });
  source.addEventListener("keydown", function (event) {
    if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
      event.preventDefault();
      runAudit();
    }
  });
  document.getElementById("sample").addEventListener("click", function () {
    source.value = sampleText;
    previewInput();
    resetResult();
    setStatus("Loaded the built-in synthetic example.", "");
  });
  document.getElementById("format").addEventListener("click", function () {
    try {
      source.value = JSON.stringify(JSON.parse(source.value), null, 2);
      previewInput();
      setStatus("Formatted the editor as ordinary JSON. Strict duplicate-key checking still happens on audit.", "success");
    } catch (err) {
      setStatus("Cannot format until the JSON syntax is valid: " + err.message, "error");
    }
  });
  document.getElementById("clear").addEventListener("click", function () {
    source.value = "";
    file.value = "";
    previewInput();
    resetResult();
    setStatus("Editor cleared.", "");
    source.focus();
  });
  run.addEventListener("click", runAudit);
  document.getElementById("copy-json").addEventListener("click", function () {
    copyText(currentJson, "JSON report");
  });
  document.getElementById("copy-md").addEventListener("click", function () {
    copyText(currentMarkdown, "Markdown summary");
  });
  window.addEventListener("beforeunload", revokeDownloads);
  previewInput();
}());
</script>
</body>
</html>
"""
    return (
        page.replace("__INITIAL__", safe_source)
        .replace("__VERSION__", html.escape(__version__))
        .replace("__SAMPLE_JSON__", json.dumps(SAMPLE_INPUT))
        .replace("__UI_TOKEN__", json.dumps(token))
        .replace("__MAX_BODY_BYTES__", str(MAX_BODY_BYTES))
    )


def _json_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, allow_nan=False, separators=(",", ":")).encode("utf-8")


def _handler(initial_text: str | None, token: str):
    page = _app_html(initial_text, token).encode("utf-8")

    class Handler(BaseHTTPRequestHandler):
        server_version = "IDKMeshGateAuditUI/0.2"

        def log_message(self, format: str, *args: Any) -> None:
            return

        def _headers(self, status: int, content_type: str, length: int) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(length))
            send_security_headers(self)
            self.end_headers()

        def _send_json(self, status: int, payload: dict[str, Any]) -> None:
            body = _json_bytes(payload)
            self._headers(status, "application/json; charset=utf-8", len(body))
            self.wfile.write(body)

        def _host_allowed(self) -> bool:
            if is_loopback_host(self.headers.get("Host")):
                return True
            self._send_json(
                403,
                {
                    "ok": False,
                    "error": "local UI requests must use a loopback Host header",
                },
            )
            return False

        def do_GET(self) -> None:
            if not self._host_allowed():
                return
            if self.path in ("/", "/index.html"):
                self._headers(200, "text/html; charset=utf-8", len(page))
                self.wfile.write(page)
                return
            if self.path == "/healthz":
                body = b"ok\n"
                self._headers(200, "text/plain; charset=utf-8", len(body))
                self.wfile.write(body)
                return
            self._send_json(404, {"ok": False, "error": "not found"})

        def do_OPTIONS(self) -> None:
            if not self._host_allowed():
                return
            self._send_json(
                405,
                {
                    "ok": False,
                    "error": "cross-origin preflight is not supported",
                },
            )

        def do_POST(self) -> None:
            if not self._host_allowed():
                return
            if self.path != "/api/audit":
                self._send_json(404, {"ok": False, "error": "not found"})
                return
            if self.headers.get(TOKEN_HEADER) != token:
                self._send_json(
                    403,
                    {
                        "ok": False,
                        "error": "missing or invalid local UI session token",
                    },
                )
                return
            content_type = self.headers.get("Content-Type", "")
            media_type = content_type.split(";", 1)[0].strip().lower()
            if media_type != "application/json":
                self._send_json(
                    415,
                    {
                        "ok": False,
                        "error": "audit requests must use application/json",
                    },
                )
                return
            raw_length = self.headers.get("Content-Length")
            if raw_length is None:
                self._send_json(
                    411,
                    {"ok": False, "error": "missing Content-Length header"},
                )
                return
            try:
                length = int(raw_length)
            except ValueError:
                self._send_json(
                    400,
                    {"ok": False, "error": "invalid Content-Length header"},
                )
                return
            if length < 0 or length > MAX_BODY_BYTES:
                self._send_json(
                    413,
                    {
                        "ok": False,
                        "error": (
                            "input is larger than the 2 MiB local-UI limit; "
                            "use the CLI for larger matrices"
                        ),
                    },
                )
                return
            body = self.rfile.read(length)
            try:
                source = body.decode("utf-8")
            except UnicodeDecodeError:
                self._send_json(
                    400,
                    {"ok": False, "error": "browser input is not UTF-8 text"},
                )
                return
            try:
                report = audit_text(source, source="browser input")
            except GateAuditInputError as exc:
                self._send_json(400, {"ok": False, "error": str(exc)})
                return
            self._send_json(
                200,
                {
                    "ok": True,
                    "report": report,
                    "markdown": render_markdown(report),
                },
            )

    return Handler


class GateAuditUIServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    ui_token: str


def create_server(
    initial_text: str | None = None,
    *,
    port: int = DEFAULT_PORT,
) -> GateAuditUIServer:
    """Create, but do not start, the loopback-only audit UI server.

    port=0 is supported for tests and library callers that want the kernel to
    choose an unused local port.
    """
    token = new_session_token()
    server = GateAuditUIServer((HOST, port), _handler(initial_text, token))
    server.ui_token = token
    return server


def serve_gate_audit_ui(
    initial_text: str | None = None,
    *,
    port: int = DEFAULT_PORT,
    open_browser: bool = True,
) -> None:
    """Serve the audit UI until interrupted."""
    server = create_server(initial_text, port=port)
    url = "http://{}:{}/".format(HOST, server.server_port)
    print("IDKMesh gate-audit UI: {}".format(url))
    print("Verdict data stays in this local process. Press Ctrl+C to stop.")
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
