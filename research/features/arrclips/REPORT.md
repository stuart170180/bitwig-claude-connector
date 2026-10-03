# Arranger cursor clip experiment

Code: `Controller Scripts/BitwigMCP/arrangerclips.js` (`initArrClips`, `handleArrClips`; commands arrclip_info, arrclip_refresh, arrclip_notes, arrclip_set_name, arrclip_clear, arrclip_write, arrclip_op[duplicate, duplicate_content, show_in_editor, quantize, transpose, launch, return_to_arrangement]).

## Integration (BitwigMCP.control.js)
1. top: `load("arrangerclips.js");`
2. in init(), after `initActions();`: `initArrClips();`
3. handler chain, before `throw "unknown command"`: `r = handleArrClips(cmd, a); if (r !== undefined) return r;`

## Verdicts
VERIFIED LIVE
- `createArrangerCursorClip` works. It reports nothing (exists=false) until the arranger panel is focused (`focus_or_toggle_arranger`, it toggles); then exists=true with a track (`getTrack()`), loop/play start/stop.
- Read: the scroll-away refresh trick works; notes written into it read back exactly (pitch 72 etc.). Write/clear (setStep/clearSteps/loop length) work and read back. duplicate()/duplicateContent() act on it (loop 3 -> 6 -> 12).
- Tracks that had a launcher clip launched keep playing the launcher until `returnToArrangement()` (added as op return_to_arrangement); without it recorded arranger content is silent. record_arrangement leaves tracks in this state.
NOT ACHIEVED
- Launcher-vs-arranger comparison: launcher clip B (pitches 72-79) read correctly via get_clip_notes, but the arranger cursor clip always showed an EMPTY clip (loop_start 1, loop_length 3, play 1..4) after recording clip A (36-43), whatever I tried: select_track, focus arranger, Select All, Select first/next/last item, item left/right, move cursor + select_item_at_cursor, open_in_editor. Writes/clears on it did NOT change what plays back from the arrangement (metering over beats 0-20 identical, sound from ~beat 4 to 9). So this cursor clip is a real, editable clip object but I could not make it follow the clip that record_arrangement recorded. It also stayed bound to its track when other tracks were selected (stale selection).
- Copy/Paste actions ran without observable effect. No launcher->arranger move/copy found.
- Cause unknown (guess: it needs a real mouse selection of an arranger clip, or recorded clips differ from what the cursor binds to). Earlier worker saw loop 8 beats on an audio clip with the same route, so selection can work in some states.
UNVERIFIED: whether a user-clicked arranger clip is picked up (expected yes by the API docs).

## Proposed MCP tools (only worthwhile if selection is solved)
- `get_arranger_clip_notes(track_index=None)` -> {exists, track, loop_start, loop_length, notes}
- `edit_arranger_clip(operation, notes=None, name=None, length_beats=None)` (write, clear, rename, transpose, quantize)
- helper `return_to_arrangement()` is useful now (verified).

Cleanup: all ZZ tracks deleted, transport stopped, record off, actions.js byte-identical to actions.js.orig.
