from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from autoresearch_lab.report import ReportWriter


class ReportWriterTest(unittest.TestCase):
    def test_writes_markdown_and_html(self) -> None:
        records = [
            {
                "trial": 1,
                "score": 1.0,
                "accepted": True,
                "seconds": 0.1,
                "summary": "baseline",
            }
        ]
        with tempfile.TemporaryDirectory() as temp:
            run_dir = Path(temp)
            ReportWriter(run_dir).write(records)

            self.assertTrue((run_dir / "report.md").exists())
            self.assertTrue((run_dir / "report.html").exists())


if __name__ == "__main__":
    unittest.main()
