from __future__ import annotations

from pathlib import Path
import json
import tempfile
import unittest

from autoresearch_lab.proposer import ParameterProposer


class ParameterProposerTest(unittest.TestCase):
    def test_mutates_json_parameter_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp)
            path = workspace / "params.json"
            original = {"learning_rate": 0.01, "depth": 3}
            path.write_text(json.dumps(original), encoding="utf-8")

            proposal = ParameterProposer("params.json", seed=7).propose(workspace, trial=1)
            updated = json.loads(path.read_text(encoding="utf-8"))

            self.assertNotEqual(original, updated)
            self.assertTrue(proposal.summary.startswith("trial 1: changed"))
            self.assertTrue(proposal.changes)


if __name__ == "__main__":
    unittest.main()
