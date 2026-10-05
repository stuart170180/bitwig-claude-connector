"""DRAFT - NOT INSTALLED. MCP tools for Bitwig's popup browser (see DESIGN.md). To wire in: save as bwmcp/tools/browse.py,
import it where the other tool modules are imported, add the names to a group in scripts/make_docs.py, run `python manage.py docs`.
Needs browser_draft.js in the controller script. The browser is asynchronous: every step waits SETTLE and the tools poll."""
import time

from bwmcp.core.bridge import bw, tool

SETTLE = 0.4


def _wait_open(want: bool, tries: int = 15) -> dict:
    st = {}
    for _ in range(tries):
        time.sleep(0.2)
        st = bw.call("browse_status")
        if st.get("open") == want:
            return st
    raise RuntimeError(f"Bitwig's browser did not {'open' if want else 'close'} (status: {st})")


@tool()
def browse_open(track_index: int | None = None, where: str = "end", device_index: int | None = None, content_type: str | None = None) -> dict:
    """Open Bitwig's popup browser at an insertion point WITHOUT touching the screen.
    where: end / start of a track's chain (track_index, default = selected track), or after / before / replace the device at device_index
    on the SELECTED track (select_track first and check list_devices). content_type optionally switches the tab (Device, Preset, ...).
    Always finish with browse_commit or browse_cancel. Returns the browser state (filter columns, result count)."""
    args = {"where": where}
    if track_index is not None:
        args["track_index"] = track_index
    if device_index is not None:
        args["device_index"] = device_index
    bw.call("browse_open", **args)
    _wait_open(True)
    if content_type:
        bw.call("browse_content_type", name=content_type)
        time.sleep(SETTLE)
    return bw.call("browse_status")


@tool()
def browse_columns(column: str, start: int = 0) -> dict:
    """List one filter column of the open browser: location, file_type, category, tag, creator, device_type or device.
    Shows entry names and hit counts from window offset `start` (24 per page; use start to page through big columns)."""
    return bw.call("browse_columns", column=column, start=start)


@tool()
def browse_filter(column: str, value: str | None = None) -> dict:
    """Pick an entry in a filter column by exact name (value=None or '*' clears that column). Narrows the results; call browse_results after."""
    out = bw.call("browse_filter", column=column, value=value)
    time.sleep(SETTLE)
    return {"result": out, "state": bw.call("browse_status")}


@tool()
def browse_results(limit: int = 20, start: int = 0) -> dict:
    """List the browser's current results (name + window slot, 32 per page, `start` pages further). Use the slot with browse_select."""
    return bw.call("browse_results", limit=limit, start=start)


@tool()
def browse_select(slot: int) -> dict:
    """Select one result by its slot from browse_results (loads nothing yet) and confirm it is the browser's cursor result."""
    bw.call("browse_select", slot=slot)
    time.sleep(SETTLE)
    st = bw.call("browse_status")
    return {"selected": st.get("result_cursor"), "total": st.get("result_count")}


@tool()
def browse_commit(expect: str | None = None) -> dict:
    """Load the selected result at the insertion point and close the browser. Pass expect (the name you chose) to refuse when the
    browser's selection differs. Check list_devices afterwards."""
    st = bw.call("browse_status")
    if not st.get("open"):
        raise RuntimeError("no browser session is open")
    cur = st.get("result_cursor")
    if expect and (cur or "").lower() != expect.lower():
        raise RuntimeError(f"selected result is {cur!r}, not {expect!r}; not committing")
    bw.call("browse_commit")
    _wait_open(False)
    time.sleep(1.0)
    return {"loaded": cur}


@tool()
def browse_cancel() -> str:
    """Close the popup browser without loading anything."""
    bw.call("browse_cancel")
    return "cancelled"


@tool()
def browse_load(query_filters: dict, result: str, track_index: int | None = None, where: str = "end",
                device_index: int | None = None, content_type: str | None = None) -> dict:
    """One-shot: open the browser, apply filters ({"creator": "u-he", "category": "Bass"}), pick the first result whose name contains
    `result` (case-insensitive), commit. Cancels the browser on any failure. Stops with the candidate list if nothing matches."""
    browse_open(track_index, where, device_index, content_type)
    try:
        for col, val in query_filters.items():
            bw.call("browse_filter", column=col, value=val)
            time.sleep(SETTLE)
        want = result.lower()
        start = 0
        while True:
            page = bw.call("browse_results", limit=32, start=start)
            for r in page["results"]:
                if want in r["name"].lower():
                    bw.call("browse_select", slot=r["slot"])
                    time.sleep(SETTLE)
                    return browse_commit(expect=r["name"])
            start += 32
            if start >= page["total"]:
                raise RuntimeError(f"no result containing {result!r} ({page['total']} results under these filters)")
    except Exception:
        bw.call("browse_cancel")
        raise
