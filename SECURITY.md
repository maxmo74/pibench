# Security Policy

## Sensitive data

This repository accepts no secrets or private operational artifacts. Do not commit credentials, tokens, keys, cookies, private URLs, personal data, raw model conversations, prompts, outputs, sessions, private benchmark evidence, machine paths, hostnames, internal addresses, environment files, databases, or model files.

Tracked benchmark data is restricted to the allowlisted aggregate export in `RESULTS.csv`. Detailed evidence remains local and untracked.

## Required release checks

Before committing:

```sh
python3 scripts/public_release_audit.py --current-only
```

Before pushing:

```sh
python3 scripts/repository_audit.py --history
```

The push check scans every reachable Git object, commit identity, and commit message. A clean working tree is not enough because later deletion does not remove data from history.

Never bypass an audit or add an exception merely to make it pass.

## Exposure response

If sensitive data enters an unpushed commit, stop and rewrite all affected history before pushing. Remove branches and tags that retain the blob, then rerun the full audit.

If data may have reached a remote:

1. Stop further publication.
2. Revoke or rotate affected credentials immediately.
3. Notify the repository owner without repeating the sensitive value.
4. Purge affected remote history and cached artifacts.
5. Rerun the full audit before publication resumes.

Deleting the file in a later commit does not remediate exposure.

## Reporting

Report suspected exposure privately to the repository owner. Do not open a public issue containing the data.
