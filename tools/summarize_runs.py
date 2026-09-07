"""Summarise runs/*.log (traces written by `uv run solutions.py -- --issue … --model …`) as a markdown table.

    uv run tools/summarize_runs.py runs/
"""
import re
import sys
from pathlib import Path

rows = []
for f in sorted(Path(sys.argv[1]).glob("issue*.log")):
    text = f.read_text()
    m = re.match(r"issue(\d+)-(.+?)(-dryrun)?\.log", f.name)
    issue, model, dry = m.group(1), m.group(2), bool(m.group(3))
    turns = text.count("── turn")
    reviews = text.count("── review")
    tool_calls = text.count("\n🔧 ")
    edits = len(re.findall(r"🔧 (edit_file|write_file)\(", text))
    blocked = len(re.findall(r"↳ (ERROR|BLOCKED)", text))
    gate = "✅" if "✅ test gate passed" in text else ("❌" if "❌ test gate" in text else "–")
    verdicts = re.findall(r"reviewer \(.*?\): (APPROVE|REVISE)", text)
    pr = re.search(r"draft PR opened: (\S+)", text)
    secs = re.search(r"(\d+):(\d+\.\d+) total", text) or re.search(r"exit=\d+ (\d\d):(\d\d):(\d\d)", text)
    wall = ""
    t0 = re.search(r"=== issue \d+ (\d\d):(\d\d):(\d\d)", text)
    t1 = re.search(r"exit=\d+ (\d\d):(\d\d):(\d\d)", text)
    if t0 and t1:
        s0 = int(t0[1]) * 3600 + int(t0[2]) * 60 + int(t0[3]); s1 = int(t1[1]) * 3600 + int(t1[2]) * 60 + int(t1[3])
        wall = f"{(s1 - s0) // 60}m{(s1 - s0) % 60:02d}s"
    elif secs and ":" in secs.group(0):
        wall = f"{secs[1]}m{int(float(secs[2])):02d}s"
    rows.append((issue, model + (" (dry)" if dry else ""), turns, tool_calls, edits, blocked, reviews, gate,
                 "/".join(verdicts) or "–", pr.group(1).replace("https://github.com/", "") if pr else "–", wall))

print("| issue | model | turns | tool calls | edits | errors | reviews | gate | reviewer | PR | wall |")
print("|---|---|---|---|---|---|---|---|---|---|---|")
for r in rows:
    print("| " + " | ".join(str(x) for x in r) + " |")
