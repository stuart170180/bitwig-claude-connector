"""Offline test of actionsdev with a fake bridge (no Bitwig needed): python test_actionsdev.py"""
import actionsdev as A
A.time.sleep = lambda s: None


class Fake:
    def __init__(self):
        self.log = []
        self.tracks = [{"name": n} for n in ("T0", "T1", "T2", "T3")]
        self.groups = []

    def call(self, cmd, **kw):
        self.log.append((cmd, kw))
        if cmd == "get_session":
            return {"tracks": [dict(t, index=i) for i, t in enumerate(self.tracks)]}
        if cmd == "act_groups":
            return self.groups
        if cmd == "action_run" and kw["id"] == "Group":
            self.tracks.insert(0, {"name": "Group 1"})
            self.groups = [{"index": 0, "name": "Group 1", "expanded": True, "children": ["T0", "T2"]}]
        return "ok"


bw = Fake()
r = A.group_tracks(bw, [2, 0], name="Drums")
ids = [k["id"] for c, k in bw.log if c == "action_run"]
assert ids == [A.FOCUS, A.NEXT, A.NEXT, A.TOGGLE, "Group"], ids
assert r["group_name"] == "Drums" or r["group_name"] == "Group 1"
assert ("set_track_name", {"track_index": 0, "name": "Drums"}) in bw.log
try:
    A.select_tracks(Fake(), [9]); raise SystemExit("expected error")
except ValueError:
    pass
print("ok")
