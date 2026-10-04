# Bitwig plain preset format (container BtWg00030002): parser, semantic view, length-changing edits

Tested 2026-10-03, Bitwig 6.1 (writer schema 196), Windows 11, Python 3.14.
Labels: **[VERIFIED-LIVE]** = observed in Bitwig, **[VERIFIED-OFFLINE]** = proven on the file corpus, **[INFERRED]**, **[GUESS]**.

> **READ FIRST - incident.** While loading test file `D5_polymer_insert_lowpass.bwpreset` (a Polymer preset with an extra Low-pass module and two re-routed cables, loaded onto a scratch track that already carried ~45 other test devices) the **Bitwig audio engine process crashed** (exit code -1073741819 = 0xC0000005, `BITWIG_ENGINE.mdmp` written, log time 10:10:57). The Bitwig UI stayed up, but the engine is stopped ("Activate Audio Engine" button) and the controller connector (UDP) is dead, so I could **not** run the final clean-up. The project ("New 2", unsaved) still contains the scratch track `ZZ scratch` with dozens of test devices. **Someone has to click "Activate Audio Engine" (consider deleting the `ZZ scratch` track first, since it holds the file that probably crashed the engine), and delete `ZZ scratch`.** Inst 1 / Audio 2 were not touched (verified before the crash: tempo 110, not playing, position 4.62, faders -10 dB). Synthetic mouse clicks from my side had no effect on the Bitwig window, so I did not try further. Cause of the crash is **undetermined** (see section 6.6).

## 0. Result summary

| Gate | Result |
|---|---|
| 1 Parser + serializer | **396 of 396** version-0002 files (160 `.bwpreset` + 236 `.bwremotecontrols`) round-trip byte-identical. No failures. (The brief said ~391; the file finder in `bwscan.py` skipped `.bwremotecontrols`.) |
| 2 Semantic view | Works on all 160 `.bwpreset` (device params, modulators + mappings, Grid modules + cables). Examples in section 4. |
| 3 Live length-changing edits | Name change, mapping amount, added mapping, added module, added cable, added modulator: **all accepted by Bitwig without error and parameters after the edit point read back correctly**. Functional effect of a new module / cable / modulator is **not proven** (no readback exists in the connector). One test file (D5) crashed the engine. |
| 4 Productised | `research/bwformat.py` (parse, dump, view, edits, validator, template finder), `research/test_bwformat.py` (offline tests, pass). |

## 1. Grammar [VERIFIED-OFFLINE, 396/396]

All integers big-endian.

```
file      := header(42)  meta  padding  '\n'  payload
header    := 'BtWg' '0003' '0002'                 ASCII, 12 bytes: container version 2 = plain
             <4 hex digits>                        schema/writer revision: 00c4 (6.1), 00c0 (6.0), 00ae (old). Opaque, kept verbatim.
             <8 hex digits>                        ABSOLUTE FILE OFFSET OF THE PAYLOAD (= 42 + len(meta) + len(padding) + 1)
             '0000000000000000' '00'               always zero
meta      := u32(4)  string("meta")  { u32(1)  string(key)  typed-meta-value }  u32(0)
padding   := N * 0x20   (N = 5000 normally, 0 in four old 'Containers' presets)
payload   := u32(root class)  fields
fields    := { u32(field id != 0)  u8(type)  value }  u32(0)       an object body; id 0 terminates it
```

Value types (the type byte after the field id):

| t | value | bytes |
|---|---|---|
| 01 | byte / bool | 1 |
| 05 | small enum / flag | 1 (NOT int32) |
| 02 | uint16 | 2 |
| 03 | int32 | 4 |
| 0b | int32 (enum-like) | 4 |
| 07 | double | 8 |
| 08 | string | u32 len + bytes (UTF-8). If bit 31 of len is set: (len & 0x7fffffff) UTF-16BE code units follow |
| 0a | null / empty reference | **0 bytes** |
| 15 | 16 raw bytes (UUID, e.g. device or module type) | 16 |
| 16 | 16 bytes (always zero in the corpus) | 16 |
| 0d | byte array | u32 n + n bytes |
| 17 | float array | u32 n + 4n bytes |
| 09 | object | u32 class id, then `fields` (ends with u32 0) |
| 12 | list | repeated element, ended by code 3 (see below) |
| 19 | string array, **meta section only** | u32 n + n strings |

List (`12`): a sequence of elements, each starting with a u32 *code*: **3 = end of list** (nothing follows), **1 = integer element** (u32 follows), any other code = **object class id** of the element, followed by `fields` (so the element ends with u32 0). There is no element count and no byte length anywhere.

Meta values: `08` string, `03` int32 (revision_no), `0d` byte array (orig_file_checksum, 4 old files), `19` string array (referenced_device_ids, referenced_modulator_ids, referenced_module_ids, referenced_packaged_file_ids).

What every number means:
* **Lengths in bytes**: string length (u32), byte array length. Header offset field = absolute payload offset.
* **Element counts**: float array count (u32 n), meta string-array count (u32 n). Lists and objects have no counts; they are delimited by terminators (3 and 0).
* **Checksums**: none found. `revision_id` (sha1-looking) and `revision_no` in the meta are not recomputed by my writer and Bitwig loads the edited files fine [VERIFIED-LIVE]. The header's 4-hex field is not a length (same 00c4 for files of any size); it tracks the writer version.
* Corpus statistics: 145 463 fields, 237 distinct field ids, 56 distinct object classes, type counts 01:32888 05:22647 07:27104 08:44583 09:8911 12:5266 0a:2041 15:1182 16:448 0b:192 02:73 03:72 0d:43 17:13; 206 UTF-16 strings; 86 integer list elements.

Root: preset files have class 0x561 with fields `1423 (t5)`, `150a (t5)`, `1421 (object 0x40 = the device)`, `1422 (empty list)`. `.bwremotecontrols` files have root class 0x7af.

## 2. Round-trip results [VERIFIED-OFFLINE]

`python research/test_bwformat.py` -> `round trip: 396 of 396 identical`. Sources: Program Files Library (device-settings), installed-packages, Documents\Bitwig Studio. Version-0004 files are scrambled and out of scope.

## 3. Schema knowledge

### 3.1 How names were harvested (new technique) [VERIFIED-LIVE]
Bitwig's loader is a strict schema reader. If a required property is missing it refuses the file and logs the property and class name, e.g. `Required property device_UUID in class float_core.auxiliary_device_preset not found` with the path `preset > contents (native_device_preset) > child_presets/3 (generic_module_preset) > auxiliary_devices/2 (module_grid_preset)`. `research/scratch/harvest.py` deleted every field of 14 object kinds in turn, loaded each, and read the log. Result in `research/scratch/out/harvest.json` and `FIELD_NAMES` / `CLASS_NAMES` in `bwformat.py`. Fields that load silently when removed are optional.

### 3.2 Layout of a device preset
```
root 0x561
  0x1421 device object (0x40 native_device_preset)
     0x2b9 identifier            0x12de preset name(?)       0x9a device_name   0x9b vendor   0x9c category
     0x9e creator   0xa3 enabled   0x9d device_type   0x99 device_UUID (t15)
     0x18f5 object 0x75f "MODULATORS" { 0x1a46 auxiliary_devices: list of modulators (0x6c9) }
     0x1a85, 0x1b75, 0x3a3c, 0x17cd, 0x1945, ... (device-level stuff, unknown, kept as is)
     0xa4 contents = object 0xd3 { 0x20c child_presets: list of members }
  0x1422 list
```
Members of `0x20c` (class -> kind): `0x85` real (`0x136` double), `0x7f` bool (`0x12f`, t05), `0x189` int (`0x330`), `0xf7` enum (`0x273` index + `0x7d3`), `0x7e2` input port (`0x1c4a` **source_path**), `0x2fc` modulation output (`0xe20` = list of mappings), `0x24e` slot (PRE_FX/POST_FX chains), `0xd94` POLY settings, `0x37c` note source, `0x771` **MODULES** (Grid patch).

* **Grid module** = class `0x76f` (auxiliary_device_preset) in the `0x1a46` list of the `0x771` member. Required: `0x2b9` identifier (the module id, "0", "1", ...), `0x9a/9b/9c/9e/a3`, `0x18c6` device_UUID = **module type** (t15), `0x18c7` contents (object 0xd3 with its own `0x20c` member list: parameters, input ports), `0x1a1a` grid_x, `0x1a1b` grid_y (signed byte, cell units). Optional: `0x2651/0x2652` (width/height in cells), `0x2643`.
* **Cable** = an input port member (class `0x7e2`, name e.g. `IN`, `IN2`, `GATE_IN`, `MOD_IN`) whose `0x1c4a` source_path is a string `CONTENTS/MODULES/<module id>/CONTENTS/<output port>`. The cable lives on the **destination** side; output ports are not stored. One input holds one source. Output names seen in 160 presets: `OUT` (nearly all), `MOD_OUT` (ADSR modulation output), `GATE_OUT/PITCH_OUT/VELOCITY_OUT/CHANNEL_OUT/TIMBRE_OUT/PRESSURE_OUT/GAIN_OUT/PAN_OUT` (Note In).
* **Modulator** = class `0x6c9` (modulator_preset) in the `0x75f` container. Required like a module plus `0x1a19` is_polyphonic_mode. `0x1a1b` grid_y is its row (0, 1, 2 ...). Its `contents` has parameters and one or more `0x2fc` modulation outputs (e.g. "LFO", "ENVELOPE").
* **Mapping** = class `0x2fd` (device_modulation_mapping_preset) in the output's `0xe20` list. Required: `0x2b9` ('' ), `0xe3d` **destination_path** (`CONTENTS/PITCH_TRANSPOSE`, `MODULATORS/2/CONTENTS/VALUE`, nested `CONTENTS/DEVICE_CHAIN/Chain/DEVICE_CHAIN/0:CONTENTS/MIX`), `0xe32` **amount** (double, **in the target parameter's native units** [INFERRED]: 0.5 = half a semitone on PITCH_TRANSPOSE (-36..36), 20.4 on Phaser FREQ (15..135), 0.32 on Organ GAIN (0..2)). Optional: `0x1334` = snapshot of the target's value type (object 0x7b: `0x124` min, `0x125` max, `0x37b` default/base value, `0x126` domain, `0x127` engine_domain, `0x128` unit, `0x7c4` step, ...), `0x2d3b/0x2c4c/0x2d2c`.

Parameter ids seen by the API (`deep_params`, `CONTENTS/<NAME>`) are exactly the paths used in mapping destinations.

## 4. Semantic view [VERIFIED-OFFLINE on 160 presets]

`bw.grid_inspect(bw.load(path))`, or `python research/bwformat.py inspect <file>`. Poly Grid default (device-settings\a33bba66-8cd4-4f89-aee5-68bf67f70a54):

```
device 'Poly Grid' (preset 'Default', creator 'Bitwig', category 'The Grid', uuid a33bba66-8cd4-4f89-aee5-68bf67f70a54)
  parameters:
    OUTPUT real 1.0 | PITCH_TRANSPOSE real 0.0 | SHUFFLE bool False | LENGTH int 1 | OFFSET int 0 | TIMEBASE enum 1 | ...
  modulators (2):
    [0] Vibrato (LFO) type=ca8cc421-bcbc-44d9-8ef3-6e570e528d2b
        DEPTH 1.0   FORM 0.8   DELAY 0.615   FADE_IN 0.78   RATE 4.8 ...
        output LFO -> CONTENTS/PITCH_TRANSPOSE amount 0.5 (target range -36.0..36.0, base 0.0)
    [1] Expressions (Note-driven) type=dcacb71b-0f1a-4493-8916-bd460eee71d5
  grid modules (3):
    [0] Multiosc (Oscillator) at x=-2 y=-1 size 3x2     PITCH 0.0  SAW 1.0  KEYTRACK True ...
    [1] ADSR (Envelope) at x=1 y=-1 size 3x2            ATTACK 0.2217  DECAY 0.944  SUSTAIN 0.535 ...
    [2] Audio Out (I/O) at x=4 y=-1 size 1x1            SILENCE_THRESHOLD -96.0  HOLD_TIME 0.05 ...
  cables (2):
    CONTENTS/MODULES/0/CONTENTS/OUT  ->  MODULES/1/IN
    CONTENTS/MODULES/1/CONTENTS/OUT  ->  MODULES/2/IN
```
Polymer default: 19 modules, 22 cables (module-to-module modulation too: `MODULES/3/CONTENTS/MOD_OUT -> MODULES/4/MOD_IN`), mapping `Vibrato LFO -> PITCH_TRANSPOSE`. Polysynth: 55 parameters, same 2 modulators. FX Grid: Audio In (0) -> Audio Out (1). Filter / most FX: 0 modulators, `MODULATORS` container present but empty (all 160 presets have the container, so a modulator can always be appended).

Programmatic: `device_info`, `modulators`, `modulator_view`, `modules`, `module_view`, `cables`, `contents_list`, `member`, `walk`, `dump_tree`.

## 5. Live tests (scratch track "ZZ scratch", Bitwig 6.1)

Method: build the edited copy in `research/scratch/out/`, re-parse it, `insert_file` on the scratch track, then check (1) device count rose (the call returns "ok" even for rejected files, see 5.2), (2) `BitwigStudio.log` since the call has no `Error loading file`, (3) a **canary**: a device-level value that is stored *after* the edited structure (RESONANCE=0.8 for Filter, PITCH_TRANSPOSE=7 st = 0.597222 normalized for Grids) is read back with `deep_info`; a mis-aligned stream would not return it.

### 5.1 Results (first, clean run: 13 files on a fresh track) [VERIFIED-LIVE]

| Test | Edit | Length change | Bitwig | Canary | Verdict |
|---|---|---|---|---|---|
| A0 | control (FX Grid reserialised) | 0 | inserted | - | OK |
| A1-A4 | preset name / device name / instance name longer (A1 +21 B, A2 +36 B, A3 +11 B) or all three shorter (A4 -15 B) on Filter; A2/A4 also change meta device_name | inserted, no log error | - | **Loads.** The displayed names are NOT observable through the connector (`list_devices` shows the device type "Filter" and the file name as preset), so I cannot say which field the UI shows. |
| B0 | canary only | 0 | inserted | 0.800000 OK | OK |
| B1 | long names (preset 207 chars, device 139, instance 60) | +526 | inserted | OK | **Strings of different length work.** Meta length + header payload offset recomputed correctly. |
| B2 | non-ASCII names (U+00DC U+2603 U+266B U+6F22 ...) | +42 | inserted | OK | UTF-8 strings work. |
| C1 | Poly Grid: LFO->PITCH_TRANSPOSE amount 0.5 -> 12.0 | 0 | inserted | OK | Loads. **Amount effect not observable** (no modulatedValue access). |
| C2 | + second mapping LFO -> `CONTENTS/OUTPUT` (new 0x2fd object with range snapshot) | +182 | inserted | OK | Loads, structurally accepted. Not provably active. |
| C3 | mapping removed | -191 | inserted | OK | Loads. |
| D1 | FX Grid + Low-pass module (copied from Filter+ preset), unconnected | +377 | inserted | OK | Loads. |
| D2 | D1 + cables Audio In -> Low-pass -> Audio Out | +408 | inserted | OK | Loads. |
| D3 | two added modules (Low-pass, Abs) | +677 | inserted | OK | Loads. |
| D4 | Poly Grid: cable Multiosc -> ADSR.GATE_IN (empty string -> 31-char path) | +31 | inserted | OK | Loads. |
| E1 | **Filter (no modulators) + Vibrato LFO copied from Poly Grid**, unmapped | +632 | inserted | OK | Loads. |
| E2 | E1 + mapping LFO -> `CONTENTS/RESONANCE` 0.2 | +817 | inserted | OK | Loads. |
| E3 | two modulators (Phaser's LFO + Vibrato) with mappings to RESONANCE and POST_GAIN | +1688 | inserted | OK | Loads. |

Not run: E4 (ADSR modulator copy), because the later session crashed first. Note E1-E3 were generated before I fixed `add_modulator` (it wrote the row index into `0x1a19 is_polyphonic_mode`; fixed afterwards, files regenerated but not reloaded).

In a second run on a track that by then carried 40+ test devices (the connector's device list stayed at 32 entries), C..E reloaded without any log error up to D5; those canary readbacks are void (the script read the wrong device), only the "no log error" part counts.

### 5.2 Negative controls: what Bitwig refuses and what it silently accepts [VERIFIED-LIVE]

| File | Outcome |
|---|---|
| N1 string length +3 (misaligned stream) | `insert_file` returns "ok", **device NOT inserted**, log: `Error loading file ... Null character found in binary string` |
| N2 truncated by 12 bytes | not inserted; log `java.io.EOFException` |
| N7 unknown class id on a module | not inserted; log `CouldNotReadRelationshipItemException` |
| N9 wrong type for a known field (grid_x as string) | not inserted; same exception |
| N10 module without `0x18c6` device_UUID | not inserted; `Required property device_UUID in class ...auxiliary_device_preset not found` |
| N3 module with random/unknown type uuid | **loads silently** (no log); N6 same for modulator uuid |
| N4 mapping to non-existent `CONTENTS/NO_SUCH_PARAM` | loads silently |
| N5 cable from non-existent module 99 / port NOPE | loads silently |
| N8, N12 unknown extra fields/objects | load silently (unknown fields tolerated) |
| N11 duplicate module id | loads silently |

Consequences: (1) `insert_file` "ok" means nothing; verify with device count + log. (2) A good file passing proves it is **schema-valid** (all required properties present, correct types/classes), i.e. my added module / modulator / mapping / cable objects were deserialised as the right kind of object. (3) It does **not** prove that Bitwig kept them: semantic errors (unknown uuid, dangling cable, bad target) are accepted silently, so presumably dropped or inert. `bwformat.check()` flags exactly those silent cases offline.

### 5.3 What is proven and not
* **Proven**: strings of any length incl. non-ASCII; add/remove mapping objects; add module objects; add modulator to a device that had none; set cable strings (empty -> path); all produce files Bitwig loads without errors with subsequent values read back correctly (stream alignment).
* **Not proven**: that the new module processes audio, that a cable carries signal, that the new modulator modulates, what the amount does numerically, which name field the UI displays. The connector has no readback for any of this (no `modulatedValue`, module params are not direct parameters; `deep_info` param count of Filter stayed 5 with 3 modulators added). An audio-meter test needs clip playback; I did not do it because the brief forbids touching the transport.

### 5.4 Cleaning up
After the first batches (A, B-E, negative controls) both scratch tracks were deleted with `scratch/cleanup.py`; `get_session` then showed only `Inst 1`, `Audio 2`, not playing, recording off, position 4.62 beats, tempo 110, selection restored to Audio 2, faders -10 dB. I then created ONE more track `ZZ scratch` for the property harvest (about 50 loads, mostly refused or adding Poly Grids) and the second run; that track is the one that remains after the crash (see top).

## 6. Incident analysis

### 6.1 What happened
Order of loads in the second run: B0 B1 B2 C1 C2 C3 D1 D2 D3 D4 E1 E2 E3 **D5**. All previous loads were error free. 1.7 s after D5's `isEngineReadyChanged` the engine process died with 0xC0000005 (access violation). Log: `Error launching or running engine for project New 2: Communications with engine lost`.

### 6.2 D5 contents
Polymer default + one module `Low-pass` (type 9747205f..., copied from Filter+) with id 19 at x=13, y=-2 (right of Audio Out at x=12), cables `Pan(13).OUT -> 19.IN` and `19.OUT -> Voice Level(15).IN` (replacing 13 -> 15). `bwformat.check()` finds no problem; schema-valid by Bitwig's own loader.

### 6.3 Suspects (unranked, none verified)
1. Placement/flow: the new module sits right of Audio Out and the cables point backwards (Pan x=10 -> Low-pass x=13 -> Voice Level x=11), i.e. looks like feedback. (`add_module` now has `near=` to place next to the source.)
2. A module type taken from another device family (Filter+ is an FX Grid) inside a polyphonic synth Grid.
3. Load: ~58 Grid devices were on one track and the engine was already heavily loaded (CPU time of the app 3679 s).
Isolating requires reloading D5 alone on a fresh track after the engine is back, then variants. Do that with the user's agreement, since a crash stops their audio engine.

## 7. Productised functions: `research/bwformat.py`

Offline tests: `python research/test_bwformat.py` (round trip 396/396, edits survive dump/parse, validator).

| Function | Status |
|---|---|
| `parse(bytes)`, `dump(f)`, `load(path)`, `save(f, path)`, `roundtrip(paths)` | VERIFIED-OFFLINE 396/396 |
| `device_info`, `modulators`, `modulator_view`, `modules`, `module_view`, `cables`, `grid_inspect`, `dump_tree`, `walk`, `meta_get`, `meta_set` | VERIFIED-OFFLINE on 160 presets |
| `set_device_names(f, device_name, preset_name, instance_name)` | live: loads |
| `set_mapping_amount(f, mod_id, target, amount)` | live: loads (effect unobserved) |
| `add_mapping(f, mod_id, target, amount, rng_min, rng_max, base)`, `remove_mapping` | live: loads |
| `extract_modulator(f, id)`, `add_modulator(f, template, new_id=None)` | live: loads (add on Filter) |
| `extract_module(f, id)`, `add_module(f, template, x, y, new_id, near)` | live: loads (FX Grid) |
| `connect(f, src_mod, src_port, dst_mod, dst_port)`, `disconnect` | live: loads |
| `insert_module_between(...)` | composite, offline-tested only; the D5-style use crashed the engine (6) |
| `check(f)` | offline validator (required fields, dangling cables, duplicate ids, meta lists, mapping targets) |
| `module_templates()`, `modulator_templates()` | scan the factory presets for usable templates (type uuid -> name, category, file, id) |

Templates available from factory presets (160 presets): 40 module types (e.g. Low-pass 9747205f, High-pass 052cbe38, Multiosc df0a08cc, ADSR 7e09068b, Audio In/Out b2a6b111/af7b5503, Level, Math, Mix, Pitch, Random, Shaper, Wavetable ...) and 5 modulator types (Vibrato LFO ca8cc421, LFO ad947004, ADSR fad02a39 (midi-instruments default preset), Expressions dcacb71b, Macro-4 24a03de2). Anything not in some factory v2 preset cannot be created yet (factory module/modulator files are scrambled v4).

Usage:
```python
import bwformat as bw
f   = bw.load(r"...\device-settings\d641f61b-...\Default.bwpreset")      # FX Grid
fp  = bw.load(r"...\device-settings\6d621c1c-...\Default.bwpreset")      # Filter+, has a Low-pass module
lp  = bw.extract_module(fp, "<id of Low-pass>")
bw.insert_module_between(f, lp, 0, 1)            # Audio In -> Low-pass -> Audio Out
vib = bw.extract_modulator(bw.load(poly_grid_path), 0)
g   = bw.load(filter_path); m = bw.add_modulator(g, vib)
bw.add_mapping(g, m.get(bw.F_NAME), "CONTENTS/RESONANCE", 0.2, 0.0, 1.0, 0.5)
assert bw.check(g) == []
bw.save(g, r"...\patched_presets\my.bwpreset")
```

## 8. Proposed MCP tools (not implemented; server.py untouched)

All write a **copy** to `patched_presets/`, run `check()`, and (optionally) load + verify on a track.

* `grid_inspect(preset)` -> text/dict view (device params, modulators with mappings, modules with ports, cables). Read-only.
* `preset_templates(kind="module"|"modulator", filter=None)` -> `[{name, category, type_uuid, source, id}]` from `module_templates()` / `modulator_templates()`.
* `preset_add_module(preset, module, near=None, x=None, y=None, connect_from=None, connect_to=None, track_index=None)` -> path, `check()` result, load report. `module` = name or uuid from `preset_templates`; `connect_from=[src_id, src_port]`, `connect_to=[dst_id, dst_port]`.
* `preset_connect(preset, src_module, src_port, dst_module, dst_port, track_index=None)` and `preset_disconnect(...)`.
* `preset_add_modulator(preset, modulator, mappings=[{"target": "CONTENTS/CUTOFF", "amount": 12.0, "min": ..., "max": ..., "base": ...}], track_index=None)`; for the range snapshot take min/max/base from `deep_params`/a donor preset.
* `preset_set(preset, edits)` -> device-level names/values using the structured parser instead of the byte patcher in presetpatch.py (which stays valid for same-length numeric edits).
* Every loading tool must use a **load-and-verify helper**: remember log size, `insert_file`, `list_devices` count must rise, no `Error loading file` in `%LOCALAPPDATA%\Bitwig Studio\BitwigStudio.log` since, optional canary readback via `deep_params`. Put a hard cap on devices per scratch track (the connector list truncates at 32) and delete scratch tracks after each batch.
* Warning text for the tools: a schema-valid file can still make the audio engine crash (section 6); do not auto-load large patched Grids on a session the user is working in without a warning.

## 9. Risks
* Engine crash on one edited Grid file (6); cause open. Can take down the audio engine of the user's session.
* Silent acceptance of semantically wrong files (5.2): need `check()` before loading; a missing cable/module can sound like silence rather than an error.
* No functional proof for added modules/cables/modulators; no observable effect of amount.
* Template availability limited to modules/modulators present in readable (v2) factory presets.
* Format/schema revisions: header field 4-hex (196) differs per Bitwig version; newer versions may add required fields (the strict loader will then refuse files from a stale template; the harvest technique re-derives them in minutes).
* `0x1334` range snapshot content for a new mapping is a guess (min/max/base set, display hints copied from another mapping); optional field, so a mapping without it may be safer [GUESS].
* The `identifier` of modules/modulators is a string used inside paths; I only generate max+1 ids. Duplicate ids load silently (N11), behaviour unknown.

## 10. Ranked next steps
1. Restore the session: Activate Audio Engine, delete the `ZZ scratch` track (user, or me via a re-created connector).
2. Isolate the D5 crash on a fresh track: D5 alone; same patch with the module placed left of Audio Out; module added but unconnected; Low-pass from a Polymer-native donor.
3. Get functional proof: either (a) a short audio-meter test on the scratch track (needs playback, user permission), or (b) a controller command exposing `Parameter.modulatedValue()`/`exists()` for module and modulator parameters.
4. Run E4 and the regenerated E1-E3, plus C2 variant without the optional `0x1334`, as a single small batch.
5. Implement `grid_inspect`, `preset_templates`, `preset_add_module`, `preset_connect`, `preset_add_modulator` in server.py on top of `bwformat.py` with the load-and-verify helper.
6. Extend the harvest technique to the remaining unknown ids (`0x1b75`, `0x3a3c`, `0x2643`, `0x2651/2`) and to `.bwremotecontrols` (also 100% round-trip) so remote-control pages can be authored.
7. Identify how names are shown (`0x2b9` vs `0x9a` vs `0x12de`) with a visual check in the UI.


## 11. Crash isolation and audio proof (second session, with the user's OK)

Harness: `research/grid/` (`lab.py` loads one variant on a fresh scratch track, watches the audio engine, recovers, cleans up;
`variants.py` builds the files; `proof.py`, `proof_fx.py` render a note and measure the master with Bitwig's own recorder).

### 11.1 An added module PROCESSES AUDIO (effects Grid) - PROVEN
Polysynth note -> effects Grid with a Low-pass module wired between Audio In and Audio Out (module copied from Filter+, wired with
`insert_module_between`, CUTOFF set offline), master recorded for 3 s:

| Variant | RMS | Centroid | Energy above 1 kHz |
|---|---|---|---|
| Plain Grid (control) | -31.4 dB | 876 Hz | 32.2 % |
| + Low-pass, cutoff 144 (open) | -31.4 dB | 875 Hz | 32.1 % |
| + Low-pass, cutoff 20 (closed) | -58.9 dB | 573 Hz | 7.3 % |

So the byte-edited file has a working module: the cables carry the signal, the new module's parameter value is honoured, the engine stays up.

### 11.2 The synth-Grid crash (Polymer) - ISOLATED PARTIALLY
Control: the untouched factory Polymer loads fine. Every Polymer file with ONE added module crashes the engine (exit
0xC0000005, 1-2 s after load), whatever else is varied:

| Variant | Result |
|---|---|
| D5 (effects-family Low-pass wired between Pan and Voice Level) | crash |
| Synth-native Low-pass MG wired between Pan and Voice Level | crash |
| Synth-native Low-pass MG added, **not connected** | crash |
| Same, placed **inside** the existing grid area | crash |
| Same, Polymer's remote-control pages emptied | crash |
| Poly Grid (factory, 3 modules) + 1 module | OK |
| Poly Grid + 17 modules (20 total) | OK |
| Poly Grid set to 12 voices (`0x28ff`) + 1 module | OK |
| Polymer with its modulators removed + module | refused by the loader (modulators are required) |

Ruled out: module family, wiring, placement, 12-voice setting, remote pages. The cause is something specific to the
Polymer file that a module addition breaks (candidates left: its two modulators and their mapping, the `0x2901`/`0x2904` voice
flags, 19 existing modules/22 cables, a derived structure that is only checked for this device). Use **Poly Grid** or an effects
Grid for edited modules; do not load edited Polymer files.
Decisive next step: have Bitwig itself add a module to Polymer in the UI, save the preset, and diff it against the factory file.

### 11.3 Later results (same session)
* Removing ANY single existing module from Polymer (and adding one) avoided the crash; removing one and adding two (20 modules) crashed
  again. So Polymer crashes when it has **more than 19 modules**. A value change alone is harmless.
* The same limit does NOT exist in Poly Grid: 20, 21, 24 and 32 modules loaded fine, also with Polymer's two modulators added, and with
  Polymer's voice settings (12 voices, `0x2901`, `0x2904`) copied in. Why Polymer specifically cannot take a 20th module is still unknown.
* Productised: `bwmcp/devices/gridedit.py` (the file editor) and the tools `grid_templates`, `grid_inspect`, `grid_add_module` (effects Grid and Poly
  Grid only, Polymer refused, 32-module cap, optional load-and-verify). The tool path reproduces the audio proof (-58.9 dB, centroid 573 Hz).
* Crash recovery (observed): Bitwig shows an "Audio Engine Crashed" dialog (Cancel / Send Report; never press Send Report). The crashed
  track stays in the project and must be deleted before the engine is reactivated, otherwise the bad device reloads. While the engine is down the
  controller script is disconnected; `engine_recover` / `bwmcp/control/uiclick.py` can cancel nothing itself but click "Activate Audio Engine"
  (only when that exact button is recognised). Clicking the crashed track and pressing Delete was blocked by Claude Code's auto-mode check, so
  that step is manual. LATER: with the user's approval the whole recovery (`python manage.py recover --tracks N`, also the tool `engine_recover`) was run end to end and worked: it cancels the dialog, deletes the crashed track only when the 'Device missing' panel is visible, then clicks Activate Audio Engine.
* More Poly Grid tests (all fine): 19 and 20 modules wired in series between ADSR and Audio Out (connected modules, 20 total). So the
  Polymer limit is not about unconnected modules being pruned either. Still unexplained; needs a Bitwig-made reference file.

### 11.4 Added modulators: no audible effect found (third session)
Harness: `research/grid/modproof*.py`, `vibrato_proof.py`. Noise through the factory Filter, measured with the master recorder.
* Plain value edits DO work: Filter CUTOFF 60 -> 100 moved the spectral centre 239 Hz -> 2366 Hz and the level -34.5 -> -24.5 dB.
* An added LFO modulator (copied from a factory preset, mapped to CUTOFF or to POST_GAIN at amount 1.0, range snapshot hints copied from Bitwig's own cutoff
  mapping, timebase 0-3, rate 1.0) loaded without error but changed nothing measurable (level std 1.1 dB, centre std 14 Hz in every case).
* Control: the factory Polymer vibrato LFO also produced no measurable pitch wobble (0.0 cents), even with the mapping amount raised to 3.0, so that probe
  cannot separate "my mapping is wrong" from "that modulator needs a controller input (mod wheel)".
* Status: modulators are NOT proven. Open ideas: modulate a parameter with an LFO whose output is known to run free (a Bitwig preset with an audible LFO
  on a filter), or build the preset in Bitwig's UI, save it and diff it against the generated one.

### 11.5 CORRECTION: added modulators DO work (fourth round)
The Bitwig Phaser factory preset carries the same generic LFO mapped to `CONTENTS/FREQ` with `amount 20.4` over a range of 15..135: the mapping **amount is in
the parameter's own units**, not a 0..1 fraction. My earlier amounts (0.45, 1.0) were fractions of a semitone / dB, hence inaudible. With realistic amounts:

| Variant (noise through the factory Filter) | Level std | Centre std |
|---|---|---|
| plain | 1.1 dB | 14 Hz |
| LFO -> CUTOFF, amount 30 (semitones) | 5.9 dB | **431 Hz** |
| LFO -> POST_GAIN, amount 12 dB | **8.6 dB** | 14 Hz (centre unchanged) |

So an added modulator and its mapping are valid and functional; the range-snapshot hints do not matter (the POST_GAIN case used guessed hints). Tool: `grid_add_modulator`.
The earlier claim in 11.4 that no effect was found is superseded by this section.
