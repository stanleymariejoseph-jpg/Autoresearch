"""Scorer for the landing-build objective.

Scores index.html on objective, structural/functional criteria (NOT on
subjective beauty). Score = fraction of criteria met. This is the evaluator
and is not editable by the agent.
"""
from __future__ import annotations

from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent
HTML = ROOT / "index.html"


def main() -> None:
    text = HTML.read_text(encoding="utf-8", errors="replace").lower() if HTML.exists() else ""

    checks = [
        ("doctype", "<!doctype html" in text),
        ("viewport meta", "name=\"viewport\"" in text or "name='viewport'" in text),
        ("title tag", "<title>" in text and len(re.findall(r"<title>(.+?)</title>", text)) > 0),
        ("semantic header", "<header" in text),
        ("nav", "<nav" in text),
        ("hero section", "hero" in text or "<h1" in text),
        ("at least 3 sections", len(re.findall(r"<section", text)) >= 3),
        ("call to action button", ("<button" in text) or ("class=\"cta" in text) or ("btn" in text)),
        ("footer", "<footer" in text),
        ("inline or linked css", ("<style" in text) or ("rel=\"stylesheet\"" in text)),
        ("responsive hint (media query or flex/grid)", ("@media" in text) or ("display:flex" in text) or ("display: flex" in text) or ("grid" in text)),
        ("reasonable length", len(text) > 1500),
    ]

    passed = sum(1 for _, ok in checks if ok)
    total = len(checks)
    for name, ok in checks:
        print(("PASS" if ok else "FAIL") + " - " + name)
    print(f"checks_passed={passed}/{total}")
    print(f"AUTORESEARCH_SCORE: {passed / total:.6f}")


if __name__ == "__main__":
    main()
