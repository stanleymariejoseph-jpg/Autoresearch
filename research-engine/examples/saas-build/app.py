"""SaaS backend — TO BE BUILT by the autoresearch loop / Mistral agent.

This is the editable file. The scorer (check.py) calls the functions below
and counts how many acceptance checks pass. Right now everything is a stub,
so the score starts near zero. Implement the contract described in spec.md to
raise the score toward 1.0 (100% of checks passing).

You may use only the Python standard library. Keep all the function names and
signatures below — check.py depends on them.
"""
from __future__ import annotations


def reset() -> None:
    """Clear all in-memory state (used between checks for isolation)."""
    raise NotImplementedError


def register(email: str, password: str) -> dict:
    """Create a new account. Reject duplicate emails. Return {'email': ...}."""
    raise NotImplementedError


def login(email: str, password: str) -> str | None:
    """Return a session token for valid credentials, else a falsy value."""
    raise NotImplementedError


def whoami(token: str) -> str | None:
    """Return the email for a valid token, else a falsy value."""
    raise NotImplementedError


def create_item(token: str, title: str) -> dict:
    """Create an item owned by the authenticated user. Raise if token invalid."""
    raise NotImplementedError


def list_items(token: str) -> list:
    """Return the authenticated user's items (list of dicts with 'title')."""
    raise NotImplementedError


def subscribe(token: str, plan: str) -> None:
    """Mark the authenticated user as a premium subscriber."""
    raise NotImplementedError


def is_premium(token: str) -> bool:
    """Return True if the authenticated user has an active subscription."""
    raise NotImplementedError


def premium_report(token: str) -> str:
    """Return a premium-only report. Raise if the user is not premium."""
    raise NotImplementedError
