from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
import json
import time


@dataclass
class TrialRecord:
    trial: int
    score: float | None
    accepted: bool
    summary: str
    workspace: str
    seconds: float
    error: str | None = None


class Ledger:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, record: TrialRecord) -> None:
        payload: dict[str, Any] = asdict(record)
        payload["created_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")

