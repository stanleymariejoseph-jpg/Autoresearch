from __future__ import annotations

from pathlib import Path
import argparse
import json
import math


def score(params: dict[str, float]) -> float:
    learning_rate = float(params.get("learning_rate", 0.01))
    depth = float(params.get("depth", 3))
    regularization = float(params.get("regularization", 0.1))

    return (
        abs(math.log10(learning_rate) + 2.2)
        + abs(depth - 5) * 0.08
        + abs(regularization - 0.03) * 1.7
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--params", required=True)
    args = parser.parse_args()

    params = json.loads(Path(args.params).read_text(encoding="utf-8"))
    print(f"metric: {score(params):.6f}")


if __name__ == "__main__":
    main()

