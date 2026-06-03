# Clean-Room Note

`research-engine/` is an original implementation written from scratch for this repository.

It does not copy source files, structure, notebooks, prompts, or implementation details from `karpathy/autoresearch`.

Design goals for this implementation:

- generic command runner instead of a project-specific training loop
- JSON configuration instead of hard-coded experiment settings
- isolated trial directories
- stdout/stderr capture
- JSONL ledger
- resumable state
- Markdown and HTML reports
- optional external agent command
- optional Mistral code agent using JSON full-file replacements
- `bootstrap-project` blueprint generator for new Studio IA-like applications

The earlier upstream copy was removed from the current branch history before this version was published.
