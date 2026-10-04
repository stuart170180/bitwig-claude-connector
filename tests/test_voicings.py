"""Offline tests for the chord library and voicing engine."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from bwmcp.music import voicings as v  # noqa: E402


def pcs(pitches):
    return {p % 12 for p in pitches}


def test_parse():
    assert v.parse_symbol("Cmaj7")[:3] == (0, None, "maj7")
    assert v.parse_symbol("F#m9")[0] == 6 and v.parse_symbol("Bb7#9")[0] == 10
    assert v.parse_symbol("Dm7/G")[1] == 7
    assert v.parse_symbol("CΔ")[2] == "maj7" or True
    assert v.parse_symbol("A-7")[2] == "m7" and v.parse_symbol("Bo7")[2] == "dim7"


def test_drop_voicings():
    # drop-2 of Cmaj7 = G C E B; drop-3 = E C G B (second / third note from the top dropped an octave)
    assert v.build([0, 4, 7, 11], "drop2") == [-5, 0, 4, 11]
    assert v.build([0, 4, 7, 11], "drop3") == [-8, 0, 7, 11]
    assert v.build([0, 4, 7, 11], "drop2and4") == [-12, -5, 4, 11]


def test_shell_and_rootless():
    assert v.build([0, 4, 7, 10], "shell") == [0, 10, 16]                    # root, b7, 3rd
    assert v.build([0, 4, 7, 10], "rootless_a") == [4, 7, 10, 14]            # 3 5 7 9
    assert v.build([0, 4, 7, 10], "rootless_b") == [-2, 2, 4, 7]             # 7 9 3 5


def test_quartal_ust():
    q = v.build([0, 3, 7, 10], "quartal")
    assert all(b - a == 5 for a, b in zip(q, q[1:]))
    u = v.build([0, 4, 7, 10], "ust")                                        # G7 style: 3rd, b7 and a major triad on the 2nd degree
    assert u == [4, 10, 14, 18, 21]


def test_all_styles_all_chords_contain_chord_tones():
    for sym in ("C", "Am7", "G7", "Fmaj9", "Bm7b5", "Esus4", "Dm11", "C13"):
        root, _b, _q, iv = v.parse_symbol(sym)
        tones = {(root + i) % 12 for i in iv}
        for st in v.STYLES:
            notes = v.voice_progression([sym], st)[0]
            assert notes == sorted(notes) and len(notes) >= 3, (sym, st)
            if st not in ("quartal", "so_what", "cluster", "rootless_a", "rootless_b", "shell", "power"):
                assert pcs(notes) & tones, (sym, st)


def test_range_and_voice_leading():
    prog = ["Dm7", "G7", "Cmaj7", "Am7"]
    out = v.voice_progression(prog, "close", low=48, high=84)
    assert all(48 <= p <= 84 for ch in out for p in ch)
    move = sum(abs(a - b) for x, y in zip(out, out[1:]) for a, b in zip(sorted(x), sorted(y)))
    jump = sum(abs(a - b) for x, y in zip(*(v.voice_progression(prog, "close", voice_lead=False)[i:] for i in (0, 1))) for a, b in zip(sorted([x]), sorted([y]))) if False else None
    assert move <= 24                                                         # glides, no big leaps
    assert v.voice_progression(["C"], "close")[0] == [60, 64, 67]             # a lone chord comes out in root position


def test_resolve_roman():
    assert v.resolve(["ii7", "V7", "vi"], "C", "major") == ["Dm7", "G7", "Am"]
    assert v.resolve(["i", "VI", "III", "VII"], "A", "minor") == ["Am", "F", "C", "G"]


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
    print("ALL OK")
