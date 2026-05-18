# Setup on lxplus

This repository can be used on lxplus or similar Linux servers, but there are two important constraints:

1. Browser-based login is usually easier on a desktop or laptop with a GUI.
2. NotebookLM auth state must never be committed to Git.

## Recommended setup

Clone the repo and bootstrap a virtualenv in your work area:

```bash
git clone <your-repo-url>
cd notebooklm-agent-tools
./scripts/bootstrap.sh
```

## Authentication strategy

### Best option

Authenticate on a GUI-capable machine first:

```bash
./bin/nlm-agent run login
```

Then, if your security policy allows it, copy the upstream auth state in `~/.notebooklm/` to lxplus.

### Why this helps

lxplus is often headless, so browser login can be awkward or impossible without extra forwarding or a separate workstation.

## Common usage

```bash
./bin/nlm-agent doctor
./bin/nlm-agent run list
./bin/nlm-agent run status
./bin/nlm-agent export-sources --output ./notebooklm-output/current
./bin/nlm-agent fetch-source-files --output ./notebooklm-output/source-files/current
./bin/nlm-agent download-artifacts report --output ./notebooklm-output/artifacts/report/
```

## Notes

- Prefer repo-local outputs such as `./notebooklm-output/`
- Keep large exports out of Git unless you explicitly want them versioned
- If the upstream CLI is already installed elsewhere, you can override the binary with `NLM_NOTEBOOKLM_BIN`
