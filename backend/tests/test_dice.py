import unittest

from trpg.dice import roll, roll_percentile

from ._utils import FakeRng


class TestRoll(unittest.TestCase):
    def test_single_die(self):
        r = roll("3d6", rng=FakeRng([1, 2, 3]))
        self.assertEqual(r.total, 6)
        self.assertEqual(r.faces, [1, 2, 3])

    def test_d100(self):
        r = roll("1d100", rng=FakeRng([42]))
        self.assertEqual(r.total, 42)

    def test_percent(self):
        r = roll("d%", rng=FakeRng([100]))
        self.assertEqual(r.total, 100)

    def test_modifier(self):
        r = roll("1d4+2", rng=FakeRng([3]))
        self.assertEqual(r.total, 5)

    def test_negative_modifier(self):
        r = roll("2d6-1", rng=FakeRng([3, 4]))
        self.assertEqual(r.total, 6)

    def test_implicit_count(self):
        r = roll("d8", rng=FakeRng([7]))
        self.assertEqual(r.total, 7)

    def test_invalid_empty(self):
        with self.assertRaises(ValueError):
            roll("", rng=FakeRng([]))


class TestRollPercentile(unittest.TestCase):
    def test_plain(self):
        v, cands = roll_percentile(FakeRng([57]), 0)
        self.assertEqual(v, 57)
        self.assertIsNone(cands)


if __name__ == "__main__":
    unittest.main()
