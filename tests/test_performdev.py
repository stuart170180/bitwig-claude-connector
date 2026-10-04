import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import unittest

from bwmcp.control import performdev as P


class CurveTests(unittest.TestCase):
    def test_endpoints(self):
        for c in P.CURVES:
            if c != "hold":
                self.assertEqual(P.curve(c, 0), 0)
                self.assertEqual(P.curve(c, 1), 1)
        self.assertEqual(P.curve("hold", 0.99), 0)

    def test_monotonic(self):
        for c in ("linear", "exp", "log", "ease", "ease_in", "ease_out"):
            prev = -1
            for i in range(101):
                v = P.curve(c, i / 100)
                self.assertGreaterEqual(v, prev)
                prev = v

    def test_shapes(self):
        self.assertAlmostEqual(P.curve("linear", 0.3), 0.3)
        self.assertAlmostEqual(P.curve("ease", 0.5), 0.5)
        self.assertLess(P.curve("exp", 0.5), 0.5)
        self.assertGreater(P.curve("log", 0.5), 0.5)
        self.assertAlmostEqual(P.curve("exp", 0.5) + P.curve("log", 0.5), 1.0)

    def test_bad_curve(self):
        with self.assertRaises(ValueError):
            P.curve("wobble", 0.5)


class MoveTests(unittest.TestCase):
    def test_value_at(self):
        m = P.volume_ramp(1, 0.2, 0.8, start_bar=1, bars=2)
        self.assertEqual(m["start_beat"], 4)
        self.assertEqual(m["length_beats"], 8)
        self.assertAlmostEqual(P.value_at(m, 0), 0.2)
        self.assertAlmostEqual(P.value_at(m, 8), 0.5)
        self.assertAlmostEqual(P.value_at(m, 12), 0.8)
        self.assertAlmostEqual(P.value_at(m, 99), 0.8)

    def test_descending(self):
        m = P.fade_out(2, 0, 1)
        self.assertAlmostEqual(P.value_at(m, 2), 0.4)
        self.assertEqual(m["to"], 0.0)

    def test_validation(self):
        with self.assertRaises(ValueError):
            P.volume_ramp(1, 0, 1.5)
        with self.assertRaises(ValueError):
            P.move({"kind": "pan", "track": 0}, 0, 1, 0, 0)

    def test_sweep_by_id(self):
        m, sel = P.sweep(3, 0, 7, 0.1, 0.9, bars=2, start_bar=1, curve="exp", by="id")
        self.assertEqual(m["target"], {"kind": "direct", "id": "7"})
        self.assertEqual(sel, {"track": 3, "device": 0})
        self.assertEqual(m["length_beats"], 8)

    def test_sampled_error(self):
        m = P.volume_ramp(0, 0, 1, 0, 1)
        s = [(b / 10, P.value_at(m, b / 10)) for b in range(0, 41)]
        err, n = P.sampled_error(m, s)
        self.assertEqual(err, 0)
        self.assertGreater(n, 5)


if __name__ == "__main__":
    unittest.main()
