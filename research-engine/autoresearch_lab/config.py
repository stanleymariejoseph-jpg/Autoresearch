from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import re


@dataclass(frozen=True)
class ResearchConfig:
    name: str
    workspace: Path
    command: str
    metric_regex: str = r"metric\s*[:=]\s*([-+]?[0-9]*\.?[0-9]+)"
    parameter_file: str | None = None
    metric_file: str | None = None
    output_dir: Path = Path("runs")
    iterations: int = 12
    seconds_per_trial: int = 300
    maximize: bool = False
    seed: int = 1337
    agent_command: str | None = None
    resume: bool = True
    patience: int | None = None
    baseline_first: bool = True
    keep_all_trials: bool = True
    report: bool = True
    ignore_patterns: tuple[str, ...] = ("__pycache__", ".git", "runs", ".venv")

    @classmethod
    def from_file(cls, path: Path) -> "ResearchConfig":
        data = json.loads(path.read_text(encoding="utf-8"))
        base = path.parent
        workspace = Path(data["workspace"])
        output_dir = Path(data.get("output_dir", "runs"))

        if not workspace.is_absolute():
            workspace = (base / workspace).resolve()
        if not output_dir.is_absolute():
            output_dir = (base / output_dir).resolve()

        config = cls(
            name=str(data.get("name", path.stem)),
            workspace=workspace,
            command=str(data["command"]),
            metric_regex=str(data.get("metric_regex", cls.metric_regex)),
            parameter_file=data.get("parameter_file"),
            metric_file=data.get("metric_file"),
            output_dir=output_dir,
            iterations=int(data.get("iterations", 12)),
            seconds_per_trial=int(data.get("seconds_per_trial", 300)),
            maximize=bool(data.get("maximize", False)),
            seed=int(data.get("seed", 1337)),
            agent_command=data.get("agent_command"),
            resume=bool(data.get("resume", True)),
            patience=None if data.get("patience") is None else int(data["patience"]),
            baseline_first=bool(data.get("baseline_first", True)),
            keep_all_trials=bool(data.get("keep_all_trials", True)),
            report=bool(data.get("report", True)),
            ignore_patterns=tuple(data.get("ignore_patterns", cls.ignore_patterns)),
        )
        config.validate()
        return config

    def validate(self) -> None:
        if not self.workspace.exists():
            raise ValueError(f"workspace does not exist: {self.workspace}")
        if not self.workspace.is_dir():
            raise ValueError(f"workspace must be a directory: {self.workspace}")
        if self.iterations < 1:
            raise ValueError("iterations must be at least 1")
        if self.seconds_per_trial < 1:
            raise ValueError("seconds_per_trial must be at least 1")
        if self.patience is not None and self.patience < 1:
            raise ValueError("patience must be null or at least 1")
        re.compile(self.metric_regex)

