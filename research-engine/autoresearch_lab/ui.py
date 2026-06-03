from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Event, Lock, Thread
from typing import Any
import base64
import io
import json
import time
import webbrowser
import zipfile

from .agent import MistralClient
from .config import ResearchConfig
from .ledger import Ledger
from .loop import ResearchLoop
from .report import ReportWriter

PROJECTS_DIRNAME = "uploaded-projects"


class WebState:
    """Holds everything the web app needs: active config, run thread, chat."""

    def __init__(self, config: ResearchConfig | None, base_dir: Path) -> None:
        self.lock = Lock()
        self.config = config
        self.base_dir = base_dir
        self.projects_root = base_dir / PROJECTS_DIRNAME
        self.projects_root.mkdir(parents=True, exist_ok=True)
        self.running = False
        self.stop_event = Event()
        self.last_message = "Ready"
        self.chat: list[dict[str, str]] = []

    # -- run control -----------------------------------------------------
    @property
    def run_dir(self) -> Path | None:
        if not self.config:
            return None
        return self.config.output_dir / self.config.name

    def start_run(self) -> tuple[bool, str]:
        with self.lock:
            if self.config is None:
                return False, "Aucun projet configuré. Choisis un exemple ou dépose un zip."
            if self.running:
                return False, "Une recherche est déjà en cours."
            self.running = True
            self.stop_event.clear()
            self.last_message = "Recherche démarrée"
            config = self.config

        def worker() -> None:
            try:
                ResearchLoop(config).run(stop_event=self.stop_event)
                self.last_message = "Recherche terminée"
            except Exception as exc:  # pragma: no cover - surfaced in UI
                self.last_message = f"Échec: {exc}"
            finally:
                with self.lock:
                    self.running = False

        Thread(target=worker, daemon=True).start()
        return True, "Recherche lancée"

    def request_stop(self) -> str:
        with self.lock:
            if not self.running:
                return "Aucune recherche en cours."
            self.stop_event.set()
            self.last_message = "Arrêt demandé (fin du trial en cours)"
            return self.last_message

    # -- snapshots -------------------------------------------------------
    def snapshot(self) -> dict[str, Any]:
        records: list[dict[str, Any]] = []
        run_state: dict[str, Any] = {}
        if self.run_dir is not None:
            records = Ledger(self.run_dir / "ledger.jsonl").records()
            state_path = self.run_dir / "state.json"
            if state_path.exists():
                run_state = json.loads(state_path.read_text(encoding="utf-8"))
        best = next((r for r in reversed(records) if r.get("accepted") and r.get("score") is not None), None)
        scores = [r.get("score") for r in records if r.get("score") is not None]
        return {
            "running": self.running,
            "message": self.last_message,
            "config": None
            if not self.config
            else {
                "name": self.config.name,
                "command": self.config.command,
                "metric_regex": self.config.metric_regex,
                "workspace": str(self.config.workspace),
                "maximize": self.config.maximize,
                "iterations": self.config.iterations,
                "agent": self.config.agent_provider or "none",
            },
            "trials": records[-50:],
            "best": best,
            "next_trial": run_state.get("next_trial", 1),
            "scores": scores,
            "examples": self._examples(),
            "chat": self.chat[-100:],
        }

    def _examples(self) -> list[dict[str, str]]:
        examples_dir = self.base_dir / "examples"
        out: list[dict[str, str]] = []
        if examples_dir.exists():
            for path in sorted(examples_dir.glob("*config*.json")):
                out.append({"path": str(path), "name": path.stem})
        return out


def build_config_from_form(form: dict[str, Any], base_dir: Path) -> ResearchConfig:
    workspace = Path(form["workspace"])
    if not workspace.is_absolute():
        workspace = (base_dir / workspace).resolve()
    output_dir = (base_dir / "runs").resolve()
    use_agent = bool(form.get("use_agent"))
    agent_files = tuple(
        f.strip() for f in str(form.get("agent_files", "")).replace(",", "\n").splitlines() if f.strip()
    )
    config = ResearchConfig(
        name=str(form.get("name") or workspace.name),
        workspace=workspace,
        command=str(form["command"]),
        metric_regex=str(form.get("metric_regex") or ResearchConfig.metric_regex),
        parameter_file=(form.get("parameter_file") or None),
        output_dir=output_dir,
        iterations=int(form.get("iterations", 12)),
        seconds_per_trial=int(form.get("seconds_per_trial", 120)),
        maximize=bool(form.get("maximize", False)),
        patience=(None if form.get("patience") in (None, "", "null") else int(form["patience"])),
        agent_provider=("mistral" if use_agent else None),
        agent_files=agent_files,
        objective_file=(form.get("objective_file") or None),
    )
    config.validate()
    return config


def handle_chat(state: WebState, message: str) -> dict[str, Any]:
    """Both pilot the loop AND converse with Mistral."""
    text = message.strip()
    low = text.lower()
    state.chat.append({"role": "user", "text": text})

    def reply(msg: str) -> dict[str, Any]:
        state.chat.append({"role": "assistant", "text": msg})
        return {"reply": msg}

    # --- control intents ---
    if any(w in low for w in ("lance", "démarre", "demarre", "run", "start", "go")):
        ok, msg = state.start_run()
        return reply(("✅ " if ok else "⚠️ ") + msg)
    if any(w in low for w in ("arrête", "arrete", "stop", "stoppe")):
        return reply("🛑 " + state.request_stop())
    if any(w in low for w in ("statut", "status", "état", "etat", "où en", "ou en")):
        snap = state.snapshot()
        best = snap["best"]
        bscore = best.get("score") if best else "n/a"
        return reply(
            f"Statut: {'en cours' if snap['running'] else 'inactif'} · "
            f"trials: {len(snap['trials'])} · meilleur score: {bscore} · "
            f"prochain trial: {snap['next_trial']}"
        )
    if any(w in low for w in ("meilleur", "best")):
        snap = state.snapshot()
        best = snap["best"]
        if not best:
            return reply("Aucun trial accepté pour l'instant.")
        return reply(
            f"Meilleur trial: #{best.get('trial')} · score {best.get('score')} · {best.get('summary', '')}"
        )
    if any(w in low for w in ("rapport", "report")):
        if state.run_dir is not None:
            ReportWriter(state.run_dir).write(Ledger(state.run_dir / "ledger.jsonl").records())
            return reply("📄 Rapport régénéré. Ouvre 'Rapport HTML' en haut.")
        return reply("Configure d'abord un projet.")
    if any(w in low for w in ("aide", "help", "commandes")):
        return reply(
            "Je peux piloter la recherche et discuter de ton projet.\n"
            "Commandes: « lance », « arrête », « statut », « meilleur », « rapport ».\n"
            "Sinon, pose-moi une question (ex: comment améliorer mon modèle ?)."
        )

    # --- free conversation with Mistral ---
    try:
        client = MistralClient(model="mistral-large-latest")
        snap = state.snapshot()
        cfg = snap["config"]
        ctx = "Aucun projet configuré."
        if cfg:
            best = snap["best"]
            ctx = (
                f"Projet actif: {cfg['name']} · commande: {cfg['command']} · "
                f"objectif: {'maximiser' if cfg['maximize'] else 'minimiser'} la métrique. "
                f"Trials: {len(snap['trials'])} · meilleur score: {best.get('score') if best else 'n/a'}."
            )
        sys_prompt = (
            "Tu es l'assistant d'Autoresearch, un moteur d'expérimentation autonome. "
            "Tu aides l'utilisateur à comprendre sa recherche en cours et à l'améliorer. "
            "Réponds en français, de façon concise et concrète. Contexte: " + ctx
        )
        history = [{"role": "system", "content": sys_prompt}]
        for m in state.chat[-10:]:
            history.append(
                {"role": "user" if m["role"] == "user" else "assistant", "content": m["text"]}
            )
        out = client.complete(history, json_mode=False)
        return reply(out.strip())
    except Exception as exc:
        return reply(
            "💬 (Chat IA indisponible: " + str(exc) + ")\n"
            "Les commandes de pilotage fonctionnent quand même: « lance », « statut », « meilleur »."
        )


def extract_zip(state: WebState, filename: str, data_b64: str) -> dict[str, Any]:
    raw = base64.b64decode(data_b64)
    stem = Path(filename).stem or "projet"
    safe = "".join(c for c in stem if c.isalnum() or c in ("-", "_")) or "projet"
    target = state.projects_root / safe
    target.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        for member in zf.namelist():
            # prevent path traversal
            dest = (target / member).resolve()
            if state.projects_root.resolve() not in dest.parents and dest != target.resolve():
                continue
            zf.extract(member, target)
    # if the zip wrapped everything in a single folder, use that as workspace
    entries = [p for p in target.iterdir() if p.name != "__MACOSX"]
    workspace = entries[0] if len(entries) == 1 and entries[0].is_dir() else target
    files = sorted(
        str(p.relative_to(workspace)) for p in workspace.rglob("*") if p.is_file()
    )[:200]
    return {"workspace": str(workspace), "files": files}


def serve_ui(config: ResearchConfig | None, host: str, port: int, open_browser: bool, base_dir: Path | None = None) -> None:
    base = base_dir or Path.cwd()
    state = WebState(config, base)

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if self.path.startswith("/api/state"):
                self._json(state.snapshot())
                return
            if self.path == "/report.html":
                self._file(state.run_dir / "report.html" if state.run_dir else None, "text/html; charset=utf-8")
                return
            if self.path == "/report.md":
                self._file(state.run_dir / "report.md" if state.run_dir else None, "text/plain; charset=utf-8")
                return
            self._html(PAGE)

        def do_POST(self) -> None:
            body = self._read_body()
            if self.path == "/api/run":
                ok, msg = state.start_run()
                self._json({"ok": ok, "message": msg})
                return
            if self.path == "/api/stop":
                self._json({"message": state.request_stop()})
                return
            if self.path == "/api/chat":
                self._json(handle_chat(state, str(body.get("message", ""))))
                return
            if self.path == "/api/upload":
                try:
                    result = extract_zip(state, str(body.get("filename", "projet.zip")), str(body.get("data", "")))
                    self._json({"ok": True, **result})
                except Exception as exc:
                    self._json({"ok": False, "error": str(exc)})
                return
            if self.path == "/api/configure":
                try:
                    state.config = build_config_from_form(body, base)
                    state.last_message = f"Projet configuré: {state.config.name}"
                    self._json({"ok": True, "message": state.last_message})
                except Exception as exc:
                    self._json({"ok": False, "error": str(exc)})
                return
            if self.path == "/api/select_example":
                try:
                    state.config = ResearchConfig.from_file(Path(body["path"]).resolve())
                    state.last_message = f"Exemple chargé: {state.config.name}"
                    self._json({"ok": True, "message": state.last_message})
                except Exception as exc:
                    self._json({"ok": False, "error": str(exc)})
                return
            if self.path == "/api/report":
                if state.run_dir is not None:
                    ReportWriter(state.run_dir).write(Ledger(state.run_dir / "ledger.jsonl").records())
                    self._json({"ok": True})
                else:
                    self._json({"ok": False, "error": "no project"})
                return
            self.send_error(404)

        def log_message(self, *_: Any) -> None:
            return

        def _read_body(self) -> dict[str, Any]:
            length = int(self.headers.get("Content-Length", 0))
            if not length:
                return {}
            raw = self.rfile.read(length)
            try:
                return json.loads(raw.decode("utf-8"))
            except Exception:
                return {}

        def _json(self, obj: Any) -> None:
            payload = json.dumps(obj).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def _html(self, body: str) -> None:
            payload = body.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def _file(self, path: Path | None, content_type: str) -> None:
            if not path or not path.exists():
                self.send_error(404)
                return
            payload = path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

    server = ThreadingHTTPServer((host, port), Handler)
    url = f"http://{host}:{port}"
    print(f"Autoresearch UI: {url}")
    if open_browser:
        try:
            webbrowser.open(url)
        except Exception:
            pass
    server.serve_forever()


PAGE = r"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Autoresearch</title>
<style>
  :root { --bg:#0a0e1a; --panel:#121a2e; --panel2:#1a2440; --line:#262f4d; --text:#e8edf7; --muted:#8b97b5; --accent:#5b8cff; --accent2:#7aa2ff; --ok:#2dd4a7; --bad:#ff6b6b; --shadow:0 6px 24px rgba(0,0,0,.35); }
  * { box-sizing:border-box; }
  body { margin:0; font-family:'Segoe UI',Inter,system-ui,Arial,sans-serif; background:var(--bg); color:var(--text); height:100vh; overflow:hidden; display:flex; flex-direction:column; -webkit-font-smoothing:antialiased; }
  ::-webkit-scrollbar { width:10px; height:10px; }
  ::-webkit-scrollbar-thumb { background:#2c3859; border-radius:8px; border:2px solid transparent; background-clip:padding-box; }
  ::-webkit-scrollbar-thumb:hover { background:#3a4a73; background-clip:padding-box; }
  ::-webkit-scrollbar-track { background:transparent; }
  header { flex-shrink:0; display:flex; align-items:center; justify-content:space-between; padding:14px 24px; background:linear-gradient(90deg,#0f1830,#0a0e1a); border-bottom:1px solid var(--line); box-shadow:0 1px 0 rgba(255,255,255,.02); }
  header h1 { font-size:18px; margin:0; letter-spacing:.2px; font-weight:800; }
  header .sub { color:var(--muted); font-size:12px; margin-top:2px; }
  .topbtns a { color:var(--text); text-decoration:none; font-size:12px; border:1px solid var(--line); padding:8px 13px; border-radius:9px; margin-left:8px; background:var(--panel); transition:.15s; }
  .topbtns a:hover { border-color:var(--accent); color:var(--accent2); }
  .layout { flex:1; min-height:0; display:grid; grid-template-columns:400px 1fr; }
  /* chat */
  .chat { display:flex; flex-direction:column; min-height:0; border-right:1px solid var(--line); background:var(--panel); }
  .chat .head { flex-shrink:0; padding:14px 18px; border-bottom:1px solid var(--line); font-weight:700; font-size:12px; color:var(--muted); text-transform:uppercase; letter-spacing:.6px; }
  .msgs { flex:1; min-height:0; overflow-y:auto; padding:18px; display:flex; flex-direction:column; gap:12px; }
  .msg { padding:10px 13px; border-radius:12px; max-width:90%; font-size:14px; line-height:1.45; white-space:pre-wrap; }
  .msg.user { align-self:flex-end; background:linear-gradient(135deg,var(--accent),#4a6fe0); color:#fff; border-bottom-right-radius:4px; box-shadow:var(--shadow); }
  .msg.assistant { align-self:flex-start; background:var(--panel2); border:1px solid var(--line); border-bottom-left-radius:4px; }
  .composer { flex-shrink:0; display:flex; gap:8px; padding:14px; border-top:1px solid var(--line); background:var(--panel); }
  .composer input { flex:1; background:var(--bg); border:1px solid var(--line); color:var(--text); padding:12px 14px; border-radius:11px; font-size:14px; outline:none; transition:.15s; }
  .composer input:focus { border-color:var(--accent); }
  .composer button { background:var(--accent); border:none; color:#fff; padding:0 18px; border-radius:11px; font-weight:700; cursor:pointer; transition:.15s; }
  .composer button:hover { background:var(--accent2); }
  .quick { flex-shrink:0; display:flex; gap:6px; padding:0 14px 12px; flex-wrap:wrap; background:var(--panel); }
  .quick button { background:var(--panel2); border:1px solid var(--line); color:var(--muted); font-size:12px; padding:7px 11px; border-radius:9px; cursor:pointer; transition:.15s; }
  .quick button:hover { border-color:var(--accent); color:var(--text); }
  /* main */
  .main { min-height:0; overflow-y:auto; padding:24px; }
  .cards { display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:12px; margin-bottom:18px; }
  .card { background:linear-gradient(180deg,var(--panel),#0f1628); border:1px solid var(--line); border-radius:14px; padding:16px 18px; box-shadow:var(--shadow); }
  .card .l { color:var(--muted); font-size:11px; text-transform:uppercase; letter-spacing:.6px; font-weight:700; }
  .card .v { font-size:24px; font-weight:800; margin-top:8px; }
  .v.ok { color:var(--ok); } .v.run { color:var(--accent2); }
  .panel { background:var(--panel); border:1px solid var(--line); border-radius:14px; padding:18px; margin-bottom:18px; box-shadow:var(--shadow); }
  .panel h2 { font-size:13px; margin:0 0 12px; color:var(--muted); text-transform:uppercase; letter-spacing:.5px; }
  .row { display:flex; gap:10px; flex-wrap:wrap; align-items:center; }
  .btn { background:var(--accent); border:none; color:#fff; padding:10px 16px; border-radius:9px; font-weight:700; cursor:pointer; font-size:13px; }
  .btn.ghost { background:transparent; border:1px solid var(--line); color:var(--text); }
  .btn.danger { background:var(--bad); }
  select, input[type=text], input[type=number] { background:var(--bg); border:1px solid var(--line); color:var(--text); padding:9px 11px; border-radius:8px; font-size:13px; }
  label { font-size:12px; color:var(--muted); display:block; margin:8px 0 4px; }
  .grid2 { display:grid; grid-template-columns:1fr 1fr; gap:10px; }
  .drop { border:2px dashed var(--line); border-radius:12px; padding:26px; text-align:center; color:var(--muted); cursor:pointer; transition:.15s; }
  .drop.hover { border-color:var(--accent); color:var(--text); background:var(--panel2); }
  table { width:100%; border-collapse:collapse; font-size:13px; }
  th,td { text-align:left; padding:9px 10px; border-bottom:1px solid var(--line); }
  th { color:var(--muted); font-weight:600; font-size:11px; text-transform:uppercase; }
  .tag { font-size:11px; padding:2px 8px; border-radius:20px; font-weight:700; }
  .tag.yes { background:rgba(45,212,167,.15); color:var(--ok); }
  .tag.no { background:rgba(139,151,181,.15); color:var(--muted); }
  .spark { height:60px; width:100%; }
  .hint { color:var(--muted); font-size:12px; margin-top:6px; }
  .files { max-height:120px; overflow:auto; font-size:12px; color:var(--muted); background:var(--bg); border:1px solid var(--line); border-radius:8px; padding:8px; margin-top:8px; }
</style>
</head>
<body>
<header>
  <div><h1>🔬 Autoresearch</h1><div class="sub" id="sub">—</div></div>
  <div class="topbtns">
    <a href="/report.html" target="_blank">Rapport HTML</a>
    <a href="/report.md" target="_blank">Rapport MD</a>
  </div>
</header>
<div class="layout">
  <!-- CHAT -->
  <section class="chat">
    <div class="head">💬 Assistant</div>
    <div class="msgs" id="msgs"></div>
    <div class="quick">
      <button onclick="send('lance la recherche')">▶ Lancer</button>
      <button onclick="send('arrête')">⏹ Arrêter</button>
      <button onclick="send('statut')">📊 Statut</button>
      <button onclick="send('meilleur résultat')">🏆 Meilleur</button>
    </div>
    <div class="composer">
      <input id="inp" placeholder="Écris un ordre ou une question…" onkeydown="if(event.key==='Enter')send()">
      <button onclick="send()">Envoyer</button>
    </div>
  </section>
  <!-- MAIN -->
  <section class="main">
    <div class="cards">
      <div class="card"><div class="l">Statut</div><div class="v" id="c-status">—</div></div>
      <div class="card"><div class="l">Trials</div><div class="v" id="c-trials">0</div></div>
      <div class="card"><div class="l">Meilleur score</div><div class="v ok" id="c-best">n/a</div></div>
      <div class="card"><div class="l">Prochain trial</div><div class="v" id="c-next">1</div></div>
    </div>

    <div class="panel">
      <h2>Projet & contrôle</h2>
      <div class="row">
        <button class="btn" onclick="run()">▶ Lancer la recherche</button>
        <button class="btn danger" onclick="stop()">⏹ Arrêter</button>
        <select id="examples" onchange="selectExample()"><option value="">— charger un exemple —</option></select>
      </div>
      <div class="hint" id="cfg-hint">Aucun projet configuré.</div>
    </div>

    <div class="panel">
      <h2>Déposer un projet (zip)</h2>
      <div class="drop" id="drop">📦 Glisse un .zip ici, ou clique pour choisir un fichier
        <input type="file" id="file" accept=".zip" style="display:none">
      </div>
      <div id="uploaded" style="display:none">
        <div class="files" id="filelist"></div>
        <div class="grid2">
          <div><label>Nom</label><input type="text" id="f-name"></div>
          <div><label>Commande qui lance et note le projet</label><input type="text" id="f-command" placeholder="python train.py"></div>
          <div><label>Regex de la note (métrique)</label><input type="text" id="f-metric" value="val_bpb:\s*([0-9.]+)"></div>
          <div><label>Fichier de paramètres (optionnel)</label><input type="text" id="f-params" placeholder="params.json"></div>
          <div><label>Itérations</label><input type="number" id="f-iter" value="12"></div>
          <div><label>Secondes / trial</label><input type="number" id="f-secs" value="120"></div>
        </div>
        <label><input type="checkbox" id="f-max"> Maximiser la note (sinon: minimiser)</label>
        <label><input type="checkbox" id="f-agent"> Laisser Mistral éditer le code</label>
        <div id="agentbox" style="display:none">
          <label>Fichiers éditables par Mistral (séparés par des virgules)</label>
          <input type="text" id="f-agentfiles" placeholder="train.py, params.json">
          <label>Fichier objectif (optionnel)</label>
          <input type="text" id="f-objective" placeholder="program.md">
        </div>
        <div class="row" style="margin-top:12px">
          <button class="btn" onclick="configure()">✓ Configurer ce projet</button>
        </div>
      </div>
    </div>

    <div class="panel">
      <h2>Progression du score</h2>
      <svg class="spark" id="spark" viewBox="0 0 600 60" preserveAspectRatio="none"></svg>
    </div>

    <div class="panel">
      <h2>Trials récents</h2>
      <table><thead><tr><th>#</th><th>Score</th><th>Accepté</th><th>Résumé</th><th>Erreur</th></tr></thead>
      <tbody id="rows"><tr><td colspan="5" style="color:var(--muted)">Aucun trial.</td></tr></tbody></table>
    </div>
  </section>
</div>
<script>
let uploadedWorkspace = null;
async function api(path, body){ const r = await fetch(path, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body||{})}); return r.json(); }
async function getState(){ const r = await fetch('/api/state'); return r.json(); }

let chatPending=false;
function addMsg(role, text){ const d=document.getElementById('msgs'); const e=document.createElement('div'); e.className='msg '+role; e.textContent=text; d.appendChild(e); d.scrollTop=d.scrollHeight; return e; }
async function send(forced){
  const inp=document.getElementById('inp'); const msg=forced||inp.value.trim();
  if(!msg||chatPending)return;
  if(!forced){inp.value='';}
  chatPending=true;
  addMsg('user',msg);
  const thinking=addMsg('assistant','… (réflexion)');
  try{
    const res=await api('/api/chat',{message:msg});
    thinking.textContent=res.reply||'(pas de réponse)';
  }catch(e){
    thinking.textContent='❌ Erreur de connexion: '+e;
  }finally{
    chatPending=false; lastChatLen=-1; refresh();
  }
}

async function run(){ const r=await api('/api/run',{}); flash(r.message); refresh(); }
async function stop(){ const r=await api('/api/stop',{}); flash(r.message); refresh(); }
function flash(m){ document.getElementById('cfg-hint').textContent=m||''; }

async function selectExample(){ const v=document.getElementById('examples').value; if(!v)return; const r=await api('/api/select_example',{path:v}); flash(r.ok?r.message:('Erreur: '+r.error)); refresh(); }

// upload
const drop=document.getElementById('drop'), file=document.getElementById('file');
drop.onclick=()=>file.click();
drop.ondragover=e=>{e.preventDefault();drop.classList.add('hover');};
drop.ondragleave=()=>drop.classList.remove('hover');
drop.ondrop=e=>{e.preventDefault();drop.classList.remove('hover'); if(e.dataTransfer.files[0])upload(e.dataTransfer.files[0]);};
file.onchange=()=>{ if(file.files[0])upload(file.files[0]); };
document.getElementById('f-agent').onchange=e=>{ document.getElementById('agentbox').style.display=e.target.checked?'block':'none'; };

function upload(f){
  const reader=new FileReader();
  reader.onload=async()=>{
    const b64=reader.result.split(',')[1];
    drop.textContent='⏳ Extraction…';
    const r=await api('/api/upload',{filename:f.name, data:b64});
    if(!r.ok){ drop.textContent='❌ '+r.error; return; }
    uploadedWorkspace=r.workspace;
    document.getElementById('uploaded').style.display='block';
    document.getElementById('filelist').textContent=r.files.join('\n')||'(vide)';
    document.getElementById('f-name').value=f.name.replace('.zip','');
    drop.textContent='✅ '+f.name+' extrait. Configure ci-dessous.';
  };
  reader.readAsDataURL(f);
}

async function configure(){
  if(!uploadedWorkspace){ flash('Dépose d\'abord un zip.'); return; }
  const body={
    workspace:uploadedWorkspace,
    name:document.getElementById('f-name').value,
    command:document.getElementById('f-command').value,
    metric_regex:document.getElementById('f-metric').value,
    parameter_file:document.getElementById('f-params').value,
    iterations:document.getElementById('f-iter').value,
    seconds_per_trial:document.getElementById('f-secs').value,
    maximize:document.getElementById('f-max').checked,
    use_agent:document.getElementById('f-agent').checked,
    agent_files:document.getElementById('f-agentfiles').value,
    objective_file:document.getElementById('f-objective').value
  };
  const r=await api('/api/configure',body);
  flash(r.ok?('✅ '+r.message):('❌ '+r.error));
  refresh();
}

function sparkline(scores){
  const svg=document.getElementById('spark'); svg.innerHTML='';
  if(!scores.length){ return; }
  const min=Math.min(...scores), max=Math.max(...scores), span=(max-min)||1;
  const pts=scores.map((s,i)=>{ const x=scores.length>1? i/(scores.length-1)*600:300; const y=58-((s-min)/span)*54; return x+','+y; }).join(' ');
  const poly=document.createElementNS('http://www.w3.org/2000/svg','polyline');
  poly.setAttribute('points',pts); poly.setAttribute('fill','none'); poly.setAttribute('stroke','#4f7cff'); poly.setAttribute('stroke-width','2');
  svg.appendChild(poly);
}

let lastChatLen=0;
async function refresh(){
  const s=await getState();
  document.getElementById('c-status').textContent=s.running?'En cours':'Inactif';
  document.getElementById('c-status').className='v '+(s.running?'run':'');
  document.getElementById('c-trials').textContent=s.trials.length;
  document.getElementById('c-best').textContent=s.best?s.best.score:'n/a';
  document.getElementById('c-next').textContent=s.next_trial;
  document.getElementById('sub').textContent=s.config?(s.config.name+' · '+s.config.command):'Aucun projet';
  document.getElementById('cfg-hint').textContent=s.message||'';
  // examples
  const sel=document.getElementById('examples');
  if(sel.options.length<=1 && s.examples.length){ s.examples.forEach(e=>{ const o=document.createElement('option'); o.value=e.path; o.textContent=e.name; sel.appendChild(o); }); }
  // trials
  const rows=document.getElementById('rows');
  if(s.trials.length){ rows.innerHTML=s.trials.slice().reverse().map(t=>`<tr><td>${t.trial}</td><td>${t.score==null?'—':t.score}</td><td><span class="tag ${t.accepted?'yes':'no'}">${t.accepted?'oui':'non'}</span></td><td>${(t.summary||'').slice(0,90)}</td><td style="color:var(--bad)">${(t.error||'')}</td></tr>`).join(''); }
  else { rows.innerHTML='<tr><td colspan="5" style="color:var(--muted)">Aucun trial.</td></tr>'; }
  sparkline(s.scores);
  // chat sync (e.g. messages added server-side) — paused while a chat is pending
  if(!chatPending && s.chat.length!==lastChatLen){ document.getElementById('msgs').innerHTML=''; s.chat.forEach(m=>addMsg(m.role,m.text)); lastChatLen=s.chat.length; }
}
addMsg('assistant','Bonjour ! Je pilote la recherche et je peux discuter de ton projet.\nDépose un zip à droite, ou tape « lance » pour démarrer.');
refresh(); setInterval(refresh, 3000);
</script>
</body>
</html>
"""
