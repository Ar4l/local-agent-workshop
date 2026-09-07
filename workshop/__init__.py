"""Helpers for the "How to create a local agent" workshop.

The notebook cells hold the code students write (chat, run_shell, execute,
agent_loop).  This package holds the plumbing that is provided:

- harness:    clone the repo, run the loop, commit, open the draft PR
- mcp_server: a 30-line MCP server exposing read_file / write_file / edit_file
- mcp_bridge: connect to any stdio MCP server from synchronous code
- trace:      print a readable trace of what the agent does
"""
from pathlib import Path

# The directory every tool operates in.  harness.prepare_repo() sets it to the
# cloned repository; until then it is the notebook directory.
_WORKDIR = Path.cwd()


def workdir() -> Path:
    return _WORKDIR


def set_workdir(path) -> Path:
    global _WORKDIR
    _WORKDIR = Path(path).resolve()
    return _WORKDIR


def schema_of(fn) -> dict:
    """The JSON tool schema Ollama derives from a Python function's signature + docstring."""
    from ollama._utils import convert_function_to_tool
    return convert_function_to_tool(fn).model_dump(exclude_none=True)
