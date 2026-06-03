from __future__ import annotations

from pathlib import Path
import argparse

from .config import ResearchConfig
from .loop import ResearchLoop


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a clean-room autoresearch loop.")
    parser.add_argument("--config", required=True, help="Path to a JSON config file.")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    config = ResearchConfig.from_file(Path(args.config).resolve())
    ResearchLoop(config).run()


if __name__ == "__main__":
    main()

