from __future__ import annotations

from pathlib import Path
import shutil
import subprocess

from .config import ResearchConfig
from .ledger import Ledger, TrialRecord
from .proposer import ParameterProposer
from .runner import ExperimentRunner


class ResearchLoop:
    def __init__(self, config: ResearchConfig) -> None:
        self.config = config
        self.run_dir = config.output_dir / config.name
        self.trials_dir = self.run_dir / "trials"
        self.best_dir = self.run_dir / "best"
        self.ledger = Ledger(self.run_dir / "ledger.jsonl")
        self.proposer = ParameterProposer(config.parameter_file, config.seed)
        self.runner = ExperimentRunner(
            command=config.command,
            metric_regex=config.metric_regex,
            seconds_per_trial=config.seconds_per_trial,
            metric_file=config.metric_file,
        )
        self.best_score: float | None = None

    def run(self) -> None:
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.trials_dir.mkdir(parents=True, exist_ok=True)

        for trial in range(1, self.config.iterations + 1):
            trial_workspace = self.trials_dir / f"trial-{trial:04d}"
            self._copy_workspace(self.config.workspace, trial_workspace)

            proposal = self._prepare_trial(trial_workspace, trial)
            result = self.runner.run(trial_workspace)
            accepted = self._is_improvement(result.score)

            if accepted:
                self.best_score = result.score
                if self.best_dir.exists():
                    shutil.rmtree(self.best_dir)
                shutil.copytree(trial_workspace, self.best_dir)

            self.ledger.append(
                TrialRecord(
                    trial=trial,
                    score=result.score,
                    accepted=accepted,
                    summary=proposal,
                    workspace=str(trial_workspace),
                    seconds=result.seconds,
                    error=result.error,
                )
            )

            marker = "accepted" if accepted else "rejected"
            print(f"[{trial:04d}] {marker} score={result.score} {proposal}")

    def _prepare_trial(self, workspace: Path, trial: int) -> str:
        if self.config.agent_command:
            completed = subprocess.run(
                self.config.agent_command,
                cwd=workspace,
                shell=True,
                text=True,
                capture_output=True,
                timeout=self.config.seconds_per_trial,
                check=False,
            )
            summary = completed.stdout.strip().splitlines()[-1:] or ["external agent command ran"]
            return summary[0]

        return self.proposer.propose(workspace, trial).summary

    def _is_improvement(self, score: float | None) -> bool:
        if score is None:
            return False
        if self.best_score is None:
            return True
        if self.config.maximize:
            return score > self.best_score
        return score < self.best_score

    @staticmethod
    def _copy_workspace(source: Path, destination: Path) -> None:
        if destination.exists():
            shutil.rmtree(destination)
        shutil.copytree(
            source,
            destination,
            ignore=shutil.ignore_patterns("__pycache__", ".git", "runs", ".venv"),
        )

