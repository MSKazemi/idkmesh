"""Loopback-only dashboard for aggregated steward history.

The dashboard serves one validated, already-aggregated local history snapshot.
It has no GitHub client, no network fetches, no scripts, and no mutation route.
"""

from __future__ import annotations

import html
import json
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlsplit

from idkmesh.steward_history import HISTORY_SCHEMA, validate_history

HOST = "127.0.0.1"
DEFAULT_PORT = 8767

_SECURITY_HEADERS = {
    "Cache-Control": "no-store",
    "Content-Security-Policy": (
        "default-src 'none'; style-src 'unsafe-inline'; "
        "base-uri 'none'; frame-ancestors 'none'; form-action 'none'"
    ),
    "Cross-Origin-Resource-Policy": "same-origin",
    "Referrer-Policy": "no-referrer",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
}


def _h(value: Any) -> str:
    return html.escape(str(value), quote=True)


def _display(value: Any, fallback: str = "n/a") -> str:
    return fallback if value is None else str(value)


def _status_class(status: str) -> str:
    return {
        "completed": "ok",
        "blocked": "warn",
        "disabled": "muted",
    }.get(status, "muted")


def _run_rows(history: dict[str, Any]) -> str:
    rows: list[str] = []
    for run in history["runs"]:
        run_identity = "local"
        if run["run_id"] is not None:
            run_identity = (
                f"{run['run_id']}/{_display(run['run_attempt'], '?')}"
            )
        blocked = run["blocked_reason"] or ""
        rows.append(
            "<tr>"
            f"<td><code>{_h(run['generated_at'])}</code></td>"
            f"<td><span class='badge {_status_class(run['status'])}'>"
            f"{_h(run['status'])}</span></td>"
            f"<td class='num'>{_h(_display(run['candidate_count'], '—'))}</td>"
            f"<td class='num'>{run['planned']}</td>"
            f"<td class='num'>{run['created']}</td>"
            f"<td class='num'>{run['skipped']}</td>"
            f"<td class='num'>{run['head_moved']}</td>"
            f"<td class='num'>{run['pr_already_exists']}</td>"
            f"<td class='num'>{_h(_display(run['rate_limit_remaining'], '—'))}</td>"
            f"<td><code>{_h(run['policy_sha256'][:12])}</code></td>"
            f"<td><code>{_h(run['report_sha256'][:12])}</code></td>"
            f"<td><code>{_h(run_identity)}</code></td>"
            f"<td>{_h(blocked)}</td>"
            f"<td><code>{_h(run['source'])}</code></td>"
            "</tr>"
        )
    return "".join(rows)


def render_dashboard(history: dict[str, Any]) -> str:
    validate_history(history)

    statuses = history["status_counts"]
    outcomes = history["outcome_totals"]
    api = history["api_budget"]
    policy = history["policy"]
    raw = html.escape(
        json.dumps(history, indent=2, sort_keys=True, ensure_ascii=False)
    )

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="color-scheme" content="dark light">
  <meta name="robots" content="noindex,nofollow">
  <title>IDKMesh Steward History</title>
  <style>
    :root {{
      --bg:#07111d; --panel:#0e1a2a; --panel2:#13233a; --line:#293c59;
      --text:#edf4ff; --muted:#9eafc3; --cyan:#84d8ff; --green:#9ff0bd;
      --amber:#ffd28d; --violet:#c9b8ff; --red:#ffaaa8;
      --shadow:0 22px 58px rgba(0,0,0,.25);
      --sans:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
      --mono:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
    }}
    * {{ box-sizing:border-box; }}
    body {{
      margin:0; min-height:100vh; color:var(--text); font-family:var(--sans);
      background:
        radial-gradient(900px 520px at 95% -5%,rgba(132,216,255,.12),transparent 58%),
        radial-gradient(720px 460px at -8% 40%,rgba(159,240,189,.07),transparent 58%),
        var(--bg);
    }}
    code,pre {{ font-family:var(--mono); }}
    .wrap {{ width:min(1320px,calc(100% - 2rem)); margin:auto; }}
    header {{
      border-bottom:1px solid var(--line); background:rgba(7,17,29,.92);
      backdrop-filter:blur(10px); position:sticky; top:0; z-index:10;
    }}
    .top {{ min-height:62px; display:flex; align-items:center; gap:.8rem; }}
    .brand {{ font-weight:850; letter-spacing:-.02em; }}
    .local {{ margin-left:auto; color:var(--green); font-size:.76rem; font-weight:850; }}
    main {{ padding:2rem 0 4rem; }}
    .eyebrow {{ color:var(--green); font-size:.72rem; font-weight:850; letter-spacing:.12em; text-transform:uppercase; }}
    h1 {{ font-size:clamp(2rem,5vw,3.5rem); line-height:1; letter-spacing:-.04em; margin:.35rem 0 .7rem; }}
    .lead {{ color:var(--muted); max-width:82ch; margin:0 0 1.3rem; }}
    .banner {{
      border:1px solid var(--line); border-left:3px solid var(--cyan);
      border-radius:12px; padding:.8rem 1rem; margin-bottom:1rem;
      background:rgba(132,216,255,.04); color:var(--muted);
    }}
    .grid {{ display:grid; grid-template-columns:repeat(6,minmax(0,1fr)); gap:.7rem; }}
    .card {{
      border:1px solid var(--line); border-radius:14px; padding:.9rem;
      background:linear-gradient(180deg,var(--panel),#0b1625); box-shadow:var(--shadow);
    }}
    .metric .value {{ font-size:1.55rem; font-weight:850; letter-spacing:-.03em; overflow-wrap:anywhere; }}
    .metric .label {{ color:var(--muted); font-size:.74rem; margin-top:.18rem; }}
    section {{ margin-top:1rem; }}
    .section-title {{ display:flex; align-items:end; justify-content:space-between; gap:1rem; margin-bottom:.55rem; }}
    h2 {{ margin:0; font-size:1.05rem; }}
    .hint {{ color:var(--muted); font-size:.76rem; }}
    .two {{ display:grid; grid-template-columns:1fr 1fr; gap:1rem; }}
    dl {{ display:grid; grid-template-columns:auto 1fr; gap:.42rem .8rem; margin:.2rem 0 0; font-size:.82rem; }}
    dt {{ color:var(--muted); }}
    dd {{ margin:0; overflow-wrap:anywhere; }}
    .table-wrap {{ overflow:auto; border:1px solid var(--line); border-radius:12px; background:var(--panel); }}
    table {{ width:100%; border-collapse:collapse; min-width:1180px; font-size:.78rem; }}
    th,td {{ padding:.58rem .64rem; border-bottom:1px solid var(--line); text-align:left; vertical-align:top; }}
    th {{ color:var(--muted); font-size:.65rem; letter-spacing:.06em; text-transform:uppercase; background:rgba(255,255,255,.02); }}
    tr:last-child td {{ border-bottom:0; }}
    .num {{ font-variant-numeric:tabular-nums; white-space:nowrap; }}
    .badge {{ display:inline-block; border:1px solid currentColor; border-radius:999px; padding:.11rem .45rem; font-size:.65rem; font-weight:850; text-transform:uppercase; }}
    .badge.ok {{ color:var(--green); }}
    .badge.warn {{ color:var(--amber); }}
    .badge.muted {{ color:var(--muted); }}
    details {{ border:1px solid var(--line); border-radius:12px; padding:.8rem .9rem; background:var(--panel); }}
    summary {{ cursor:pointer; color:var(--muted); font-weight:800; }}
    pre {{ white-space:pre-wrap; word-break:break-word; max-height:560px; overflow:auto; padding:.8rem; background:#050a12; border-radius:9px; font-size:.74rem; }}
    footer {{ color:var(--muted); text-align:center; font-size:.75rem; margin-top:1.2rem; }}
    @media (max-width:1050px) {{
      .grid {{ grid-template-columns:repeat(3,minmax(0,1fr)); }}
      .two {{ grid-template-columns:1fr; }}
      header {{ position:static; }}
    }}
    @media (max-width:560px) {{
      .wrap {{ width:min(100% - 1rem,1320px); }}
      .grid {{ grid-template-columns:1fr 1fr; }}
      .local {{ display:none; }}
    }}
  </style>
</head>
<body>
<header>
  <div class="wrap top">
    <div class="brand">IDKMesh / Steward History</div>
    <div class="local">LOCAL · OFFLINE · READ ONLY · 127.0.0.1</div>
  </div>
</header>
<main class="wrap">
  <div class="eyebrow">Longitudinal branch / PR stewardship evidence</div>
  <h1>How is the steward behaving over time?</h1>
  <p class="lead">A validated local aggregation of saved steward runs. This page
  performs no live GitHub calls and exposes no control or remediation endpoint.</p>

  <div class="banner">
    <strong>Descriptive only:</strong> these counts show observed run states,
    branch outcomes, API capacity, and policy changes. They do not authorize
    approval, merge, deletion, or any repository mutation.
  </div>

  <div class="grid">
    <div class="card metric"><div class="value">{history['report_count']}</div><div class="label">validated reports</div></div>
    <div class="card metric"><div class="value">{statuses['completed']}</div><div class="label">completed runs</div></div>
    <div class="card metric"><div class="value">{statuses['blocked']}</div><div class="label">blocked runs</div></div>
    <div class="card metric"><div class="value">{outcomes['created']}</div><div class="label">Draft PRs created</div></div>
    <div class="card metric"><div class="value">{outcomes['skipped']}</div><div class="label">candidate skips</div></div>
    <div class="card metric"><div class="value">{policy['changes']}</div><div class="label">policy transitions</div></div>
  </div>

  <section class="two">
    <div class="card">
      <div class="section-title"><h2>Observation window</h2><div class="hint">chronological validated evidence</div></div>
      <dl>
        <dt>Repository</dt><dd><code>{_h(history['repository'])}</code></dd>
        <dt>First report</dt><dd><code>{_h(history['first_generated_at'])}</code></dd>
        <dt>Latest report</dt><dd><code>{_h(history['last_generated_at'])}</code></dd>
        <dt>Disabled runs</dt><dd>{statuses['disabled']}</dd>
        <dt>Planned candidates</dt><dd>{outcomes['planned']}</dd>
        <dt>Head moved</dt><dd>{outcomes['head_moved']}</dd>
        <dt>PR already exists</dt><dd>{outcomes['pr_already_exists']}</dd>
      </dl>
    </div>
    <div class="card">
      <div class="section-title"><h2>Capacity &amp; policy</h2><div class="hint">not a health verdict</div></div>
      <dl>
        <dt>API observations</dt><dd>{api['observed_runs']}</dd>
        <dt>Minimum remaining</dt><dd><code>{_h(_display(api['min_remaining']))}</code></dd>
        <dt>Maximum remaining</dt><dd><code>{_h(_display(api['max_remaining']))}</code></dd>
        <dt>Distinct policies</dt><dd>{policy['distinct_digests']}</dd>
        <dt>Policy transitions</dt><dd>{policy['changes']}</dd>
        <dt>Latest policy</dt><dd><code>{_h(policy['latest_sha256'])}</code></dd>
        <dt>Input set digest</dt><dd><code>{_h(history['integrity']['input_set_sha256'])}</code></dd>
      </dl>
    </div>
  </section>

  <section>
    <div class="section-title"><h2>Run timeline</h2><div class="hint">oldest → newest</div></div>
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Generated</th><th>State</th><th>Candidates</th><th>Planned</th>
            <th>Created</th><th>Skipped</th><th>Head moved</th><th>PR exists</th>
            <th>API left</th><th>Policy</th><th>Report digest</th><th>Run</th><th>Blocked reason</th><th>Source</th>
          </tr>
        </thead>
        <tbody>{_run_rows(history)}</tbody>
      </table>
    </div>
  </section>

  <section>
    <details>
      <summary>Raw aggregated history JSON</summary>
      <pre>{raw}</pre>
    </details>
  </section>

  <footer>Offline history viewer · no artifact downloads · no live GitHub access · no mutation endpoint</footer>
</main>
</body>
</html>
"""


def _host_is_loopback(value: str | None) -> bool:
    if not value or "@" in value or "/" in value or "\\" in value:
        return False
    host = value
    if host.startswith("["):
        name = host.split("]", 1)[0] + "]"
    else:
        name = host.split(":", 1)[0]
    return name in {"127.0.0.1", "localhost", "[::1]"}


class _Handler(BaseHTTPRequestHandler):
    server: "StewardHistoryServer"

    def log_message(self, format: str, *args: object) -> None:
        return

    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        for key, value in _SECURITY_HEADERS.items():
            self.send_header(key, value)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _error(self, status: int, message: str) -> None:
        body = json.dumps({"ok": False, "error": message}).encode("utf-8")
        self._send(status, body, "application/json; charset=utf-8")

    def _check_host(self) -> bool:
        if _host_is_loopback(self.headers.get("Host")):
            return True
        self._error(403, "dashboard accepts only loopback Host headers")
        return False

    def do_GET(self) -> None:
        if not self._check_host():
            return
        if urlsplit(self.path).path != "/":
            self._error(404, "not found")
            return
        self._send(200, self.server.page, "text/html; charset=utf-8")

    def do_HEAD(self) -> None:
        self.do_GET()

    def do_POST(self) -> None:
        if not self._check_host():
            return
        self._error(405, "dashboard is read-only; POST is not supported")

    def do_PUT(self) -> None:
        self.do_POST()

    def do_PATCH(self) -> None:
        self.do_POST()

    def do_DELETE(self) -> None:
        self.do_POST()

    def do_OPTIONS(self) -> None:
        if not self._check_host():
            return
        self._error(405, "cross-origin preflight is not supported")


class StewardHistoryServer(ThreadingHTTPServer):
    page: bytes


def create_server(
    history: dict[str, Any], *, port: int = DEFAULT_PORT
) -> StewardHistoryServer:
    server = StewardHistoryServer((HOST, port), _Handler)
    server.page = render_dashboard(history).encode("utf-8")
    return server


def serve_steward_history_ui(
    history: dict[str, Any],
    *,
    port: int = DEFAULT_PORT,
    open_browser: bool = True,
) -> None:
    server = create_server(history, port=port)
    url = f"http://{HOST}:{server.server_port}/"
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
