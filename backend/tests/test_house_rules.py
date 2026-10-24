import unittest

from trpg.check import coc_check
from trpg.house_rules import CocHouseRules, CriticalRule, FumbleRule

from ._utils import FakeRng


class TestDefaultStandard(unittest.TestCase):
    def test_default_is_standard(self):
        hr = CocHouseRules.standard()
        self.assertIs(hr.critical, CriticalRule.ROLL_1)
        self.assertIs(hr.fumble, FumbleRule.STANDARD)
        self.assertEqual(hr.extreme_divisor, 5)
        self.assertEqual(hr.hard_divisor, 2)

    def test_none_dict_gives_standard(self):
        hr = CocHouseRules.from_dict(None)
        self.assertIs(hr.critical, CriticalRule.ROLL_1)


class TestImportExport(unittest.TestCase):
    def test_from_dict_partial(self):
        hr = CocHouseRules.from_dict({"critical": "roll_le_5"})
        self.assertIs(hr.critical, CriticalRule.ROLL_LE_5)
        self.assertIs(hr.fumble, FumbleRule.STANDARD)  # 未指定回退标准

    def test_roundtrip(self):
        hr = CocHouseRules(
            critical=CriticalRule.ROLL_LE_SKILL_DIV_5,
            fumble=FumbleRule.ROLL_GE_96,
        )
        self.assertEqual(CocHouseRules.from_dict(hr.to_dict()), hr)

    def test_from_json(self):
        hr = CocHouseRules.from_json('{"fumble": "roll_ge_96"}')
        self.assertIs(hr.fumble, FumbleRule.ROLL_GE_96)

    def test_invalid_divisor_order(self):
        with self.assertRaises(ValueError):
            CocHouseRules(extreme_divisor=2, hard_divisor=5)


class TestHouseRuleEffects(unittest.TestCase):
    def test_critical_le_5(self):
        hr = CocHouseRules(critical=CriticalRule.ROLL_LE_5)
        r = coc_check(60, rng=FakeRng([5]), house_rules=hr)
        self.assertEqual(r.degree, "critical_success")

    def test_critical_skill_div_5(self):
        hr = CocHouseRules(critical=CriticalRule.ROLL_LE_SKILL_DIV_5)
        r = coc_check(60, rng=FakeRng([12]), house_rules=hr)
        self.assertEqual(r.degree, "critical_success")

    def test_fumble_ge_96(self):
        hr = CocHouseRules(fumble=FumbleRule.ROLL_GE_96)
        r = coc_check(60, rng=FakeRng([96]), house_rules=hr)
        self.assertEqual(r.degree, "fumble")

    def test_fumble_roll_100_only(self):
        hr = CocHouseRules(fumble=FumbleRule.ROLL_100)
        r = coc_check(49, rng=FakeRng([96]), house_rules=hr)
        self.assertEqual(r.degree, "failure")  # 房规 100 才大失败，96 不算


if __name__ == "__main__":
    unittest.main()
