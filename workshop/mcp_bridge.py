"""Use a stdio MCP server from synchronous code.

    src = McpSource([sys.executable, "workshop/mcp_server.py", "/path/to/repo"])
    src.tools          # list of mcp.types.Tool (name, description, input_schema)
    src.call("read_file", {"path": "app.js"})   # -> str
    src.close()

MCP clients are asyncio-based; the notebook and the agent loop are synchronous,
so the client runs on its own event loop in a background thread.
"""
import asyncio
import threading
from contextlib import AsyncExitStack

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class McpSource:
    def __init__(self, command: list[str]):
        self._params = StdioServerParameters(command=command[0], args=command[1:])
        self._loop = asyncio.new_event_loop()
        self._stop = None
        self._ready = threading.Event()
        self._error: list[BaseException] = []
        self.tools = []
        threading.Thread(target=self._run, daemon=True).start()
        self._ready.wait(timeout=30)
        if self._error:
            raise self._error[0]

    def _run(self):
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self._serve())

    async def _serve(self):
        try:
            async with AsyncExitStack() as stack:
                read, write = await stack.enter_async_context(stdio_client(self._params))
                self._session = await stack.enter_async_context(ClientSession(read, write))
                await self._session.initialize()
                self.tools = (await self._session.list_tools()).tools
                self._stop = asyncio.Event()
                self._ready.set()
                await self._stop.wait()
        except BaseException as e:  # surface startup errors to the caller
            self._error.append(e)
            self._ready.set()

    def call(self, name: str, arguments: dict) -> str:
        fut = asyncio.run_coroutine_threadsafe(self._session.call_tool(name, arguments), self._loop)
        result = fut.result(timeout=120)
        text = "\n".join(getattr(c, "text", "") for c in result.content)
        return f"ERROR: {text}" if result.is_error else text

    def close(self):
        if self._stop is not None:
            self._loop.call_soon_threadsafe(self._stop.set)


def to_ollama_tool(tool) -> dict:
    """MCP tool description -> the JSON schema shape Ollama's chat API expects."""
    return {"type": "function", "function": {
        "name": tool.name, "description": tool.description or "",
        "parameters": tool.input_schema}}
