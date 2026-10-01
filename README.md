# Bitwig connector for Claude

Lets Claude drive Bitwig Studio: write and edit MIDI, build whole song sketches, load sounds and samples, mix, master with
live measurements, and record scenes into the arrangement. Everything reads back from Bitwig to confirm it took effect.
65 tools — the full list is in [TOOLS.md](TOOLS.md).

## How it fits together

```
Claude ──MCP (stdio)──> server.py ──OSC over UDP──> BitwigMCP controller script (inside Bitwig)
                          │  8765 → Bitwig, replies on 8766–8771 (one per client)
                          ├── music.py / expert.py / variations.py   note generation and editing
                          ├── presets.py / samples.py / bookmarks.py sound libraries
                          ├── mastering.py / reference.py / pitch.py audio analysis (WAV files or live capture)
                          └── live_monitor.py ──> http://127.0.0.1:8780   live dashboard (loudness, M/S, tuner, master controls)
```

Bitwig's script API cannot see audio, so analysis works on files or on Windows "loopback" capture of Bitwig's output.

## Setup (already done on this machine)

1. **Bitwig script:** `Documents\Bitwig Studio\Controller Scripts\BitwigMCP\` (`BitwigMCP.control.js`, `pro.js`, `expert.js`,
   `arranger.js`). In Bitwig: *Settings → Controllers → Add controller → Claude → Bitwig MCP*. Bitwig reloads the script
   whenever a file changes.
2. **Python:** `pip install -r requirements.txt`
3. **Claude:** `claude mcp add --scope user bitwig -- python C:/Users/stuar/Documents/Bitwig/bitwig_mcp/server.py`
   (then start a new Claude session; tools are loaded at session start).
4. **Live capture (optional):** set Bitwig *Settings → Audio → Driver model* to **Windows Audio (WASAPI)**. Exclusive ASIO
   drivers (e.g. ASIO4ALL) can't be captured; file-based analysis works with any driver.

## Everyday use

Ask Claude in plain language, for example:

- "Sketch a 124 bpm house track in F minor" → `sketch_song` (tracks, sounds, 7 scenes of clips)
- "Record those scenes into the arrangement" → `record_arrangement`
- "Show me the mid/side on the master" → `analyze_master` · "Start the live monitor" → `live_monitor`
- "Is the lead in tune?" → `check_tuning` · "Compare to this reference" → `compare_reference`
- "Tidy my track names" → `auto_name_tracks` · "Save the mixer as 'before'" → `snapshot`

**Live monitor without Claude:** double-click `start_monitor.bat` (opens http://127.0.0.1:8780).
**Start automatically at login:** `python autostart.py` (hidden, no admin needed); `--status` to check, `--remove` to undo.
Every panel has a × to close it; the **Panels** menu in the header brings them back (or *Compact* for loudness only).
Your layout is remembered in the browser, and a closed Master-controls panel never touches Bitwig.

## Files

| File | Purpose |
|---|---|
| `server.py` | MCP server: all 65 tools, the Bitwig bridge |
| `music.py`, `expert.py`, `variations.py` | Theory, generators, expert note edits, variations |
| `presets.py`, `samples.py`, `bookmarks.py`, `naming.py` | Libraries, bookmarks (`bookmarks.json`), track auto-naming |
| `mastering.py`, `reference.py`, `pitch.py` | Loudness / M-S / spectrum, reference comparison, pitch and tuning |
| `live_monitor.py` / `.html` | Live dashboard web server and page |
| `autostart.py` | Starts the dashboard hidden at Windows login (`--status`, `--remove`) |
| `start_monitor.bat` | Starts the dashboard in a window on demand |
| `tests/live_test.py` | Regression test that calls every tool through a real MCP client |
| `make_docs.py` | Regenerates `TOOLS.md` |
| `backup.py` | Timestamped zip backups and restore |
| `bitwig_script/` | Git-tracked copy of the Bitwig controller script (Bitwig loads the original from its own folder) |
| `sync_script.py` | Mirrors the script between Bitwig's folder and `bitwig_script/` (`--install`, `--check`) |
| `snapshots/`, `reports/` | Saved mixer snapshots / monitor reports (created on first use) |

## Maintenance

- **Back up:** `python backup.py` (zips this folder and the Bitwig script into `..\backups\`, keeps the newest 10);
  `python backup.py --list`; `python backup.py --restore <zip>` (makes a safety copy first).
- **Version control:** this folder is a git repo. Before committing run `python sync_script.py` so `bitwig_script/` matches what
  Bitwig is running; on a fresh machine run `python sync_script.py --install` to put the script back into Bitwig.
- **Test:** open Bitwig with the controller enabled, then `python tests/live_test.py`. It creates its own tracks and removes
  them again. Lint with `python -m pyflakes *.py`.
- **After adding a tool:** `python make_docs.py` to refresh `TOOLS.md`.

## Ports

`8765` requests to Bitwig · `8766–8771` replies (a client takes the first free one, so up to 6 can run at once) ·
`8780` live monitor. All bound to 127.0.0.1 only.

## Troubleshooting

- **"No reply from Bitwig"** — Bitwig isn't open, or the controller isn't enabled (see Setup 1).
- **"all Bitwig reply ports … are in use"** — close other Claude sessions or stray `python server.py` processes.
- **Monitor page won't load** — it isn't running: `python autostart.py --status`, or double-click `start_monitor.bat`.
- **Live capture says it can't capture** — Bitwig is on an exclusive driver; switch to Windows Audio (Setup 4).
- **Script errors** — search `%LOCALAPPDATA%\Bitwig Studio\BitwigStudio.log` for "Bitwig MCP".
- **Tools missing in Claude** — start a new session; check `claude mcp get bitwig` shows *Connected*.

## Known limits

- Bitwig's API can't place or read **arranger clips**; `record_arrangement` records scenes instead, and the arrangement can't
  be read back (check the Arrange view yourself).
- Sounds load from preset/device **files** (6,000+ indexed), not by browsing Bitwig's own browser or its favourites.
- Per-note **pressure** can be set but Bitwig doesn't report it back, so it can't be verified.
- Meters are on Bitwig's 0–1 scale; true LUFS / dBTP come from the captured audio, not from Bitwig's meters.
- Master-chain sliders and tools select Bitwig's master track; don't use the monitor's sliders while Claude is also
  changing the master chain.
