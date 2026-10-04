# Bitwig Studio user guide (v5.3): what we learned and where to look

The guide itself is copyrighted and kept local (`data/manual/`, not in git). Index it once from the PDF, then ask Claude to use `manual_search` / `manual_section`:

    pip install pymupdf
    python manage.py manual "C:\Users\<you>\Downloads\Bitwig_Studio_User_Guide_en_53.pdf"

Page numbers below are PDF pages (the same numbers `manual_section(page=...)` takes).

## Chapter map
| Topic | Pages | | Topic | Pages |
|---|---|---|---|---|
| Dashboard / settings | 21-46 | | Operators (Chance, Repeats, Occurrence, Recurrence) | 374-388 |
| Concepts | 48-56 | | Notes <-> audio (bounce, slice) | 389-401 |
| Window anatomy | 57-77 | | Projects, groove, export, master recording | 402-427 |
| Arranger + tracks | 78-94 | | MIDI controllers / mappings | 428-442 |
| Browsers | 95-136 | | Nested chains, unified modulation, voice stacking, plug-ins | 443-492 |
| Arranger clips | 137-180 | | The Grid (editor, special connections, signals) | 493-530 |
| Clip launcher | 181-200 | | Tablet | 531-540 |
| Mixer, routing | 201-225 | | Device descriptions (Dynamics 559, EQ 564, Filter 568, Reverb 602, Synth 612, Grid 629) | 541-694 |
| Devices | 226-245 | | Modulators / Grid modules (reference for every module) | 635-694 |
| Automation | 246-272 | | Legacy devices | 695+ |
| Audio events / note events | 273-373 | | | |

## Facts that matter for our Grid and preset work
- **Signal types** (p.504): logic (yellow, >= 0.5 is high), phase (purple, 0..1 wraps), pitch (orange, 0 = C3, +-0.1 per octave), untyped (red/turquoise), secondary untyped (blue).
- **Every Grid signal is stereo and runs at 4x the sample rate**; **modulators are mono at the normal rate** - even inside a Grid (p.507). Modulators are the way to reach a module parameter that has no in-port.
- **Affect Voice Lifetime** (p.507): ADSR/AR/AD/Pluck (on by default), Note In (on), Gate In (off), Audio Out (off, with Silence Threshold + Hold Time). A voice ends only when *all* of them are finished; enabling one can only lengthen notes.
- **Pre-cords** (p.499): wireless connections from the device's note gate/pitch buss to a module (ADSR gate, oscillator retrigger, keyboard tracking). Presets can rely on them, so a missing cable is not always a missing connection.
- **Feedback** is blocked on direct cables; put a **Long Delay** module in the loop (p.503).
- **Thru parameters** (p.498): Poly/FX/Note Grid have Note Thru and Control Thru; Note Grid also Audio Thru. Poly Grid always passes audio through; FX Grid blends with Mix.
- **FX Grid / Poly Grid on an audio track** (p.509): note-triggered voices need a note source. Change *Note Source* in the device Inspector (this also re-routes the I/O modules and pre-cords); *Auto-gate* adds an invisible envelope so a note on opens the voice. True Mono ignores Auto-gate and stays on (right for a normal effect).
- **Voice stacking** works in every voice mode and every Grid device; the *Voice Stack Spread* modulator gives each stack voice different settings (p.484).

## Facts that matter for clips and editing
- **Operators** are per-event settings: Chance (dice), Repeats (rate + curve + velocity end/curve), Occurrence (first/never first/with or without previous/key/channel, Fill on/off), Recurrence (loop-cycle mask of up to 8). The connector already writes them (`write_notes` expert fields -> `NoteStep.setChance/setRepeatCount/setOccurrence/setRecurrence`).
- **Expand** (Clip menu, launcher) prints N cycles of a clip with Operators baked in (keeps Chance/Spread only if asked). **Consolidate** flattens a clip at its current size and keeps randomness unless the clip has a replayable Seed (p.366).
- **Bounce** (p.391-396): source = Pre-FX, Pre-Fader, Post-Fader or Custom (any top-level device output); options bit depth, dither, real-time, in-place. **Bounce In Place** has no dialog, takes Pre-FX, replaces the clip, and turns a note-only track into an audio track (or a *hybrid* track if other note clips remain). Copy the clip first.
- **Slice**: Slice to Multisample / Drum Machine (dialogs: bounce-and-slice or raw; slice at beat marker, onset, audio event, or a grid) and Slice at Repeats (no dialog; each part keeps its other settings).
- **Global groove** (p.416): Shuffle (rate 1/8 or 1/16, amount) and Accent (rate, amount, phase); all automatable from the master track's Transport category, as is tempo.

## What the guide added to the connector (7.6.0)
- `manual_search`, `manual_section` tools and `python manage.py manual <pdf>`.
- `edit_action` gained `slice_in_place`, `slice_at_repeats`, `next_take`, `previous_take`, `toggle_groove`, `unwrap` (all dialog-free actions that exist in Bitwig's action list).

## Not yet used (ideas, each backed by a section above)
- Set a Poly Grid's *Note Source* / Auto-gate so a Poly Grid works on an audio track (p.509) - needs the device Inspector (UI driver).
- Drive Bounce / Slice dialogs with the UI driver (OCR the dialog, pick Source, press OK) so bounce-to-audio and slice-to-drum-machine can run unattended.
- Automate the master track's Transport category (groove shuffle/accent, tempo) with `perform_ramp`.
- Read more of chapter 19 (device descriptions) to fill `data/device_ranges.json` and the preset library.
