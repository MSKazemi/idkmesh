"""Local, dependency-free browser UI for idkmesh gate-audit.

The UI is intentionally a localhost tool rather than a hosted service. Review
verdicts can be sensitive, so the browser talks only to the Python process on
127.0.0.1 and the audit delegates to idkmesh.gate_audit rather than
reimplementing any panel mathematics in JavaScript.
"""

from __future__ import annotations

import html
import json
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from idkmesh import __version__
from idkmesh.gate_audit import GateAuditInputError, audit_text

HOST = "127.0.0.1"
DEFAULT_PORT = 8765
MAX_BODY_BYTES = 2 * 1024 * 1024

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


def _app_html(initial_text: str | None = None) -> str:
    source = SAMPLE_INPUT if initial_text is None else initial_text
    safe_source = html.escape(source)
    page = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="color-scheme" content="dark">
  <title>IDKMesh Gate Audit</title>
  <style>
    :root {
      --bg:#080d19; --panel:#10182a; --panel2:#151f34; --line:#273451;
      --text:#eef4ff; --muted:#9cabc5; --cyan:#8bd3ff; --mint:#b9ffcf;
      --amber:#ffd28b; --red:#ff9d9d; --violet:#c9b8ff;
      --mono: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      --sans: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }
    * { box-sizing:border-box; }
    body { margin:0; background:radial-gradient(circle at 80% 0, #12213a 0, transparent 34%), var(--bg); color:var(--text); font-family:var(--sans); line-height:1.5; }
    button, input, textarea { font:inherit; }
    a { color:var(--cyan); }
    .wrap { width:min(1180px, calc(100% - 2rem)); margin:auto; }
    header { border-bottom:1px solid var(--line); padding:1.1rem 0; background:rgba(8,13,25,.9); position:sticky; top:0; z-index:4; backdrop-filter:blur(10px); }
    .top { display:flex; align-items:center; gap:1rem; }
    .brand { font-weight:800; letter-spacing:-.02em; }
    .pill { margin-left:auto; border:1px solid var(--line); border-radius:999px; padding:.3rem .7rem; color:var(--mint); font-size:.82rem; }
    main { padding:2.2rem 0 4rem; }
    .hero { display:grid; grid-template-columns:minmax(0,1.2fr) minmax(280px,.8fr); gap:1.2rem; align-items:end; margin-bottom:1.3rem; }
    h1 { font-size:clamp(2rem,5vw,3.35rem); line-height:1; margin:.25rem 0 .65rem; letter-spacing:-.035em; }
    h1 span { color:var(--cyan); }
    .eyebrow { color:var(--mint); font-size:.75rem; font-weight:800; letter-spacing:.1em; text-transform:uppercase; }
    .lead { color:var(--muted); max-width:70ch; margin:0; }
    .privacy { color:var(--muted); font-size:.9rem; border-left:3px solid var(--mint); padding:.55rem .8rem; background:rgba(185,255,207,.04); border-radius:.35rem; }
    .workspace { display:grid; grid-template-columns:minmax(0,1.05fr) minmax(340px,.95fr); gap:1rem; align-items:start; }
    .panel { background:linear-gradient(180deg,var(--panel),#0d1424); border:1px solid var(--line); border-radius:16px; padding:1rem; box-shadow:0 18px 50px rgba(0,0,0,.2); }
    .panel h2 { font-size:1rem; margin:0; }
    .panel-head { display:flex; gap:.8rem; align-items:center; justify-content:space-between; margin-bottom:.8rem; flex-wrap:wrap; }
    .toolbar { display:flex; gap:.5rem; flex-wrap:wrap; }
    .file-label, button, .download {
      border:1px solid var(--line); background:var(--panel2); color:var(--text);
      padding:.55rem .8rem; border-radius:9px; cursor:pointer; text-decoration:none; font-weight:700; font-size:.9rem;
    }
    button.primary { background:var(--text); color:var(--bg); border-color:var(--text); }
    button:hover, .file-label:hover, .download:hover { border-color:var(--cyan); }
    #file { position:absolute; width:1px; height:1px; overflow:hidden; clip:rect(0 0 0 0); }
    textarea {
      width:100%; min-height:510px; resize:vertical; border:1px solid var(--line); border-radius:12px;
      background:#070b14; color:#dce8ff; padding:1rem; font-family:var(--mono); font-size:.82rem; line-height:1.55;
    }
    textarea:focus, button:focus-visible, .file-label:focus-within, a:focus-visible { outline:2px solid var(--cyan); outline-offset:2px; }
    .status { min-height:1.5rem; margin:.65rem 0 0; color:var(--muted); font-size:.9rem; }
    .status.error { color:var(--red); }
    .metrics { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:.7rem; margin:.8rem 0 1rem; }
    .metric { border:1px solid var(--line); border-radius:12px; padding:.85rem; background:rgba(255,255,255,.018); }
    .metric .v { font-size:1.65rem; font-weight:850; letter-spacing:-.03em; font-variant-numeric:tabular-nums; }
    .metric .k { color:var(--muted); font-size:.8rem; margin-top:.2rem; }
    .metric.eff .v { color:var(--cyan); } .metric.probe .v { color:var(--amber); }
    .badge { display:inline-block; border:1px solid currentColor; border-radius:999px; padding:.12rem .5rem; font-size:.74rem; font-weight:800; color:var(--violet); }
    .summary { border:1px solid var(--line); border-radius:12px; padding:.9rem; margin:.8rem 0; }
    .summary strong { color:var(--mint); }
    .warnings { margin:.8rem 0 0; padding-left:1.2rem; color:var(--amber); }
    details { border-top:1px solid var(--line); margin-top:1rem; padding-top:.8rem; }
    summary { cursor:pointer; color:var(--muted); font-weight:700; }
    pre { white-space:pre-wrap; word-break:break-word; background:#070b14; border:1px solid var(--line); border-radius:10px; padding:.8rem; max-height:360px; overflow:auto; font: .78rem/1.5 var(--mono); }
    .empty { color:var(--muted); padding:2.2rem .6rem; text-align:center; }
    footer { color:var(--muted); font-size:.82rem; margin-top:1rem; }
    @media (max-width:900px) { .hero,.workspace { grid-template-columns:1fr; } textarea { min-height:390px; } header { position:static; } }
    @media (max-width:520px) { .wrap { width:min(100% - 1rem,1180px); } .metrics { grid-template-columns:1fr; } .panel { padding:.75rem; border-radius:12px; } }
  </style>
</head>
<body>
<header>
  <div class="wrap top">
    <div class="brand">IDKMesh · Gate Audit</div>
    <span class="pill">local-only · v__VERSION__</span>
  </div>
</header>
<main class="wrap">
  <div class="hero">
    <div>
      <div class="eyebrow">Review-panel diagnostic</div>
      <h1>See how many votes your panel is <span>actually worth.</span></h1>
      <p class="lead">Load a verdict-matrix JSON file, audit it with the same engine as the CLI, and inspect effective independent votes, correlation, panel error and seeded-probe breaches.</p>
    </div>
    <div class="privacy"><strong>Private by default.</strong> This page is served by your local Python process on 127.0.0.1. The browser posts verdicts only back to that process; IDKMesh does not upload them to a hosted service.</div>
  </div>

  <div class="workspace">
    <section class="panel" aria-labelledby="input-title">
      <div class="panel-head">
        <h2 id="input-title">Verdict matrix</h2>
        <div class="toolbar">
          <label class="file-label">Open JSON<input id="file" type="file" accept=".json,application/json"></label>
          <button id="sample" type="button">Load example</button>
          <button id="run" class="primary" type="button">Audit panel</button>
        </div>
      </div>
      <textarea id="source" spellcheck="false" aria-label="Verdict matrix JSON">__INITIAL__</textarea>
      <div id="status" class="status" role="status" aria-live="polite">Ready. Edit the JSON or load your own file.</div>
    </section>

    <section class="panel" aria-labelledby="result-title">
      <div class="panel-head">
        <h2 id="result-title">Audit result</h2>
        <div class="toolbar">
          <button id="copy" type="button" disabled>Copy JSON</button>
          <a id="download" class="download" href="#" download="gate-audit-report.json" hidden>Download JSON</a>
        </div>
      </div>
      <div id="result" class="empty">Run an audit to see the panel measurements.</div>
    </section>
  </div>
  <footer>Decision support only: worker success ≠ acceptance; verification recommendation ≠ merge authority.</footer>
</main>
<script>
(function () {
  "use strict";
  var source = document.getElementById("source");
  var file = document.getElementById("file");
  var status = document.getElementById("status");
  var result = document.getElementById("result");
  var run = document.getElementById("run");
  var copy = document.getElementById("copy");
  var download = document.getElementById("download");
  var sampleText = __SAMPLE_JSON__;
  var currentJson = "";
  var downloadUrl = "";

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
  function setStatus(message, isError) {
    status.textContent = message;
    status.className = isError ? "status error" : "status";
  }
  function render(report) {
    var p = report.panel;
    var probes = report.probes;
    var eff = p.effective_votes === null ? "n/a" : fmt(p.effective_votes, 2);
    var probeText = probes ? probes.breached + " / " + probes.total : "none";
    var warningHtml = report.warnings.length
      ? '<ul class="warnings">' + report.warnings.map(function (w) { return "<li>" + esc(w) + "</li>"; }).join("") + "</ul>"
      : '<p style="color:var(--muted);margin:.8rem 0 0">No audit warnings.</p>';
    result.className = "";
    result.innerHTML =
      '<div><span class="badge">' + esc(report.evidence_class) + '</span></div>' +
      '<div class="summary"><strong>' + esc(report.gate_id) + '</strong><br>' +
      esc(p.nominal_votes) + ' nominal votes → <strong>' + esc(eff) + ' effective independent votes</strong>.</div>' +
      '<div class="metrics">' +
        '<div class="metric eff"><div class="v">' + esc(eff) + '</div><div class="k">effective votes</div></div>' +
        '<div class="metric"><div class="v">' + esc(p.nominal_votes) + '</div><div class="k">nominal votes</div></div>' +
        '<div class="metric"><div class="v">' + esc(pct(p.mean_verifier_accuracy)) + '</div><div class="k">mean verifier accuracy</div></div>' +
        '<div class="metric"><div class="v">' + esc(fmt(p.mean_pairwise_error_correlation, 3)) + '</div><div class="k">mean pairwise error correlation</div></div>' +
        '<div class="metric"><div class="v">' + esc(pct(p.error)) + '</div><div class="k">panel error</div></div>' +
        '<div class="metric probe"><div class="v">' + esc(probeText) + '</div><div class="k">seeded probes breached</div></div>' +
      '</div>' +
      warningHtml +
      '<details><summary>Raw report JSON</summary><pre>' + esc(currentJson) + '</pre></details>';
  }
  function setDownload(text) {
    if (downloadUrl) URL.revokeObjectURL(downloadUrl);
    downloadUrl = URL.createObjectURL(new Blob([text], {type:"application/json"}));
    download.href = downloadUrl;
    download.hidden = false;
  }

  file.addEventListener("change", function () {
    if (!file.files || !file.files[0]) return;
    var reader = new FileReader();
    reader.onload = function () {
      source.value = String(reader.result || "");
      setStatus("Loaded " + file.files[0].name + ". Ready to audit.", false);
    };
    reader.onerror = function () { setStatus("Could not read that file.", true); };
    reader.readAsText(file.files[0], "utf-8");
  });

  document.getElementById("sample").addEventListener("click", function () {
    source.value = sampleText;
    setStatus("Loaded the built-in synthetic example.", false);
  });

  run.addEventListener("click", async function () {
    run.disabled = true;
    copy.disabled = true;
    download.hidden = true;
    result.className = "empty";
    result.textContent = "Auditing…";
    setStatus("Running the audit locally…", false);
    try {
      var response = await fetch("/api/audit", {
        method:"POST",
        headers:{"Content-Type":"application/json; charset=utf-8"},
        body:source.value
      });
      var payload = await response.json();
      if (!response.ok || !payload.ok) throw new Error(payload.error || "Audit failed.");
      currentJson = JSON.stringify(payload.report, null, 2);
      render(payload.report);
      setDownload(currentJson + "\n");
      copy.disabled = false;
      setStatus("Audit complete. No verdict data left this local process.", false);
    } catch (err) {
      result.className = "empty";
      result.textContent = "No report generated.";
      setStatus(err && err.message ? err.message : String(err), true);
    } finally {
      run.disabled = false;
    }
  });

  copy.addEventListener("click", async function () {
    try {
      await navigator.clipboard.writeText(currentJson);
      setStatus("Report JSON copied.", false);
    } catch (err) {
      setStatus("Clipboard access was blocked by the browser; use Download JSON instead.", true);
    }
  });
}());
</script>
</body>
</html>
"""
    return (
        page.replace("__INITIAL__", safe_source)
        .replace("__VERSION__", html.escape(__version__))
        .replace("__SAMPLE_JSON__", json.dumps(SAMPLE_INPUT))
    )


def _json_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, allow_nan=False, separators=(",", ":")).encode("utf-8")


def _handler(initial_text: str | None):
    page = _app_html(initial_text).encode("utf-8")

    class Handler(BaseHTTPRequestHandler):
        server_version = "IDKMeshGateAuditUI/0.1"

        def log_message(self, format: str, *args: Any) -> None:
            return

        def _headers(self, status: int, content_type: str, length: int) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(length))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header(
                "Content-Security-Policy",
                "default-src 'none'; style-src 'unsafe-inline'; "
                "script-src 'unsafe-inline'; connect-src 'self'; "
                "img-src 'self' data: blob:; base-uri 'none'; "
                "form-action 'none'; frame-ancestors 'none'",
            )
            self.end_headers()

        def _send_json(self, status: int, payload: dict[str, Any]) -> None:
            body = _json_bytes(payload)
            self._headers(status, "application/json; charset=utf-8", len(body))
            self.wfile.write(body)

        def do_GET(self) -> None:
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

        def do_POST(self) -> None:
            if self.path != "/api/audit":
                self._send_json(404, {"ok": False, "error": "not found"})
                return
            raw_length = self.headers.get("Content-Length")
            if raw_length is None:
                self._send_json(
                    411, {"ok": False, "error": "missing Content-Length header"})
                return
            try:
                length = int(raw_length)
            except ValueError:
                self._send_json(
                    400, {"ok": False, "error": "invalid Content-Length header"})
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
                    {
                        "ok": False,
                        "error": "browser input is not UTF-8 text",
                    },
                )
                return
            try:
                report = audit_text(source, source="browser input")
            except GateAuditInputError as exc:
                self._send_json(400, {"ok": False, "error": str(exc)})
                return
            self._send_json(200, {"ok": True, "report": report})

    return Handler


def create_server(
    initial_text: str | None = None,
    *,
    port: int = DEFAULT_PORT,
) -> ThreadingHTTPServer:
    """Create, but do not start, the loopback-only audit UI server.

    port=0 is supported for tests and library callers that want the kernel to
    choose an unused local port.
    """
    return ThreadingHTTPServer((HOST, port), _handler(initial_text))


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
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
