"""Claude backend 2: the Anthropic API with your own key (keyring) and the Bitwig MCP server as tools. Same signals as the CLI backend."""
import asyncio
import json
import sys
import threading
from contextlib import AsyncExitStack

from PySide6.QtCore import QObject, Signal

from bwapp.chat import keystore
from bwapp.chat.cli import SYSTEM
from bwmcp.core import paths

MAX_ROUNDS = 25


class ApiChat(QObject):
    text = Signal(str)
    tool = Signal(str, str, str)
    tool_result = Signal(str, str, bool)
    finished = Signal(str, float)
    failed = Signal(str)

    def __init__(self, model="claude-sonnet-5-5"):
        super().__init__()
        self.model, self.busy = model, False
        self.msgs, self.session, self.tools, self.stack, self.task = [], None, None, None, None
        self.loop = asyncio.new_event_loop()
        threading.Thread(target=self.loop.run_forever, daemon=True).start()

    def send(self, text, images=()):
        content = [{"type": "image", "source": {"type": "base64", "media_type": m, "data": d}} for m, d in images]
        content.append({"type": "text", "text": text})
        self.busy = True
        self.task = asyncio.run_coroutine_threadsafe(self._turn(content), self.loop)

    def stop(self):
        if self.task:
            self.task.cancel()
        self.busy = False

    def close(self):
        self.stop()
        if self.stack:
            asyncio.run_coroutine_threadsafe(self.stack.aclose(), self.loop)

    async def _connect(self):
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
        self.stack = AsyncExitStack()
        r, w = await self.stack.enter_async_context(stdio_client(StdioServerParameters(command=sys.executable, args=[str(paths.ROOT / "server.py")])))
        self.session = await self.stack.enter_async_context(ClientSession(r, w))
        await self.session.initialize()
        listing = await self.session.list_tools()
        self.tools = [{"name": t.name, "description": t.description or "", "input_schema": t.inputSchema} for t in listing.tools]

    async def _turn(self, content):
        try:
            key = keystore.get()
            if not key:
                raise RuntimeError("No API key yet - press 'API key...' and paste yours (it is kept in Windows Credential Manager).")
            import anthropic
            client = anthropic.AsyncAnthropic(api_key=key)
            if self.session is None:
                await self._connect()
            self.msgs.append({"role": "user", "content": content})
            for _ in range(MAX_ROUNDS):
                async with client.messages.stream(model=self.model, max_tokens=8000, system=SYSTEM, messages=self.msgs, tools=self.tools) as s:
                    async for t in s.text_stream:
                        self.text.emit(t)
                    final = await s.get_final_message()
                self.msgs.append({"role": "assistant", "content": [b.model_dump(exclude_none=True) for b in final.content]})
                if final.stop_reason != "tool_use":
                    break
                results = []
                for b in final.content:
                    if b.type != "tool_use":
                        continue
                    self.tool.emit(b.id, b.name, json.dumps(b.input))
                    r = await self.session.call_tool(b.name, b.input)
                    out = "".join(c.text for c in r.content if getattr(c, "type", "") == "text")
                    self.tool_result.emit(b.id, out, bool(r.isError))
                    results.append({"type": "tool_result", "tool_use_id": b.id, "content": [{"type": "text", "text": out or "(no output)"}],
                                    "is_error": bool(r.isError)})
                self.msgs.append({"role": "user", "content": results})
            self.busy = False
            self.finished.emit("done", 0.0)
        except asyncio.CancelledError:
            self.busy = False
            raise
        except Exception as e:  # noqa: BLE001
            self.busy = False
            self.failed.emit(str(e) or e.__class__.__name__)
