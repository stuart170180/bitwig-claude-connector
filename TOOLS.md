# Tool reference

Generated from the running connector (72 tools) by `make_docs.py`. Each entry is the description Claude sees.

## Session & transport

### `get_session(with_clips)`

Overview: tempo, transport, selected track, tracks (index, name, colour, mute/solo/arm, volume, pan, sends) and scenes. with_clips=True also lists filled clip-launcher slots.

### `get_track(track_index)`

Detailed info for one track including sends and launcher clips.

### `health_check()`

Check the Bitwig connection, script version and any API features missing in this Bitwig version.

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

### `device_insert(track_index, device, slot, device_index, where)`

Insert a device (name like 'EQ+' or a file path) on a track (-1 = master). Top level: where = end, start or before (needs device_index). Inside a nested chain: slot = 'Mid'/'Side' and device_index = the top-level Mid-Side Split; the device goes to the end of that slot. Returns the tree afterwards.

### `device_delete(track_index, device_index, slot, slot_index)`

Remove a device from any track (-1 = master), including from inside a nested slot (slot + slot_index). Undo in Bitwig brings it back. Returns the tree afterwards.

### `mid_side_eq(track_index, side_lowcut_hz, side_air_db, side_air_hz, mid_bass_cut_db, mid_bass_hz, mid_presence_db, mid_presence_hz, mid_gain_db, side_gain_db)`

Mid/side EQ on a track (-1 = master). Builds a Mid-Side Split with an EQ+ in each of its Mid and Side slots (re-uses ones already there; on the master it goes before the Peak Limiter) and sets: Side = low-cut at side_lowcut_hz (mono-ises the bass; 0 = off) and a high shelf of side_air_db at side_air_hz (widens the top); Mid = bell of mid_bass_cut_db at mid_bass_hz and bell of mid_presence_db at mid_presence_hz (0 dB = band off); mid_gain_db / side_gain_db trim the two halves (+-24 dB). Returns both EQs.

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

Mastering analysis shown directly in the chat (data + a dashboard image): integrated / short-term / momentary LUFS, loudness range, true peak, sample peak, clipping, crest factor, PLR, L/R balance, MID/SIDE levels and width, phase correlation (overall and worst 400 ms), mono-compatibility loss, per-band mid/side (sub, bass, low-mid, high-mid, air), DC offset, and advice vs a target (streaming, spotify, youtube, apple, soundcloud, club, cd, broadcast). source='live' records what's playing right now through Windows loopback (play your song first; needs Bitwig on a WASAPI/'Windows Audio' driver, not exclusive ASIO). source=<wav path> analyzes an exported bounce or recording (start/seconds pick a section; seconds=0 = whole file).

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

