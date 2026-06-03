"""Download and install third-party skills into research-engine/skills/.

These skills are external projects with their own licenses; they are NOT
committed to this repo. Run this script to fetch them locally so the
autoresearch agent can use them.

Usage:
    python scripts/install_skills.py
"""
from __future__ import annotations

from pathlib import Path
import io
import shutil
import sys
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SKILLS_DIR = ROOT / "skills"

SOURCES = [
    # (url, inner_prefix that precedes each "<skill>/SKILL.md")
    ("https://github.com/anthropics/skills/archive/refs/heads/main.zip", "skills-main/skills/"),
    ("https://github.com/nextlevelbuilder/ui-ux-pro-max-skill/archive/refs/heads/main.zip", ".claude/skills/"),
    ("https://github.com/lackeyjb/playwright-skill/archive/refs/heads/main.zip", "skills/playwright-skill/"),
]


def install_from_zip(data: bytes, inner_prefix: str) -> int:
    count = 0
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        names = zf.namelist()
        skill_dirs = {
            nm[: -len("SKILL.md")]
            for nm in names
            if nm.endswith("/SKILL.md") and inner_prefix in nm
        }
        for d in skill_dirs:
            skill_name = d.rstrip("/").split("/")[-1]
            target = SKILLS_DIR / skill_name
            for nm in names:
                if nm.startswith(d) and not nm.endswith("/"):
                    dest = target / nm[len(d):]
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    with zf.open(nm) as src, open(dest, "wb") as out:
                        shutil.copyfileobj(src, out)
            count += 1
    return count


def main() -> None:
    SKILLS_DIR.mkdir(parents=True, exist_ok=True)
    total = 0
    for url, prefix in SOURCES:
        print(f"downloading {url}")
        try:
            with urllib.request.urlopen(url, timeout=90) as resp:
                data = resp.read()
        except Exception as exc:
            print(f"  failed: {exc}", file=sys.stderr)
            continue
        n = install_from_zip(data, prefix)
        print(f"  installed {n} skill(s)")
        total += n
    installed = sorted(p.name for p in SKILLS_DIR.iterdir() if p.is_dir())
    print(f"\nTotal: {total} skill(s) under {SKILLS_DIR}")
    print("Available:", ", ".join(installed))


if __name__ == "__main__":
    main()
