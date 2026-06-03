"""Smoke tests for the nanogpt-torch (PyTorch CPU) example."""
from __future__ import annotations

from pathlib import Path
import json
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "nanogpt-torch"
CONFIG = ROOT / "examples" / "nanogpt-torch-mistral-config.json"


class NanoGPTTorchExampleTests(unittest.TestCase):
    def test_files_exist(self) -> None:
        for name in ("prepare.py", "train.py", "params.json", "program.md"):
            self.assertTrue((EXAMPLE / name).exists(), f"missing {name}")
        self.assertTrue(CONFIG.exists())

    def test_config_valid(self) -> None:
        data = json.loads(CONFIG.read_text(encoding="utf-8"))
        self.assertEqual(data["workspace"], "nanogpt-torch")
        self.assertIn("val_bpb", data["metric_regex"])
        self.assertEqual(data["agent_provider"], "mistral")
        self.assertIn("train.py", data["agent_files"])

    def test_train_compiles(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "py_compile", str(EXAMPLE / "train.py")],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
