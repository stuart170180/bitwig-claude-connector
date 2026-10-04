"""MCP server that drives Bitwig Studio through the BitwigMCP controller script (OSC over UDP).

This file is only the entry point: the tools live in bwmcp/tools/, grouped by topic, and the connection in bwmcp/core/.
Run it with `python server.py` (that is what `claude mcp add` registers)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from bwmcp.core.bridge import bw, deep, mcp  # noqa: E402,F401  (re-exported)
from bwmcp.tools import (  # noqa: E402  (importing registers the tools)
    clips,
    devices,
    extras,
    grid,
    library,
    mixing,
    presets,
    session,
    tracks,
)

# Keep `server.<name>` working for scripts that import this module (the live monitor, tests, quick experiments).
for _module in (tracks, session, clips, devices, presets, mixing, library, extras, grid):
    globals().update({k: v for k, v in vars(_module).items() if not k.startswith("__")})

if __name__ == "__main__":
    mcp.run()
