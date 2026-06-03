"""Smoke tests for the saas-build (acceptance-test driven) example."""
from __future__ import annotations

from pathlib import Path
import json
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "saas-build"
CONFIG = ROOT / "examples" / "saas-build-mistral-config.json"


class SaasBuildExampleTests(unittest.TestCase):
    def test_files_exist(self) -> None:
        for name in ("check.py", "app.py", "spec.md"):
            self.assertTrue((EXAMPLE / name).exists(), f"missing {name}")
        self.assertTrue(CONFIG.exists())

    def test_config_excludes_checker_from_agent(self) -> None:
        data = json.loads(CONFIG.read_text(encoding="utf-8"))
        self.assertTrue(data["maximize"])
        self.assertIn("app.py", data["agent_files"])
        self.assertNotIn("check.py", data["agent_files"])

    def test_stub_scores_zero(self) -> None:
        result = subprocess.run(
            [sys.executable, "check.py"],
            cwd=str(EXAMPLE),
            capture_output=True,
            text=True,
        )
        self.assertIn("AUTORESEARCH_SCORE: 0.0", result.stdout)


if __name__ == "__main__":
    unittest.main()
