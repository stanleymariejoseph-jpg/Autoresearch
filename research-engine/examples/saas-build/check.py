"""Acceptance-test scorer for the saas-build objective.

THIS FILE IS THE EVALUATOR. It is intentionally NOT in the agent's editable
file list — the agent must make `app.py` pass these checks, not edit the
checks. Score = fraction of acceptance checks that pass (higher is better).

It imports app.py from the same directory and exercises a real SaaS backend
contract: authentication, persistence, business logic, per-user isolation,
and billing gating.
"""
from __future__ import annotations

import importlib
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))


def load_app():
    if "app" in sys.modules:
        del sys.modules["app"]
    return importlib.import_module("app")


CHECKS = []


def check(name):
    def deco(fn):
        CHECKS.append((name, fn))
        return fn
    return deco


# -- authentication ---------------------------------------------------------
@check("register returns the new user")
def _(app):
    app.reset()
    u = app.register("a@x.com", "pw123")
    assert isinstance(u, dict) and u.get("email") == "a@x.com"


@check("duplicate email is rejected")
def _(app):
    app.reset()
    app.register("a@x.com", "pw123")
    try:
        app.register("a@x.com", "other")
        return False
    except Exception:
        return True


@check("login with good credentials returns a token")
def _(app):
    app.reset()
    app.register("a@x.com", "pw123")
    token = app.login("a@x.com", "pw123")
    assert isinstance(token, str) and len(token) > 0


@check("login with wrong password is refused")
def _(app):
    app.reset()
    app.register("a@x.com", "pw123")
    assert not app.login("a@x.com", "WRONG")


@check("whoami resolves a valid token to its email")
def _(app):
    app.reset()
    app.register("a@x.com", "pw123")
    token = app.login("a@x.com", "pw123")
    assert app.whoami(token) == "a@x.com"


@check("whoami rejects an invalid token")
def _(app):
    app.reset()
    assert not app.whoami("not-a-real-token")


# -- persistence / business logic ------------------------------------------
@check("create_item requires authentication")
def _(app):
    app.reset()
    try:
        app.create_item("bad-token", "task 1")
        return False
    except Exception:
        return True


@check("created items are listed back")
def _(app):
    app.reset()
    app.register("a@x.com", "pw123")
    t = app.login("a@x.com", "pw123")
    app.create_item(t, "task 1")
    app.create_item(t, "task 2")
    titles = [i["title"] for i in app.list_items(t)]
    assert "task 1" in titles and "task 2" in titles


@check("items are isolated per user")
def _(app):
    app.reset()
    app.register("a@x.com", "pw1")
    app.register("b@x.com", "pw2")
    ta = app.login("a@x.com", "pw1")
    tb = app.login("b@x.com", "pw2")
    app.create_item(ta, "secret of A")
    assert all(i["title"] != "secret of A" for i in app.list_items(tb))


# -- billing ----------------------------------------------------------------
@check("new users are not premium")
def _(app):
    app.reset()
    app.register("a@x.com", "pw123")
    t = app.login("a@x.com", "pw123")
    assert app.is_premium(t) is False


@check("subscribing grants premium")
def _(app):
    app.reset()
    app.register("a@x.com", "pw123")
    t = app.login("a@x.com", "pw123")
    app.subscribe(t, "pro")
    assert app.is_premium(t) is True


@check("premium_report is blocked for free users")
def _(app):
    app.reset()
    app.register("a@x.com", "pw123")
    t = app.login("a@x.com", "pw123")
    try:
        app.premium_report(t)
        return False
    except Exception:
        return True


@check("premium_report works once subscribed")
def _(app):
    app.reset()
    app.register("a@x.com", "pw123")
    t = app.login("a@x.com", "pw123")
    app.subscribe(t, "pro")
    out = app.premium_report(t)
    assert isinstance(out, str) and len(out) > 0


def main() -> None:
    passed = 0
    details = []
    try:
        app = load_app()
    except Exception as exc:
        print("import error:", exc)
        print(f"AUTORESEARCH_SCORE: 0.0")
        return

    for name, fn in CHECKS:
        try:
            result = fn(app)
            ok = result is not False
        except Exception:
            ok = False
        passed += 1 if ok else 0
        details.append(("PASS" if ok else "FAIL") + " - " + name)

    total = len(CHECKS)
    score = passed / total if total else 0.0
    for line in details:
        print(line)
    print(f"checks_passed={passed}/{total}")
    print(f"AUTORESEARCH_SCORE: {score:.6f}")


if __name__ == "__main__":
    main()
