# PiBench Agent Rules

## Publication safety

- Assume all Git objects and GitHub content are public and permanent.
- Never track credentials, tokens, keys, cookies, private URLs, personal data, raw prompts or outputs, sessions, private result artifacts, machine-specific paths, hostnames, internal addresses, environment files, databases, or model files.
- Publish only allowlisted aggregate benchmark data. Raw evidence stays outside the repository.
- Use placeholders in examples. Keep real configuration under ignored local paths or external secret stores.
- Before committing, inspect the staged diff and run `python3 scripts/public_release_audit.py --current-only`.
- Before pushing, run `python3 scripts/repository_audit.py --history`. A current-tree pass alone never authorizes a push.
- Never bypass or weaken an audit. Ask before adding a publication exception.
- If an unpushed commit contains private data, rewrite history and remove every retaining ref before pushing. A later deletion is insufficient.
- If data may have reached GitHub, stop, report it, rotate affected credentials, and purge remote history.
- Never include sensitive values in commit messages, branches, tags, commands, logs, issues, pull requests, or replies.

## Results

- `RESULTS.csv` is the sole tracked result artifact.
- Keep SQLite, prompts, outputs, errors, notes, commands, sessions, replay fixtures, and detailed reports private.
- Do not mix benchmark protocol versions in rankings.
