"""Readable, compact trace of an agent run (works in the notebook and in a terminal)."""
import json
import shutil
import textwrap

WIDTH = min(shutil.get_terminal_size((100, 20)).columns, 100)


def _clip(text: str, lines: int = 12, chars: int = 900) -> str:
    text = (text or "").rstrip()
    if len(text) > chars:
        text = text[: chars // 2] + f"\n   … [{len(text) - chars} chars cut] …\n" + text[-chars // 2 :]
    parts = text.splitlines()
    if len(parts) > lines:
        parts = parts[: lines // 2] + [f"   … [{len(parts) - lines} lines cut] …"] + parts[-lines // 2 :]
    return "\n".join(parts)


def rule(title: str) -> None:
    print(f"\n── {title} " + "─" * max(0, WIDTH - len(title) - 4))


def thinking(text: str) -> None:
    if text:
        print("💭 " + textwrap.shorten(" ".join(text.split()), 300, placeholder=" …"))


def assistant(text: str) -> None:
    if text:
        print("💬 " + textwrap.indent(_clip(text, 20, 2000), "   ").lstrip())


def tool_call(name: str, args: dict) -> None:
    shown = {k: (v if len(str(v)) < 120 else f"<{len(str(v))} chars>") for k, v in args.items()}
    print(f"🔧 {name}({json.dumps(shown, ensure_ascii=False)[1:-1]})")


def tool_result(text: str) -> None:
    print(textwrap.indent(_clip(text), "   ↳ ", lambda _: True))


def note(text: str) -> None:
    print("ℹ️  " + text)


def verdict(ok: bool, text: str) -> None:
    print(("✅ " if ok else "❌ ") + text)
