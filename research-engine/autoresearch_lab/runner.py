from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import re
import subprocess
import time


@dataclass(frozen=True)
class RunResult:
    score: float | None
    stdout: str
    stderr: str
    seconds: float
    error: str | None


class ExperimentRunner:
    def __init__(
        self,
        command: str,
        metric_regex: str,
        seconds_per_trial: int,
        metric_file: str | None = None,
    ) -> None:
        self.command = command
        self.metric_pattern = re.compile(metric_regex)
        self.seconds_per_trial = seconds_per_trial
        self.metric_file = metric_file

    def run(self, workspace: Path) -> RunResult:
        start = time.perf_counter()
        try:
            completed = subprocess.run(
                self.command,
                cwd=workspace,
                shell=True,
                text=True,
                capture_output=True,
                timeout=self.seconds_per_trial,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            return RunResult(
                score=None,
                stdout=exc.stdout or "",
                stderr=exc.stderr or "",
                seconds=time.perf_counter() - start,
                error=f"timeout after {self.seconds_per_trial}s",
            )

        score = self._read_metric(workspace, completed.stdout)
        error = None if completed.returncode == 0 else f"exit code {completed.returncode}"
        return RunResult(
            score=score,
            stdout=completed.stdout,
            stderr=completed.stderr,
            seconds=time.perf_counter() - start,
            error=error,
        )

    def _read_metric(self, workspace: Path, stdout: str) -> float | None:
        if self.metric_file:
            path = workspace / self.metric_file
            if path.exists():
                data = json.loads(path.read_text(encoding="utf-8"))
                value = data.get("metric", data.get("score"))
                return float(value)

        match = self.metric_pattern.search(stdout)
        if not match:
            return None
        return float(match.group(1))

