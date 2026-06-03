# nanogpt-torch objective

You are improving a real nanoGPT-style Transformer (PyTorch) trained on CPU.
Lower `val_bpb` is better (bits per byte on a held-out validation split).

This mirrors karpathy/autoresearch: PyTorch autograd computes gradients, so
you only write the FORWARD pass and the config. Never write a backward pass.

## What you may edit

- `train.py` — the model (`GPT`, `Block`, `CausalSelfAttention`, `MLP`) and
  the training loop. Keep `GPT(vocab_size, params)` constructible and keep
  `forward(idx, targets)` returning `(logits, loss)`.
- `params.json` — hyperparameters.

## What you must NOT touch

- `prepare.py` and `data/` — fixed dataset.
- The `estimate_bpb` evaluation and the final `val_bpb:` print line.
- `max_seconds` must stay strictly below the loop's `seconds_per_trial`.
- No new pip dependencies beyond torch + numpy + stdlib.

## Ideas worth trying (one focused change per trial)

- Tune `learning_rate`, `warmup_steps`, `weight_decay`, `dropout`.
- Scale `n_layer`, `n_head`, `n_embed`, `block_size` (mind the CPU time budget).
- Better init (scaled residual projections, e.g. divide by sqrt(2*n_layer)).
- Add a cosine learning-rate decay after warmup.
- Try RMSNorm instead of LayerNorm, or SwiGLU in the MLP.
- Untie/retie embeddings, add/remove the final LayerNorm.
- Use `F.scaled_dot_product_attention` for a faster, cleaner attention.

Keep each trial small and verifiable. A smaller accepted change beats a big
rejected one. Watch the CPU time budget: if a config can't finish enough
steps within `max_seconds`, val_bpb will be poor.

## Output contract

The last line of stdout must match `val_bpb: <float>`.
