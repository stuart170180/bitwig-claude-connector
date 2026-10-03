"""One-off: wire insert-by-UUID, device_catalog, preset_inspect and preset_patch_and_load into the connector."""
import shutil
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DEEPJS = Path.home() / "Documents/Bitwig Studio/Controller Scripts/BitwigMCP/deep.js"


def edit(path, pairs):
    s = Path(path).read_text(encoding="utf-8")
    nl = "\r\n" if "\r\n" in s else "\n"
    for a, b in pairs:
        a, b = a.replace("\n", nl), b.replace("\n", nl)
        assert a in s, (str(path), a[:60])
        s = s.replace(a, b, 1)
    Path(path).write_text(s, encoding="utf-8", newline="")


shutil.copy(REPO / "research/device_uuids.json", REPO / "bitwig_device_ids.json")

edit(DEEPJS, [('      case "deep_delete":', '''      case "deep_insert_uuid": {
         // Insert any Bitwig device by UUID (no file needed): top level end/start/before/after, or the end of a slot.
         var uid = java.util.UUID.fromString(String(need(a, "uuid"))), wh = a.where || "end";
         if (wh === "slot_end") {
            if (a.slot) deepSlot.selectSlot(String(a.slot));
            deepSlot.endOfDeviceChainInsertionPoint().insertBitwigDevice(uid);
         } else if (wh === "after") cursorDevice.afterDeviceInsertionPoint().insertBitwigDevice(uid);
         else if (wh === "before") cursorDevice.beforeDeviceInsertionPoint().insertBitwigDevice(uid);
         else if (wh === "start") cursorTrack.startOfDeviceChainInsertionPoint().insertBitwigDevice(uid);
         else cursorTrack.endOfDeviceChainInsertionPoint().insertBitwigDevice(uid);
         return "ok";
      }
      case "deep_delete":''')])

edit(REPO / "deepdev.py", [
    ('    def insert(self, track_index, device, slot=None, where="end", device_index=None):',
     '    def insert(self, track_index, device, slot=None, where="end", device_index=None, by_uuid=False):'),
    ('        path = presets.resolve(device, None)\n', '        ref = self._uuid(device) if by_uuid else presets.resolve(device, None)\n'),
    ('''            args = {"path": path}
            if where == "start":''', '''            if by_uuid:
                bw.call("deep_insert_uuid", uuid=ref, where="start" if where == "start" else "end")
                time.sleep(1.2)
                return
            args = {"path": ref}
            if where == "start":'''),
    ('            bw.call("deep_insert_file", where="slot_end", path=path)',
     '''            if by_uuid:
                bw.call("deep_insert_uuid", uuid=ref, where="slot_end")
            else:
                bw.call("deep_insert_file", where="slot_end", path=ref)'''),
    ('    def delete(self,', '''    @staticmethod
    def _uuid(name):
        import json
        ids = json.load(open(Path(__file__).resolve().parent / "bitwig_device_ids.json", encoding="utf-8"))
        hits = [u for u, n in ids.items() if n.lower() == name.lower()]
        if len(hits) != 1:
            raise ValueError(f"no single Bitwig device named {name!r} (use device_catalog)")
        return hits[0]

    def delete(self,'''),
    ('import math\nimport time\n', 'import math\nimport time\nfrom pathlib import Path\n'),
])

NEW_TOOLS = '''
import presetpatch


@tool()
def device_catalog(query: str = "", limit: int = 40) -> dict:
    """Search Bitwig's built-in devices (152 known, such as 'Polysynth', 'Poly Grid', 'FX Layer', 'Multiband FX-2') by
    name. device_insert(..., by_uuid=True) inserts any of them directly, including ones that have no preset file."""
    ids = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "bitwig_device_ids.json"), encoding="utf-8"))
    q = query.lower()
    rows = sorted((n, u) for u, n in ids.items() if n != "?" and q in n.lower())
    return {"count": len(rows), "devices": [{"name": n, "uuid": u} for n, u in rows[:limit]]}


@tool()
def preset_inspect(preset: str) -> dict:
    """Look inside a Bitwig preset file (a path, or a name from search_presets): device name, how many modules and
    modulators it references, and every plain numeric value stored in it (name, occurrence, value). Works on
    version-0002 presets (device-settings defaults and presets you saved); the factory device, module and modulator
    files are scrambled and are refused."""
    return presetpatch.inspect(preset if os.path.isfile(preset) else presets.resolve(preset, "preset"))


@tool()
def preset_patch_and_load(preset: str, values: dict, track_index: int | None = None) -> dict:
    """Change numeric values inside a copy of a preset, then load the copy onto a track (omit track_index to only write
    the copy; -1 = master). values: {name: number} or {name: {"value": n, "occurrence": k}} using names from
    preset_inspect, in the preset's own units (PITCH_TRANSPOSE 7 = seven semitones). Same-length edits only: this
    cannot add modules, cables or modulators. The original preset is never touched; the copy goes in patched_presets/."""
    src = preset if os.path.isfile(preset) else presets.resolve(preset, "preset")
    dst, report = presetpatch.patch(src, values)
    out = {"patched_copy": dst, "changes": report}
    if track_index is not None:
        if track_index == -1:
            bw.call("select_master")
        else:
            bw.call("select_track", track_index=track_index)
        time.sleep(0.7)
        bw.call("insert_file", path=dst)
        time.sleep(1.2)
        out["devices"] = bw.call("list_devices")["devices"]
    return out

'''
edit(REPO / "server.py", [
    ('if __name__ == "__main__":', NEW_TOOLS + 'if __name__ == "__main__":'),
    ('''                  where: str = "end") -> dict:
    """Insert a device''', '''                  where: str = "end", by_uuid: bool = False) -> dict:
    """Insert a device'''),
    ('''Mid-Side Split; the device goes to the end of that slot. Returns the tree afterwards."""
    deep.insert(track_index, device, slot, where, device_index)''',
     '''Mid-Side Split; the device goes to the end of that slot. by_uuid=True inserts a Bitwig device by name from the
    built-in catalogue (see device_catalog), no preset file needed. Returns the tree afterwards."""
    deep.insert(track_index, device, slot, where, device_index, by_uuid)'''),
])
edit(REPO / "make_docs.py", [('"mid_side_eq", "mix_audit", "recipe", "ab_test"]),',
                              '"mid_side_eq", "mix_audit", "recipe", "ab_test", "device_catalog",\n                                    "preset_inspect", "preset_patch_and_load"]),')])
print("ok")
