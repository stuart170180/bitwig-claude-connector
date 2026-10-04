"""The MCP tools, grouped by topic. Importing this package registers every tool with the server."""
from bwmcp.tools import (  # noqa: F401  (registration happens on import)
    clips,
    devices,
    extras,
    library,
    mixing,
    presets,
    session,
    tracks,
)
