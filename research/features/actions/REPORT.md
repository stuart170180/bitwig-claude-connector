# ACTIONS feature report

Files: `actions.js` (controller script), `actionsdev.py`, `test_actionsdev.py` (offline, passes).

## !! Warning: the open project changed during testing
Partway through, Bitwig's window became "Bitwig Studio - New 1" (an empty project); "Inst 1" and "Audio 2" were gone
(first noticed during a selection-action sweep, when I saw the track list go empty). I did NOT knowingly cause it
(deny-list blocks File New/Open/Close/Quit/project switching; no such action was run by me), but I cannot prove it.
All later tests ran on scratch tracks in that "New 1" project and were deleted; the project is empty and stopped.
The user should check whether their original project is still open in another tab / needs reopening.

## Verified live
- `action_list(filter, limit<=200)` and `action_run(id)` (id or exact name). Deny-list verified (`Close` refused; `action_blocked` lists 40ish:
  all File actions except Save, edit:Delete, project switching, delete_all_*). Reply packets must stay <64 KB, hence the limit cap.
- Category ids differ from actions.txt names: edit, file, document, general, navigation ...
- Multi-track selection: `Track.selectInMixer/selectInEditor/select` are all single-select (last wins); `Extend selection...` actions,
  `Select All`, `moveTracks/copyTracks` insertion points do nothing/aren't usable. What WORKS: `focus_track_header_area`, then
  `move_selection_cursor_to_next_item` (moves invisible cursor) and `Toggle selection of item at cursor`. Observers only show one selected track,
  but the Group action sees the full selection.
- `Group` only acts when the track header area is focused (`focus_track_header_area` first); otherwise silently no-op.
- `group_tracks([i,...], name)`: verified for contiguous and non-contiguous tracks (B1,B3 grouped, B2 left out; then Ungroup, then all three with name "ZZ Grp").
  Children come out contiguous inside the group; verified via `act_groups` (each group track's own child track bank).
  Flat indices: group first, children right after.
- `ungroup(i)`: verified, children return to top level, group removed. Group of a single track also works.
- `act_arr_clip`: focusing the arranger (`focus_or_toggle_arranger`) + `Select All` makes the arranger cursor clip exist (loop 8 beats) after
  record_arrangement created arranger content: arranger clips can be selected this way.
- Export Audio: opens an in-app modal dialog (screenshot confirmed: formats, tracks, time range, OK/Cancel); script keeps answering; `Cancel Dialog` closes it (verified by screenshot).

## Invoked but effect NOT verifiable through the API
- `normalize`, `Consolidate`, `bounce_in_place`, `_pre_fader`, `_post_fader` ran without error on an arranger audio clip (selected as above) and on a
  launcher clip / a selected track. No observable change (track count, clip loop length); meter check inconclusive (peak read 0). The API
  exposes no arranger clip list, gain or audio info, so results cannot be confirmed from the script. Needs the user to eyeball them.
  Bounce on MIDI+instrument tracks not tested (no instrument loaded).

## Not tested / not possible
- `export_midi` (likely a native OS file dialog that Cancel Dialog may not close) - deliberately not run.
- Export Audio cannot be completed unattended: the dialog needs OK click; there is no action for it besides `Dialog: OK` (untested, would write files to the dialog's default folder).
- Moving tracks into groups via InsertionPoint.moveTracks: no effect (tried after-track, child-after, device-chain points).
- Side effects: `focus_or_toggle_*` toggle panels (UI changes); the selection-cursor actions can leave focus in the track header.
- Collapsed groups between first and last selected track break the cursor walk (children skipped); `select_tracks` raises.

## Proposed MCP tools (server.py; import actionsdev, call with `bw`)
- `list_bitwig_actions(filter: str=None, limit: int=50)` - "Search Bitwig's built-in actions by text; shows id, name, blocked flag."
- `run_bitwig_action(action_id: str)` - "Run a Bitwig action on the current selection/focus. Dangerous ones are refused."
- `group_tracks(track_indices: list[int], name: str=None)` - "Group tracks (get_session indices) into a new named group track."
- `ungroup_track(track_index: int)` - "Dissolve a group track, keeping its children."
- `get_groups()` - "List group tracks and their children."
- `select_tracks(track_indices: list[int])` - "Select several tracks, then run_bitwig_action e.g. bounce_in_place."
- `run_action_on_tracks(track_indices: list[int], action_id: str)` - "Select tracks then run an action (results not verifiable; check get_session)."
