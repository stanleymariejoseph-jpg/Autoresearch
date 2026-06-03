"""Gradient-check the numpy autograd engine used by the nanogpt-cpu example.

If numpy is unavailable the test is skipped (the engine is example-only).
"""
from __future__ import annotations

from pathlib import Path
import importlib.util
import unittest

ROOT = Path(__file__).resolve().parents[1]
AUTOGRAD = ROOT / "examples" / "nanogpt-cpu" / "autograd.py"

try:
    import numpy as np  # noqa: F401

    HAVE_NUMPY = True
except Exception:  # pragma: no cover
    HAVE_NUMPY = False


def _load_autograd():
    spec = importlib.util.spec_from_file_location("nanogpt_autograd", AUTOGRAD)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@unittest.skipUnless(HAVE_NUMPY, "numpy not installed")
class AutogradTests(unittest.TestCase):
    def test_gradient_check_against_finite_differences(self) -> None:
        import numpy as np

        ag = _load_autograd()
        rng = np.random.default_rng(0)

        emb = ag.Embedding(10, 8, rng)
        l1 = ag.Linear(8, 8, rng)
        ln = ag.LayerNorm(8)
        l2 = ag.Linear(8, 10, rng)
        params = (
            emb.parameters() + l1.parameters() + ln.parameters() + l2.parameters()
        )

        x = rng.integers(0, 10, size=(4, 5))
        y = rng.integers(0, 10, size=(4,))

        def loss_fn():
            h = emb(x).mean(axis=1)
            h = l1(h)
            h = ln(h)
            h = h.relu()
            logits = l2(h)
            return ag.cross_entropy(logits, y)

        ag.zero_grad(params)
        loss = loss_fn()
        loss.backward()

        target = l1.weight
        analytic = target.grad.copy()

        eps = 1e-5
        numeric = np.zeros_like(target.data)
        for idx in np.ndindex(*target.data.shape):
            orig = target.data[idx]
            target.data[idx] = orig + eps
            lp = loss_fn().data
            target.data[idx] = orig - eps
            lm = loss_fn().data
            target.data[idx] = orig
            numeric[idx] = (lp - lm) / (2 * eps)

        max_err = float(np.abs(analytic - numeric).max())
        self.assertLess(max_err, 1e-4, f"gradient mismatch {max_err}")


if __name__ == "__main__":
    unittest.main()
