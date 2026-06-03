# Research Program

Goal: improve an experiment score through repeated, measurable trials.

Operating rules:

1. Change one small thing per trial.
2. Keep every trial reproducible.
3. Prefer simple parameter changes before complex code edits.
4. Accept a trial only when the metric improves.
5. Write down what changed and why.

This clean-room implementation is intentionally generic. The loop can optimize a toy objective, a model training script, a benchmark, or any command that emits a numeric metric.

