"""Check slide rules in a marimo notebook: ≤3 bullets per slide, ≤16 words per bullet.

    uv run tools/check_slides.py solutions.py
Counts top-level `- ` bullets inside each mo.md / task( r\"\"\"...\"\"\" ) block, ignoring
tables, code fences and footnote definitions. Inline code counts as one word.
"""
import re
import sys

src = open(sys.argv[1]).read()
blocks = re.findall(r'r"""(.*?)"""', src, re.S)
bad = 0
for block in blocks:
    lines, in_code = [], False
    for line in block.splitlines():
        s = line.strip()
        if s.startswith("```"):
            in_code = not in_code
            continue
        if not in_code:
            lines.append(s)
    title = next((l for l in lines if l.startswith("#")), "(no title)")
    bullets = [l for l in lines if l.startswith("- ")]
    problems = []
    if len(bullets) > 3:
        problems.append(f"{len(bullets)} bullets")
    for b in bullets:
        text = re.sub(r"`[^`]*`", "X", b[2:])           # inline code = 1 word
        text = re.sub(r"\[\^[^\]]+\]", "", text)         # footnote refs don't count
        text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)  # link text counts, URL doesn't
        n = len(text.split())
        if n > 16:
            problems.append(f"{n} words: {b[:60]}…")
    if problems:
        bad += 1
        print(f"✗ {title}\n   " + "\n   ".join(problems))
print(f"{len(blocks)} slides checked, {bad} with problems")
sys.exit(1 if bad else 0)
