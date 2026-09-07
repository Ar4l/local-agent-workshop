import marimo

__generated_with = "0.24.0"
app = marimo.App(width="medium", layout_file="layouts/agent.slides.json")


@app.cell
def _():
    import json
    import subprocess
    import sys
    from pathlib import Path

    import marimo as mo
    import ollama

    sys.path.insert(0, str(mo.notebook_dir()))
    import workshop
    from workshop import harness, trace
    from workshop.mcp_bridge import McpSource, to_ollama_tool

    WORK = mo.notebook_dir() / "work"          # clones live here (git-ignored)
    ARGS = mo.cli_args()                        # `uv run agent.py -- --issue URL --model NAME`

    def task(md: str):
        """Slides that ask YOU to do something look like this."""
        return mo.callout(mo.md("### 👉 Your turn\n" + md), kind="warn")
    return ARGS, McpSource, WORK, harness, json, mo, ollama, subprocess, sys, task, to_ollama_tool, trace, workshop


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # Local Agent Workshop @ IFI

    0. Overview, prerequisites
    1. LLM inference (via Ollama)
    2. Tool calling
    3. Model Context Protocol
    4. Solving issues from GitHub
    5. Ready harnesses

    By the end you run `uv run agent.py -- --issue <url>` and it opens a PR.
    Orange boxes are exercises. Solutions are in `agent.py`.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 0.1 `whoami`

    - studied at TU Delft
    - experimented with transformers
    - now training Mellum models
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.vstack([
        mo.md(r"""
        ## 0.2 What is an LLM?

        A transformer predicting the next token, over and over.
        """),
        mo.mermaid("""
        flowchart LR
          P["prompt tokens<br/>[The, cat, sat, on, the]"] --> T["transformer<br/>(weights)"]
          T --> D["distribution over next token<br/>mat 0.62 · floor 0.21 · …"]
          D -->|sample| N["mat"]
          N -->|append| P
        """),
    ])
    return


@app.cell(hide_code=True)
def _(mo):
    mo.vstack([mo.md(r"""
    ## 0.3 What is an agent?

    Model + tool calls, in a loop.
    """), mo.image(mo.notebook_dir() / "public/agents-meme.jpg", width=720)])
    return


@app.cell(hide_code=True)
def _(mo):
    mo.vstack([mo.md(r"""
    ## 0.4 What is a harness?

    Different ways of implementing agents; mainly just a system prompt, model loop, and tool implementations.
    """), mo.image(mo.notebook_dir() / "public/json-meme.jpeg", width=560)])
    return


@app.cell(hide_code=True)
def _(mo, task):
    task(r"""
    ## 0.5 What do you need?

    - `ollama`, `uv`, `git`, `gh` (run `gh auth login`), `node` ≥ 20
    - `git clone https://github.com/Ar4l/local-agent-workshop && cd local-agent-workshop`
    - `uv run marimo edit notebook.py`

    ```bash
    brew install ollama uv gh node                                                 # macOS
    winget install Ollama.Ollama astral-sh.uv GitHub.cli OpenJS.NodeJS.LTS Git.Git   # Windows
    # Linux: see README.md
    ```
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # 1. LLM inference

    Generate text using model weights, a large set of numbers.
    """)
    return


@app.cell(hide_code=True)
def _(ARGS, mo, task):
    model_ui = mo.ui.dropdown(
        options=["qwen3.5:4b", "gemma4:e4b-it-qat", "gemma4:12b",
                 "hf.co/JetBrains/Mellum2-12B-A2.5B-Thinking-GGUF-Q4_K_M", "qwen3.8:27b", "qwen3.5:9b"],
        value=ARGS.get("model") or "qwen3.5:4b", label="model")
    mo.vstack([task(r"""
    ## 1.1 Choose a model for your RAM

    | RAM | model | download |
    |:---|:---|:---|
    | 8 GB | `qwen3.5:4b` (or `gemma4:e4b-it-qat`) | 3.4 GB |
    | 16 GB | `gemma4:12b` (or `hf.co/JetBrains/Mellum2-12B-A2.5B-Thinking-GGUF-Q4_K_M`) | 7.4 GB |
    | 32 GB | `qwen3.8:27b` | 17 GB |

    - Pull it yourself in a terminal now: the notebook never downloads models
    - Ollama must be running: the macOS/Windows app starts it, on Linux run `ollama serve`
    - Then pick the same model in the dropdown below

    ```bash
    ollama pull qwen3.5:4b      # pick yours from the table
    ```
    """), model_ui])
    return (model_ui,)


@app.cell
def _(ARGS, model_ui):
    MODEL = ARGS.get("model") or model_ui.value
    OPTIONS = {"num_ctx": 32768}   # Ollama defaults to 4k tokens on <24 GiB GPUs: an agent overflows that fast
    return MODEL, OPTIONS


@app.cell(hide_code=True)
def _(MODEL, mo, ollama):
    mo.stop(not mo.running_in_notebook())   # preflight only matters in the notebook
    import httpx
    try:
        ollama.show(MODEL)
        _status = mo.md(f"✅ `{MODEL}` is available")
    except ollama.ResponseError as _e:
        if _e.status_code != 404:
            raise
        _status = mo.callout(mo.md(f"Model `{MODEL}` is not downloaded. Run in a terminal:\n\n```bash\nollama pull {MODEL}\n```"), kind="danger")
    except (ConnectionError, httpx.ConnectError):
        _status = mo.callout(mo.md("Ollama is not running. Start the Ollama app (macOS/Windows) or run `ollama serve` (Linux), then re-run this cell."), kind="danger")
    _status
    return


@app.cell(hide_code=True)
def _(mo):
    mo.vstack([mo.md(r"""
    ## 1.2 While that downloads: what is an inference server?

    - It loads weights onto the GPU once, then answers HTTP requests
    - Ollama provides pull, run and API commands. It launches llama.cpp's `llama-server`
    - Ollama defaults to a 4k context on small GPUs. Agents need `num_ctx` ≥ 16k
    """), mo.hstack([mo.md(r"""
    | | Ollama | llama.cpp (`llama-server`) | DwarfStar (`antirez/ds4`) |
    |:---|:---|:---|:---|
    | what | Docker-for-models: pull, run, one local API | the engine itself, every knob exposed | one-model-class C engine by the Redis author |
    | run | `ollama run qwen3.5:9b` | `llama-server -hf ggml-org/…-GGUF` | `./ds4-server --ctx 32768` |
    | hardware | Metal, CUDA, ROCm, Vulkan, CPU | same + SYCL, OpenCL, RPC … | 96 GB Macs, CUDA, ROCm |
    """), mo.image(mo.notebook_dir() / "public/inference-meme.png", width=300)], widths=[3, 1], align="start")])
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 1.3 Four API shapes, one model

    - `/api/chat` is Ollama's, `/v1/chat/completions` and `/v1/responses` OpenAI's, `/v1/messages` Anthropic's
    - Existing clients like OpenAI SDK, Claude Code and Codex can use a local model
    - The same prompt produced the same tool call. Only the JSON envelope differed

    | endpoint | tool call lives in | thinking lives in |
    |:---|:---|:---|
    | `POST /api/chat` | `message.tool_calls[].function.{name, arguments: object}` | `message.thinking` |
    | `POST /v1/chat/completions` | `choices[0].message.tool_calls[].function.arguments` (JSON **string**) | `message.reasoning` |
    | `POST /v1/responses` | `output[]` item `type: "function_call"` | `output[]` item `type: "reasoning"` |
    | `POST /v1/messages` | `content[]` block `type: "tool_use"`, `input: object` | `content[]` block `type: "thinking"` |

    We use `/api/chat` through the `ollama` Python package because only it accepts `num_ctx`.
    """)
    return


@app.cell(hide_code=True)
def _(mo, task):
    task(r"""
    ## 1.4 Your first local chat

    - Implement `chat(messages, tools)`: call `ollama.chat` once and return `.message`
    - Pass `MODEL` and `OPTIONS`. The message contains `.content`, `.thinking` and `.tool_calls`
    - Run the next cell and read the thinking trace
    """)
    return


@app.cell
def _(MODEL, OPTIONS, ollama):
    def chat(messages, tools=None):
        """One model call. Returns the assistant message (content, thinking, tool_calls)."""
        # --- solution: chat ---
        return ollama.chat(MODEL, messages=messages, tools=tools, options=OPTIONS).message
        # --- end solution ---
    return (chat,)


@app.cell
def _(chat, mo, trace):
    mo.stop(not mo.running_in_notebook())   # skip this demo when run as a script
    _reply = chat([{"role": "user", "content": "In one sentence: what is a tool call?"}])
    trace.thinking(_reply.thinking)
    trace.assistant(_reply.content)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # 2. Tool calling

    ## 2.0 A tool call is just text

    - The model emits the tags it was trained on. The server parses them into JSON
    - Qwen3.5 writes `<tool_call><function=run_shell><parameter=command>`. Ollama returns `tool_calls`
    - Your program decides whether to run it. Valid syntax does not grant permission

    ```text
    <think>The user wants to list files. I'll use run_shell.</think>
    <tool_call>
    <function=run_shell>
    <parameter=command>
    ls -la
    </parameter>
    </function>
    </tool_call>
    ```
    """)
    return


@app.cell(hide_code=True)
def _(mo, task):
    task(r"""
    ## 2.1 Tool number one: `run_shell`

    - Implement `run_shell(command: str) -> str`: run `subprocess.run` in `workshop.workdir()`, then return output and exit code
    - Always return a string. Never raise because errors inform the model
    - The model sees the docstring as its schema. Run the next cell to inspect it
    """)
    return


@app.cell
def _(subprocess, workshop):
    DENY = ("rm -rf", "sudo", "curl", "wget", "git ")

    def run_shell(command: str) -> str:
        """Run a shell command in the repo root and return its output and exit code.

        Args:
            command: the command to run, e.g. `node --check app.js`
        """
        # --- solution: run_shell ---
        if any(bad in command for bad in DENY):
            return f"BLOCKED: {command!r} is not allowed"
        try:
            p = subprocess.run(command, shell=True, cwd=workshop.workdir(), timeout=60, text=True,
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        except subprocess.TimeoutExpired:
            return "ERROR: timed out after 60 s"
        return f"{p.stdout[-4000:]}\n[exit code {p.returncode}]"
        # --- end solution ---

    SHELL_TOOLS = {"run_shell": (workshop.schema_of(run_shell), run_shell)}
    return SHELL_TOOLS, run_shell


@app.cell
def _(SHELL_TOOLS, mo):
    mo.vstack([mo.md("## 2.1 The schema the model sees\n\nThis is everything the model knows about your tool:"),
               mo.json(SHELL_TOOLS["run_shell"][0])])
    return


@app.cell(hide_code=True)
def _(mo, task):
    task(r"""
    ## 2.2 The loop

    - `execute(call, tools)`: find the name, call it with `**arguments`, return a string, cap its length
    - `agent_loop(messages, tools)`: chat, append reply, run tool calls, append results and repeat
    - Stop when the reply has no tool calls, or after `max_turns`. Return the reason

    ```text
    for turn in range(max_turns):
        reply = chat(messages, schemas);  messages.append(reply)
        if not reply.tool_calls: return "stopped"
        for call in reply.tool_calls:
            messages.append({"role": "tool", "tool_name": call.function.name, "content": execute(call, tools)})
    return "max_turns"
    ```
    """)
    return


@app.cell
def _(chat, trace):
    def execute(call, tools) -> str:
        """Run one tool call. Always returns a string: errors are for the model to read."""
        # --- solution: execute ---
        name, args = call.function.name, dict(call.function.arguments or {})
        if name not in tools:
            return f"ERROR: unknown tool {name!r}; available: {sorted(tools)}"
        try:
            result = str(tools[name][1](**args))
        except Exception as e:
            return f"ERROR: {type(e).__name__}: {e}"
        if len(result) > 8000:  # tool output eats context: keep the head, tell the model
            result = result[:8000] + f"\n… [{len(result) - 8000} more chars cut; read smaller ranges]"
        return result
        # --- end solution ---

    def agent_loop(messages, tools, max_turns=25) -> str:
        """Call the model until it answers without tool calls (or the turn budget runs out)."""
        # --- solution: agent_loop ---
        schemas = [schema for schema, _fn in tools.values()]
        for turn in range(max_turns):
            trace.rule(f"turn {turn + 1}")
            reply = chat(messages, schemas)
            messages.append(reply)
            trace.thinking(reply.thinking)
            trace.assistant(reply.content)
            if not reply.tool_calls:
                return "stopped"
            for call in reply.tool_calls:
                trace.tool_call(call.function.name, dict(call.function.arguments or {}))
                result = execute(call, tools)
                trace.tool_result(result)
                messages.append({"role": "tool", "tool_name": call.function.name, "content": result})
        return "max_turns"
        # --- end solution ---
    return agent_loop, execute


@app.cell(hide_code=True)
def _(mo, task):
    task(r"""
    ## 2.3 Try it on a real repo

    - The next cell clones `Ar4l/simple-todo-app` and forks it under your account
    - Ask: "How many lines does app.js have, and which function deletes a todo?"
    - Read the trace. Did it call the tool or guess?
    """)
    return


@app.cell
def _(WORK, harness, mo):
    REPO_DIR = harness.prepare_repo("Ar4l/simple-todo-app", WORK)
    question_ui = mo.ui.text(value="How many lines does app.js have, and which function deletes a todo?", full_width=True)
    ask_ui = mo.ui.run_button(label="Ask the agent")
    _rel = REPO_DIR.relative_to(mo.notebook_dir()) if REPO_DIR.is_relative_to(mo.notebook_dir()) else REPO_DIR
    mo.vstack([mo.md(f"## 2.3 Ask the agent\n\nworking directory: `{_rel}`"), question_ui, ask_ui])
    return REPO_DIR, ask_ui, question_ui


@app.cell
def _(SHELL_TOOLS, agent_loop, ask_ui, mo, question_ui):
    mo.stop(not ask_ui.value, mo.md("*press **Ask the agent** first*"))
    _messages = [{"role": "system", "content": "You answer questions about the repo in the working directory using run_shell. Paths are relative to the repo root; never use cd."},
                 {"role": "user", "content": question_ui.value}]
    agent_loop(_messages, SHELL_TOOLS)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 2.4 Do special tool tokens matter?

    - Every vendor uses different tags: `<tool_call>`, `[TOOL_CALLS]`, `<|DSML|>`. Parsers lag months behind
    - No vendor publishes an ablation. One internal controlled run found BFCL −0.8 to +1.6 points
    - Training on many formats and using fewer atomic tools made the difference

    | family | delimiter | argument encoding |
    |:---|:---|:---|
    | Qwen3.5 / Qwen3-Coder | `<tool_call><function=…><parameter=…>` | XML per argument, raw strings |
    | DeepSeek V3.2 / V4 | `<｜DSML｜invoke name=…>` | XML per argument |
    | Gemma 4 | `<｜tool_call>call:NAME{…}<tool_call｜>` | key:value, quote token |
    | Mistral | `[TOOL_CALLS]` name `[ARGS]` json | JSON |
    | Hermes, Granite 4, Mellum2 | `<tool_call>{…}</tool_call>` | JSON |
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 2.5 Small-model realities

    - Keep 3–5 atomic tools in context to improve tool choice
    - Thinking improves small-model tool use by +9 to +12 BFCL Live points for Qwen3 4B/8B
    - Never combine JSON `format=` with `tools=`. The grammar mask cannot emit `<tool_call>`
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.vstack([
        mo.md(r"""
        # 3. Model Context Protocol

        A server (local or remote) uses MCP to expose tools and data to agents.
        """),
        mo.mermaid("""
        sequenceDiagram
          participant S as MCP server
          participant H as agent host (your loop)
          participant M as model
          S->>H: list_tools → name, description, inputSchema
          H->>M: tool schemas + messages
          M->>H: tool call (name, arguments)
          H->>S: call_tool(name, arguments)
          S->>H: result text
          H->>M: role=tool message
        """),
    ])
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 3.1 MCP or CLI?

    - GitHub work does not require MCP. Scaffolding, not interface, drives token cost [^controlled_mcp]
    - Structured atomic edit tools reduce execution errors and improve consistency, especially for weaker models [^interface_mcp]
    - Fewer tools in context improves tool choice: 93% at ~2 tools vs 87% at 5 [^interface_mcp_2]

    Choose MCP for remote services, delegated authorization (OAuth 2.1) and hosts without a shell [^mcp_spec].

    [^controlled_mcp]: https://arxiv.org/abs/2608.08654
    [^interface_mcp]: https://arxiv.org/abs/2608.11386
    [^interface_mcp_2]: https://arxiv.org/abs/2605.24660
    [^mcp_spec]: https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization
    """)
    return


@app.cell(hide_code=True)
def _(mo, task):
    task(r"""
    ## 3.2 Plug an MCP server into your loop

    - `workshop/mcp_server.py` provides `read_file`, `write_file` and `edit_file`, restricted to the repo
    - Start it with `McpSource([...])`, then create `FILE_TOOLS` from `src.tools`
    - Build each entry as `(to_ollama_tool(t), (lambda name: lambda **args: src.call(name, args))(t.name))`: a plain lambda would late-bind `t`
    """)
    return


@app.cell
def _(McpSource, REPO_DIR, mo, sys, to_ollama_tool):
    src = McpSource([sys.executable, str(mo.notebook_dir() / "workshop" / "mcp_server.py"), str(REPO_DIR)])

    # --- solution: mcp ---
    FILE_TOOLS = {t.name: (to_ollama_tool(t), (lambda name: lambda **args: src.call(name, args))(t.name))
                  for t in src.tools}
    # --- end solution ---
    mo.md("## 3.2 Tools from the MCP server\n\n" + ("MCP server exposes: " + ", ".join(f"`{n}`" for n in FILE_TOOLS)
                                                  if FILE_TOOLS else "nothing registered yet: fill in the TODO in this cell"))
    return FILE_TOOLS, src


@app.cell
def _(FILE_TOOLS, SHELL_TOOLS):
    TOOLS = SHELL_TOOLS | FILE_TOOLS
    return (TOOLS,)


@app.cell(hide_code=True)
def _(mo):
    mo.vstack([
        mo.md(r"""
        # 4. Fixing a GitHub issue end to end

        - The model receives the issue text and four tools. The harness handles everything else
        - When the model stops, the harness commits the diff and opens a draft PR
        - Nothing is tested automatically. A human reviews the PR, as with any coding agent
        """),
        mo.mermaid("""
        flowchart LR
          I["issue URL"] --> C["harness: fork, clone, branch"]
          C --> L["agent_loop<br/>(model + 4 tools)"]
          L --> D{"any file changed?"}
          D -->|no| X["nothing pushed"]
          D -->|yes| P["commit · push · draft PR"]
          P --> H["human review"]
        """),
    ])
    return


@app.cell(hide_code=True)
def _(mo, task):
    task(r"""
    ## 4.1 Run it

    - Pick an issue and run it. Watch the trace, then open its PR
    - Or run: `uv run agent.py -- --issue <url> --model qwen3.5:4b`
    - Issue 1 fixes a bug. Issues 2 and 3 add features. Try 1 first
    """)
    return


@app.cell
def _(ARGS, mo):
    issue_ui = mo.ui.dropdown(
        options=[f"https://github.com/Ar4l/simple-todo-app/issues/{i}" for i in (1, 2, 3)],
        value=ARGS.get("issue") or "https://github.com/Ar4l/simple-todo-app/issues/1", label="issue")
    pr_ui = mo.ui.checkbox(value=True, label="open a draft PR when done")
    run_ui = mo.ui.run_button(label="Run the agent on this issue")
    mo.vstack([mo.md("## 4.1 Pick an issue"), mo.hstack([issue_ui, pr_ui, run_ui], justify="start")])
    return issue_ui, pr_ui, run_ui


@app.cell
def _(ARGS, MODEL, OPTIONS, TOOLS, WORK, agent_loop, harness, issue_ui, mo, pr_ui, run_ui):
    mo.stop(not (run_ui.value or ARGS.get("issue")), mo.md("*press **Run the agent on this issue** first*"))
    result = harness.solve_issue(
        ARGS.get("issue") or issue_ui.value, agent_loop, TOOLS,
        model=MODEL, options=OPTIONS, root=WORK,
        open_pr=pr_ui.value and "dry-run" not in ARGS)
    result
    return (result,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # 5. Ready harnesses

    - The same loop, with more polish: `pi` and DeepSeek's `dsh` add structured tools, sessions and compaction
    - `mini-swe-agent` uses only bash: a 190-line agent loop, near state of the art on SWE-bench
    - DeepSeek's `dsh` uses `pi`'s model layer. `pi` intentionally ships without MCP

    | | mini-swe-agent | pi | DeepSeek Harness (`dsh`) |
    |:---|:---|:---|:---|
    | language | Python | TypeScript | TypeScript + Python SDK |
    | tools | bash only | read, bash, edit, write, grep, find, ls | 17 plugins + MCP client |
    | agent loop | 190 lines | 803 lines | 2.4k lines |
    | install → answer (`qwen3.5:9b`) | 8 s → 61 s, 10 calls | 19 s → 9 s, 1 call | 3.5 min → 41 s, 1 call |
    | Ollama config | 6-line YAML | `~/.pi/agent/models.json` | `settings.yaml` plugin composition |
    """)
    return


@app.cell(hide_code=True)
def _(mo, task):
    task(r"""
    ## 5.1 Try one: `pi`

    - Install it, connect it to Ollama and ask the question your loop answered in 2.3
    - Compare its trace with yours. What did the harness add?
    - Find configurations for all three in `harnesses/`

    ```bash
    npm install -g @earendil-works/pi-coding-agent
    mkdir -p ~/.pi/agent && cp harnesses/pi/models.json ~/.pi/agent/   # edit the model id
    cd work/simple-todo-app && pi --provider ollama --model qwen3.5:9b -p "How many lines does app.js have?"
    ```
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Takeaways

    - An agent is a loop: the model proposes, your code validates and executes, then returns results
    - Small local models work with few tools, enough context and a human reviewing the PR
    - MCP supplies tools, not intelligence. Harnesses provide prompts, loops and stop rules
    """)
    return


if __name__ == "__main__":
    app.run()
