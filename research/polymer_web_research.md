# Polymer 20th-module crash: web research (2026-10-05, subagent, about 7 searches)
Nothing found that answers it directly. No documented module limit for Polymer/Grid; no report of a count-related engine crash; no public .bwpreset layout.
Related reports: Poly Grid preset crashed the engine on 4.2.1 when the wavetable index input was modulated by an LFO (KVR t=579866); release notes 5.0 Beta 9 and 5.1 Beta 5 list crash fixes
for swapping Polymer/Grid modules that are modulated from a higher level or while others are disabled (weak evidence the engine is fragile around modulation/disabled modules).
Possibly useful, unread: acidcat (github.com/hed0rah/acidcat, experimental Bitwig preset inspector), pytwig.
Ranked hypotheses to test on an EMPTY scratch project only: H1 id/index tables sized for 19-20 entries (vary the new module's id); H2 position/layout outside Polymer's fixed layout; H3 module TYPE not allowed in
Polymer (try a trivial type; try 19 modules of the new type); H4 stale length/count field in a parent container at 20 entries; H5 a connection table that changes at 20 (add the 20th module with no cable, then with one).
Note from our own evidence (docs/PRESET_FORMAT.md 11.x): Poly Grid takes 32 added modules, so the limit is Polymer-specific, which favours H1/H3/H4.
