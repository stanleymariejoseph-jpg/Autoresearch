"""Smoke tests for the web-ui-build (Playwright-scored) example.

The actual browser run requires `playwright` + chromium, so these tests only
check the files, config wiring, and that check.py compiles.
"""
from __future__ import annotations

from pathlib import Path
import json
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "web-ui-build"
CONFIG = ROOT / "examples" / "web-ui-build-mistral-config.json"


class WebUiBuildExampleTests(unittest.TestCase):
    def test_files_exist(self) -> None:
        for name in ("check.py", "index.html", "brief.md"):
            self.assertTrue((EXAMPLE / name).exists(), f"missing {name}")
        self.assertTrue(CONFIG.exists())

    def test_config_wiring(self) -> None:
        data = json.loads(CONFIG.read_text(encoding="utf-8"))
        self.assertTrue(data["maximize"])
        self.assertIn("index.html", data["agent_files"])
        self.assertNotIn("check.py", data["agent_files"])
        self.assertIn("webapp-testing", data["skills"])

    def test_checker_compiles(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "py_compile", str(EXAMPLE / "check.py")],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
