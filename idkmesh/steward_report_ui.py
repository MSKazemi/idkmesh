"""Loopback-only dashboard for validated Auto Draft PR Steward evidence.

The UI is intentionally static and read-only. The Python process validates the
report once, renders one self-contained HTML page, and serves it only from
127.0.0.1. There are no mutation endpoints, external assets, scripts, trackers,
or live GitHub calls.
"""

from __future__ import annotations

import html
import json
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit
from typing import Any

from idkmesh.steward_report import validate_report

HOST = "127.0.0.1"
DEFAULT_PORT = 8766

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


def _display(value: Any, fallback: str = "not available") -> str:
    return fallback if value is None else str(value)


def _status_class(status: str) -> str:
    return {
        "completed": "ok",
        "blocked": "warn",
        "disabled": "muted",
    }.get(status, "muted")


def _candidate_rows(report: dict[str, Any]) -> str:
    outcomes: dict[tuple[str, str, str], tuple[str, str]] = {}
    for item in report["created"]:
        key = (item["branch"], item["base"], item["head_sha"])
        outcomes[key] = (
            "created",
            f"Draft PR #{item['number']}",
        )
    for item in report["skipped"]:
        key = (item["branch"], item["base"], item["head_sha"])
        detail = item["reason"]
        if item["reason"] == "head_moved":
            detail += f" → {item['current_head_sha'][:12]}"
        outcomes[key] = ("skipped", detail)

    rows = []
    for item in report["planned"]:
        key = (item["branch"], item["base"], item["head_sha"])
        outcome, detail = outcomes.get(key, ("planned", "no mutation"))
        rows.append(
            "<tr>"
            f"<td><code>{_h(item['branch'])}</code></td>"
            f"<td><code>{_h(item['base'])}</code></td>"
            f"<td class='num'>{item['ahead_by']}</td>"
            f"<td class='num'>{item['behind_by']}</td>"
            f"<td><code>{_h(item['head_sha'][:12])}</code></td>"
            f"<td><span class='badge {outcome}'>{_h(outcome)}</span> "
            f"{_h(detail)}</td>"
            "</tr>"
        )
    if not rows:
        return (
            "<tr><td colspan='6' class='empty-cell'>"
            "No branch candidate was planned in this run."
            "</td></tr>"
        )
    return "".join(rows)


def _created_rows(report: dict[str, Any]) -> str:
    rows = []
    for item in report["created"]:
        rows.append(
            "<tr>"
            f"<td class='num'>#{item['number']}</td>"
            f"<td><code>{_h(item['branch'])}</code></td>"
            f"<td><code>{_h(item['base'])}</code></td>"
            f"<td><code>{_h(item['head_sha'])}</code></td>"
            f"<td><a href='{_h(item['url'])}' target='_blank' "
            "rel='noreferrer noopener'>open PR</a></td>"
            "</tr>"
        )
    if not rows:
        return (
            "<tr><td colspan='5' class='empty-cell'>"
            "No Draft PR was created in this run."
            "</td></tr>"
        )
    return "".join(rows)


def _authority_rows(report: dict[str, Any]) -> str:
    labels = {
        "draft_pr_create": "Create Draft PR",
        "ready_for_review": "Promote Draft",
        "approve": "Approve",
        "merge": "Merge",
        "auto_merge": "Enable auto-merge",
        "delete_branch": "Delete branch",
        "close_issue": "Close issue",
        "label_write": "Write labels",
        "contents_write": "Write repository contents",
        "repository_settings": "Change repository settings",
    }
    rows = []
    for key, label in labels.items():
        allowed = bool(report["authority"][key])
        rows.append(
            "<tr>"
            f"<td>{_h(label)}</td>"
            f"<td><span class='cap {'yes' if allowed else 'no'}'>"
            f"{'allowed' if allowed else 'not allowed'}</span></td>"
            "</tr>"
        )
    return "".join(rows)


def render_dashboard(report: dict[str, Any]) -> str:
    validate_report(report)
    summary = report["summary"]
    status = report["status"]
    raw = html.escape(
        json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False)
    )
    candidate_count = _display(report["candidate_count"], "not scanned")
    rate = _display(report["rate_limit_remaining"], "not observed")
    blocked = report["blocked_reason"] or "none"
    provenance = report["provenance"]

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="color-scheme" content="dark light">
  <meta name="robots" content="noindex,nofollow">
  <title>IDKMesh Steward Report</title>
  <style>
    :root {{
      --bg:#08101c; --panel:#101b2d; --panel2:#14223a; --line:#2b3d5c;
      --text:#edf4ff; --muted:#9cacbf; --cyan:#87d7ff; --green:#9ff0bd;
      --amber:#ffd28d; --red:#ff9d9d; --violet:#c9b8ff;
      --shadow:0 22px 60px rgba(0,0,0,.26);
      --sans:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
      --mono:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
    }}
    * {{ box-sizing:border-box; }}
    body {{
      margin:0; min-height:100vh; color:var(--text); font-family:var(--sans);
      background:
        radial-gradient(900px 520px at 90% -10%,rgba(135,215,255,.12),transparent 60%),
        radial-gradient(780px 500px at -10% 30%,rgba(159,240,189,.08),transparent 58%),
        var(--bg);
    }}
    a {{ color:var(--cyan); }}
    code,pre {{ font-family:var(--mono); }}
    .wrap {{ width:min(1180px,calc(100% - 2rem)); margin:auto; }}
    header {{
      border-bottom:1px solid var(--line); background:rgba(8,16,28,.92);
      backdrop-filter:blur(10px); position:sticky; top:0; z-index:10;
    }}
    .top {{ min-height:62px; display:flex; align-items:center; gap:.8rem; }}
    .brand {{ font-weight:850; letter-spacing:-.02em; }}
    .local {{ margin-left:auto; color:var(--green); font-size:.78rem; font-weight:800; }}
    main {{ padding:2rem 0 4rem; }}
    .eyebrow {{ color:var(--green); font-size:.73rem; font-weight:850; letter-spacing:.12em; text-transform:uppercase; }}
    h1 {{ font-size:clamp(2rem,5vw,3.6rem); line-height:1; letter-spacing:-.04em; margin:.35rem 0 .7rem; }}
    .lead {{ color:var(--muted); max-width:78ch; margin:0 0 1.4rem; }}
    .banner {{
      border:1px solid var(--line); border-left:3px solid var(--cyan);
      border-radius:12px; padding:.85rem 1rem; margin-bottom:1rem;
      background:rgba(135,215,255,.04); color:var(--muted);
    }}
    .grid {{ display:grid; grid-template-columns:repeat(5,minmax(0,1fr)); gap:.7rem; }}
    .card {{
      border:1px solid var(--line); border-radius:14px; padding:.9rem;
      background:linear-gradient(180deg,var(--panel),#0c1626); box-shadow:var(--shadow);
    }}
    .metric .value {{ font-size:1.65rem; font-weight:850; letter-spacing:-.03em; overflow-wrap:anywhere; }}
    .metric .label {{ color:var(--muted); font-size:.76rem; margin-top:.15rem; }}
    .status.ok {{ color:var(--green); }}
    .status.warn {{ color:var(--amber); }}
    .status.muted {{ color:var(--muted); }}
    section {{ margin-top:1rem; }}
    .section-title {{ display:flex; align-items:end; justify-content:space-between; gap:1rem; margin-bottom:.55rem; }}
    h2 {{ margin:0; font-size:1.05rem; }}
    .hint {{ color:var(--muted); font-size:.78rem; }}
    .table-wrap {{ overflow:auto; border:1px solid var(--line); border-radius:12px; background:var(--panel); }}
    table {{ width:100%; border-collapse:collapse; min-width:680px; font-size:.81rem; }}
    th,td {{ padding:.62rem .7rem; border-bottom:1px solid var(--line); text-align:left; vertical-align:top; }}
    th {{ color:var(--muted); font-size:.68rem; letter-spacing:.07em; text-transform:uppercase; background:rgba(255,255,255,.02); }}
    tr:last-child td {{ border-bottom:0; }}
    .num {{ font-variant-numeric:tabular-nums; white-space:nowrap; }}
    .empty-cell {{ color:var(--muted); text-align:center; padding:1.2rem; }}
    .badge,.cap {{ display:inline-block; border:1px solid currentColor; border-radius:999px; padding:.12rem .48rem; font-size:.68rem; font-weight:850; text-transform:uppercase; letter-spacing:.04em; }}
    .badge.created,.cap.yes {{ color:var(--green); }}
    .badge.skipped {{ color:var(--amber); }}
    .badge.planned {{ color:var(--violet); }}
    .cap.no {{ color:var(--muted); }}
    .two {{ display:grid; grid-template-columns:1fr 1fr; gap:1rem; }}
    dl {{ display:grid; grid-template-columns:auto 1fr; gap:.4rem .8rem; margin:.2rem 0 0; font-size:.82rem; }}
    dt {{ color:var(--muted); }}
    dd {{ margin:0; overflow-wrap:anywhere; }}
    details {{ border:1px solid var(--line); border-radius:12px; padding:.8rem .9rem; background:var(--panel); }}
    summary {{ cursor:pointer; color:var(--muted); font-weight:800; }}
    pre {{ white-space:pre-wrap; word-break:break-word; max-height:520px; overflow:auto; padding:.8rem; background:#050a12; border-radius:9px; font-size:.75rem; }}
    footer {{ color:var(--muted); text-align:center; font-size:.76rem; margin-top:1.2rem; }}
    @media (max-width:900px) {{
      .grid {{ grid-template-columns:repeat(2,minmax(0,1fr)); }}
      .two {{ grid-template-columns:1fr; }}
      header {{ position:static; }}
    }}
    @media (max-width:520px) {{
      .wrap {{ width:min(100% - 1rem,1180px); }}
      .grid {{ grid-template-columns:1fr 1fr; }}
      .local {{ display:none; }}
    }}
  </style>
</head>
<body>
<header>
  <div class="wrap top">
    <div class="brand">IDKMesh / Steward Report</div>
    <div class="local">LOCAL · READ ONLY · 127.0.0.1</div>
  </div>
</header>
<main class="wrap">
  <div class="eyebrow">Branch / PR stewardship evidence</div>
  <h1>What happened in the background?</h1>
  <p class="lead">A validated snapshot of the Auto Draft PR Steward. This page
  reads a local report file only; it does not contact GitHub or expose mutation controls.</p>

  <div class="banner">
    <strong>Authority boundary:</strong> Draft PR creation is the only write
    capability represented by this report. Merge, approval, auto-merge, branch
    deletion, issue closing, label writes, content writes, and settings changes
    are all disabled.
  </div>

  <div class="grid">
    <div class="card metric"><div class="value status {_status_class(status)}">{_h(status)}</div><div class="label">run status</div></div>
    <div class="card metric"><div class="value">{_h(candidate_count)}</div><div class="label">candidates observed</div></div>
    <div class="card metric"><div class="value">{summary['planned']}</div><div class="label">planned</div></div>
    <div class="card metric"><div class="value">{summary['created']}</div><div class="label">Draft PRs created</div></div>
    <div class="card metric"><div class="value">{summary['skipped']}</div><div class="label">skipped</div></div>
  </div>

  <section>
    <div class="section-title"><h2>Candidate lifecycle</h2><div class="hint">planned → created / skipped / no mutation</div></div>
    <div class="table-wrap">
      <table>
        <thead><tr><th>Branch</th><th>Base</th><th>Ahead</th><th>Behind</th><th>Planned head</th><th>Outcome</th></tr></thead>
        <tbody>{_candidate_rows(report)}</tbody>
      </table>
    </div>
  </section>

  <section>
    <div class="section-title"><h2>Created Draft PRs</h2><div class="hint">creation is coordination, not merge authorization</div></div>
    <div class="table-wrap">
      <table>
        <thead><tr><th>PR</th><th>Branch</th><th>Base</th><th>Head SHA</th><th>Link</th></tr></thead>
        <tbody>{_created_rows(report)}</tbody>
      </table>
    </div>
  </section>

  <section class="two">
    <div class="card">
      <div class="section-title"><h2>Authority</h2><div class="hint">explicit capabilities</div></div>
      <div class="table-wrap">
        <table>
          <thead><tr><th>Capability</th><th>State</th></tr></thead>
          <tbody>{_authority_rows(report)}</tbody>
        </table>
      </div>
    </div>
    <div class="card">
      <div class="section-title"><h2>Run provenance</h2><div class="hint">bind the report to its inputs</div></div>
      <dl>
        <dt>Repository</dt><dd><code>{_h(report['repository'])}</code></dd>
        <dt>Generated</dt><dd><code>{_h(report['generated_at'])}</code></dd>
        <dt>Blocked reason</dt><dd><code>{_h(blocked)}</code></dd>
        <dt>API remaining</dt><dd><code>{_h(rate)}</code></dd>
        <dt>Policy path</dt><dd><code>{_h(report['policy']['path'])}</code></dd>
        <dt>Policy SHA-256</dt><dd><code>{_h(report['policy']['sha256'])}</code></dd>
        <dt>Workflow</dt><dd><code>{_h(_display(provenance['workflow'], 'local'))}</code></dd>
        <dt>Run ID</dt><dd><code>{_h(_display(provenance['run_id'], 'n/a'))}</code></dd>
        <dt>Run attempt</dt><dd><code>{_h(_display(provenance['run_attempt'], 'n/a'))}</code></dd>
        <dt>Trusted head</dt><dd><code>{_h(_display(provenance['trusted_head_sha'], 'n/a'))}</code></dd>
      </dl>
    </div>
  </section>

  <section>
    <details>
      <summary>Raw validated report JSON</summary>
      <pre>{raw}</pre>
    </details>
  </section>

  <footer>Offline evidence viewer · no live GitHub access · no mutation endpoint</footer>
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
    server: "StewardReportServer"

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


class StewardReportServer(ThreadingHTTPServer):
    page: bytes


def create_server(
    report: dict[str, Any], *, port: int = DEFAULT_PORT
) -> StewardReportServer:
    validate_report(report)
    server = StewardReportServer((HOST, port), _Handler)
    server.page = render_dashboard(report).encode("utf-8")
    return server


def serve_steward_report_ui(
    report: dict[str, Any],
    *,
    port: int = DEFAULT_PORT,
    open_browser: bool = True,
) -> None:
    server = create_server(report, port=port)
    url = f"http://{HOST}:{server.server_port}/"
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
