# Tool reference

Generated from the running connector (141 tools) by `make_docs.py`. Each entry is the description Claude sees.

## Session & transport

### `get_session(with_clips)`

Overview: tempo, transport, selected track, tracks (index, name, colour, mute/solo/arm, volume, pan, sends) and scenes. with_clips=True also lists filled clip-launcher slots.

### `get_track(track_index)`

Detailed info for one track including sends and launcher clips.

### `health_check()`

Check the Bitwig connection, script version and any API features missing in this Bitwig version. Also reports the connector (Python package) version.

### `transport(action)`

Control playback. action: play, stop, record, undo, redo.

### `set_tempo(bpm)`

Set project tempo in BPM (verified by reading back).

### `set_position(beats)`

Move the play head to a position in beats (4 beats = 1 bar in 4/4).

### `set_metronome(enabled)`

Turn the metronome on or off.

### `get_transport()`

Full transport state: tempo, time signature, arranger loop, punch in/out, arranger record, automation write mode, launch quantization, groove settings and cue markers.

### `set_transport(loop_enabled, loop_start, loop_length, time_signature, punch_in, punch_out, launch_quantization, arranger_record, automation_write, automation_mode)`

Change transport settings; only given fields change. Loop positions in beats. time_signature like '3/4' or '7/8'. launch_quantization: none, 8, 4, 2, 1, 1/2, 1/4, 1/8, 1/16. automation_mode: latch, touch, write. Returns the resulting transport state.

### `set_groove(enabled, shuffle_amount, shuffle_rate, accent_amount)`

Bitwig's global groove. shuffle_amount and accent_amount 0..1 (0.5 shuffle = none, higher = swing). shuffle_rate '1/8' or '1/16'. Returns the groove state.

### `cue_markers(action, index)`

Arranger cue markers. action: list, add (at play head), jump (to marker index).

### `save_project()`

Save the current Bitwig project (same as Ctrl+S).

## Tracks & mixing

### `create_track(kind, position, name, color, instrument)`

Create a track (kind: instrument, audio or effect; position -1 = end), optionally naming and colouring it. instrument: a preset/device name to load (e.g. 'Polysynth', 'Legend 808 Normal Kit', 'Rhodes'; see search_presets). Returns the new track's info. Effect (FX) tracks appear as sends.

### `delete_track(track_index)`

Delete a track.

### `set_track(track_index, name, volume, volume_db, pan, mute, solo, arm, color)`

Change track properties; only given fields change. Returns the track state read back from Bitwig. volume_db sets the fader to an exact dB (e.g. -6); volume is the raw normalized 0..1 alternative. pan: -1 (left) .. 1 (right). color: hex like '#ff8800'.

### `set_send(track_index, send_index, value)`

Set a track's send level to an FX track, normalized 0..1.

### `sidechain_setup(source_tracks, target_tracks, bus_name, genre, depth, send_level, use_send_index, ui)`

Complete sidechain: one FX bus track that carries only the trigger signal, fed from source_tracks (e.g. the kick) through their sends, and a Compressor+ with ducking settings for the genre on every target track (bass, pads, strings ...). genre: house, deep_house, techno, trance, progressive, big_room, dubstep, dnb, hiphop, trap, pop, edm_pop, disco_funk, reggaeton, rock, lofi, ambient (see sidechain_genres). The release follows the project tempo, so it works at any bpm. depth: light, medium or heavy. ui=True also does what the API cannot, by driving Bitwig's screen (see sidechain_source and rename_fx_track): the FX track is renamed to bus_name and each compressor's sidechain source is set to it (pre-fader tap). Bitwig must be on screen for that; any step that fails is reported under `ui` and left in `todo`. use_send_index reuses an existing FX track instead of creating one.

### `sidechain_genres()`

The genre presets sidechain_setup uses: attack, release as a fraction of a beat, ratio, threshold, knee and a note on how that genre uses ducking.

### `compressor_read(track_index, device_index)`

Read a Compressor+ in real units (attack ms, release ms, ratio, threshold dB, knee, make-up, ...). device_index defaults to the first Compressor+ on the track. Bitwig's API does not expose gain reduction, so there is no live GR meter; this shows the settings.

### `compressor_set(track_index, device_index, attack_ms, release_ms, ratio, threshold_db, makeup_db, input_db, knee_pct, mix_pct)`

Set a Compressor+ in real units (ratio as the N in N:1). Finds each value by reading Bitwig's own display text, so the result is what Bitwig shows; returns wanted vs got for each.

### `mix(tracks)`

Set many tracks at once. Each item: {"track_index": int, plus any of name, volume, volume_db, pan, mute, solo, arm, color}. Returns each track's resulting state.

### `select_track(track_index)`

Select a track (device tools act on the selected track).

### `snapshot(action, name, other, include_tempo)`

Mixer snapshots (volume, pan, mute, solo, sends per track; matched by track name). action: save (name), recall (name; include_tempo to restore tempo), list, delete (name), diff (name vs current mix, or vs `other` snapshot). Use for A/B mix comparisons and as a safety net before big changes (save 'before', then recall it to undo everything).

### `auto_name_tracks(track_indices, style, only_default_names, color, analyze_notes, dry_run)`

Rename tracks from what's on them: the loaded preset/instrument, sample or clip names, or (for bare MIDI tracks) the notes themselves (drums vs bass vs chords vs lead). style: smart ('Bass - Rippin' Bass'), role ('Bass'), source ('Rippin' Bass'). color=True also colours by role. only_default_names leaves tracks you've already named alone. dry_run shows the plan without renaming. Duplicate names get numbered. Restores your track selection afterwards.

## Clips & scenes

### `launch(track_index, slot, scene)`

Launch a clip (track_index + slot) or a whole scene (scene).

### `stop_clips(track_index)`

Stop clips on one track, or all clips if track_index is omitted.

### `set_scene_name(scene, name)`

Rename a scene.

### `delete_clip(track_index, slot)`

Delete the clip in a launcher slot.

### `clip_settings(track_index, slot, loop_start, loop_length, loop_enabled, play_start, play_stop, shuffle, accent, launch_mode, launch_quantization, name, color, show_in_editor)`

Read or change a launcher clip's settings: loop start/length (beats), loop on/off, play start/stop, groove shuffle on/off, accent (0..1), launch_mode (default, from_start, continue_or_from_start, continue_or_synced, synced), launch_quantization (default, none, 8, 4, 2, 1, 1/2, 1/4, 1/8, 1/16), name, color (hex). show_in_editor opens it in Bitwig's detail editor. Returns the settings after.

## Writing music

### `write_notes(track_index, slot, notes, length_beats, name)`

Write MIDI notes into a launcher slot (clip created if empty; existing notes replaced). notes: [{"pitch": 60, "start": 0.0, "duration": 0.5, "velocity": 100}], times in beats, resolution 1/32 note.

### `write_drums(track_index, slot, style, bars, fill, swing, humanize, seed)`

Generate a drum loop (GM mapping, matches Bitwig's Drum Machine: kick=36/C1, snare=38, clap=39, closed hat=42, open hat=46). styles: house, techno, hiphop, trap, dnb, breakbeat, rock, funk, reggaeton, garage. fill adds a roll in the last bar; swing 0..1; humanize 0..1.

### `write_bass(track_index, slot, chords, progression, key, scale, style, bars_per_chord, octave, seed)`

Generate a bassline following chords. chords: roman numerals relative to key/scale (['i','VI','III','VII'], 'ii7', 'bVII') or names (['Am','F','C','G']); or a preset progression (pop, sad, jazz, minor_epic, house, andalusian, dark). styles: root, eighths, offbeat, octave, walking, syncopated.

### `write_chords(track_index, slot, chords, progression, key, scale, rhythm, bars_per_chord, octave)`

Generate a voice-led chord progression. Chords as in write_bass. rhythms: sustained, stabs, pulse, arp_up, arp_updown, strum. scales: major, minor, dorian, phrygian, lydian, mixolydian, harmonic_minor, pentatonic_major, pentatonic_minor, blues.

### `write_melody(track_index, slot, chords, progression, key, scale, bars_per_chord, octave, density, seed)`

Generate a chord-aware melody (chord tones on beats, stepwise motion between). density 0..1 controls how busy it is; change seed for a different take.

### `write_euclidean(track_index, slot, layers, steps_per_beat, bars)`

Polyrhythmic Euclidean patterns. layers: [{"pitch": 36, "pulses": 4, "steps": 16, "rotation": 0, "velocity": 110, "accent_first": true, "chance": 1.0}, ...]. Each layer spreads `pulses` hits as evenly as possible over `steps` (each step = 1/steps_per_beat beats), looping to fill `bars`. Different step counts per layer create polymeters (e.g. 3 over 16 against 4 over 16, or 5/12).

### `sketch_song(key, scale, tempo, drum_style, progression, sections, seed, load_instruments)`

Build a whole song sketch in the clip launcher: one scene per section, one track per part. Creates (or reuses by name) instrument tracks Drums, Bass, Chords, Lead, loads a genre-appropriate factory sound on each new track (drum kit, bass, pad/keys, lead), names scenes and writes every clip. sections: [{"name": "Intro", "parts": ["drums", "chords"], "variation": "build"|"alt"}]; default is Intro / Verse / Build / Drop / Breakdown / Drop 2 / Outro. Launch scenes in order to play.

### `make_variation(track_index, slot, to_slot, kind, amount, seed)`

Write a variation of a clip into another slot (for fills, transitions and evolving loops). kind: mutate (shift some notes in pitch/time, kept in the clip's key), sparse (drop notes, keep downbeats), busy (add ghost notes), fill (last beat becomes a roll), syncopate (push hits a 16th early). amount 0..1 = how much changes; change seed for another take.

## Editing & analysing notes

### `get_clip_notes(track_index, slot)`

Read every note in a launcher clip (pitch, start, duration, velocity; beats, 1/32 resolution), plus its loop length and estimated key.

### `edit_clip(track_index, slot, operation, grid, strength, swing, semitones, key, scale, amount, offset, compress, timing, velocity, factor, times, seed)`

Edit an existing clip's notes in place. operations: quantize (grid beats e.g. 0.25 = 1/16, strength 0..1, swing 0..1), humanize (timing beats, velocity), transpose (semitones), scale_correct (key, scale), reverse, stretch (factor: 2 = half speed, 0.5 = double speed), legato, velocity (amount x, offset +, compress 0..1 toward mean), repeat (times: loop the clip content N times), double (= repeat 2). Returns before/after counts.

### `note_expressions(track_index, slot, select, set, ramp, randomize, seed)`

Shape Bitwig per-note expressions on selected notes (they're kept by all other edits). Properties: velocity (1-127), release_velocity (0-127), velocity_spread (0..1), gain (0..1, 0 = default), pan (-1..1), timbre (-1..1), pressure (0..1; Bitwig doesn't report it back, so unverified), transpose (micro-pitch in semitones, e.g. 0.5), chance (0..1 probability), muted (bool), repeat ({"count": 3, "curve": -1..1, "velocity_curve": -1..1, "velocity_end": -1..1}; count 0 = off; ratchets), recurrence ({"length": 4, "mask": 5} = play on cycles 1 and 3 of 4; mask is a bitfield), occurrence ('ALWAYS', 'FIRST', 'NOT_FIRST', 'PREV', 'NOT_PREV', 'PREV_CHANNEL', 'NOT_PREV_CHANNEL', 'PREV_KEY', 'NOT_PREV_KEY', 'FILL', 'NOT_FILL'). set: fixed values; ramp: {"velocity": [40, 120]} across the selection (crescendo, pan sweep...); randomize: {"timbre": 0.3, "velocity": 12} adds +/- amount. select: optional note filter, e.g. {"pitch": [36, 36]} (range) or {"pitches": [36, 38]}, {"start": [0, 8]} beats, {"velocity": [0, 80]}, {"beat": [0, 2]} (beats 1 & 3 of each bar), {"offbeat": true}, {"every": 2, "offset": 1}, {"chance": 0.5}, {"top": true} / {"bottom": true} (highest/lowest note of each chord). Keys combine with AND; omit to edit every note.

### `transform_notes(track_index, slot, operation, select, semitones, beats, intervals, key, scale, axis, rate, pattern, gate, amount, direction, division, length, factor, spread, mode, inversion, accent_pattern, boost, keep, seed)`

Advanced edits on selected notes (per-note expressions are preserved). operations: transpose (semitones), nudge (beats, +/-), delete, mute, unmute, harmonize (intervals in scale steps: [2] = 3rd above, [2, 4] = triad, [-7] = octave below; key/scale, detected if omitted), invert (mirror around axis pitch), arpeggiate (rate beats, pattern up/down/updown/random, gate), strum (amount beats, direction down/up), flam (amount = grace offset), chop (division beats), set_length (length beats, or factor), randomize_pitch (spread steps, in key if given), voicing (mode close/open/drop2/drop3/inversion/spread_octaves, inversion n), accent (accent_pattern of x . - per 16th, boost), thin (keep 0..1 of notes). select: optional note filter, e.g. {"pitch": [36, 36]} (range) or {"pitches": [36, 38]}, {"start": [0, 8]} beats, {"velocity": [0, 80]}, {"beat": [0, 2]} (beats 1 & 3 of each bar), {"offbeat": true}, {"every": 2, "offset": 1}, {"chance": 0.5}, {"top": true} / {"bottom": true} (highest/lowest note of each chord). Keys combine with AND; omit to edit every note.

### `detect_chords(track_index, slot, resolution)`

Name the chords in a clip (with inversions, e.g. 'C/E'), plus the clip's key and Roman numerals. resolution: beats per chord slot (default: per bar, or per half bar when harmony moves faster).

### `transpose_project(semitones, include_drums, track_indices)`

Transpose every MIDI clip in the project (or the given tracks) by semitones, keeping all per-note expressions. Drum tracks (Drum Machine or drum-named) are skipped unless include_drums - transposing drums would swap kit pieces.

### `project_report(analyze_clips, max_clips)`

One-call overview of the whole project: tempo, transport, every track (type, devices and presets, fader/pan/mute/solo, sends, clips) and - with analyze_clips - each MIDI clip's note count, key and chords, plus an overall project key estimate and a mixer summary. Restores your track selection.

## Sounds, samples & bookmarks

### `search_presets(query, kind, limit)`

Search the factory/user preset library and built-in devices by name or pack (e.g. 'pad', '808 kit', 'rhodes', 'EQ+', 'Analog Waves bass'). kind: 'preset' or 'device'.

### `load_preset(name, track_index, where)`

Load a preset or built-in device (Polysynth, Drum Machine, EQ+, Compressor, Reverb...) onto a track by name or file path. where: 'end' (after existing devices) or 'start'. Verified by listing the track's devices afterwards.

### `refresh_preset_index()`

Rescan the disk for presets (after installing packages or saving new presets).

### `search_samples(query, category, kind, bpm, bpm_tolerance, key, pack, limit)`

Search ~14k samples (Bitwig packs, Splice, extra folders). BPM/key/category are parsed from file names. category: kick, snare, clap, hat, cymbal, tom, perc, 808, drum loop, bass, vocal, guitar, piano, pad, synth, strings, brass, fx, other. kind: loop or one-shot. bpm matches half/double time too. key like 'Am', 'F#', 'C'.

### `load_sample(sample, track_index, slot, mode, new_track_name)`

Load a sample (name from search_samples, a bookmark label, or a file path). mode 'clip': put it as an audio clip in a launcher slot (needs an audio track). mode 'sampler': load it into a Sampler instrument on an instrument track (play it with MIDI). If track_index is omitted, a new track of the right type is created.

### `preview_sample(sample, stop)`

Audition a .wav sample through Windows audio (outside Bitwig). stop=True stops playback.

### `sample_folders(add, rescan)`

List the folders the sample index scans; add a folder; or rescan after adding new samples.

### `suggest_samples(category, query, kind, limit, match_key)`

Samples that fit the current project: matches the project tempo (incl. half/double time) and, with match_key, the key detected from your MIDI clips (relative major/minor also accepted). category as in search_samples (drum loop, vocal, bass, synth, ...).

### `bookmark(action, item, label, tags, note, tag, kind, query, remove_tags, track_index, slot, mode)`

Your favourite sounds. action: add (item = preset/device/sample name or file/folder path; optional label, tags, note), list (filter by tag, kind preset|device|sample|folder, or query), tag (item = bookmark label; tags to add, remove_tags, note), remove (item = bookmark label), load (item = bookmark label; presets/devices go onto track_index, samples use slot/mode like load_sample; folders return their samples).

## Devices

### `list_devices(track_index)`

List devices on a track (selects it first if track_index given; otherwise the selected track).

### `get_device(track_index, device_index)`

Show a device's remote-control pages and the 8 parameters on the current page. Optionally selects the track/device first.

### `set_param(value, name, index, track_index, device_index)`

Set a device Remote Control by name (case-insensitive substring like 'cutoff', searched across all pages) or by index 0-7 on the current page. value is normalized 0..1. Returns the new value.

### `set_device_enabled(enabled, track_index, device_index)`

Enable or bypass a device.

### `open_device_browser(track_index)`

Open Bitwig's browser to insert a device at the end of a track's chain (you pick it in Bitwig).

## Deep devices & mid/side EQ

### `device_tree(track_index)`

Every device on a track (-1 = master) including what sits inside nested chains such as the Mid and Side slots of Mid-Side Split. Slow-ish (it selects each device in turn).

### `deep_params(track_index, device_index, slot, slot_index, filter, limit)`

All parameters of one device, not just its 8 remote controls: id, name and normalized 0..1 value. track_index -1 = master. device_index = top-level position. slot = enter a nested slot of that device ('Mid' / 'Side' on Mid-Side Split) and slot_index = which device inside it. filter = name substring.

### `deep_set(track_index, device_index, values, slot, slot_index)`

Set any parameters on a device, nested or not. values: {parameter id or name: normalized 0..1}, ids/names from deep_params. Returns what each parameter is now. For EQ+ use eq_set instead (real units).

### `eq_set(track_index, device_index, bands, slot, slot_index)`

Configure Bitwig's EQ+ in real units, anywhere (top level, master, or inside a Mid-Side Split slot). bands: [{"band": 1-8, "type": "Bell|Low-shelf|High-shelf|Notch|Low-cut 4P|High-cut 2P|Off|...", "freq_hz": 80, "gain_db": -3, "q": 1.0, "enabled": true}]; only given fields change. A fresh EQ+ has every band type Off, so set type for each band you use. Low-cut/High-cut have no gain. Returns all 8 bands as they now stand (omit bands to just read them).

### `device_insert(track_index, device, slot, device_index, where, by_uuid, layer)`

Insert a device (name like 'EQ+' or a file path) on a track (-1 = master). Top level: where = end, start or before (needs device_index). Inside a nested chain: slot = 'Mid'/'Side' and device_index = the top-level Mid-Side Split; the device goes to the end of that slot. by_uuid=True inserts a Bitwig device by name from the built-in catalogue (see device_catalog), no preset file needed. layer = insert at the end of that layer (0-based) of the layer device device_index (FX Layer, Instrument Layer, Drum Machine ...). Returns the tree afterwards.

### `device_delete(track_index, device_index, slot, slot_index)`

Remove a device from any track (-1 = master), including from inside a nested slot (slot + slot_index). Undo in Bitwig brings it back. Returns the tree afterwards.

### `mid_side_eq(track_index, side_lowcut_hz, side_air_db, side_air_hz, mid_bass_cut_db, mid_bass_hz, mid_presence_db, mid_presence_hz, mid_gain_db, side_gain_db)`

Mid/side EQ on a track (-1 = master). Builds a Mid-Side Split with an EQ+ in each of its Mid and Side slots (re-uses ones already there; on the master it goes before the Peak Limiter) and sets: Side = low-cut at side_lowcut_hz (mono-ises the bass; 0 = off) and a high shelf of side_air_db at side_air_hz (widens the top); Mid = bell of mid_bass_cut_db at mid_bass_hz and bell of mid_presence_db at mid_presence_hz (0 dB = band off); mid_gain_db / side_gain_db trim the two halves (+-24 dB). Returns both EQs.

### `mix_audit(track_indices, fix, include_master)`

Walk the project (all tracks, or track_indices) and report every device with its real state (EQ+ bands in Hz/dB/Q), flagging problems: EQ+ bands that have a gain but type Off (they do nothing), EQ+ that is entirely flat or Off, bypassed devices, several compressors stacked on one track, duplicate devices. fix=True applies the safe repairs only: gives gain-but-Off EQ bands a sensible type (shelf at the ends, bell between) and re-enables bypassed devices. Nothing is ever deleted. Takes about a second per device.

### `recipe(action, name, track_index, note, replace)`

Save and recall whole device chains. action: save (capture track_index's Bitwig devices and every parameter under `name`; -1 = master; third-party plugins are skipped), apply (build recipe `name` on track_index, appended after existing devices, or replace=True to clear the track's devices first), list, delete. Recipes live in the repo's recipes/ folder as JSON.

### `ab_test(track_index, device_index, values, seconds, slot, slot_index, keep, target)`

A/B a change by measurement: captures the playing master (play first), applies `values` ({parameter id or name: normalized 0..1}, see deep_params) to a device, captures again, and returns both sets of numbers (LUFS, true peak, crest, width, correlation, side/mid) with the difference. keep=False restores the original values afterwards; keep=True leaves the change in place. Needs live capture (WASAPI) and Bitwig playing.

### `device_catalog(query, limit)`

Search Bitwig's built-in devices (152 known, such as 'Polysynth', 'Poly Grid', 'FX Layer', 'Multiband FX-2') by name. device_insert(..., by_uuid=True) inserts any of them directly, including ones that have no preset file.

### `preset_inspect(preset)`

Look inside a Bitwig preset file (a path, or a name from search_presets): device name, how many modules and modulators it references, and every plain numeric value stored in it (name, occurrence, value). Works on version-0002 presets (device-settings defaults and presets you saved); the factory device, module and modulator files are scrambled and are refused.

### `preset_patch_and_load(preset, values, track_index)`

Change numeric values inside a copy of a preset, then load the copy onto a track (omit track_index to only write the copy; -1 = master). values: {name: number} or {name: {"value": n, "occurrence": k}} using names from preset_inspect, in the preset's own units (PITCH_TRANSPOSE 7 = seven semitones). Same-length edits only: this cannot add modules, cables or modulators. The original preset is never touched; the copy goes in patched_presets/.

## Mastering, metering & monitoring

### `get_levels(seconds)`

Measure peak levels on every track and the master while Bitwig plays (start playback or launch clips first). Meters are Bitwig's 0..1 meter scale; ~1.0 means clipping.

### `gain_stage(target_peak, track_indices, seconds, passes, max_change_db)`

Auto-balance track faders so each track's peak meter lands near target_peak (0..1), leaving master headroom. Needs audio playing (launch a scene first). Iterates `passes` times, measuring and nudging faders; silent or muted tracks are skipped. Returns before/after levels.

### `master_meters(seconds)`

Bitwig's own master meters over a few seconds (works with any audio driver): left/right peak and RMS on Bitwig's 0..1 meter scale plus L/R balance. For LUFS, mid/side and spectrum use analyze_master.

### `mastering_chain(action, style, target, device_index)`

Manage the master-bus chain. action: list (devices + their main controls), build (append a chain: streaming = EQ+ > Compressor+ > Tool > Peak Limiter; club adds Saturator; gentle = EQ+ > Tool > Peak Limiter; the limiter ceiling is set for `target`), remove (device_index), bypass / enable (device_index). Existing master devices are left alone on build.

### `master_control(width_pct, limiter_gain_db, ceiling_db, limiter_release_s, output_gain_db, eq_band_gains_db)`

Set mastering controls by real value (verified from Bitwig's display): stereo width % (Tool 'St. Width', 100 = unchanged, 0 = mono), limiter input gain dB, limiter ceiling dBTP, limiter release s, output gain dB (Tool 'Gain'), and EQ+ band gains {"1": -2.0, "4": 1.5} (bands 1-8). Build the chain first with mastering_chain('build').

### `analyze_master(seconds, source, target, start, show_image)`

Mastering analysis shown directly in the chat (data + a dashboard image): integrated / short-term / momentary LUFS, loudness range, true peak, sample peak, clipping, crest factor, PLR, L/R balance, MID/SIDE levels and width, phase correlation (overall and worst 400 ms), mono-compatibility loss, per-band mid/side (sub, bass, low-mid, high-mid, air), DC offset, and advice vs a target (streaming, spotify, youtube, apple, soundcloud, club, cd, broadcast). source='live' records what's playing right now: through Bitwig's own master recorder (any audio driver, exact timing; play your song first), falling back to Windows loopback if that is unavailable. source=<wav path> analyzes an exported bounce or recording (start/seconds pick a section; seconds=0 = whole file).

### `auto_master(target, seconds, passes, show_image)`

Live loudness/peak mastering loop: plays nothing itself - start your song first. Builds the chain if needed, then measures (live loopback) and adjusts the limiter input gain toward the target LUFS while keeping true peak under the target ceiling, repeating up to `passes` times. Returns before/after numbers and the final dashboard. Needs live capture (Bitwig on WASAPI).

### `compare_reference(reference, mix, seconds, ref_start, mix_start, target, show_image)`

Compare your track against a reference song: loudness, true peak, dynamics (PLR/LRA), stereo width, correlation, energy per band, mid/side per band - with matching suggestions and an overlay chart (level-matched tonal balance, side content, band energy, key numbers). reference: a WAV path (or sample name). mix: 'live' (capture what's playing; needs WASAPI) or a WAV path of your bounce. ref_start/mix_start pick comparable sections (e.g. both choruses).

### `live_monitor(action, target, open_browser)`

Real-time mastering dashboard in your web browser at http://127.0.0.1:8780 - momentary / short-term / integrated LUFS, distance to target, true-peak hold, LRA, PLR, L/R and mid/side meters, phase correlation, stereo width, vectorscope, mid/side spectrum and a 60 s loudness graph, updating ~10x/s. The page also has a pitch tuner, master-chain sliders, advice, a UK time and weather header, and closable panels (Panels menu; layout remembered in the browser). It can start at Windows login (python autostart.py). action: start (launches it in the background if not running, sets the target, opens the browser), reading (current numbers, so Claude can comment on what you're hearing), reset (restart integrated loudness / peak hold for a new pass), target (switch target), stop. Needs Bitwig on a WASAPI ('Windows Audio') driver.

### `check_tuning(source, seconds, start, mode, threshold_cents, show_image)`

Pitch and tuning check, shown in chat. Single-note material (vocal, lead, bass, solo instrument) gets a per-note report: each note's name and cents sharp/flat, vibrato width, worst offenders and advice. Chords and full mixes get the overall tuning offset against A=440 (and the implied A4 frequency) plus a key estimate. source: 'live' (what Bitwig is playing now; needs a WASAPI driver, press play first) or a WAV path / sample name (start/seconds pick a section; seconds=0 = whole file). mode: auto, mono, poly. threshold_cents: how far off counts as out of tune (25 is audible to most ears).

## Arrangement

### `record_arrangement(action, scenes, bars, wait)`

Turn launcher scenes into a real arrangement. Bitwig's API can't place arranger clips directly, so this records them: it starts arranger record and launches each scene on the bar, stopping tracks that have no clip in that scene (so a breakdown really drops the drums). Timing runs inside Bitwig. action: start, status, abort. scenes: scene numbers in song order, repeats allowed ([0, 1, 2, 3, 3, 4, 5, 6]), or dicts {"scene": 3, "bars": 8}; default = every scene that contains clips, in order. bars = bars per scene (sketch_song clips are 4 bars). The playhead restarts at 0 and the song plays out loud in real time; existing arranger content on the recorded tracks is overwritten. wait: block until finished (default: only when it takes under ~40 s; otherwise poll with action='status').

### `perform_plan(moves, total_bars, record, scenes)`

Write real automation by performing it: the script moves parameters in time while Bitwig records the arranger with automation write on, then the lanes replay on their own. Runs in REAL TIME and is audible. moves: [{"param": "volume"|"pan"|"send"|"remote", "track_index": n, "from": 0-1, "to": 0-1, "start_bar": 0, "bars": 2, "curve": linear|exp|log|ease|ease_in|ease_out|hold, "send": 0, "device_index": d, "remote_index": 0-7}]; values are Bitwig's normalized 0..1. Device automation goes through the 8 remote controls (page 0): direct parameters move but are not recordable. All remote moves in one plan must target the same device. Recording overwrites existing lane content. scenes: optional [{"scene": n, "start": beat}] launches during the take.

### `perform_ramp(track_index, param, from_value, to_value, start_bar, bars, curve, send, device_index, remote_index, record)`

One automated move (see perform_plan): param = volume, pan, send (send index) or remote (device_index + remote_index 0-7). Example: a 4-bar filter rise on a synth = param 'remote', device_index 0, remote_index 0 (the first knob on the device's current page), from 0.2 to 0.9. Real time and audible; overwrites existing lane content.

### `perform_status()`

State of a running perform_plan / perform_ramp.

### `perform_abort()`

Stop a running automation performance (turns record and write off).

### `return_to_arrangement()`

Make every track follow the arrangement again. After launching clips, a track keeps playing its launcher clip and ignores the arranger (recorded arranger content is silent) until this is called. record_arrangement now calls it.

### `get_arranger_clip_notes(limit)`

Notes, loop and name of the ARRANGER clip currently selected in Bitwig (select one in the Arrange view first; it reports exists=false when none is focused). Same 1/32 grid as launcher clips. Limitation: it follows Bitwig's own selection and could not be pointed at a clip recorded by record_arrangement from the script, so select the clip by hand.

### `edit_arranger_clip(operation, notes, name, length_beats, semitones)`

Edit the arranger clip currently selected in Bitwig. operation: write (replace its notes with `notes`, optional length_beats), clear, rename (name), transpose (semitones), quantize, duplicate, duplicate_content. Select the clip in the Arrange view first. Not verified against arrangement playback in live tests: read it back with get_arranger_clip_notes.

## MIDI files & references

### `inspect_midi_file(path)`

Summarise a .mid file: tracks (name, note count, channels), tempo map, time signatures, length in beats.

### `import_midi_file(path, track_index, slot, midi_track, name)`

Load a .mid file into a launcher clip. midi_track = which non-empty MIDI track (0, 1, ...), 'all' to merge them, or 'ch10' style to take one channel (ch10 = General MIDI drums). Clip length rounds up to whole bars. The file's tempo is reported but not applied. Waits for Bitwig to finish writing and reports the notes it holds.

### `export_clip_midi(track_index, slot, path)`

Write a launcher clip to a Standard MIDI File at the project tempo (waits for the clip to settle first).

### `add_reference(path, label, start, seconds, note)`

Analyse a reference track (WAV or AIFF; convert MP3/FLAC first) and store it in the reference library under a label: loudness, true peak, crest, loudness range, width, mid/side bands and a 1/3-octave tonal balance.

### `list_references()`

The stored reference tracks with their headline numbers.

### `remove_reference(label)`

Delete a stored reference.

### `reference_target(labels)`

Averaged tonal balance and headline numbers of several references (default: all stored): a target to mix toward.

### `compare_to_library(label, source, seconds, start)`

Compare a mix to a stored reference (or several: comma-separated labels, averaged). source = 'live' (what is playing, needs WASAPI capture) or a WAV/AIFF path. Returns loudness, crest, width and per-band tonal differences (mix minus reference) with plain advice. Use full songs as references: single loops give extreme differences.

## Mix problem-solving

### `masking_report(track_indices, seconds)`

Find frequency clashes between tracks: solos each track in turn while the song plays (audible!), captures it, and scores where two tracks both carry energy in the same band. Returns ranked findings and the EQ cut it would make. Playback must be running. Use a capture of at least one loop length. About 'seconds' + 0.4 s per track.

### `masking_fix(track_indices, seconds, max_fixes, min_score)`

Run masking_report, then apply the proposed EQ cuts for the worst clashes (inserting EQ+ where needed, one band each) and re-measure. Returns what was cut and the clash score before and after; the 'after' number can be noisy if the capture doesn't cover a full loop.

## Bitwig actions & grouping

### `list_bitwig_actions(filter, limit)`

Search Bitwig's ~780 built-in actions (category, id, name, 'blocked' if the safety deny-list refuses it).

### `run_bitwig_action(action_id)`

Run a Bitwig action by id on the current selection or focus. Dangerous ones (quit, close or switch project, delete everything, generic Delete) are refused. Results are not always visible to the script: check get_session.

### `group_tracks(track_indices, name)`

Group tracks (flat get_session indices, any combination) into a new group track and optionally name it. Collapsed groups between the first and last index aren't supported. Verified from the track bank.

### `ungroup_track(track_index)`

Dissolve a group track, keeping its children.

### `get_groups()`

All group tracks with their direct children.

### `select_tracks(track_indices)`

Select several tracks at once so a selection-based action can act on them (then run_bitwig_action).

### `run_action_on_tracks(track_indices, action_id)`

Select the tracks, then run a track-level action on all of them (e.g. bounce_in_place). Effects of bounce, consolidate and normalize cannot be confirmed from the script: check the result in Bitwig.

## Project, window & recording

### `project_state()`

Quick state of the open project: name, whether undo / redo are available, whether the audio engine is active, and whether any track is soloed, muted or armed (handy before a mix audit: a forgotten solo ruins every measurement).

### `undo_redo(action, steps)`

Undo or redo in Bitwig (action: undo or redo), up to 20 steps. Returns the new undo/redo availability.

### `ui_layout(arranger, mixer)`

Show or hide parts of Bitwig's arranger and mixer, or just read them (call with no arguments). arranger keys: cue_markers, follow (playback follow), double_row (tall track rows) can be changed; timeline, launcher, io, fx_tracks are read-only here. mixer keys (all changeable): launcher, crossfade, devices, io, meters, sends. Example: ui_layout(mixer={"meters": True, "io": False}).

### `project_notes(action, notes, genre, mix_target)`

Claude's per-project notebook, stored inside the Bitwig project (it shows in Bitwig's controller settings, so you can read and edit it too). Fields: notes (500 characters), genre, mix_target (e.g. '-14 LUFS'). action: get or set. Use it to remember decisions per song, such as the genre for sidechain_setup or the loudness goal.

### `last_clicked()`

The parameter you last touched in Bitwig (name, value, display text), e.g. after you move a knob and ask 'what is this one?'. Empty name = nothing touched yet in this session.

### `transport_extras(punch_in, punch_out, pre_roll, loop_start, loop_length)`

Read or set punch in/out, count-in pre-roll (none, one_bar, two_bars, four_bars) and the arranger loop range (beats). Call with no arguments to read. Returns the state after a short wait.

### `look_at_bitwig(max_width)`

A picture of Bitwig's window right now, for reading what the API cannot show: FX track names and faders, which sidechain source a compressor uses, gain-reduction and level meters, device displays. Read-only (nothing is clicked, focus does not change). Bitwig must not be minimized.

### `project_file_report(path)`

Read-only report on a Bitwig project FILE, without opening it: the Bitwig version that saved it, the stock devices it uses, audio files it references (and which are missing on disk), plug-ins, presets, and how much disk its folder uses (master recordings, bounces, auto-backups). path = a .bwproject file; default = the most recently changed project in your Documents\Bitwig Studio\Projects. It cannot read the track tree or parameter values.

### `record_master(action, seconds)`

Record Bitwig's own master output to a WAV, no Windows loopback and any audio driver. action: start, stop, status, or capture (record `seconds`, keep the file and return its path; play the song first). The analysis tools (analyze_master and the others with source='live') already use this recorder automatically. Files land in the project's master-recordings folder and can get big; delete the ones you do not need.

### `device_units(track_index, device_index, set)`

Read a device's parameters in real units ('125 ms', '-12.0 dB', '3.08 kHz', ...) and optionally set them in those units. Works for Compressor+, Delay+, Reverb, Peak Limiter, Tool, De-Esser, Gate, Saturator (EQ+ has eq_set). set = {PARAM_ID: number}, ids as in the result, e.g. {"FEEDBACK": 40, "HICUT": 6000}: time in ms, frequency in Hz, otherwise the displayed unit (dB, %). Non-numeric choices (modes, on/off) can only be read here; use deep_set for them.

### `edit_action(action, track_indices)`

Run a common editing command in Bitwig on the current selection (or on track_indices, which are selected first). action: consolidate, split, reverse, normalize, bounce_in_place, bounce_pre_fader, bounce_post_fader, quantize, quantize_audio, quantize_length, quantize_to_key, fade_in_to_here, fade_out_from_here, reset_fades, stretch_to_project_tempo, detect_tempo, merge_duplicate_patterns, zoom_to_fit, transpose_semitone_up/down, transpose_octave_up/down (clips or notes selected in the Arrange view or editor). These act on what is selected in the Arrange view (clips need to be selected there); Bitwig does not report back whether anything changed, so check with get_session or look_at_bitwig.

### `engine_recover(wait_seconds, normal_tracks)`

Bring Bitwig's audio engine back after it crashed. While the engine is down the controller script cannot answer, so this presses Cancel on Bitwig's crash dialog (never Send Report), deletes the crashed track (only when the window clearly shows its 'Device missing' panel), clicks 'Activate Audio Engine' and waits for the script to return. normal_tracks = how many tracks the project had before the crash. Safe to call when everything is fine: it then does nothing.

## Driving the Bitwig window

### `read_window_text(region, contains)`

Read the text currently on Bitwig's screen with OCR (cheaper than a picture): every label with its pixel position. region = [x0, y0, x1, y1] in window pixels to read only part of the screen (the device panel is about [166, 585, 1310, 830]); contains filters the lines. Use it to check values the API cannot report, such as which sidechain source is chosen or an FX track's name.

### `sidechain_source(track_index, source_track, device, device_index, tap)`

Choose which track a device listens to for its sidechain (the one thing the API cannot set), by clicking Bitwig's own selector. track_index = the track the compressor (or gate etc.) is on, device = its name or give device_index, source_track = the trigger track's exact name (e.g. 'Kick'), tap = pre (before its fader, so fader moves do not change the ducking) or post. Works for devices with a 'Device Input' selector in the device panel (Compressor+, Gate, ...). Bitwig must be on screen; takes about 20 seconds (OCR). Verified by reading the screen.

### `rename_fx_track(current_name, new_name)`

Rename an FX (send) track, which the API cannot do: double-clicks its name in the track list, types the new name and checks the screen. current_name = what it is called now (e.g. 'FX 1'). Bitwig must show the Arrange view with the FX track visible.

### `delete_fx_track(name)`

Delete an FX (send) track by name, which the API cannot do: right-clicks it, checks that Bitwig's inspector says 'FX TRACK' with exactly that name (so nothing else can be deleted by mistake), then presses DELETE in the context menu and checks the track is gone. Undo restores it.

### `add_layer(track_index, device_index)`

Add a layer (a parallel chain) to a layer device such as FX Layer or Instrument Layer, which the API cannot do: shows the device on screen and double-clicks its empty layer area (Bitwig's 'Add layer' gesture). Checks the layer count afterwards. Then fill the layers with device_insert(..., layer=N).

### `select_arranger_clip(track_index, clip, limit)`

Select an arranger clip on a track by clicking it in the Arrange view, then read its notes. This is the missing link for clips that record_arrangement recorded (the API can only follow Bitwig's own selection). clip = which clip on that track, counted from the left (0 = the first). Bitwig must show the Arrange view with the track's clips on screen (scroll or zoom first, e.g. edit_action 'zoom_to_fit'). Returns the clip info and notes, or exists=false when no clip is found.

## Device presets

### `device_presets(device)`

The device preset library: for each device (Reverb, Delay+, Compressor+, Saturator, De-Esser, Gate, Peak Limiter, Pitch Shifter, Tool) the preset names with a one-line description and their values (time values written as notes or beats follow the project tempo). Your own saved presets are included.

### `apply_device_preset(track_index, device, preset, as_send, device_index)`

Put a library preset on a track: inserts the device if the track has none (or use device_index to target one) and sets every value in real units, reading what Bitwig shows back. Tempo-based values (reverb sizes, pre-delay) are computed from the project tempo. as_send=True sets the reverb MIX to 100 % wet (for a device used on a send); otherwise the preset's insert mix is used. track_index -1 = master.

### `save_device_preset(track_index, device_index, name, about)`

Save a device's current numeric settings (as Bitwig displays them) as your own preset in the library, under the device's name.

### `layer_chain(track_index, layers, layer_device, device_index)`

Build parallel chains: an FX Layer (or Instrument Layer) whose layers each hold their own devices. layers = one list per layer, e.g. [[], ["Compressor+:parallel_smash", "Saturator:warm"]] = a dry layer plus a compressed and saturated one. An entry is a device name, or 'Device:preset' to also apply a library preset (see device_presets). The layer device is added if the track has none; missing layers are added by clicking Bitwig's screen (the API cannot make layers), so Bitwig must be visible. Returns the resulting tree.

### `parallel_compression(track_index, preset, level_db)`

Parallel compression on a track: an FX Layer with a dry layer (left empty, so the original signal passes) and a layer with a hard-squashed Compressor+ (library preset, default parallel_smash) at 100 % wet, whose level is set with its make-up gain (level_db, relative blend). Needs Bitwig visible (a layer is added by clicking).

## Audio pitch & colour

### `pitch_shift(track_index, semitones, cents, mix_pct, grain_rate_hz)`

Shift the pitch of a whole track with Bitwig's Pitch Shifter (added if the track has none): semitones plus fine cents (+-24 st range). mix_pct 100 = fully shifted, lower blends with the original (a quick harmony/thickener). grain_rate_hz sets the shifter's grain rate. IMPORTANT: the shifter only produces frequencies on a grid equal to its grain rate (measured: at 10 Hz a +1 st shift of a 220 Hz tone landed on 220 or 250 Hz, at 1 Hz it was within 1 Hz). Use 1 to 2 Hz for fine (cents) or exact shifts, 10 Hz or more for big shifts on drums and transients. Works on audio and instrument tracks. Returns what Bitwig shows.

### `fix_tuning(track_index, seconds, threshold_cents, apply)`

Measure how far a track's tuning is from A=440 and correct it. The track is soloed, Bitwig plays for `seconds` (it starts the transport if it is stopped) while the master recorder captures it, the tuning offset in cents is measured on the audio, and when it is off by more than threshold_cents a Pitch Shifter (grain rate 1 Hz, the only setting that keeps cents-level accuracy) is set to the opposite fine-tune. Accuracy is about 1 Hz, so a low note can remain several cents off. apply=False only measures. Needs pitched material (a sample, vocal, chords or a synth), and playback from a clip or the arrangement.

### `colour_schemes()`

The colouring schemes color_tracks understands and the named palettes (genres and moods).

### `color_tracks(scheme, track_indices, base, end, palette)`

Colour tracks in one go. scheme: roles (by what each track is), rainbow, gradient (base -> end), mono (shades of base), warm_cool (warm = drums/bass/FX, cool = pads/keys/leads), palette (cycle a named palette, see colour_schemes). track_indices default = every track (effect tracks and master are not reachable from the API). Returns the colour given to each.

### `color_clips(track_index, color, slots)`

Give a track's launcher clips a colour (hex, e.g. '#ff8800'). slots default = every clip on the track.

## Chords & voicings

### `chord_library()`

Every chord quality chord_voicings / write_voiced_chords understands (with its intervals in semitones from the root), the voicing styles with a one-line description, and the genre -> suggested voicing styles table.

### `suggest_voicing(genre)`

Voicing styles that suit a genre (jazz, neo_soul, lofi, pop, rock, house, deep_house, techno, trance, progressive, big_room, dubstep, dnb, hiphop, trap, ambient, cinematic, funk, reggaeton ...), each with what it sounds like.

### `chord_voicings(chord, styles, center)`

Show one chord (e.g. 'Dm9', 'G13', 'Bb7#9', 'Cmaj7/E') in several voicing styles: note names and MIDI pitches for each. styles default = all. center = the MIDI note the voicing is placed around (60 = middle C).

### `write_voiced_chords(track_index, slot, chords, progression, key, scale, style, rhythm, bars_per_chord, center, low, high, voice_lead, add_bass)`

Write a chord progression into a clip using a voicing style, voice-led for the smallest movement between chords. chords: symbols ('Dm7','G7','Cmaj7') or roman numerals (ii7, V7, I) resolved in key/scale; or progression = a preset name. style: see chord_library (close, open, drop2, drop3, drop2and4, shell, rootless_a, rootless_b, quartal, so_what, ust, cluster, power, pad, spread, neo_soul, edm_stab, supersaw, gospel, triad_stack). rhythm: sustained, stabs, pulse, arp_up, arp_updown, strum. low/high keep every voicing inside a register; add_bass puts the root two octaves down as a bass note.

## Grid patch editing

### `grid_templates()`

The Grid modules that grid_add_module can add (name and category), harvested from Bitwig's factory presets.

### `grid_inspect(base)`

Readable view of a Grid preset: device values, modulators, every module with its parameters, and all cables. base = 'fx' (FX Grid), 'poly' (Poly Grid) or the path of a plain .bwpreset file.

### `grid_add_module(base, module, between, params, x, y, name, load_to_track)`

Add one module to a copy of a Grid preset (the original is never changed). base: 'fx' (FX Grid), 'poly' (Poly Grid) or a plain .bwpreset path. module: a name from grid_templates (e.g. 'Low-pass'). between: [source, destination] module names or ids to wire the new module into the signal path, e.g. ['Audio In', 'Audio Out'] (FX Grid) - the cable from source to destination is replaced by source -> new -> destination. params: {PARAMETER: value} on the new module, e.g. {'CUTOFF': 20} (look at grid_inspect for names and units). x, y: grid cell (default: next free spot). load_to_track: also insert the edited device on that track and check that Bitwig accepted it and the audio engine stayed up. Refuses Polymer files (more than 19 modules crash the audio engine) and anything over 32 modules.

