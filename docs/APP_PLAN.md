# Native Bitwig Remote app - plan (started 2026-10-11)

Goal: one dedicated desktop program. **No web page, no web server, no web view** anywhere in the app. Every block can be
moved, resized, closed and added back; the layout is remembered. Blocks: all current monitor features, a Claude chat, and a
sample mode.

## Framework (decided from the research)
- **PySide6 6.11.2 (Qt Widgets)**, LGPL (fits the AGPL project). Not QML (no web-style layer), not JUCE (C++ rewrite, no reuse of the Python analysis).
- **PySide6-QtAds 5.1.1** for docking: drag, tab, float, resize, close, re-add (View menu), `saveState` / `restoreState`. Pinned with PySide6 6.11.2 (QtAds pins 6.11.2; tested to install together on Python 3.14).
- **QPainter** custom widgets for meters, vectorscope, tuner; **pyqtgraph 0.14** for the spectrum, loudness history and sample waveform.
- **sounddevice** (PortAudio callback, atomic position) for sample playback: sample-accurate seek / rewind / fast-forward / loop.
- **pedalboard 0.9.26** (bundled Rubber Band) to time-stretch / pitch-shift samples offline; **soundfile** to decode; BPM from a scipy onset autocorrelation plus a whole-bars sanity check (librosa as an optional upgrade).
- **Chat**: two backends behind one panel. (1) `claude` CLI in stream-json mode (uses the owner's own Claude Code login and the already registered `bitwig` MCP server: personal use only). (2) Anthropic SDK with an API key kept in Windows Credential Manager (keyring). Tool calls show as collapsible blocks, text streams, Stop button.

## Layout of the code
```
bwapp/
  main.py          entry (BitwigRemote.pyw calls it)
  window.py        QtAds main window, View menu, save/restore layout, reset layout
  theme.py         dark palette + stylesheet
  feed.py          starts the existing Capture/Analyzer in-process and hands frames to the panels (no HTTP)
  panels/          one file per block (readouts, history, scope, spectrum, levels, tuner, vst, master, chords, advice ...)
  chat/            panel, CLI backend, API backend, key store
  audio/           sample library, decode, tempo, peaks, player, stretch
```

## Stages (1, 2 and 3 done in 9.0.0)
1. **Shell + live blocks + chat + sample mode (first cut).** App opens, docking works, meters live, chat answers, samples play. *(this stage)*
2. Port the remaining blocks: BW Remote VST card, master chain sliders, compressors, chord builder, advice, UK clock + weather, target select, report.
3. **Remove the web**: delete `live_monitor.html`, the HTTP handler / SSE in `live_monitor.py`, `desktop.py` (pywebview), `autostart.py` web launcher (replace by app autostart), `pywebview` requirement; point the `live_monitor` MCP tool at the native app; update packaging (PyInstaller spec) and docs. Only after stage 2 has parity.
4. Sample mode extras: library tags/search, drag a sample into Bitwig (controller `insert_file`), time-stretch to project tempo, key detection.

## Known constraints
- QtAds floating windows can land on a missing monitor: View > Reset layout.
- Never touch widgets off the GUI thread: audio / capture / chat threads emit Qt signals.
- The `claude` CLI route is for the owner's own use; shipping the app to others needs the API-key route.
