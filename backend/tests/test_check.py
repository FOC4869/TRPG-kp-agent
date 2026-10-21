import unittest

from trpg.check import coc_check

from ._utils import FakeRng


def check(skill, roll_value, **kwargs):
    """以固定出目执行一次检定。"""
    return coc_check(skill, rng=FakeRng([roll_value]), **kwargs)


class TestStandardDegrees(unittest.TestCase):
    def test_critical_is_roll_1(self):
        self.assertEqual(check(60, 1).degree, "critical_success")

    def test_extreme_boundary(self):
        # 60 // 5 == 12
        self.assertEqual(check(60, 12).degree, "extreme_success")

    def test_hard_boundary(self):
        # 60 // 2 == 30
        self.assertEqual(check(60, 30).degree, "hard_success")

    def test_regular_boundary(self):
        self.assertEqual(check(60, 60).degree, "regular_success")

    def test_failure(self):
        self.assertEqual(check(60, 61).degree, "failure")

    def test_critical_outranks_extreme(self):
        self.assertEqual(check(60, 1).degree, "critical_success")

    def test_success_flag(self):
        self.assertTrue(check(60, 1).success)
        self.assertFalse(check(60, 61).success)


class TestStandardFumble(unittest.TestCase):
    def test_low_skill_96_is_fumble(self):
        self.assertEqual(check(49, 96).degree, "fumble")

    def test_low_skill_100_is_fumble(self):
        self.assertEqual(check(49, 100).degree, "fumble")

    def test_high_skill_96_is_not_fumble(self):
        self.assertEqual(check(50, 96).degree, "failure")

    def test_high_skill_100_is_fumble(self):
        self.assertEqual(check(50, 100).degree, "fumble")

    def test_100_fumble_overrides_success_at_skill_100(self):
        self.assertEqual(check(100, 100).degree, "fumble")


class TestBonusDice(unittest.TestCase):
    def test_bonus_takes_min(self):
        # units=5, tens=[7,4] -> 候选 [75,45] -> 奖励取 45
        res = coc_check(60, bonus_dice=1, rng=FakeRng([5, 7, 4]))
        self.assertEqual(res.roll, 45)
        self.assertEqual(res.candidates, [75, 45])

    def test_penalty_takes_max(self):
        res = coc_check(60, bonus_dice=-1, rng=FakeRng([5, 7, 4]))
        self.assertEqual(res.roll, 75)

    def test_00_maps_to_100(self):
        # units=0, tens=[0,9] -> 候选 [100, 90]
        res = coc_check(60, bonus_dice=1, rng=FakeRng([0, 0, 9]))
        self.assertEqual(res.roll, 90)
        self.assertEqual(res.candidates, [100, 90])
        res2 = coc_check(60, bonus_dice=-1, rng=FakeRng([0, 0, 9]))
        self.assertEqual(res2.roll, 100)


if __name__ == "__main__":
    unittest.main()
