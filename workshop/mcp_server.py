"""A tiny MCP server: three file tools confined to one directory.

    python workshop/mcp_server.py /path/to/repo

Any MCP host can use it (Claude Desktop, Cursor, your own loop).  The server
enforces its own safety: paths that escape the root are refused.
"""
import sys
from pathlib import Path

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
mcp = MCPServer("files")


def confine(path: str, must_exist: bool = False) -> Path:
    """Resolve `path` inside ROOT; refuse anything outside (symlinks included)."""
    p = (ROOT / path).resolve()
    if p != ROOT and ROOT not in p.parents:
        raise ToolError(f"path escapes the repo: {path}")
    if must_exist and not p.is_file():
        raise ToolError(f"no such file: {path}")
    return p


@mcp.tool()
def read_file(path: str) -> str:
    """Read a text file. `path` is relative to the repo root, e.g. `app.js`."""
    return confine(path, must_exist=True).read_text()


@mcp.tool()
def write_file(path: str, content: str) -> str:
    """Create or overwrite a file with `content` (send the complete file)."""
    target = confine(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content)
    return f"wrote {len(content)} chars to {path}"


@mcp.tool()
def edit_file(path: str, old: str, new: str) -> str:
    """Replace `old` with `new` in a file. `old` must appear exactly once; copy it verbatim."""
    target = confine(path, must_exist=True)
    text = target.read_text()
    n = text.count(old)
    if n != 1:
        return f"ERROR: `old` occurs {n} times in {path}; it must occur exactly once"
    target.write_text(text.replace(old, new, 1))
    return f"edited {path}: replaced {len(old)} chars with {len(new)} chars"


if __name__ == "__main__":
    mcp.run()  # stdio transport
