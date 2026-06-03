"""Tests for the skill loader."""
from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from autoresearch_lab.skills import build_prompt, load_skills, parse_skill


class SkillLoaderTests(unittest.TestCase):
    def _make_skill(self, root: Path, name: str, desc: str, body: str) -> None:
        d = root / name
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text(
            f"---\nname: {name}\ndescription: {desc}\n---\n{body}\n", encoding="utf-8"
        )

    def test_parse_front_matter_and_body(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._make_skill(root, "demo", "a demo skill", "Do the thing well.")
            skill = parse_skill(root / "demo")
            self.assertIsNotNone(skill)
            self.assertEqual(skill.name, "demo")
            self.assertEqual(skill.description, "a demo skill")
            self.assertIn("Do the thing well.", skill.body)

    def test_load_by_name_and_build_prompt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._make_skill(root, "alpha", "first", "Alpha body here.")
            self._make_skill(root, "beta", "second", "Beta body here.")
            skills = load_skills(("alpha", "beta", "missing"), root)
            self.assertEqual([s.name for s in skills], ["alpha", "beta"])
            prompt = build_prompt(skills, max_chars_each=1000)
            self.assertIn("Skill: alpha", prompt)
            self.assertIn("Skill: beta", prompt)
            self.assertIn("first", prompt)

    def test_truncation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._make_skill(root, "big", "huge", "X" * 5000)
            skills = load_skills(("big",), root)
            prompt = build_prompt(skills, max_chars_each=500)
            self.assertIn("tronqué", prompt)

    def test_empty_returns_empty_prompt(self) -> None:
        self.assertEqual(build_prompt([], 100), "")


if __name__ == "__main__":
    unittest.main()
