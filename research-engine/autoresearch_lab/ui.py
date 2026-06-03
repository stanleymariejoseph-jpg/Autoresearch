from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from html import escape
from pathlib import Path
from threading import Lock, Thread
from typing import Any
import json
import time
import webbrowser

from .config import ResearchConfig
from .ledger import Ledger
from .loop import ResearchLoop
from .report import ReportWriter


class UiState:
    def __init__(self, config: ResearchConfig) -> None:
        self.config = config
        self.run_dir = config.output_dir / config.name
        self.lock = Lock()
        self.running = False
        self.last_message = "Ready"

    def start_run(self) -> bool:
        with self.lock:
            if self.running:
                return False
            self.running = True
            self.last_message = "Run started"

        def worker() -> None:
            try:
                ResearchLoop(self.config).run()
                self.last_message = "Run finished"
            except Exception as exc:
                self.last_message = f"Run failed: {exc}"
            finally:
                with self.lock:
                    self.running = False

        Thread(target=worker, daemon=True).start()
        return True


def serve_ui(config: ResearchConfig, host: str, port: int, open_browser: bool) -> None:
    state = UiState(config)

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if self.path == "/report.md":
                self._send_file(state.run_dir / "report.md", "text/plain; charset=utf-8")
                return
            if self.path == "/report.html":
                self._send_file(state.run_dir / "report.html", "text/html; charset=utf-8")
                return
            self._send_html(render_dashboard(state))

        def do_POST(self) -> None:
            if self.path == "/run":
                started = state.start_run()
                message = "Run launched" if started else "Run already running"
                self._redirect(f"/?message={message}")
                return
            if self.path == "/report":
                ReportWriter(state.run_dir).write(Ledger(state.run_dir / "ledger.jsonl").records())
                self._redirect("/?message=Report regenerated")
                return
            self.send_error(404)

        def log_message(self, format: str, *args: Any) -> None:
            return

        def _send_html(self, body: str) -> None:
            payload = body.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def _send_file(self, path: Path, content_type: str) -> None:
            if not path.exists():
                self.send_error(404)
                return
            payload = path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def _redirect(self, location: str) -> None:
            self.send_response(303)
            self.send_header("Location", location)
            self.end_headers()

    server = ThreadingHTTPServer((host, port), Handler)
    url = f"http://{host}:{port}"
    print(f"Autoresearch UI: {url}")
    if open_browser:
        webbrowser.open(url)
    server.serve_forever()


def render_dashboard(state: UiState) -> str:
    ledger = Ledger(state.run_dir / "ledger.jsonl")
    records = ledger.records()
    state_path = state.run_dir / "state.json"
    run_state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
    best = next((row for row in reversed(records) if row.get("accepted")), None)
    rows = "".join(render_row(row) for row in records[-25:])
    running = "Running" if state.running else "Idle"

    return f"""<!doctype html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta http-equiv="refresh" content="8">
  <title>Autoresearch UI</title>
  <style>
    body {{ margin: 0; background: #f6f7f9; color: #172033; font-family: Arial, sans-serif; }}
    header {{ background: #101828; color: white; padding: 18px 28px; display: flex; justify-content: space-between; gap: 16px; }}
    main {{ padding: 24px; display: grid; gap: 18px; max-width: 1180px; margin: 0 auto; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 14px; }}
    .card, table {{ background: white; border: 1px solid #d8dee8; border-radius: 8px; }}
    .card {{ padding: 16px; }}
    .label {{ color: #667085; font-size: 12px; text-transform: uppercase; font-weight: 800; }}
    .value {{ font-size: 24px; font-weight: 800; margin-top: 6px; }}
    table {{ border-collapse: collapse; width: 100%; overflow: hidden; }}
    th, td {{ border-bottom: 1px solid #d8dee8; padding: 10px; text-align: left; vertical-align: top; }}
    th {{ background: #eef2f7; }}
    button, a.button {{ border: 1px solid #1769aa; background: #1769aa; color: white; padding: 10px 14px; border-radius: 6px; text-decoration: none; font-weight: 700; }}
    form {{ display: inline; }}
    .actions {{ display: flex; gap: 10px; flex-wrap: wrap; }}
  </style>
</head>
<body>
  <header>
    <div><strong>Autoresearch</strong><br>{escape(str(state.config.name))}</div>
    <div>{escape(time.strftime("%Y-%m-%d %H:%M:%S"))}</div>
  </header>
  <main>
    <section class="grid">
      <div class="card"><div class="label">Status</div><div class="value">{running}</div></div>
      <div class="card"><div class="label">Trials</div><div class="value">{len(records)}</div></div>
      <div class="card"><div class="label">Best score</div><div class="value">{escape(str(best.get("score") if best else "n/a"))}</div></div>
      <div class="card"><div class="label">Next trial</div><div class="value">{escape(str(run_state.get("next_trial", 1)))}</div></div>
    </section>
    <section class="card">
      <div class="label">Message</div>
      <p>{escape(state.last_message)}</p>
      <div class="actions">
        <form method="post" action="/run"><button type="submit">Run</button></form>
        <form method="post" action="/report"><button type="submit">Regenerate report</button></form>
        <a class="button" href="/report.html" target="_blank">Open HTML report</a>
        <a class="button" href="/report.md" target="_blank">Open Markdown report</a>
      </div>
    </section>
    <section>
      <h2>Recent trials</h2>
      <table>
        <thead><tr><th>Trial</th><th>Score</th><th>Accepted</th><th>Summary</th><th>Error</th></tr></thead>
        <tbody>{rows or '<tr><td colspan="5">No trials yet.</td></tr>'}</tbody>
      </table>
    </section>
  </main>
</body>
</html>"""


def render_row(row: dict[str, Any]) -> str:
    return (
        "<tr>"
        f"<td>{escape(str(row.get('trial')))}</td>"
        f"<td>{escape(str(row.get('score')))}</td>"
        f"<td>{'yes' if row.get('accepted') else 'no'}</td>"
        f"<td>{escape(str(row.get('summary', '')))}</td>"
        f"<td>{escape(str(row.get('error') or ''))}</td>"
        "</tr>"
    )
