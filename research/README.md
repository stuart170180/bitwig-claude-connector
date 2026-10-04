# Research

Experiments and evidence behind the connector. Nothing here is used by the running connector.
Write-ups: [docs/PRESET_FORMAT.md](../docs/PRESET_FORMAT.md), [docs/MODULATORS_AND_GRID.md](../docs/MODULATORS_AND_GRID.md).

Run any script from anywhere: each one finds the repo root itself. Scripts marked **live** drive the open Bitwig project
(they create and delete scratch tracks) and take the `bwlock` lock, so run one at a time.

| Path | What it is |
|---|---|
| `bwformat.py`, `test_bwformat.py` | Bitwig preset-file reader/writer (396/396 files round-trip). Offline. |
| `bwscan.py`, `bwpatch.py`, `uuids.py` | Scan preset files, patch values, collect device UUIDs. Offline. |
| `bwlock.py` | Lock so two live experiments never touch Bitwig at once. |
| `live1.py` ... `live6.py` | **Live** probes of devices, layers and modulator access. |
| `modgrid_probe.js` | Controller-script probe for modulators and Grid (nothing reachable). |
| `features/perform/` | **Live** automation-by-performance experiments (`exp*.py`) and the replay check. |
| `features/masking/`, `features/midi/` | **Live** runs of the masking finder and the MIDI round-trip; `clean.py` removes scratch tracks. |
| `features/actions/`, `features/arrclips/` | Reports (`REPORT.md`) on Bitwig actions and arranger clips. |
| `archive/` | Finished one-offs and the first prototypes of features now in `bwmcp/` (not runnable, kept for history). |
| `actions.txt`, `device_uuids.json` | Data: the 781 Bitwig action ids, the device UUID list. |
| `scratch/`, `shots/` | Throw-away output and screenshot tooling (git-ignored). |
