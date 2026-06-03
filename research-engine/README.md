# Autoresearch Lab

Clean-room autonomous research loop inspired by the general idea of iterative experiments.

This code does not copy `karpathy/autoresearch`. It is a fresh implementation with a different structure and a generic experiment runner.

See `CLEANROOM.md` for the clean-room note.

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
python -m autoresearch_lab run --config examples/demo-config.json
```

The demo runs `examples/demo-workspace/objective.py`, which prints a synthetic score.

## nanoGPT CPU example (karpathy-style)

A real autonomous-research target inspired by `karpathy/autoresearch`, adapted
to run on CPU with numpy only. The loop trains a tiny char-level language
model on a TinyShakespeare snippet and minimizes `val_bpb`.

```powershell
cd research-engine
pip install numpy
python examples/nanogpt-cpu/prepare.py
python -m autoresearch_lab run --config examples/nanogpt-cpu-config.json
```

Like the official project (which relies on PyTorch autograd), the agent only
writes the **forward pass**: `examples/nanogpt-cpu/autograd.py` is a small
reverse-mode autograd engine that computes gradients automatically, so the
agent never has to hand-write a backward pass. The editable file is
`examples/nanogpt-cpu/train.py` (the `Model` class) plus `params.json`.

The baseline (order-agnostic mean pooling) scores ~4.56 val_bpb; an
attention model reachable by editing only the forward pass scores ~3.5, so
there is real headroom for the agent to discover.

### Run it with the Mistral agent

```powershell
$env:MISTRAL_API_KEY = "your-key"
python -m autoresearch_lab run --config examples/nanogpt-cpu-mistral-config.json
```

Uses `mistral-large-latest`. The agent receives `train.py`, `params.json`,
and the objective (`program.md`), and returns full replacement files. It is
sandboxed: it cannot edit `autograd.py`, `prepare.py`, or the evaluator, and
the previous trial's failure (if any) is fed back into the next prompt.

## nanoGPT with REAL PyTorch (still CPU, no GPU)

The closest thing to the official karpathy/autoresearch: a real GPT
(multi-head causal self-attention, MLP blocks, LayerNorm, residuals, AdamW,
weight tying) written in PyTorch. No GPU required — it runs on CPU, just at a
smaller scale. PyTorch autograd handles gradients, so the agent only edits
the forward pass and hyperparameters.

```powershell
cd research-engine
pip install torch --index-url https://download.pytorch.org/whl/cpu
python examples/nanogpt-torch/prepare.py
# without an agent (random hyperparameter search):
python -m autoresearch_lab run --config examples/nanogpt-torch-config.json
# with the Mistral agent editing the model:
$env:MISTRAL_API_KEY = "your-key"
python -m autoresearch_lab run --config examples/nanogpt-torch-mistral-config.json
```

Editable file: `examples/nanogpt-torch/train.py` (the `GPT` model + loop) plus
`params.json`. This is the same architecture family as the official project;
the only remaining gap is hardware scale (GPU + larger data + longer budget).

## Files

- `autoresearch_lab/cli.py` - command-line entrypoint
- `autoresearch_lab/config.py` - JSON configuration parsing
- `autoresearch_lab/loop.py` - research loop
- `autoresearch_lab/proposer.py` - clean parameter mutation engine
- `autoresearch_lab/runner.py` - subprocess execution and metric parsing
- `autoresearch_lab/report.py` - Markdown and HTML report writer
- `examples/demo-config.json` - demo configuration
- `examples/demo-workspace/objective.py` - toy objective function

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
  "maximize": false,
  "patience": 8,
  "baseline_first": true,
  "report": true
}
```

Your command must either print the metric to stdout or write a JSON file if `metric_file` is configured.

## Commands

```powershell
python -m autoresearch_lab validate --config examples/demo-config.json
python -m autoresearch_lab run --config examples/demo-config.json
python -m autoresearch_lab status --config examples/demo-config.json
python -m autoresearch_lab report --config examples/demo-config.json
python -m autoresearch_lab ui --config examples/demo-config.json
```

## Build A Windows EXE

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build_exe.ps1
```

The executable is created locally at:

```text
dist-exe/autoresearch.exe
```

Example:

```powershell
.\dist-exe\autoresearch.exe bootstrap-project --name studio-ia-next --output-dir generated-projects
.\dist-exe\autoresearch.exe validate --config examples\demo-config.json
.\dist-exe\autoresearch.exe ui --config examples\demo-config.json
```

`dist-exe/` is ignored by Git so the generated executable is not pushed to GitHub.

## Create A New Studio IA Project

```powershell
python -m autoresearch_lab bootstrap-project --name studio-ia-next --output-dir generated-projects
```

This creates:

- a React/Vite/TypeScript starter
- Studio IA dashboard, canvas, knowledge graph, and owner console files
- `scripts/score_project.py`
- `autoresearch.config.json` configured for Mistral

Then run:

```powershell
cd generated-projects/studio-ia-next
$env:MISTRAL_API_KEY = "your-key"
python -m autoresearch_lab run --config autoresearch.config.json
```

## Outputs

Each run writes:

- `ledger.jsonl` - every trial
- `state.json` - resume state
- `best/` - best accepted workspace
- `trials/trial-0001/` etc. - isolated trial workspaces
- `report.md` and `report.html` - readable summaries

## Skills (Claude-style skill packs)

The Mistral agent can use packaged skills (a `SKILL.md` of instructions plus
optional helper scripts). Install third-party skills locally (not committed —
they are external projects with their own licenses):

```powershell
python scripts/install_skills.py
```

This downloads into `skills/`:
- the official `anthropics/skills` (docx, pdf, pptx, xlsx, frontend-design, …)
- `ui-ux-pro-max` design intelligence
- `playwright-skill` browser testing

Then reference skills from any config:

```json
{
  "skills": ["ui-ux-pro-max", "frontend-design"],
  "skills_max_chars": 3000,
  "copy_skill_assets": false
}
```

The engine injects each skill's instructions into the agent's objective. Set
`copy_skill_assets: true` to also copy the skill folders into every trial
workspace (so helper scripts can run). See
`examples/landing-build-mistral-config.json` for a working example that builds
a landing page guided by the design skills.

## Build mode (autoresearch builds software, not just ML)

Express any functional requirement as automatic acceptance tests; the score
becomes the fraction of tests passing, and the agent builds code to pass them.
See `examples/saas-build/` (auth, persistence, business logic, billing — all
test-measured) and `examples/landing-build/` (structured landing page).

```powershell
$env:MISTRAL_API_KEY = "your-key"
python -m autoresearch_lab run --config examples/saas-build-mistral-config.json
```

## Optional Agent Mode

Set `agent_command` in the config to let another tool modify the trial workspace before the experiment command runs. The engine still handles isolation, metric parsing, acceptance, reports, and resume.

## Mistral Agent Mode

Set a Mistral API key:

```powershell
$env:MISTRAL_API_KEY = "your-key"
```

Then run:

```powershell
python -m autoresearch_lab run --config examples/mistral-agent-config.json
```

Key config fields:

```json
{
  "agent_provider": "mistral",
  "agent_model": "codestral-latest",
  "agent_files": ["train.py", "params.json"],
  "agent_temperature": 0.2,
  "agent_max_tokens": 4096
}
```

The Mistral agent receives only the files listed in `agent_files`, returns JSON with full replacement file contents, and the engine evaluates the result in an isolated trial workspace. Rejected trials are not copied into `best/`.

## Tests

```powershell
python -m unittest discover -s tests
```

