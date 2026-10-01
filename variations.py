"""Pattern variations: new versions of a clip for fills, transitions and evolving loops."""
import random

import expert


def variation(notes, length, kind="mutate", amount=0.3, key=None, scale="major", seed=None):
    """kind: mutate (move some notes in pitch/time), sparse (drop notes, keep bar downbeats),
    busy (add quiet ghost notes after hits), fill (last beat becomes a roll over the pattern's pitches),
    syncopate (push some on-beat notes a 16th early). amount 0..1 = how much changes."""
    rng = random.Random(seed)
    out = [dict(n) for n in notes]
    if kind == "mutate":
        for n in out:
            if rng.random() < amount:
                if key:
                    n["pitch"] = expert.randomize_pitch([n], [n], 1, key, scale, rng.randint(0, 10 ** 6))[0]["pitch"]
                else:
                    n["pitch"] += rng.choice([-2, -1, 1, 2])
            if rng.random() < amount / 2:
                n["start"] = max(0.0, min(length - 0.125, n["start"] + rng.choice([-0.25, 0.25])))
    elif kind == "sparse":
        out = [n for n in out if n["start"] % 4 < 1e-6 or rng.random() > amount]
    elif kind == "busy":
        out += [{**n, "start": n["start"] + 0.25, "duration": min(n["duration"], 0.2),
                 "velocity": max(1, n["velocity"] - 45)}
                for n in notes if rng.random() < amount and n["start"] + 0.25 < length]
    elif kind == "fill":
        roll_start = length - 1
        tail = [n for n in out if n["start"] >= max(0.0, length - 4)]
        pitches = sorted({n["pitch"] for n in tail}) or sorted({n["pitch"] for n in out}) or [38]
        out = [n for n in out if n["start"] < roll_start]
        steps = 8 if amount < 0.5 else 16
        for i in range(steps):
            p = pitches[min(len(pitches) - 1, int(i * len(pitches) / steps))]
            out.append({"pitch": p, "start": roll_start + i / steps, "duration": 0.9 / steps,
                        "velocity": min(127, 60 + i * (60 // steps))})
    elif kind == "syncopate":
        for n in out:
            if n["start"] % 1 < 1e-6 and n["start"] % 4 > 1e-6 and rng.random() < amount:
                n["start"] -= 0.25
    else:
        raise ValueError("kind must be mutate, sparse, busy, fill or syncopate")
    seen, result = set(), []
    for n in sorted(out, key=lambda n: (n["start"], n["pitch"])):
        k = (round(n["start"], 4), n["pitch"])
        if k not in seen and 0 <= n["pitch"] <= 127:
            seen.add(k)
            result.append(n)
    return result
