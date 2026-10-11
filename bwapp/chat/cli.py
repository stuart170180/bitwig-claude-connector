"""Claude backend: the `claude` CLI in stream-json mode (uses the owner's own Claude Code login; only the Bitwig MCP server is loaded).
One long-lived process per conversation; each user turn is one JSON line, events come back one JSON object per line."""
import json
import subprocess
import threading

from PySide6.QtCore import QObject, Signal

from bwmcp.core import paths

SYSTEM = ("You are inside the Bitwig Remote desktop app, talking to the owner about their Bitwig Studio project. Use the bitwig tools to "
          "act. Check get_session before changing anything, keep answers short, and say what you did.")


def mcp_config() -> str:
    p = paths.DATA / "app_mcp.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"mcpServers": {"bitwig": {"command": "python", "args": [str(paths.ROOT / "server.py")]}}}), encoding="utf-8")
    return str(p)


class CliChat(QObject):
    text = Signal(str)                     # streamed assistant text
    tool = Signal(str, str, str)           # tool_use id, name, input json
    tool_result = Signal(str, str, bool)   # tool_use id, result text, is_error
    finished = Signal(str, float)          # reason, cost usd
    failed = Signal(str)

    def __init__(self, model="claude-sonnet-5-5"):
        super().__init__()
        self.model, self.session_id = model, None
        self.proc = None
        self.busy = False

    def _start(self):
        cmd = ["claude", "-p", "--input-format", "stream-json", "--output-format", "stream-json", "--verbose", "--include-partial-messages",
               "--mcp-config", mcp_config(), "--strict-mcp-config", "--allowedTools", "mcp__bitwig", "--model", self.model,
               "--append-system-prompt", SYSTEM]
        if self.session_id:
            cmd += ["--resume", self.session_id]
        self.proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, encoding="utf-8",
                                     bufsize=1, cwd=str(paths.ROOT), creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        threading.Thread(target=self._read, args=(self.proc,), daemon=True).start()

    def send(self, text, images=()):
        """images: list of (media_type, base64 data)."""
        if self.proc is None or self.proc.poll() is not None:
            self._start()
        content = [{"type": "image", "source": {"type": "base64", "media_type": m, "data": d}} for m, d in images]
        content.append({"type": "text", "text": text})
        self.busy = True
        self.proc.stdin.write(json.dumps({"type": "user", "message": {"role": "user", "content": content}}) + "\n")
        self.proc.stdin.flush()

    def stop(self):
        """Stop button: end the process; the conversation resumes from its session id on the next message."""
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
        self.busy = False

    def close(self):
        self.stop()

    def _read(self, proc):
        try:
            for line in proc.stdout:
                try:
                    e = json.loads(line)
                except ValueError:
                    continue
                t = e.get("type")
                if t == "system" and e.get("subtype") == "init":
                    self.session_id = e.get("session_id", self.session_id)
                elif t == "stream_event":
                    d = e["event"].get("delta", {})
                    if d.get("type") == "text_delta":
                        self.text.emit(d["text"])
                elif t == "assistant":
                    for b in e["message"].get("content", []):
                        if b.get("type") == "tool_use":
                            self.tool.emit(b["id"], b["name"].replace("mcp__bitwig__", ""), json.dumps(b.get("input", {})))
                elif t == "user":
                    for b in (e.get("message", {}).get("content") or []):
                        if isinstance(b, dict) and b.get("type") == "tool_result":
                            c = b.get("content")
                            c = "".join(x.get("text", "") for x in c) if isinstance(c, list) else str(c)
                            self.tool_result.emit(b["tool_use_id"], c, bool(b.get("is_error")))
                elif t == "result":
                    self.session_id = e.get("session_id", self.session_id)
                    self.busy = False
                    self.finished.emit("error" if e.get("is_error") else "done", float(e.get("total_cost_usd") or 0))
        except Exception as ex:  # noqa: BLE001
            self.failed.emit(str(ex))
        self.busy = False
