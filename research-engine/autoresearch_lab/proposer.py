from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import json
import random


@dataclass(frozen=True)
class Proposal:
    summary: str
    changes: dict[str, Any] = field(default_factory=dict)


class ParameterProposer:
    def __init__(self, parameter_file: str | None, seed: int) -> None:
        self.parameter_file = parameter_file
        self.random = random.Random(seed)

    def propose(self, workspace: Path, trial: int) -> Proposal:
        if not self.parameter_file:
            return Proposal("No parameter_file configured; workspace left unchanged.")

        path = workspace / self.parameter_file
        if not path.exists():
            path.write_text("{}\n", encoding="utf-8")

        params = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(params, dict):
            raise ValueError(f"{self.parameter_file} must contain a JSON object")

        if not params:
            params = {"learning_rate": 0.01, "depth": 3, "regularization": 0.1}

        key = self.random.choice(list(params.keys()))
        old_value = params[key]
        params[key] = self._mutate(old_value)
        path.write_text(json.dumps(params, indent=2, sort_keys=True) + "\n", encoding="utf-8")

        return Proposal(
            summary=f"trial {trial}: changed {key} from {old_value!r} to {params[key]!r}",
            changes={key: {"from": old_value, "to": params[key]}},
        )

    def _mutate(self, value: Any) -> Any:
        if isinstance(value, bool):
            return not value
        if isinstance(value, int) and not isinstance(value, bool):
            step = self.random.choice([-2, -1, 1, 2])
            return max(1, value + step)
        if isinstance(value, float):
            factor = self.random.choice([0.5, 0.8, 1.2, 1.5])
            return round(max(1e-8, value * factor), 8)
        if isinstance(value, str):
            return value
        return value

