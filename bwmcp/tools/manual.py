"""Search and read the Bitwig Studio user guide (a local copy, built from the PDF you own; never committed - it is copyrighted).
Build it once with `python manage.py manual <path to the PDF>`, then use manual_search / manual_section from Claude."""
import json
import re

from bwmcp.core import paths
from bwmcp.core.bridge import tool

FILE = paths.DATA / "manual" / "guide53.json"
DEVICES = paths.DATA / "manual" / "devices.json"
_cache = {}


def _guide():
    if "g" not in _cache:
        if not FILE.exists():
            raise RuntimeError("the user guide is not indexed yet: run  python manage.py manual <path to Bitwig_Studio_User_Guide.pdf>")
        _cache["g"] = json.loads(FILE.read_text(encoding="utf-8"))
    return _cache["g"]


def build(pdf: str) -> int:
    """Index a user-guide PDF into data/manual/guide53.json (needs pymupdf). Returns the page count."""
    import pymupdf
    d = pymupdf.open(pdf)
    toc = d.get_toc()
    secs = []
    for i, (lvl, title, pg) in enumerate(toc):
        end = next((p2 for l2, _t, p2 in toc[i + 1:] if l2 <= lvl), d.page_count)
        secs.append({"level": lvl, "title": title.replace("\xa0", " "), "start": pg, "end": max(pg, end)})
    FILE.parent.mkdir(parents=True, exist_ok=True)
    FILE.write_text(json.dumps({"pages": [p.get_text() for p in d], "sections": secs}), encoding="utf-8")
    _build_devices(json.loads(FILE.read_text(encoding="utf-8")))
    _cache.clear()
    return d.page_count


def _build_devices(g):
    """Cut the 'Device Descriptions' chapter (devices, modulators, Grid modules) into one text per entry."""
    pages = g["pages"]
    secs = [s for s in g["sections"] if s["title"].startswith("19.")]
    out = {}
    for i, s in enumerate(secs):
        if s["level"] < 3:
            continue
        title = re.sub(r"^[\d.]+\s*", "", s["title"])
        nxt = next((x for x in secs[i + 1:] if x["level"] <= s["level"]), None)
        end = nxt["start"] if nxt else s["end"]
        txt = "".join(pages[p - 1] for p in range(s["start"], max(s["start"], end) + 1)).replace(" ", " ")
        a = txt.find(title)
        txt = txt[a:] if a >= 0 else txt
        if nxt:
            b = txt.find(re.sub(r"^[\d.]+\s*", "", nxt["title"]), len(title))
            txt = txt[:b] if b > 0 else txt
        parent = next((x["title"] for x in reversed(secs[:i]) if x["level"] == 2), "")
        txt = re.sub(r"\n\d+\.\d+[\d.]*\.?\s*$", "", txt.strip())          # drop the next heading's number left at the end
        out[s["title"]] = {"name": title, "group": re.sub(r"^[\d.]+\s*", "", parent), "page": s["start"], "text": txt}
    DEVICES.write_text(json.dumps(out), encoding="utf-8")


@tool()
def manual_search(query: str, limit: int = 8) -> dict:
    """Search the Bitwig Studio user guide (v5.3). Returns the best-matching pages with a snippet and the section each is in; read more with manual_section.
    Use it to check how a device, modulator, Grid module, shortcut or feature really works before guessing."""
    g = _guide()
    words = [w for w in re.findall(r"\w+", query.lower()) if len(w) > 1]
    if not words:
        raise ValueError("give some words to search for")
    phrase = query.lower().strip()
    scored = []
    for i, text in enumerate(g["pages"]):
        low = text.lower()
        s = sum(min(low.count(w), 5) for w in words) + (6 if phrase in low else 0)
        if all(w in low for w in words):
            s += 10
        if s:
            scored.append((s, i))
    scored.sort(reverse=True)
    out = []
    for s, i in scored[:limit]:
        text = g["pages"][i]
        k = text.lower().find(words[0])
        snippet = " ".join(text[max(0, k - 120):k + 260].split())
        sec = next((x["title"] for x in reversed(g["sections"]) if x["start"] <= i + 1 <= x["end"]), "")
        out.append({"page": i + 1, "section": sec, "score": s, "snippet": snippet})
    return {"query": query, "hits": out}


@tool()
def manual_section(title: str | None = None, page: int | None = None, pages: int = 3, max_chars: int = 12000) -> str:
    """Read part of the user guide: either a section by (part of) its title, e.g. 'Operators', 'Polymer', 'Unified Modulation System',
    or `pages` pages starting at a page number. Long text is cut at max_chars (ask for a later page to continue)."""
    g = _guide()
    if title:
        want = title.lower()
        cands = [s for s in g["sections"] if want == s["title"].lower()] or [s for s in g["sections"] if want in s["title"].lower()]
        if not cands:
            raise ValueError(f"no section titled like '{title}'")
        s = min(cands, key=lambda x: x["end"] - x["start"] if x["end"] > x["start"] else 1)
        first, last = s["start"], max(s["start"], s["end"] - 1)
        head = f"[{s['title']}  pages {first}-{last}]\n"
    elif page:
        first, last = page, min(len(g["pages"]), page + pages - 1)
        head = f"[pages {first}-{last}]\n"
    else:
        raise ValueError("give title or page")
    body = "\n".join(g["pages"][p - 1] for p in range(first, last + 1))
    return head + (body if len(body) <= max_chars else body[:max_chars] + f"\n... cut; continue from page {first + max(1, int(len(body[:max_chars]) / max(1, len(body)) * (last - first + 1)))}")


@tool()
def device_manual(name: str, max_chars: int = 9000) -> str:
    """What the user guide says about a Bitwig device, modulator or Grid module (e.g. 'Compressor+', 'Delay+', 'LFO', 'Wavefolder', 'Ø Shift').
    Gives its description, modes and parameter meanings. Several matches are listed by name first so you can ask again with the exact one."""
    if not DEVICES.exists():
        _guide()
        raise RuntimeError("run  python manage.py manual <pdf>  again to build the device texts")
    d = json.loads(DEVICES.read_text(encoding="utf-8"))
    want = name.strip().lower()
    exact = [v for v in d.values() if v["name"].lower() == want]
    hits = exact or [v for v in d.values() if want in v["name"].lower()]
    if not hits:
        raise ValueError(f"nothing called '{name}' in the guide's device chapter")
    if len(hits) > 1 and not exact:
        listing = [f"  {v['name']}  ({v['group']}, p.{v['page']})" for v in hits[:40]]
        return "several matches, ask again with one:\n" + "\n".join(listing)
    v = hits[0]
    t = v["text"]
    head = f"[{v['name']} - {v['group']} - page {v['page']}]\n"
    return head + (t if len(t) <= max_chars else t[:max_chars] + "\n... cut")


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        sys.exit("usage: python manage.py manual <path to the Bitwig user guide PDF>")
    print(f"indexed {build(sys.argv[1])} pages into {FILE}")
