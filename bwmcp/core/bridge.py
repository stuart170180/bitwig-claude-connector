"""Connection to Bitwig (OSC over UDP), the MCP server object, the @tool() decorator and the shared device walker."""
import functools
import itertools
import json
import socket
import threading

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from bwmcp.devices import deepdev

HOST, PORT = "127.0.0.1", 8765


REPLY_PORTS = range(8766, 8772)  # must match REPLY_PORTS in BitwigMCP.control.js


mcp = MCPServer("bitwig")


def tool():
    """Register an MCP tool whose errors reach Claude with their message. The SDK hides the text of any
    exception that isn't a ToolError, which would turn useful errors into 'Error executing tool X'."""
    def deco(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            try:
                return fn(*args, **kwargs)
            except ToolError:
                raise
            except Exception as e:
                raise ToolError(str(e) if isinstance(e, (RuntimeError, ValueError)) else f"{type(e).__name__}: {e}") from e
        mcp.tool()(wrapper)
        return wrapper
    return deco


def _osc_str(s: bytes) -> bytes:
    s += b"\0"
    return s + b"\0" * (-len(s) % 4)


def osc_encode(address: str, arg: str) -> bytes:
    return _osc_str(address.encode()) + _osc_str(b",s") + _osc_str(arg.encode("utf-8"))


def osc_decode_string_arg(packet: bytes) -> str:
    """Return the first string argument of an OSC message."""
    def read_str(i):
        end = packet.index(b"\0", i)
        return packet[i:end], end + 1 + (-(end + 1) % 4)
    _, i = read_str(0)        # address
    tags, i = read_str(i)     # type tags
    if not tags.startswith(b",s"):
        raise ValueError(f"unexpected OSC type tags {tags!r}")
    val, _ = read_str(i)
    return val.decode("utf-8")


class Bridge:
    def __init__(self):
        self.sock = None
        self.port = None
        self.lock = threading.Lock()
        self.ids = itertools.count(1)

    def _open(self):
        # Each client (Claude session, script) takes the first free reply port so several can run at once.
        for port in REPLY_PORTS:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                sock.bind((HOST, port))
            except OSError:
                sock.close()
                continue
            sock.settimeout(5)
            self.sock, self.port = sock, port
            return
        raise RuntimeError(f"all Bitwig reply ports {REPLY_PORTS.start}-{REPLY_PORTS.stop - 1} are in use; "
                           "close other Claude sessions using Bitwig")

    def call(self, cmd, **args):
        with self.lock:
            if self.sock is None:
                self._open()
            rid = next(self.ids)
            payload = json.dumps({"id": rid, "cmd": cmd, "args": args, "reply_port": self.port})
            if len(payload) > 60000:
                raise RuntimeError("request too large; split it into smaller calls")
            self.sock.sendto(osc_encode("/mcp", payload), (HOST, PORT))
            try:
                while True:
                    reply = json.loads(osc_decode_string_arg(self.sock.recv(65535)))
                    if reply.get("id") == rid:
                        break  # ignore stale replies from timed-out calls
            except (OSError, ValueError) as e:
                raise RuntimeError(
                    "No reply from Bitwig. Is Bitwig open with the 'Claude > Bitwig MCP' "
                    f"controller enabled (Settings > Controllers)? ({e})"
                )
        if not reply.get("ok"):
            raise RuntimeError(reply.get("error"))
        return reply.get("result")

    def batch(self, commands):
        """Run [(cmd, args), ...] in one round trip; raises if any failed."""
        results = self.call("batch", commands=[{"cmd": c, "args": a} for c, a in commands])
        errors = [r["error"] for r in results if not r["ok"]]
        if errors:
            raise RuntimeError("; ".join(errors))
        return [r["result"] for r in results]


bw = Bridge()


SETTLE = 0.25  # seconds for Bitwig to apply a change before reading it back


deep = deepdev.Deep(bw)
