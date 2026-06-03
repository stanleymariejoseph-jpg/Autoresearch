"""A real nanoGPT-style Transformer in PyTorch, trained on CPU.

This is the file the autoresearch loop (or a Mistral agent) edits to lower
val_bpb. It mirrors karpathy/autoresearch's train.py: a full GPT (multi-head
causal self-attention, MLP, LayerNorm, residuals) with AdamW. PyTorch's
autograd computes gradients, so you only describe the forward pass + config.

No GPU required. Everything runs on CPU; it is just smaller and slower than
the official H100 setup. Hyperparameters live in params.json.

Output contract: the last stdout line must be `val_bpb: <float>`.
"""
from __future__ import annotations

from pathlib import Path
import json
import math
import time

import numpy as np
import torch
import torch.nn as nn
from torch.nn import functional as F

ROOT = Path(__file__).parent
DATA_DIR = ROOT / "data"
torch.manual_seed(1337)


def load_params() -> dict:
    defaults = {
        "block_size": 64,
        "n_embed": 64,
        "n_head": 4,
        "n_layer": 2,
        "dropout": 0.0,
        "batch_size": 32,
        "learning_rate": 3e-3,
        "weight_decay": 0.1,
        "max_seconds": 25.0,
        "warmup_steps": 50,
        "eval_iters": 50,
    }
    path = ROOT / "params.json"
    if path.exists():
        try:
            defaults.update(json.loads(path.read_text(encoding="utf-8")))
        except json.JSONDecodeError:
            pass
    return defaults


# --------------------------------------------------------------------------
# MODEL — edit freely. PyTorch autograd handles gradients; never write a
# backward pass by hand. Keep the GPT(...) constructor signature usable by
# main(), and keep forward returning (logits, loss).
# --------------------------------------------------------------------------
class CausalSelfAttention(nn.Module):
    def __init__(self, n_embed: int, n_head: int, block_size: int, dropout: float) -> None:
        super().__init__()
        assert n_embed % n_head == 0
        self.n_head = n_head
        self.attn = nn.Linear(n_embed, 3 * n_embed)
        self.proj = nn.Linear(n_embed, n_embed)
        self.drop = nn.Dropout(dropout)
        self.register_buffer(
            "mask", torch.tril(torch.ones(block_size, block_size)).view(1, 1, block_size, block_size)
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        B, T, C = x.shape
        q, k, v = self.attn(x).split(C, dim=2)
        hs = C // self.n_head
        q = q.view(B, T, self.n_head, hs).transpose(1, 2)
        k = k.view(B, T, self.n_head, hs).transpose(1, 2)
        v = v.view(B, T, self.n_head, hs).transpose(1, 2)
        att = (q @ k.transpose(-2, -1)) * (1.0 / math.sqrt(hs))
        att = att.masked_fill(self.mask[:, :, :T, :T] == 0, float("-inf"))
        att = F.softmax(att, dim=-1)
        y = att @ v
        y = y.transpose(1, 2).contiguous().view(B, T, C)
        return self.drop(self.proj(y))


class Block(nn.Module):
    def __init__(self, n_embed: int, n_head: int, block_size: int, dropout: float) -> None:
        super().__init__()
        self.ln1 = nn.LayerNorm(n_embed)
        self.attn = CausalSelfAttention(n_embed, n_head, block_size, dropout)
        self.ln2 = nn.LayerNorm(n_embed)
        self.mlp = nn.Sequential(
            nn.Linear(n_embed, 4 * n_embed),
            nn.GELU(),
            nn.Linear(4 * n_embed, n_embed),
            nn.Dropout(dropout),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = x + self.attn(self.ln1(x))
        x = x + self.mlp(self.ln2(x))
        return x


class GPT(nn.Module):
    def __init__(self, vocab_size: int, params: dict) -> None:
        super().__init__()
        c = int(params["n_embed"])
        bs = int(params["block_size"])
        self.block_size = bs
        self.tok_emb = nn.Embedding(vocab_size, c)
        self.pos_emb = nn.Embedding(bs, c)
        self.drop = nn.Dropout(float(params["dropout"]))
        self.blocks = nn.ModuleList(
            [Block(c, int(params["n_head"]), bs, float(params["dropout"])) for _ in range(int(params["n_layer"]))]
        )
        self.ln_f = nn.LayerNorm(c)
        self.head = nn.Linear(c, vocab_size, bias=False)
        self.tok_emb.weight = self.head.weight  # weight tying

    def forward(self, idx: torch.Tensor, targets: torch.Tensor | None = None):
        B, T = idx.shape
        pos = torch.arange(T, device=idx.device)
        x = self.drop(self.tok_emb(idx) + self.pos_emb(pos))
        for block in self.blocks:
            x = block(x)
        x = self.ln_f(x)
        logits = self.head(x)
        loss = None
        if targets is not None:
            loss = F.cross_entropy(logits.view(-1, logits.size(-1)), targets.view(-1))
        return logits, loss


# --------------------------------------------------------------------------
# Harness — tune if you like, but keep the val_bpb output contract.
# --------------------------------------------------------------------------
def get_batch(data: np.ndarray, block_size: int, batch_size: int):
    ix = torch.randint(0, len(data) - block_size - 1, (batch_size,))
    x = torch.stack([torch.from_numpy(data[i : i + block_size].astype(np.int64)) for i in ix])
    y = torch.stack([torch.from_numpy(data[i + 1 : i + 1 + block_size].astype(np.int64)) for i in ix])
    return x, y


@torch.no_grad()
def estimate_bpb(model: GPT, data: np.ndarray, block_size: int, batch_size: int, iters: int) -> float:
    model.eval()
    losses = []
    for _ in range(iters):
        x, y = get_batch(data, block_size, batch_size)
        _, loss = model(x, y)
        losses.append(loss.item())
    model.train()
    return float(np.mean(losses)) / math.log(2)


def main() -> None:
    params = load_params()
    torch.manual_seed(int(params.get("seed", 1337)))

    train_ids = np.fromfile(DATA_DIR / "train.bin", dtype=np.uint16)
    val_ids = np.fromfile(DATA_DIR / "val.bin", dtype=np.uint16)
    meta = json.loads((DATA_DIR / "meta.json").read_text(encoding="utf-8"))

    model = GPT(meta["vocab_size"], params)
    n_params = sum(p.numel() for p in model.parameters())
    print(f"model_params={n_params}")

    opt = torch.optim.AdamW(
        model.parameters(),
        lr=float(params["learning_rate"]),
        weight_decay=float(params["weight_decay"]),
    )
    warmup = int(params["warmup_steps"])
    base_lr = float(params["learning_rate"])

    block_size = int(params["block_size"])
    batch_size = int(params["batch_size"])
    deadline = time.perf_counter() + float(params["max_seconds"])
    step = 0
    while time.perf_counter() < deadline:
        lr = base_lr * min(1.0, (step + 1) / max(1, warmup))
        for g in opt.param_groups:
            g["lr"] = lr
        x, y = get_batch(train_ids, block_size, batch_size)
        _, loss = model(x, y)
        opt.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step()
        step += 1
        if step % 50 == 0:
            print(f"step={step} train_loss={loss.item():.4f} lr={lr:.5f}")

    val_bpb = estimate_bpb(model, val_ids, block_size, batch_size, int(params["eval_iters"]))
    print(f"steps_completed={step}")
    print(f"val_bpb: {val_bpb:.6f}")


if __name__ == "__main__":
    main()
