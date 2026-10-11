"""Compare Bitwig's public controller-API documentation (installed with Bitwig, resources/doc/control-surface/api) with the method names the
connector's script calls, and list what is still unused. Public documentation only.   python scripts/api_coverage.py"""
import re, glob, collections, os, sys
DOC = r"C:\Program Files\Bitwig Studio\resources\doc\control-surface\api"
idx = open(os.path.join(DOC, "index-all.html"), encoding="utf-8").read()
pat = re.compile(r'<a href="(com/bitwig/extension/controller/api/(\w+)\.html#(\w+)\([^"]*)"[^>]*>(\w+)\(', re.S)
methods = collections.defaultdict(set)
for m in pat.finditer(idx):
    methods[m.group(2)].add(m.group(3))
ours = ""
for f in glob.glob(r"C:\Users\stuar\Documents\Bitwig\bitwig_mcp\bitwig_script\*.js"):
    ours += open(f, encoding="utf-8", errors="ignore").read()
used_names = set(re.findall(r"\.(\w+)\(", ours))
rows = []
for iface, ms in methods.items():
    used = {m for m in ms if m in used_names}
    rows.append((iface, len(ms), len(used), sorted(ms - used)))
rows.sort(key=lambda r: -(r[1] - r[2]))
print("interfaces:", len(rows), "methods:", sum(r[1] for r in rows), "used names:", sum(r[2] for r in rows))
for iface, n, u, unused in rows[:45]:
    print(f"{iface:34s} {u:3d}/{n:3d}  unused: {', '.join(unused[:14])}{' ...' if len(unused) > 14 else ''}")
