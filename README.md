# How to create a local agent

A 2-hour workshop: run a model locally with Ollama, give it tools, wire in an MCP server,
and let it fix real GitHub issues in [Ar4l/simple-todo-app](https://github.com/Ar4l/simple-todo-app)
and open draft PRs for you to review. No API keys.

## Setup (before the workshop)

1. Install `ollama`, `uv`, `git`, `gh`, `node` ≥ 20.

   ```bash
   # macOS
   brew install ollama uv gh node
   # Windows (PowerShell)
   winget install Ollama.Ollama astral-sh.uv GitHub.cli OpenJS.NodeJS.LTS Git.Git
   # Linux (Debian/Ubuntu; other distros: see the links below)
   curl -fsSL https://ollama.com/install.sh | sh
   curl -LsSf https://astral.sh/uv/install.sh | sh
   sudo apt install -y git gh nodejs      # node must be >= 20; see https://nodejs.org if apt is older
   ollama serve &                          # on Linux the server does not start by itself
   ```
   Docs: https://ollama.com/download · https://docs.astral.sh/uv · https://cli.github.com · https://nodejs.org
2. `gh auth login` (the agent forks the sample repo under your account and opens a draft PR).
3. Pull a model for your RAM yourself (the notebook never downloads models):

   | RAM | model | size |
   |---|---|---|
   | 8 GB | `ollama pull qwen3.5:4b` (or `gemma4:e4b-it-qat`) | 3.4 GB |
   | 16 GB | `ollama pull gemma4:12b` | 7.4 GB |
   | 32 GB | `ollama pull qwen3.8:27b` | 17 GB |

4. Clone and open the notebook:

   ```bash
   git clone https://github.com/Ar4l/local-agent-workshop && cd local-agent-workshop
   uv run marimo edit notebook.py
   ```

## What is where

| file | what |
|---|---|
| `notebook.py` | the workshop: slides + cells with `TODO`s you fill in |
| `agent.py` | the same notebook with everything implemented |
| `workshop/` | provided plumbing: git/PR harness, MCP server, MCP bridge, trace printer |
| `harnesses/` | configs to point `pi`, `mini-swe-agent` and `dsh` at Ollama |
| `tools/` | maintainer scripts: derive `notebook.py` from `agent.py`, check slide rules |

## Run the agent on an issue from a terminal

The notebook doubles as a script:

```bash
uv run agent.py -- --issue https://github.com/Ar4l/simple-todo-app/issues/1 --model qwen3.5:4b
uv run agent.py -- --issue <url> --model <model> --dry-run   # fix only, no push/PR
```

It clones (forks) the repo under `work/`, branches, runs the agent loop, then commits, pushes
and opens a draft PR. Nothing is tested automatically: you review the PR.

## Presenting

`./serve` starts a private editor on port 2718, a read-only student view on 2719 and a Cloudflare
tunnel; the public URL is written into this README between the markers below.

<!-- live-url:start -->
_Not running._
<!-- live-url:end -->
