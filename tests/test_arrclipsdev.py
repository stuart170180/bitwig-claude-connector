import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
import arrclipsdev as m

class Fake:
    def __init__(self): self.calls = []
    def call(self, cmd, **kw):
        self.calls.append((cmd, kw))
        if cmd == "arrclip_notes": return {"notes": [{"pitch": 60}], "total": 1, "offset": kw.get("offset", 0)}
        return "ok"

def test_notes_and_write():
    m.SETTLE = 0
    f = Fake()
    assert m.arrclip_notes(f)["notes"][0]["pitch"] == 60
    m.arrclip_write(f, [{"pitch": 1, "start": 0}])
    assert f.calls[0][0] == "arrclip_refresh" and f.calls[-1][0] == "arrclip_write"

if __name__ == "__main__":
    test_notes_and_write(); print("ok")
