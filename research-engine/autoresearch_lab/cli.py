from __future__ import annotations

from pathlib import Path
import argparse
import json

from .config import ResearchConfig
from .ledger import Ledger
from .loop import ResearchLoop
from .report import ReportWriter


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

    parser.add_argument("--config", help=argparse.SUPPRESS)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.command_name is None and args.config:
        args.command_name = "run"
    if args.command_name is None:
        build_parser().print_help()
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

