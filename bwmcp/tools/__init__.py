"""The MCP tools, grouped by topic. Importing this package registers every tool with the server."""
from bwmcp.tools import (  # noqa: F401  (registration happens on import)
    chords,
    clips,
    devicepresets,
    devices,
    extras,
    grid,
    library,
    manual,
    mixing,
    pitchcolour,
    presets,
    session,
    tracks,
    uitools,
)
