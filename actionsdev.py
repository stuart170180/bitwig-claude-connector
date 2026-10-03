"""Bitwig built-in actions through the controller script (actions.js): generic action list/run with a deny-list,
group / ungroup tracks, and driving selection-dependent actions (bounce, consolidate, normalize ...).

Bitwig lets a script act only on what is *selected*, and exposes just one selected track to scripts. The trick that
makes multi-selection possible: focus the track header area, move the (invisible) selection cursor with
`move_selection_cursor_to_next_item` and toggle items with `Toggle selection of item at cursor`.
All functions take the `bw` bridge (server.bw)."""
import time

STEP = 0.6          # seconds for Bitwig to follow a selection / action
FOCUS = "focus_track_header_area"
NEXT = "move_selection_cursor_to_next_item"
TOGGLE = "Toggle selection of item at cursor"


def _tracks(bw):
    return bw.call("get_session")["tracks"]


def _run(bw, aid, wait=STEP):
    r = bw.call("action_run", id=aid)
    time.sleep(wait)
    return r


# ---- generic -------------------------------------------------------------------------------------------------
def action_list(bw, filter=None, limit=100):
    """Search Bitwig's ~780 built-in actions (matches category, id and name, case-insensitive). Each result has
    category, id, name and 'blocked' (True = refused by the safety deny-list). Max 200 per call."""
    return bw.call("action_list", filter=filter, limit=limit)


def action_run(bw, action_id):
    """Run a Bitwig action by id (or exact name). Acts on whatever is currently selected / focused in Bitwig.
    Blocked: quit/close/new/open/save-as, project switching, delete-all-automation, generic Delete."""
    return bw.call("action_run", id=action_id)


# ---- selection ---------------------------------------------------------------------------------------------------
def select_tracks(bw, track_indices):
    """Select several tracks at once (any combination, flat get_session indices) so selection-based actions
    (Group, Bounce in Place, ...) act on all of them. Leaves the track header focused. Collapsed groups between the
    first and last index are not supported (their children are skipped by the cursor); raises in that case."""
    idx = sorted(set(int(i) for i in track_indices))
    if not idx:
        raise ValueError("no tracks given")
    tr = _tracks(bw)
    n = len(tr)
    if idx[0] < 0 or idx[-1] >= n:
        raise ValueError(f"track index out of range 0-{n - 1}")
    for g in bw.call("act_groups"):
        if not g["expanded"] and idx[0] <= g["index"] < idx[-1] and g["children"]:
            raise RuntimeError(f"group '{g['name']}' is collapsed; expand it first (children are skipped by the selection cursor)")
    bw.call("act_select", track_index=idx[0])
    time.sleep(STEP + 0.3)
    _run(bw, FOCUS)
    want = set(idx[1:])
    for p in range(idx[0] + 1, idx[-1] + 1):
        _run(bw, NEXT, 0.35)
        if p in want:
            _run(bw, TOGGLE, 0.35)
    return {"selected": [tr[i]["name"] for i in idx]}


# ---- grouping --------------------------------------------------------------------------------------------------
def group_tracks(bw, track_indices, name=None):
    """Group the given tracks (flat get_session indices) into a NEW group track and optionally name it. Bitwig puts
    the tracks next to each other inside the group. Returns the new group's index/name and its children (verified
    from the track bank)."""
    before = {t["name"] for t in _tracks(bw)}
    sel = select_tracks(bw, track_indices)
    _run(bw, "Group", 1.5)
    groups = bw.call("act_groups")
    new = [g for g in groups if g["name"] not in before]
    if not new:
        raise RuntimeError("Group action did not create a group (focus lost? use get_session to check)")
    g = new[0]
    if name:
        bw.call("set_track_name", track_index=g["index"], name=name)
        time.sleep(0.5)
        g = [x for x in bw.call("act_groups") if x["index"] == g["index"]][0]
    return {"group_index": g["index"], "group_name": g["name"], "children": g["children"], "requested": sel["selected"]}


def ungroup(bw, track_index):
    """Ungroup the group track at track_index: its children move out to the parent level and the group track is
    removed."""
    tr = _tracks(bw)
    g = [x for x in bw.call("act_groups") if x["index"] == track_index]
    if not g:
        raise ValueError(f"track {track_index} ({tr[track_index]['name']}) is not a group track")
    bw.call("act_select", track_index=track_index)
    time.sleep(STEP + 0.3)
    _run(bw, FOCUS)
    _run(bw, "Ungroup", 1.5)
    after = {t["name"] for t in _tracks(bw)}
    if g[0]["name"] in after:
        raise RuntimeError("Ungroup did not remove the group")
    return {"ungrouped": g[0]["name"], "children": g[0]["children"]}


def groups(bw):
    """All group tracks with their direct children (names), from the track bank."""
    return bw.call("act_groups")


# ---- selection-based editing actions -----------------------------------------------------------------------------
def run_on_tracks(bw, track_indices, action_id):
    """Select the tracks (flat indices), focus the track header and run an action on them. Works for track-level
    actions (Group, bounce_in_place*, ...). Result must be verified with get_session."""
    select_tracks(bw, track_indices)
    return _run(bw, action_id, 1.5)
