"""Skill loading for the autoresearch agent.

A "skill" is a folder containing a SKILL.md file (instructions) and optional
helper scripts/assets. This module discovers skills, parses their metadata,
and turns them into a prompt block that is injected into the agent's
objective so the Mistral agent knows the skills exist and how to use them.

Skills are how Claude Code packages reusable expertise; here we make the same
packaged instructions available to the autoresearch agent.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil


@dataclass(frozen=True)
class Skill:
    name: str
    description: str
    body: str
    directory: Path


def _parse_front_matter(text: str) -> tuple[dict[str, str], str]:
    """Very small YAML front-matter parser (key: value lines only)."""
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    header = text[3:end].strip()
    body = text[end + 4 :].lstrip("\n")
    meta: dict[str, str] = {}
    for line in header.splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            meta[key.strip()] = value.strip().strip('"').strip("'")
    return meta, body


def parse_skill(directory: Path) -> Skill | None:
    skill_md = directory / "SKILL.md"
    if not skill_md.exists():
        return None
    raw = skill_md.read_text(encoding="utf-8", errors="replace")
    meta, body = _parse_front_matter(raw)
    name = meta.get("name") or directory.name
    description = meta.get("description") or ""
    return Skill(name=name, description=description, body=body, directory=directory)


def resolve_skill(entry: str, skills_dir: Path | None) -> Path | None:
    """Resolve a skill entry (a name under skills_dir, or a path)."""
    candidate = Path(entry)
    if candidate.is_absolute() and (candidate / "SKILL.md").exists():
        return candidate
    if skills_dir is not None:
        by_name = skills_dir / entry
        if (by_name / "SKILL.md").exists():
            return by_name
    if (candidate / "SKILL.md").exists():
        return candidate
    return None


def load_skills(entries: tuple[str, ...], skills_dir: Path | None) -> list[Skill]:
    skills: list[Skill] = []
    for entry in entries:
        directory = resolve_skill(entry, skills_dir)
        if directory is None:
            continue
        skill = parse_skill(directory)
        if skill is not None:
            skills.append(skill)
    return skills


def build_prompt(skills: list[Skill], max_chars_each: int = 2500) -> str:
    if not skills:
        return ""
    parts = [
        "## Skills available to you",
        "You may apply the expertise in these skills. Their full files (and any "
        "helper scripts) live under the workspace folder `skills/<name>/`.",
        "",
    ]
    for skill in skills:
        body = skill.body.strip()
        if len(body) > max_chars_each:
            body = body[:max_chars_each].rstrip() + "\n…(tronqué — voir skills/" + skill.name + "/SKILL.md)"
        parts.append(f"### Skill: {skill.name}")
        if skill.description:
            parts.append(f"_{skill.description}_")
        parts.append("")
        parts.append(body)
        parts.append("")
    return "\n".join(parts)


def copy_skill_assets(skills: list[Skill], workspace: Path) -> None:
    """Copy each skill folder into <workspace>/skills/<name> so scripts run."""
    if not skills:
        return
    dest_root = workspace / "skills"
    for skill in skills:
        dest = dest_root / skill.directory.name
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(skill.directory, dest, ignore=shutil.ignore_patterns("__pycache__", ".git"))
