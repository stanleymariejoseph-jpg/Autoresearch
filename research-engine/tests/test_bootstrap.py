from __future__ import annotations

from pathlib import Path
import json
import tempfile
import unittest

from autoresearch_lab.bootstrap import ProjectBootstrapper
from autoresearch_lab.config import ResearchConfig


class ProjectBootstrapperTest(unittest.TestCase):
    def test_creates_studio_ia_project_and_config(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            result = ProjectBootstrapper(Path(temp), "studio-ia-next").run()

            self.assertTrue((result.project_dir / "package.json").exists())
            self.assertTrue((result.project_dir / "src/app.tsx").exists())
            self.assertTrue((result.project_dir / "scripts/score_project.py").exists())
            self.assertTrue(result.config_path.exists())

            data = json.loads(result.config_path.read_text(encoding="utf-8"))
            self.assertEqual(data["agent_provider"], "mistral")
            self.assertIn("src/app.tsx", data["agent_files"])

    def test_generated_config_is_valid(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            result = ProjectBootstrapper(Path(temp), "studio-ia-next").run()
            config = ResearchConfig.from_file(result.config_path)

            self.assertTrue(config.workspace.exists())
            self.assertEqual(config.agent_provider, "mistral")


if __name__ == "__main__":
    unittest.main()
