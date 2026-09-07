"""Round-trip slide text through Codex (gpt-5.6-sol) for plain, human-readable English.

    uv run tools/polish_slides.py extract solutions.py > /tmp/slides.md   # numbered blocks
    codex exec -m gpt-5.6-sol ... < prompt  > /tmp/slides.polished.md
    uv run tools/polish_slides.py apply solutions.py /tmp/slides.polished.md

Blocks are the r\"\"\"...\"\"\" strings in the notebook; only bullets and plain prose may change.
Tables, code fences, image links, footnote definitions and mermaid must be copied verbatim.
"""
import re
import sys

SEP = "\n<<<SLIDE {i}>>>\n"


def blocks(src):
    return list(re.finditer(r'(r""")(.*?)(""")', src, re.S))


if sys.argv[1] == "extract":
    src = open(sys.argv[2]).read()
    for i, m in enumerate(blocks(src)):
        sys.stdout.write(SEP.format(i=i) + m.group(2))
    sys.stdout.write("\n<<<END>>>\n")
elif sys.argv[1] == "apply":
    src = open(sys.argv[2]).read()
    polished = open(sys.argv[3]).read()
    parts = re.split(r"\n?<<<SLIDE (\d+)>>>\n", polished)
    new = {int(parts[i]): parts[i + 1].split("\n<<<END>>>")[0] for i in range(1, len(parts), 2)}
    out, pos, changed = [], 0, 0
    for i, m in enumerate(blocks(src)):
        out.append(src[pos:m.start(2)])
        body = new.get(i, m.group(2))
        # guard: verbatim regions must survive
        for tag in ("```", "|", "![", "[^", "mo.mermaid"):
            assert m.group(2).count(tag) == body.count(tag), f"slide {i}: {tag!r} count changed"
        changed += body != m.group(2)
        out.append(body)
        pos = m.end(2)
    out.append(src[pos:])
    open(sys.argv[2], "w").write("".join(out))
    print(f"applied: {changed} slides changed")
