import sys
from pathlib import Path
_R = Path(__file__).resolve()
while not (_R / "server.py").exists(): _R = _R.parent
sys.path[:0] = [str(_R), str(_R / "research")]
import json, time
from bwlock import hold
import server
bw = server.bw
c = bw.call
LOG = _R / "research/discoveries/FULL_LOG.md"
N = [0]
def ev(code):
    return c("px_eval", code=code)
def log(title, code, result, verdict, learned=""):
    N[0] += 1
    with open(LOG, "a", encoding="utf8") as f:
        f.write(f"\n### {title}\n- Verdict: **{verdict}**\n- Call/code: `{code}`\n- Result: `{str(result)[:1500]}`\n" + (f"- Learned: {learned}\n" if learned else ""))
def T(title, code, learned=""):
    try:
        r = ev(code); log(title, code, r, "worked", learned); print(title, "->", str(r)[:300]); return r
    except Exception as e:
        log(title, code, e, "failed", learned); print(title, "FAIL", str(e)[:300]); return None
