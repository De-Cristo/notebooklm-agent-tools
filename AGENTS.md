# AGENTS

This repository is designed to be used by AI coding agents as well as humans.

## Preferred entrypoint

Use the repo-local launcher:

```bash
./bin/nlm-agent
```

Do not assume that `notebooklm` is installed globally. This repo intentionally resolves the upstream CLI through the project virtualenv when possible.

## Safe workflow

1. Run `./bin/nlm-agent doctor`
2. If needed, run `./bin/nlm-agent run login`
3. Inspect context with `./bin/nlm-agent run status`
4. Use `./bin/nlm-agent run ...` for generic upstream commands
5. Use `./bin/nlm-agent export-sources` for predictable local source export
6. Use `./bin/nlm-agent fetch-source-files` for best-effort original URL downloads
7. Use `./bin/nlm-agent download-artifacts ...` for stable artifact downloads

## Expected output layout

By default, exports go under:

```text
./notebooklm-output/<notebook-slug>/
```

Typical files:

- `manifest.json`
- `README.md`
- `errors.json`
- `NNN-<slug>-<source-id>.txt`

For source-file fetching, expect:

- downloaded binaries or HTML files
- one per-source metadata `.json` file
- `downloads.json`
- `errors.json`

## Auth expectations

- Do not commit `~/.notebooklm/`
- Do not commit browser profiles, cookies, or storage state
- If running on a headless server, assume login may need to happen on another machine first

## Common commands

```bash
./bin/nlm-agent doctor
./bin/nlm-agent run list
./bin/nlm-agent run source list --json
./bin/nlm-agent export-sources --notebook <id>
./bin/nlm-agent fetch-source-files --notebook <id>
./bin/nlm-agent download-artifacts slide-deck --selector all
./bin/nlm-agent run artifact list
./bin/nlm-agent run download slide-deck ./artifacts/slides.pdf
```
