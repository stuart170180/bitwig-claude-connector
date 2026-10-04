# Chords and voicings

Code: `bwmcp/music/voicings.py` (library and engine), `bwmcp/tools/chords.py` (tools), `tests/test_voicings.py`.
Tools: `chord_library`, `suggest_voicing`, `chord_voicings`, `write_voiced_chords`.

## Chord library
44 qualities: triads and sus chords, 6, 6/9, maj7/9/13/7#11, add9, minor 6/7/9/11/13/maj7, dominant 7/9/11/13 with b9, #9, b5, #5, #11, b13, alt and sus,
diminished, half-diminished, augmented, power chords. Symbols accept the usual aliases (`M7`, `Maj7`, `-7`, `min9`, `m7-5`, `o7`, `+`, slash bass `Dm7/G`).
Roman numerals (I, ii7, V7, bVII, i) are resolved diatonically in the given key and scale.

## Voicing styles (20)
| Style | Construction | Use |
|---|---|---|
| close / open | stacked tones; open lifts every second note an octave | everything / pads |
| drop2, drop3, drop2and4 | second, third, (second and fourth) note from the top of a close 4-note chord dropped an octave | jazz piano and guitar comping |
| shell | root, 7th, 3rd | bebop, funk, leaves room for the melody |
| rootless_a / rootless_b | 3 5 7 9 and 7 9 3 5 (Bill Evans) | piano with a bass player |
| quartal, so_what | stacked fourths; three fourths plus a major third on top | modern jazz, ambient |
| ust | upper-structure triad (major triad a whole tone above the root) over the dominant's 3rd and 7th | tension on dominants |
| cluster, power | tight seconds; root-fifth-octave | dense textures; rock, big room |
| pad, spread | low root plus the chord; root and fifth low with tensions above | warm / cinematic pads |
| neo_soul | root, 7th, then 3 5 9 above | neo-soul, lo-fi keys |
| edm_stab, supersaw | octave root with a triad; doubled root with a triad and upper triad | house/techno stabs; trance |
| gospel | open 6/9 and 9 colours, third on top | gospel, R&B |
| triad_stack | triad with the same triad above in another inversion | bright layered synths |

Genre suggestions (`suggest_voicing`): jazz drop2/rootless/shell/ust; neo_soul neo_soul/rootless/gospel; lofi neo_soul/rootless_b/shell; pop open/pad/close;
rock power; house edm_stab/pad; deep_house neo_soul/rootless_a; techno edm_stab/power/cluster; trance supersaw/pad/triad_stack; hiphop and trap shell/cluster/neo_soul;
ambient and cinematic spread/quartal/cluster.

## Voice leading
`voice_progression` builds every candidate voicing (inversions where the style allows it, three octaves, inside `low`..`high`) and picks the path through the
whole progression with the smallest total movement (dynamic programming), a smooth top line and similar density. A lone chord comes out in root position.

## Sources used for the definitions
- Drop-2 voicings: second note from the top of a close 4-note chord dropped an octave (pianowithjonny.com, "Jazz Piano Comping With Two Hand Voicings").
- Overview of shell, drop, quartal, rootless and upper-structure voicings: learnjazzstandards.com ("Chord Voicings Crash Course"), jenslarsen.nl ("Jazz Chord Voicings: the 9 types").
- Neo-soul 9th voicings: pianowithjonny.com ("4 Steps to Play Neo Soul Chords on Piano").
- Progressions that work across house, techno, trance, trap, drum and bass and pop: edmtips.com.
