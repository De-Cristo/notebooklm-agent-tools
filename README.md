# notebooklm-agent-tools

Portable tooling for using `notebooklm-py` from local machines, GitHub-hosted repos, AI agents, and remote Linux environments such as lxplus at CERN.

This repository does **not** ship real NotebookLM data, browser state, or authentication. It focuses on repeatable setup and predictable local exports.

## What This Repo Provides

- A portable Python CLI for AI agents and humans
- Bulk export of NotebookLM source fulltext into a local directory
- Best-effort fetching of original URL-backed source files
- Stable local wrapper for NotebookLM artifact downloads
- A thin passthrough to the upstream `notebooklm` CLI for commands this repo does not wrap directly
- Bootstrap instructions for macOS and Linux
- Server-friendly usage notes for lxplus and similar hosts

## Repository Layout

- `bin/nlm-agent`: repo-local launcher
- `scripts/bootstrap.sh`: create a virtualenv and install `notebooklm-py`
- `src/notebooklm_agent_tools/`: Python implementation
- `docs/setup-lxplus.md`: lxplus-oriented setup notes
- `AGENTS.md`: instructions for AI agents using this repo

## Quick Start

### 1. Bootstrap

```bash
./scripts/bootstrap.sh
```

If you need browser-based login on a workstation:

```bash
./scripts/bootstrap.sh --browser
```

### 2. Verify the install

```bash
./bin/nlm-agent doctor
```

### 3. Log in

```bash
./bin/nlm-agent run login
```

### 4. List notebooks

```bash
./bin/nlm-agent run list
```

### 5. Export the current notebook's indexed source text

```bash
./bin/nlm-agent export-sources
```

## Wrapped Commands

### Health and discovery

```bash
./bin/nlm-agent doctor
```

### Generic passthrough

Use this for any upstream `notebooklm` command:

```bash
./bin/nlm-agent run list
./bin/nlm-agent run status
./bin/nlm-agent run source list --json
./bin/nlm-agent run artifact list
./bin/nlm-agent run download audio ./artifacts/audio.mp3
```

### Bulk source export

```bash
./bin/nlm-agent export-sources
./bin/nlm-agent export-sources --notebook <notebook_id>
./bin/nlm-agent export-sources --output ./notebooklm-output/my-notebook
./bin/nlm-agent export-sources --limit 25
```

This writes:

- `manifest.json`
- `README.md`
- `errors.json`
- one `.txt` file per source

The `.txt` files contain the **NotebookLM-indexed fulltext**, which is what NotebookLM uses internally when answering questions. They are not guaranteed to be the original PDFs or HTML pages.

### Best-effort original source fetch

```bash
./bin/nlm-agent fetch-source-files
./bin/nlm-agent fetch-source-files --notebook <notebook_id>
./bin/nlm-agent fetch-source-files --output ./notebooklm-output/source-files/current
./bin/nlm-agent fetch-source-files --limit 20
```

This downloads original content from source URLs when NotebookLM exposes a URL in the source manifest.

Important:

- this only works for URL-backed sources
- it does not reconstruct direct local uploads that were added to NotebookLM without a public URL
- some sites may block automated fetches, so `errors.json` is part of the expected output

### Artifact download wrapper

```bash
./bin/nlm-agent download-artifacts audio
./bin/nlm-agent download-artifacts slide-deck --selector all
./bin/nlm-agent download-artifacts slide-deck --format pptx
./bin/nlm-agent download-artifacts report --output ./artifacts/reports/
./bin/nlm-agent download-artifacts audio --dry-run --json
```

By default, artifact downloads go under `./notebooklm-output/artifacts/<artifact-type>/`.

## Authentication Notes

- Upstream auth is handled by `notebooklm-py`
- Default upstream storage usually lives under `~/.notebooklm/`
- This repo does not commit auth state
- For headless servers, authenticate on a desktop first and then copy the upstream storage state only if your security policy allows it

## lxplus Notes

See [docs/setup-lxplus.md](./docs/setup-lxplus.md).

Short version:

- install into a virtualenv in your home directory or work area
- prefer plain `notebooklm-py` on servers unless you explicitly need browser login
- authenticate on a GUI-capable machine first when possible

## For AI Agents

Start with [AGENTS.md](./AGENTS.md). It explains the expected command patterns and output locations.
