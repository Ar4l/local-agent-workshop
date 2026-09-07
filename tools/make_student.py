"""Derive notebook.py (student version) from agent.py.

Replaces every `# --- solution: NAME ---` … `# --- end solution ---` block with a TODO stub,
and swaps the layout file / title mentions. Run after editing agent.py:

    uv run tools/make_student.py
"""
import json
import re
from pathlib import Path

STUBS = {
    "chat": '''        # TODO: one call to ollama.chat(...) with MODEL, messages, tools and OPTIONS; return .message
        raise NotImplementedError("chat(): fill in the TODO above")''',
    "run_shell": '''        # TODO: refuse commands containing anything in DENY (return "BLOCKED: ...")
        # TODO: p = subprocess.run(command, shell=True, cwd=workshop.workdir(), timeout=60, text=True, ...)
        # TODO: ... with stdout=subprocess.PIPE, stderr=subprocess.STDOUT so the model sees stderr too
        # TODO: return the output followed by a last line "[exit code N]"; on timeout return an ERROR string
        raise NotImplementedError("run_shell(): fill in the TODO above")''',
    "execute": '''        # TODO: name = call.function.name, args = dict(call.function.arguments or {})
        # TODO: unknown name -> return an ERROR string listing the available tools
        # TODO: result = str(tools[name][1](**args)); wrap exceptions into an ERROR string
        # TODO: cap result at ~8000 chars (tool output eats context), then return it
        raise NotImplementedError("execute(): fill in the TODO above")''',
    "agent_loop": '''        # TODO: schemas = [schema for schema, fn in tools.values()]
        # TODO: for each turn: reply = chat(messages, schemas); messages.append(reply)
        # TODO:   print the trace: trace.rule(), trace.thinking(), trace.assistant()
        # TODO:   if not reply.tool_calls: return "stopped"
        # TODO:   for call in reply.tool_calls: result = execute(call, tools)
        # TODO:       messages.append({"role": "tool", "tool_name": call.function.name, "content": result})
        # TODO: after the loop: return "max_turns"
        raise NotImplementedError("agent_loop(): fill in the TODO above")''',
    "mcp": '''    # TODO: FILE_TOOLS = {t.name: (to_ollama_tool(t), (lambda name: lambda **args: src.call(name, args))(t.name)) for t in src.tools}
    # TODO: (a plain `lambda **args: src.call(t.name, args)` late-binds t, so every tool would call the last one;
    # TODO:  the closure factory above, or a small make_tool(name) helper, binds the name per tool)
    FILE_TOOLS = {}''',
}

src = Path("agent.py").read_text()
out, n = src, 0
for name, stub in STUBS.items():
    pattern = re.compile(rf"( *)# --- solution: {name} ---\n.*?\n *# --- end solution ---\n", re.S)
    out, k = pattern.subn(stub + "\n", out)
    n += k
assert n == len(STUBS), f"replaced {n} of {len(STUBS)} solution blocks"
out = out.replace('layout_file="layouts/agent.slides.json"', 'layout_file="layouts/notebook.slides.json"')
out = out.replace("uv run agent.py --", "uv run notebook.py --")
Path("notebook.py").write_text(out)
cells = out.count("@app.cell")
Path("layouts/notebook.slides.json").write_text(json.dumps(
    {"type": "slides", "data": {"cells": [{} for _ in range(cells)], "deck": {}}}, indent=2))
print(f"notebook.py written: {cells} cells, {n} TODO blocks")
