from __future__ import annotations

from pathlib import Path
import json
import shutil
import subprocess

from .agent import CodeAgent, MistralClient
from .config import ResearchConfig
from .ledger import Ledger, TrialRecord
from .proposer import ParameterProposer
from .report import ReportWriter
from .runner import ExperimentRunner


class ResearchLoop:
    def __init__(self, config: ResearchConfig) -> None:
        self.config = config
        self.run_dir = config.output_dir / config.name
        self.trials_dir = self.run_dir / "trials"
        self.best_dir = self.run_dir / "best"
        self.state_path = self.run_dir / "state.json"
        self.ledger = Ledger(self.run_dir / "ledger.jsonl")
        self.proposer = ParameterProposer(config.parameter_file, config.seed)
        self.runner = ExperimentRunner(
            command=config.command,
            metric_regex=config.metric_regex,
            seconds_per_trial=config.seconds_per_trial,
            metric_file=config.metric_file,
        )
        self.agent = self._build_agent()
        self.best_score: float | None = None
        self.next_trial = 1
        self.no_improvement = 0

    def run(self) -> None:
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.trials_dir.mkdir(parents=True, exist_ok=True)
        self._load_state()

        stop_trial = self.next_trial + self.config.iterations
        for trial in range(self.next_trial, stop_trial):
            trial_workspace = self.trials_dir / f"trial-{trial:04d}"
            source = self.best_dir if self.best_dir.exists() else self.config.workspace
            self._copy_workspace(source, trial_workspace, self.config.ignore_patterns)

            proposal = "baseline trial"
            if not (trial == 1 and self.config.baseline_first and self.best_score is None):
                try:
                    proposal = self._prepare_trial(trial_workspace, trial)
                except Exception as exc:
                    self.no_improvement += 1
                    self.ledger.append(
                        TrialRecord(
                            trial=trial,
                            score=None,
                            accepted=False,
                            summary="agent preparation failed",
                            workspace=str(trial_workspace),
                            seconds=0.0,
                            error=str(exc),
                            best_score=self.best_score,
                        )
                    )
                    self._save_state(trial + 1)
                    print(f"[{trial:04d}] rejected score=None best={self.best_score} agent error: {exc}")
                    continue
            result = self.runner.run(trial_workspace)
            accepted = self._is_improvement(result.score)
            stdout_path, stderr_path = self._write_outputs(trial_workspace, result.stdout, result.stderr)

            if accepted:
                self.best_score = result.score
                self.no_improvement = 0
                if self.best_dir.exists():
                    shutil.rmtree(self.best_dir)
                shutil.copytree(trial_workspace, self.best_dir)
            else:
                self.no_improvement += 1

            self.ledger.append(
                TrialRecord(
                    trial=trial,
                    score=result.score,
                    accepted=accepted,
                    summary=proposal,
                    workspace=str(trial_workspace),
                    seconds=result.seconds,
                    error=result.error,
                    stdout_path=str(stdout_path),
                    stderr_path=str(stderr_path),
                    best_score=self.best_score,
                )
            )
            self._save_state(trial + 1)

            marker = "accepted" if accepted else "rejected"
            print(f"[{trial:04d}] {marker} score={result.score} best={self.best_score} {proposal}")

            if self.config.patience is not None and self.no_improvement >= self.config.patience:
                print(f"stopping: no improvement for {self.no_improvement} trial(s)")
                break

            if not self.config.keep_all_trials and not accepted and trial_workspace.exists():
                shutil.rmtree(trial_workspace)

        if self.config.report:
            ReportWriter(self.run_dir).write(self.ledger.records())

    def _prepare_trial(self, workspace: Path, trial: int) -> str:
        if self.agent:
            patch = self.agent.propose(workspace, trial, self.best_score)
            (workspace / "agent-response.json").write_text(patch.raw_response, encoding="utf-8")
            return f"{patch.summary}; changed: {', '.join(patch.changed_files)}"

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

    def _build_agent(self) -> CodeAgent | None:
        if self.config.agent_provider != "mistral":
            return None
        client = MistralClient(
            model=self.config.agent_model,
            temperature=self.config.agent_temperature,
            max_tokens=self.config.agent_max_tokens,
        )
        objective = self._objective_text()
        return CodeAgent(
            client=client,
            files=self.config.agent_files,
            objective=objective,
            maximize=self.config.maximize,
        )

    def _objective_text(self) -> str:
        if self.config.objective_file:
            configured = self.config.workspace / self.config.objective_file
            if configured.exists():
                return configured.read_text(encoding="utf-8", errors="replace")

        build_program = self.config.workspace / "docs" / "BUILD_PROGRAM.md"
        if build_program.exists():
            return build_program.read_text(encoding="utf-8", errors="replace")

        program_path = self.config.workspace / "program.md"
        if program_path.exists():
            return program_path.read_text(encoding="utf-8", errors="replace")
        return (
            "Improve the application source files. Make small code changes that improve the parsed metric. "
            "Do not modify scoring, tests, generated artifacts, or evaluation commands."
        )

    def _is_improvement(self, score: float | None) -> bool:
        if score is None:
            return False
        if self.best_score is None:
            return True
        if self.config.maximize:
            return score > self.best_score
        return score < self.best_score

    @staticmethod
    def _copy_workspace(source: Path, destination: Path, ignore_patterns: tuple[str, ...]) -> None:
        if destination.exists():
            shutil.rmtree(destination)
        shutil.copytree(
            source,
            destination,
            ignore=shutil.ignore_patterns(*ignore_patterns),
        )

    def _write_outputs(self, workspace: Path, stdout: str, stderr: str) -> tuple[Path, Path]:
        stdout_path = workspace / "stdout.txt"
        stderr_path = workspace / "stderr.txt"
        stdout_path.write_text(stdout, encoding="utf-8")
        stderr_path.write_text(stderr, encoding="utf-8")
        return stdout_path, stderr_path

    def _load_state(self) -> None:
        if not self.config.resume or not self.state_path.exists():
            return

        state = json.loads(self.state_path.read_text(encoding="utf-8"))
        self.best_score = state.get("best_score")
        self.next_trial = int(state.get("next_trial", 1))
        self.no_improvement = int(state.get("no_improvement", 0))

    def _save_state(self, next_trial: int) -> None:
        payload = {
            "name": self.config.name,
            "next_trial": next_trial,
            "best_score": self.best_score,
            "no_improvement": self.no_improvement,
            "maximize": self.config.maximize,
            "best_workspace": str(self.best_dir) if self.best_dir.exists() else None,
        }
        self.state_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

