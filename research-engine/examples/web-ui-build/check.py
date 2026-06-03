"""Browser-verified scorer for the web-ui-build objective.

Unlike a regex/structure checker, this actually opens index.html in a real
Chromium browser via Playwright and verifies the page FUNCTIONS: it renders,
has a usable heading and button, navigates, is responsive, and logs no console
errors. Score = fraction of functional checks that pass (higher is better).

This is the evaluator and is not editable by the agent. Requires:
    pip install playwright
    python -m playwright install chromium
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent
PAGE = ROOT / "index.html"


def run_checks() -> list[tuple[str, bool]]:
    from playwright.sync_api import sync_playwright

    results: list[tuple[str, bool]] = []
    console_errors: list[str] = []

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.on("console", lambda m: console_errors.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: console_errors.append(str(e)))

        url = PAGE.as_uri()
        page.goto(url, wait_until="networkidle")

        # heading
        h1 = page.query_selector("h1")
        results.append(("visible non-empty <h1>", bool(h1 and h1.is_visible() and (h1.inner_text() or "").strip())))

        # navigation with at least 2 links
        nav_links = page.query_selector_all("nav a, header a")
        results.append(("nav with >= 2 links", len(nav_links) >= 2))

        # a usable button / CTA
        btn = page.query_selector("button, a.btn, .cta, [role=button]")
        results.append(("visible call-to-action", bool(btn and btn.is_visible())))

        # clicking the CTA does not crash the page
        click_ok = True
        if btn:
            try:
                btn.click(timeout=2000)
            except Exception:
                click_ok = False
        results.append(("CTA is clickable without error", click_ok))

        # at least 3 sections
        sections = page.query_selector_all("section")
        results.append(("at least 3 <section> blocks", len(sections) >= 3))

        # footer present and visible
        footer = page.query_selector("footer")
        results.append(("visible <footer>", bool(footer and footer.is_visible())))

        # meaningful visible text
        body_text = (page.inner_text("body") or "").strip()
        results.append(("substantial visible text (>300 chars)", len(body_text) > 300))

        # responsive: no horizontal overflow at mobile width
        page.set_viewport_size({"width": 375, "height": 800})
        page.wait_for_timeout(200)
        overflow = page.evaluate("() => document.documentElement.scrollWidth - window.innerWidth")
        results.append(("no horizontal overflow on mobile (375px)", overflow is not None and overflow <= 4))

        # desktop layout renders tall enough (real content)
        page.set_viewport_size({"width": 1280, "height": 900})
        page.wait_for_timeout(200)
        height = page.evaluate("() => document.body.scrollHeight")
        results.append(("desktop content height > 500px", height > 500))

        # no console errors
        results.append(("no console errors", len(console_errors) == 0))

        browser.close()
    return results


def main() -> None:
    try:
        results = run_checks()
    except Exception as exc:
        print("browser check failed to run:", exc)
        print("AUTORESEARCH_SCORE: 0.0")
        return

    passed = sum(1 for _, ok in results if ok)
    total = len(results)
    for name, ok in results:
        print(("PASS" if ok else "FAIL") + " - " + name)
    print(f"checks_passed={passed}/{total}")
    print(f"AUTORESEARCH_SCORE: {passed / total:.6f}")


if __name__ == "__main__":
    main()
