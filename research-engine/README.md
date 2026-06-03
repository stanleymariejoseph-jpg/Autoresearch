# Autoresearch Lab

Clean-room autonomous research loop inspired by the general idea of iterative experiments.

This code does not copy `karpathy/autoresearch`. It is a fresh implementation with a different structure and a generic experiment runner.

## What It Does

- Creates an isolated trial workspace
- Mutates a small parameter file or runs an optional external agent command
- Executes a user-defined experiment command
- Parses a metric from stdout or a metric file
- Keeps the best trial and logs every attempt
- Stops on iteration count or time budget

Lower scores are better by default.

## Quick Start

```powershell
cd research-engine
python -m autoresearch_lab --config examples/demo-config.json
```

The demo runs `examples/objective.py`, which prints a synthetic score.

## Files

- `autoresearch_lab/cli.py` - command-line entrypoint
- `autoresearch_lab/config.py` - JSON configuration parsing
- `autoresearch_lab/loop.py` - research loop
- `autoresearch_lab/proposer.py` - clean parameter mutation engine
- `autoresearch_lab/runner.py` - subprocess execution and metric parsing
- `examples/demo-config.json` - demo configuration
- `examples/objective.py` - toy objective function

## Using Your Own Experiment

Create a JSON config like:

```json
{
  "name": "my-study",
  "workspace": "my-target",
  "command": "python train.py --config params.json",
  "metric_regex": "val_loss\\s*=\\s*([0-9.]+)",
  "parameter_file": "params.json",
  "iterations": 20,
  "seconds_per_trial": 300,
  "maximize": false
}
```

Your command must either print the metric to stdout or write a JSON file if `metric_file` is configured.

