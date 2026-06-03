# web-ui-build objective

Build a complete, modern, responsive landing page in `index.html`. The page
is opened in a **real Chromium browser** by `check.py` (via Playwright) and
tested functionally. The score is the fraction of functional checks that
pass; **higher is better**. Reach 1.0 = all checks pass.

Use the **ui-ux-pro-max**, **frontend-design**, and **webapp-testing** skills
(provided in your context) for layout, hierarchy, palette, and to understand
how the page will be tested.

## What you may edit

- `index.html` only (single self-contained file with inline `<style>` is fine).

## What you must NOT touch

- `check.py` — the browser evaluator.

## What the browser checks (functional, not cosmetic)

- A visible, non-empty `<h1>`.
- A `<nav>`/header with at least 2 links.
- A visible call-to-action (`<button>`, `.btn`, `.cta`, or `[role=button]`)
  that can be clicked without throwing.
- At least 3 `<section>` blocks and a visible `<footer>`.
- Substantial visible text (more than ~300 characters).
- Responsive: no horizontal scroll at 375px width.
- Real content height on desktop.
- **No console errors** when the page loads.

## Guidance

Write clean, valid HTML/CSS. Keep JavaScript minimal and error-free (console
errors cost a point). Make one focused improvement per trial; the best score
is always kept.
