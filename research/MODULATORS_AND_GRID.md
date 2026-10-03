# Modulators and the Grid: what the connector can and cannot automate

Tested 2026-10-03 on Bitwig 6.1 (controller API v17), live on a scratch track "ZZ research" (deleted afterwards; project back to "Inst 1", "Audio 2", not playing).
Labels: **[LIVE]** = tested in Bitwig, **[DOC]** = read in the API HTML docs, **[FILE]** = byte-inspected files, **[GUESS]** = not verified.

## 1. Verdicts

### Q1 Modulators: NOT possible through the controller API; PARTLY possible through preset files

| Need | Verdict | Evidence |
|---|---|---|
| (a) list modulators on a device | Not possible | [DOC] The only modulation-source calls are `Device.getModulationSource(i)`, `addActiveModulationSourceObserver`, `getMacro`, `getEnvelopeParameter`, all marked deprecated ("remote controls deprecate this"). [LIVE] `cursorDevice.getModulationSource(0..7)` throws `This has been deprecated since API version 2` in v17. `ModulationSource` only has `name/isMapped/isMapping/toggleIsMapping`. |
| (b) add a modulator | Not possible via API | [LIVE] `slotNames()` on Polysynth = [FX, Note FX], Sampler = [FX, Note, Release], Filter+ = [Post FX, Pre FX], Polymer / Poly Grid = [FX, Note FX], FX Grid = [Post FX, Pre FX], EQ+ and FX Layer = none. No modulator slot exists. [LIVE] `insertFile` of `Library/modulators/LFO.bwmodulator` after / into a slot of Polysynth returns "ok" but nothing changes (device list identical). [LIVE] `insertBitwigDevice(UUID)` with two modulator UUIDs (Vibrato LFO `ca8cc421-...`, Expressions `dcacb71b-...`) is also silently ignored, while the same call with a device UUID (Polysynth) inserts. |
| (c) set modulator parameters | Not via API | Modulator parameters are not in the device's direct-parameter list. [LIVE] deep_info on Polymer / Poly Grid shows only device-level params (OUTPUT, PITCH_TRANSPOSE, SHUFFLE...). |
| (d) map to a target with an amount | Not via API | [DOC] `Parameter` exposes only `modulatedValue()` (read the post-modulation value). `toggleIsMapping` is only on deprecated sources. No routing-creation call anywhere (grepped every doc html for "modulat": only ModulationSource, Macro, Parameter.modulatedValue, Device deprecated, RemoteControl/HardwareControl unrelated). |
| (e) read routings | Only the effect | `Parameter.modulatedValue()` (via `createSpecificBitwigDevice(uuid).createParameter(id)`) lets you compare value vs modulated value of a target. [DOC], not exercised live (needs a running note). |
| Library modulator files | Exist, unusable via insert | [FILE] 43 modulators in `Library/modulators/*.bwmodulator` (LFO, ADSR, Macro, Steps, Random, ParSeq-8...). They are version-4 "scrambled" files (see 2), and Bitwig ignores them at a device insertion point. |

What works: modulators that ship **inside presets** come along when a preset is inserted. Example [FILE] `Library/device-settings/a33bba66-.../Default.bwpreset` (Poly Grid default) contains a Vibrato LFO and an Expressions modulator, with the LFO's mapping target stored as the string `CONTENTS/PITCH_TRANSPOSE`. So modulation setups can be delivered as preset files, and (see 2) their numbers can be edited.

### Q2 Grid: API can insert an empty Grid device only; patches are reachable through preset FILES

| Need | Verdict | Evidence |
|---|---|---|
| (a) insert empty Grid device | Possible | [LIVE] `insert_file` of `devices/Poly Grid.bwdevice`, `FX Grid.bwdevice`; (Polymer is also Grid-based: it has the same grid slots). `Note Grid.bwdevice` also exists. |
| (b) see/change modules and cables | Not via API | [LIVE] Poly Grid exposes 9 direct params, all device-level: OUTPUT, PITCH_TRANSPOSE, SHUFFLE, LENGTH, OFFSET, TIMEBASE, FREERUN, NOTE_THRU, CONTROL_THRU. FX Grid 11 (adds MIX, AUTO_GATE, AUTO_RELEASE). Polymer 7. Slots: Poly Grid [FX, Note FX]. Modules are not slots, layers or params. |
| (c) module parameters | Not via API | not in direct-parameter list (above). |
| (d) add modules | Not via API | no such call. |
| Via preset files | Partly proven | see below. |

### Preset container format [FILE + LIVE]

Two kinds of files:

1. **Version 0002 = plain** (all `.bwpreset` in Library/presets, `device-settings/<uuid>/Default.bwpreset` = the factory "init" state of 152 devices, installed packages, user presets). Header (42 bytes, ASCII):
   `BtWg0003 0002 00c4 000016bd 0000000000000000 00` = "BtWg" + version fields; the 8-hex-digit field (0x16bd) is the meta length. Then a **meta section** (readable): `00000004 00000004 "meta"` then entries `00000001 <len><key> <type 08 + len + utf8 value>`: application_version_name, device_name, device_id (UUID), device_type, device_category, referenced_device_ids / referenced_modulator_ids / referenced_module_ids (string arrays, type 0x19), referenced_packaged_file_ids, revision_id, type "application/bitwig-preset". Then padding spaces, then the **payload**: a binary tag stream. Observed tags: `08` string (int32 len + utf8), `07` big-endian double, `05`/`03` int32, `01` byte/bool, `09`/`12`/`0a` object/reference markers; fields are preceded by a 4-byte numeric field id (e.g. 0x2b9 = name string, 0x136 = double value). Strings visible in the payload: "MODULATORS", "MODULES", module names ("Multiosc", "ADSR", "Audio Out"), parameter ids ("ATTACK", "RATE", "DEPTH", ...) and cable/target paths such as `CONTENTS/MODULES/0/CONTENTS/OUT` and `CONTENTS/PITCH_TRANSPOSE`.
   So a Grid patch IS serialized as readable modules + params + cable path strings. Example (Poly Grid Default.bwpreset, 10404 bytes): modulators Vibrato LFO + Expressions; modules Multiosc, ADSR, Audio Out; params such as LFO RATE 4.8, ADSR ATTACK 0.2217 stored as doubles.
2. **Version 0004 = scrambled** (all `Library/devices/*.bwdevice`, `modulators/*.bwmodulator`, `modules/*.bwmodule`, 580 files). Header `BtWg0003 0004 00c8 000015cb ...` then bytes with entropy 7.4 bits/byte, not zlib. Not readable; not a route.

**Round trip [LIVE]** (on copies in `research/scratch`, nothing in the Library touched):
- unmodified copy of the Poly Grid default preset inserted with `insert_file` -> loaded as a Poly Grid, preset name shown as the file name.
- same file with one double patched (`PITCH_TRANSPOSE` 0.0 -> 7.0 semitones, a same-length edit) inserted -> deep_info reads `CONTENTS/PITCH_TRANSPOSE = 0.5972` (= 0.5 + 7/72, exactly 7 semitones). So Bitwig accepts byte-edited preset files and honours the new value.
- Bitwig also loaded an accidentally mis-offset (corrupting) patch without complaint (no integrity checksum visible), so validate edits by reading back.

What is NOT proven: edits that change length (adding a module, a cable, a modulator, a string longer than before). The payload has length prefixes/object counts/ids that I did not fully decode (stopped after identifying the tag types above). Generating a Grid patch from scratch therefore needs a proper parser/serializer, is feasible in principle (format is regular and uses plain tags) but is unverified. [GUESS] that a loader tolerates re-serialized output.

### Q3 Other doors

- **Insert any Bitwig device by UUID** [LIVE]: `InsertionPoint.insertBitwigDevice(UUID)` works (Polysynth inserted). `research/device_uuids.json` maps 152 device UUIDs -> names (from the Library's device-settings folder). No file path needed. Also `insertVST3Device(String)`, `insertCLAPDevice(String)`, `insertVST2Device(int)` [DOC].
- **Copy/move devices between insertion points**: `InsertionPoint.copyDevices/moveDevices(Device...)`, also copyTracks/moveTracks [DOC]. Would allow duplicating a device (incl. its internal Grid patch and modulators) from one track to another without files. Not run live.
- **782 Bitwig actions** callable with `application.getAction(id)` [LIVE list, saved in `research/actions.txt`]. Relevant: `File | add_to_library` (opens Save to Library dialog), `save_default_preset`/`load_default_preset`, `export_project` (DAWproject), `bounce_in_place*`, `Consolidate`, `Group/Ungroup`, browser navigation (57 browser actions), `show_presets_for_device`. None touch modulators or the Grid (only "Beat Grid" snap actions matched "grid"). [GUESS] "Save to Library..." plus dialog actions could be scripted but is a GUI flow.
- **Clipboard**: `InsertionPoint.paste()` exists [DOC]; contents come from the user's clipboard, unexplored.
- **Browser sessions** (`DeviceBrowsingSession`, `PresetBrowsingSession`, `PopupBrowser`, `InsertionPoint.browse()`) [DOC] exist; the repo already has open_device_browser.
- **Drum pads, chain selector, layers** [DOC]: createDrumPadBank/createChainSelector/createLayerBank exist; layers/slots already used by deep.js.

## 2. Recommended design

Principle: since modules/modulators cannot be driven by the API, use **preset templates + binary patching**, plus read-back through the API.

New Python module `preset_patch.py` (promote `research/bwpatch.py`), new commands only where needed:

1. `preset_inspect(path_or_name)` -> meta (device, modulators, modules, referenced ids) + list of named values with offsets (from `bwpatch.info`). No Bitwig needed.
2. `preset_patch(src, edits: {"RATE": 2.0, "DEPTH": 0.5}, occurrence=...)` -> writes a copy into a scratch folder (e.g. `Documents/Bitwig Studio/Library/Presets/MCP generated/`), returns path. Disambiguation needed since names repeat (RATE in several modules): accept `module/param` by walking preceding "MODULES"/"MODULATORS" markers, or occurrence index.
3. `device_insert_preset(track_index, path, slot=None)` : already covered by `deepdev.insert` / `insert_file`.
4. `device_insert_uuid(track_index, uuid_or_name)`: new controller command `deep_insert_uuid` (the `probe_insert_uuid` block in `modgrid_probe.js`, using before/after/slot/layer insertion points like `deep_insert_file`).
5. `modulation_value(device_uuid, param_id)`: new controller command wrapping `createSpecificBitwigDevice(uuid).createParameter(id)` with `value()` and `modulatedValue()`, to confirm that a routing is live.
6. A small **template library** of curated presets with modulators already wired (e.g. the factory presets that reference LFO/ADSR/Macro; scan with `bwscan.py` which lists presets with referenced modulators/modules), exposed as `search_presets(has_modulators=True)`.

MCP tool names: `preset_inspect`, `preset_patch_and_load(track_index, template, edits)`, `device_insert_uuid`, `get_modulated_value`.

## 3. Prototype code and commands

All in `C:\Users\stuar\Documents\Bitwig\bitwig_mcp\research\`:
- `bwpatch.py`: `python bwpatch.py info "<file.bwpreset>"` lists meta, strings and every plain double param with offset; `python bwpatch.py set in.bwpreset out.bwpreset PITCH_TRANSPOSE 7` writes a patched copy.
- `bwscan.py`: scans Library / installed-packages / user Library presets (counts printed there are mis-decoded, only the file list is reliable).
- `uuids.py` -> `device_uuids.json`.
- `live2.py` ... `live6.py`: the live tests (run `cd bitwig_mcp && PYTHONIOENCODING=utf-8 PYTHONPATH=. python research/liveN.py`; they use track index 2 as scratch, so adjust first). `live4.py` is the patch round trip. `live5.py`/`live6.py` need the probe block in `modgrid_probe.js` pasted into deep.js's switch (it was removed again; deep.js is byte-identical to `deep.js.orig`, checked with cmp).
- `actions.txt`: all 782 Bitwig actions.

## 4. Risks and unknowns
- Patch offsets: names repeat; a mis-offset write silently corrupts and Bitwig still loads. Always read back.
- Edits that change length untested; payload grammar not fully decoded.
- Only version-0002 files are editable; 0004 library device/module/modulator files are not.
- Presets saved by future Bitwig versions may switch format or add checksums.
- Modulators on a plain device (e.g. add an LFO to Filter+ cutoff) need a full preset containing that device + modulator; not demonstrated. Generating one is the unproven part.
- Mapping amount fields were not located (only the target path string was seen).
- Loading a hand-edited file is not covered by Bitwig support.
- Leftover: selecting/creating the scratch track changed the selected track in Bitwig; tracks themselves are unchanged.

## 5. Next steps (ranked)
1. Add `deep_insert_uuid` + `device_insert_uuid` (cheap, verified, removes the dependence on file paths).
2. Productise `bwpatch` as `preset_inspect` / `preset_patch_and_load` for value edits (verified route), with module/modulator-aware naming.
3. Locate the modulator mapping-amount field by diffing two presets that differ only in that amount (needs the user to save two presets, v2 files, from the UI).
4. Build the payload parser/serializer round-trip (parse -> write == identical bytes for all 391 v2 presets) as the gate before any length-changing edits (add module / modulator / cable).
5. Add `get_modulated_value` read-back tool.
6. Test `copyDevices`/`moveDevices` as a way to clone Grid devices between tracks.
