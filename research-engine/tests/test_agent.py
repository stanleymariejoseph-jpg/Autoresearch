from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from autoresearch_lab.agent import CodeAgent


class FakeClient:
    def complete(self, messages: list[dict[str, str]]) -> str:
        return (
            '{"summary":"tune params",'
            '"files":[{"path":"params.json","content":"{\\"learning_rate\\": 0.02}\\n"}]}'
        )


class CodeAgentTest(unittest.TestCase):
    def test_applies_full_file_replacement(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp)
            (workspace / "params.json").write_text('{"learning_rate": 0.01}\n', encoding="utf-8")

            agent = CodeAgent(
                client=FakeClient(),  # type: ignore[arg-type]
                files=("params.json",),
                objective="lower metric",
                maximize=False,
            )
            patch = agent.propose(workspace, trial=2, best_score=0.5)

            self.assertEqual(patch.changed_files, ("params.json",))
            self.assertIn("0.02", (workspace / "params.json").read_text(encoding="utf-8"))

    def test_rejects_path_escape(self) -> None:
        class BadClient:
            def complete(self, messages: list[dict[str, str]]) -> str:
                return '{"summary":"bad","files":[{"path":"../x","content":"bad"}]}'

        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp)
            agent = CodeAgent(
                client=BadClient(),  # type: ignore[arg-type]
                files=("params.json",),
                objective="lower metric",
                maximize=False,
            )
            with self.assertRaises(ValueError):
                agent.propose(workspace, trial=1, best_score=None)

    def test_rejects_unlisted_file(self) -> None:
        class UnlistedClient:
            def complete(self, messages: list[dict[str, str]]) -> str:
                return '{"summary":"bad","files":[{"path":"other.py","content":"print(1)"}]}'

        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp)
            agent = CodeAgent(
                client=UnlistedClient(),  # type: ignore[arg-type]
                files=("params.json",),
                objective="lower metric",
                maximize=False,
            )
            with self.assertRaises(ValueError):
                agent.propose(workspace, trial=1, best_score=None)


if __name__ == "__main__":
    unittest.main()
