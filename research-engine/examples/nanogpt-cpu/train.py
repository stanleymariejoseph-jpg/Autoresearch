"""Tiny char-level language model trained on CPU using the numpy autograd
engine in autograd.py. THIS is the file the autoresearch loop (or a Mistral
agent) edits to lower val_bpb.

You only write the FORWARD pass. Gradients are automatic (autograd.py handles
them), exactly like PyTorch does in karpathy/autoresearch. Never implement a
backward pass by hand; just build the model with Tensor ops and call
loss.backward().

Hyperparameters live in params.json so they can be tuned without code edits.

Output contract: the last stdout line must be `val_bpb: <float>`.
"""
from __future__ import annotations

from pathlib import Path
import json
import math
import time

import numpy as np

from autograd import Tensor, Embedding, Linear, cross_entropy, zero_grad

ROOT = Path(__file__).parent
DATA_DIR = ROOT / "data"


def load_params() -> dict:
    defaults = {
        "block_size": 16,
        "n_embed": 32,
        "batch_size": 32,
        "learning_rate": 0.5,
        "max_seconds": 8.0,
        "warmup_frac": 0.1,
        "seed": 1337,
    }
    path = ROOT / "params.json"
    if path.exists():
        try:
            defaults.update(json.loads(path.read_text(encoding="utf-8")))
        except json.JSONDecodeError:
            pass
    return defaults


# --------------------------------------------------------------------------
# MODEL — edit freely. Use only autograd Tensor ops; gradients are automatic.
# --------------------------------------------------------------------------
class Model:
    """Baseline: mean-pooled token embeddings -> linear head.

    This ignores word order, so there is clear headroom. Good next steps:
    add positional embeddings, then a self-attention head, then an MLP block
    with LayerNorm (all importable from autograd.py).
    """

    def __init__(self, vocab_size: int, params: dict, rng: np.random.Generator) -> None:
        c = int(params["n_embed"])
        self.tok = Embedding(vocab_size, c, rng)
        self.head = Linear(c, vocab_size, rng)

    def forward(self, x: np.ndarray) -> Tensor:
        # x: (B, T) int context. Predict the next token from the context.
        emb = self.tok(x)                 # (B, T, C)
        h = emb.mean(axis=1)              # (B, C)  -- order-agnostic for now
        logits = self.head(h)            # (B, vocab)
        return logits

    def parameters(self) -> list[Tensor]:
        return self.tok.parameters() + self.head.parameters()


# --------------------------------------------------------------------------
# Training / evaluation harness (you may tune, but keep the output contract).
# --------------------------------------------------------------------------
def get_batch(data: np.ndarray, block_size: int, batch_size: int, rng: np.random.Generator):
    ix = rng.integers(0, len(data) - block_size - 1, size=batch_size)
    x = np.stack([data[i : i + block_size] for i in ix])
    y = np.array([data[i + block_size] for i in ix])
    return x, y


def evaluate(model: Model, data: np.ndarray, block_size: int) -> float:
    """Deterministic full-coverage validation pass (low variance)."""
    total_nll = 0.0
    count = 0
    chunk = 256
    starts = np.arange(0, len(data) - block_size - 1)
    for s in range(0, len(starts), chunk):
        ix = starts[s : s + chunk]
        x = np.stack([data[i : i + block_size] for i in ix])
        y = np.array([data[i + block_size] for i in ix])
        logits = model.forward(x).data        # (N, V)
        m = logits.max(axis=-1, keepdims=True)
        log_sum = np.log(np.exp(logits - m).sum(axis=-1, keepdims=True)) + m
        nll = -(logits[np.arange(len(y)), y] - log_sum[:, 0])
        total_nll += float(nll.sum())
        count += len(y)
    mean_nll = total_nll / max(count, 1)
    return mean_nll / math.log(2)  # bits per byte (char-level approximation)


def main() -> None:
    params = load_params()
    rng = np.random.default_rng(int(params["seed"]))

    train_ids = np.array(json.loads((DATA_DIR / "train.json").read_text(encoding="utf-8")), dtype=np.int64)
    val_ids = np.array(json.loads((DATA_DIR / "val.json").read_text(encoding="utf-8")), dtype=np.int64)
    vocab = json.loads((DATA_DIR / "vocab.json").read_text(encoding="utf-8"))["chars"]

    block_size = int(params["block_size"])
    batch_size = int(params["batch_size"])
    base_lr = float(params["learning_rate"])
    warmup_frac = float(params.get("warmup_frac", 0.0))

    model = Model(vocab_size=len(vocab), params=params, rng=rng)
    p = model.parameters()

    deadline = time.perf_counter() + float(params["max_seconds"])
    step = 0
    # Rough step budget for the LR schedule (estimated, refined as we go).
    est_total = 2000
    while time.perf_counter() < deadline:
        x, y = get_batch(train_ids, block_size, batch_size, rng)
        logits = model.forward(x)
        loss = cross_entropy(logits, y)
        zero_grad(p)
        loss.backward()

        # Linear warmup then constant.
        if warmup_frac > 0.0 and step < warmup_frac * est_total:
            lr = base_lr * (step + 1) / max(1.0, warmup_frac * est_total)
        else:
            lr = base_lr
        for t in p:
            t.data -= lr * t.grad

        step += 1
        if step % 200 == 0:
            print(f"step={step} train_loss={float(loss.data):.4f}")

    val_bpb = evaluate(model, val_ids, block_size)
    print(f"steps_completed={step}")
    print(f"val_bpb: {val_bpb:.6f}")


if __name__ == "__main__":
    main()
