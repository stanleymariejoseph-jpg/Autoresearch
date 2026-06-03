"""Smoke tests for the nanogpt-cpu example.

These tests do not run the full training loop; they only verify the example
files are in place and the prepare/train scripts are valid Python that
exposes the expected output contract.
"""
from __future__ import annotations

from pathlib import Path
import json
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "nanogpt-cpu"
CONFIG = ROOT / "examples" / "nanogpt-cpu-config.json"


class NanoGPTExampleTests(unittest.TestCase):
    def test_files_exist(self) -> None:
        for name in ("prepare.py", "train.py", "params.json", "program.md"):
            self.assertTrue((EXAMPLE / name).exists(), f"missing {name}")
        self.assertTrue(CONFIG.exists())

    def test_config_is_valid_json_with_expected_keys(self) -> None:
        data = json.loads(CONFIG.read_text(encoding="utf-8"))
        self.assertEqual(data["name"], "nanogpt-cpu")
        self.assertEqual(data["workspace"], "nanogpt-cpu")
        self.assertEqual(data["parameter_file"], "params.json")
        self.assertIn("val_bpb", data["metric_regex"])

    def test_train_script_compiles(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "py_compile", str(EXAMPLE / "train.py")],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_prepare_script_compiles(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "py_compile", str(EXAMPLE / "prepare.py")],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
