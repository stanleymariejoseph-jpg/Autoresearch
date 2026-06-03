from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest

from autoresearch_lab.runner import ExperimentRunner


class ExperimentRunnerTest(unittest.TestCase):
    def test_extracts_metric_from_stdout(self) -> None:
        runner = ExperimentRunner(
            command=f"\"{sys.executable}\" -c \"print('metric: 0.125')\"",
            metric_regex=r"metric:\s*([0-9.]+)",
            seconds_per_trial=10,
        )
        with tempfile.TemporaryDirectory() as temp:
            result = runner.run(Path(temp))

        self.assertEqual(result.score, 0.125)
        self.assertIsNone(result.error)


if __name__ == "__main__":
    unittest.main()
