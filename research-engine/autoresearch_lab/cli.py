from __future__ import annotations

from pathlib import Path
import argparse
import json

from .bootstrap import ProjectBootstrapper
from .config import ResearchConfig
from .ledger import Ledger
from .loop import ResearchLoop
from .report import ReportWriter
from .ui import serve_ui


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a clean-room autoresearch loop.")
    subparsers = parser.add_subparsers(dest="command_name")

    run = subparsers.add_parser("run", help="Run experiments.")
    run.add_argument("--config", required=True, help="Path to a JSON config file.")

    validate = subparsers.add_parser("validate", help="Validate a config file.")
    validate.add_argument("--config", required=True, help="Path to a JSON config file.")

    status = subparsers.add_parser("status", help="Show current run status.")
    status.add_argument("--config", required=True, help="Path to a JSON config file.")

    report = subparsers.add_parser("report", help="Regenerate Markdown and HTML reports.")
    report.add_argument("--config", required=True, help="Path to a JSON config file.")

    ui = subparsers.add_parser("ui", help="Start a local web interface.")
    ui.add_argument("--config", help="Optional path to a JSON config file (can also be set from the UI).")
    ui.add_argument("--host", default="127.0.0.1", help="Host to bind.")
    ui.add_argument("--port", type=int, default=8765, help="Port to bind.")
    ui.add_argument("--no-open", action="store_true", help="Do not open the browser.")

    bootstrap = subparsers.add_parser("bootstrap-project", help="Create a new project from a blueprint.")
    bootstrap.add_argument("--name", required=True, help="Project folder name.")
    bootstrap.add_argument("--output-dir", default="generated-projects", help="Where to create the project.")
    bootstrap.add_argument("--blueprint", default="studio-ia", help="Blueprint name.")
    bootstrap.add_argument("--force", action="store_true", help="Overwrite existing blueprint files.")

    parser.add_argument("--config", help=argparse.SUPPRESS)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.command_name is None and args.config:
        args.command_name = "run"
    if args.command_name is None:
        build_parser().print_help()
        return

    if args.command_name == "bootstrap-project":
        result = ProjectBootstrapper(
            output_dir=Path(args.output_dir).resolve(),
            name=args.name,
            blueprint=args.blueprint,
        ).run(force=args.force)
        print(
            json.dumps(
                {
                    "project_dir": str(result.project_dir),
                    "config_path": str(result.config_path),
                    "files_written": result.files_written,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return

    if args.command_name == "ui":
        config = ResearchConfig.from_file(Path(args.config).resolve()) if args.config else None
        serve_ui(
            config,
            host=args.host,
            port=args.port,
            open_browser=not args.no_open,
            base_dir=Path.cwd(),
        )
        return

    config = ResearchConfig.from_file(Path(args.config).resolve())

    if args.command_name == "run":
        ResearchLoop(config).run()
        return

    if args.command_name == "validate":
        print("config ok")
        return

    run_dir = config.output_dir / config.name
    ledger = Ledger(run_dir / "ledger.jsonl")

    if args.command_name == "status":
        records = ledger.records()
        state_path = run_dir / "state.json"
        state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
        print(json.dumps({"records": len(records), "state": state}, indent=2, sort_keys=True))
        return

    if args.command_name == "report":
        ReportWriter(run_dir).write(ledger.records())
        print(f"wrote {run_dir / 'report.md'} and {run_dir / 'report.html'}")
        return


if __name__ == "__main__":
    main()

