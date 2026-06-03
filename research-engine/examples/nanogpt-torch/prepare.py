"""Prepare a char-level dataset for the nanogpt-torch objective.

Same role as karpathy/autoresearch's prepare.py: build the data once and
leave it alone. Char-level keeps it dependency-free (no tokenizer download).
"""
from __future__ import annotations

from pathlib import Path
import json
import urllib.request

import numpy as np

DATA_DIR = Path(__file__).parent / "data"
SOURCE_URL = "https://raw.githubusercontent.com/karpathy/char-rnn/master/data/tinyshakespeare/input.txt"

FALLBACK_TEXT = (
    "To be, or not to be, that is the question:\n"
    "Whether 'tis nobler in the mind to suffer\n"
    "The slings and arrows of outrageous fortune,\n"
    "Or to take arms against a sea of troubles\n"
    "And by opposing end them. To die-to sleep,\n"
    "No more; and by a sleep to say we end\n"
    "The heart-ache and the thousand natural shocks\n"
    "That flesh is heir to: 'tis a consummation\n"
    "Devoutly to be wish'd. To die, to sleep;\n"
    "To sleep, perchance to dream-ay, there's the rub:\n"
) * 400


def fetch_text() -> str:
    try:
        with urllib.request.urlopen(SOURCE_URL, timeout=10) as response:
            raw = response.read().decode("utf-8")
        if len(raw) > 1000:
            return raw
    except Exception:
        pass
    return FALLBACK_TEXT


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    text = fetch_text()

    vocab = sorted(set(text))
    stoi = {ch: i for i, ch in enumerate(vocab)}
    ids = np.array([stoi[ch] for ch in text], dtype=np.uint16)

    split = int(len(ids) * 0.9)
    ids[:split].tofile(DATA_DIR / "train.bin")
    ids[split:].tofile(DATA_DIR / "val.bin")
    (DATA_DIR / "meta.json").write_text(
        json.dumps({"vocab_size": len(vocab), "chars": vocab}, ensure_ascii=False),
        encoding="utf-8",
    )

    print(f"vocab_size={len(vocab)} train_tokens={split} val_tokens={len(ids) - split}")


if __name__ == "__main__":
    main()
