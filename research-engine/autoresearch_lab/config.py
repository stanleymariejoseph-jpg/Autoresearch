from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json


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

        return cls(
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
        )

