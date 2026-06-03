# saas-build objective

Build a working SaaS backend in `app.py`. You are scored by `check.py`, which
runs acceptance tests and reports `AUTORESEARCH_SCORE` = the fraction of
checks that pass (0.0 to 1.0). **Higher is better.** Reach 1.0 = all checks pass.

This proves autoresearch can build real software bricks — authentication,
persistence, business logic, per-user isolation, and billing — because each
brick is expressed as an automatic test.

## What you may edit

- `app.py` only.

## What you must NOT touch

- `check.py` — the evaluator. You cannot edit it; you must satisfy it.
- Do not import anything outside the Python standard library.

## Contract to implement in app.py (keep these exact names/signatures)

- `reset() -> None` — clear all in-memory state (the tests call it for isolation).
- `register(email, password) -> dict` — create account, return `{"email": email}`.
  Raise an exception if the email already exists.
- `login(email, password) -> str | None` — return a non-empty session token
  for correct credentials, otherwise a falsy value (None/"" /False).
- `whoami(token) -> str | None` — return the email for a valid token, else falsy.
- `create_item(token, title) -> dict` — create an item owned by the
  authenticated user. Raise if the token is invalid.
- `list_items(token) -> list` — return that user's items only (list of dicts,
  each with a `"title"` key). Items must be isolated per user.
- `subscribe(token, plan) -> None` — mark the user as premium.
- `is_premium(token) -> bool` — True only after `subscribe`, False for new users.
- `premium_report(token) -> str` — return a non-empty report string; raise if
  the user is not premium.

## Hints

- In-memory dicts are enough for storage (no real database needed).
- Generate tokens with `secrets.token_hex` or `uuid4`.
- Hash passwords if you like (`hashlib`), but it is not required to pass checks.
- Make one focused improvement per trial; a higher score is always kept.

## Output contract

`check.py` prints the score. You only edit `app.py`.
