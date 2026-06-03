# nanogpt-cpu objective

You are optimizing a tiny char-level language model that trains on CPU.
Lower `val_bpb` is better (bits per byte on a held-out validation split).

The model uses a small numpy autograd engine (`autograd.py`). **You only write
the forward pass.** Gradients are automatic, exactly like PyTorch in the
official karpathy/autoresearch. NEVER implement a backward pass by hand and
NEVER use raw numpy math on parameters in the model — always go through
`Tensor` ops so autograd can track them.

## What you may edit

- `train.py` — primarily the `Model` class (its `__init__`, `forward`,
  `parameters`). You may also tune the training loop.
- `params.json` — hyperparameters (block_size, n_embed, batch_size,
  learning_rate, max_seconds, warmup_frac, seed).

## What you must NOT touch

- `autograd.py` — the differentiation engine. It is not in your file list.
- `prepare.py` and `data/` — fixed dataset.
- The evaluation function `evaluate()` and the final `val_bpb:` print line.
- `max_seconds` must stay strictly below the loop's `seconds_per_trial`.
- No imports beyond numpy, stdlib, and `autograd`.

## Tools available from autograd.py

`Tensor` supports: `+ - * / @`, `sum`, `mean`, `relu`, `gelu`, `tanh`, `exp`,
`log`, `sqrt`, `transpose`, `reshape`, `softmax`, `**`, and indexing/slicing
via `t[...]` (e.g. `t[:, -1, :]` to read the last position, or `t[:, :T]`).
Ready-made modules:
`Embedding(num, dim, rng)`, `Linear(fan_in, fan_out, rng, bias=True)`,
`LayerNorm(dim)`, plus `cross_entropy(logits, targets)` and `zero_grad(params)`.

## Why the baseline is weak (read this first)

The baseline does `emb.mean(axis=1)` over the context. Mean-pooling DESTROYS
word order: `mean(tok + pos) = mean(tok) + mean(pos)`, and `mean(pos)` is the
same constant for every example, so **adding positional embeddings while you
still mean-pool gives ZERO improvement.** Do not waste trials on that.

The single biggest win is to STOP mean-pooling and instead read the
representation at the LAST position of the context (a proper next-token
predictor). Only after that do positional embeddings and attention help.

## Change protocol (MANDATORY)

Make ONE focused change per trial and climb this ladder, only advancing once
the current rung is accepted (val_bpb improved):

1. Replace mean-pooling with last-position prediction. Instead of
   `h = emb.mean(axis=1)`, read the last time step: `h = emb[:, -1, :]`
   (slicing a `Tensor` is supported and differentiable). This alone is a real
   next-char model and should beat the mean baseline clearly.
2. Add positional embeddings now that order is preserved:
   `pos = Embedding(block_size, n_embed)` indexed by `np.arange(T)`, added to
   the token embeddings BEFORE selecting the last position.
3. Add a single self-attention head: q,k,v via `Linear`, scores
   `(q @ k.transpose(-1,-2)) * (1/sqrt(C))`, `.softmax(-1)`, then `@ v`,
   wrapped in a residual + `LayerNorm`, then read the last position.
4. Add a small MLP block (Linear -> gelu -> Linear) with residual + LayerNorm.
5. Tune hyperparameters in `params.json` (learning_rate, n_embed, batch_size,
   block_size, warmup_frac) to squeeze the chosen architecture.

A reference attention model reaches ~3.5 val_bpb vs ~4.56 for the baseline,
so there is plenty of headroom. Prefer a smaller accepted change over a big
rejected one.

## Output contract

The last line of stdout must match `val_bpb: <float>`.
