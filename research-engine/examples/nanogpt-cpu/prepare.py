"""Prepare a tiny char-level dataset for the nanogpt-cpu objective.

This script is unmodifiable on purpose. It mirrors the role of prepare.py in
karpathy/autoresearch: build the data once, then leave it alone.
"""
from __future__ import annotations

from pathlib import Path
import json
import urllib.request

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
) * 200


def fetch_text() -> str:
    try:
        with urllib.request.urlopen(SOURCE_URL, timeout=8) as response:
            raw = response.read().decode("utf-8")
        if len(raw) > 1000:
            return raw
    except Exception:
        pass
    return FALLBACK_TEXT


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    text = fetch_text()

    # Keep the corpus small so CPU training stays fast.
    text = text[:200_000]

    vocab = sorted(set(text))
    stoi = {ch: i for i, ch in enumerate(vocab)}
    ids = [stoi[ch] for ch in text]

    split = int(len(ids) * 0.9)
    train_ids = ids[:split]
    val_ids = ids[split:]

    (DATA_DIR / "vocab.json").write_text(
        json.dumps({"chars": vocab}, ensure_ascii=False),
        encoding="utf-8",
    )
    (DATA_DIR / "train.json").write_text(json.dumps(train_ids), encoding="utf-8")
    (DATA_DIR / "val.json").write_text(json.dumps(val_ids), encoding="utf-8")

    print(f"vocab_size={len(vocab)} train_tokens={len(train_ids)} val_tokens={len(val_ids)}")


if __name__ == "__main__":
    main()
