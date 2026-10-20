import unittest

from trpg.rules import (
    DEFAULT_SKILLS,
    compute_derived,
    damage_bonus,
    improve,
    improvement_increases,
    insanity_thresholds,
    movement_rate,
    skill_default,
)

RICHARD = {"STR": 65, "CON": 45, "DEX": 45, "APP": 65, "POW": 55, "INT": 75, "SIZ": 60, "EDU": 75}


class TestDerived(unittest.TestCase):
    def test_matches_richard_sheet(self):
        # 与秋叶EXODUS 角色卡上理查德的派生值逐项一致
        d = compute_derived(RICHARD, age=39)
        self.assertEqual(d.hp_max, 10)
        self.assertEqual(d.mp_max, 11)
        self.assertEqual(d.san_start, 55)
        self.assertEqual(d.san_max, 99)
        self.assertEqual(d.mov, 8)
        self.assertEqual(d.db, "+1D4")
        self.assertEqual(d.build, 1)
        self.assertEqual(d.major_wound, 5)

    def test_san_max_reduced_by_mythos(self):
        d = compute_derived(RICHARD, cthulhu_mythos=10)
        self.assertEqual(d.san_max, 89)


class TestDamageBonus(unittest.TestCase):
    def test_table_boundaries(self):
        self.assertEqual(damage_bonus(30, 30), ("-2", -2))   # 60
        self.assertEqual(damage_bonus(40, 30), ("-1", -1))   # 70
        self.assertEqual(damage_bonus(40, 45), ("0", 0))     # 85
        self.assertEqual(damage_bonus(65, 60), ("+1D4", 1))  # 125
        self.assertEqual(damage_bonus(80, 85), ("+1D6", 2))  # 165
        self.assertEqual(damage_bonus(100, 105), ("+2D6", 3))  # 205
        self.assertEqual(damage_bonus(150, 150), ("+3D6", 4))  # 300


class TestMovement(unittest.TestCase):
    def test_base_8(self):
        self.assertEqual(movement_rate(70, 50, 60), 8)  # 一大一小

    def test_fast_and_slow(self):
        self.assertEqual(movement_rate(70, 70, 60), 9)  # 均 > SIZ
        self.assertEqual(movement_rate(50, 50, 60), 7)  # 均 < SIZ

    def test_age_penalty(self):
        self.assertEqual(movement_rate(50, 50, 60, age=45), 6)  # 7 - 1
        self.assertEqual(movement_rate(50, 50, 60, age=55), 5)  # 7 - 2

    def test_floor_one(self):
        self.assertEqual(movement_rate(20, 20, 90, age=90), 1)


class TestInsanity(unittest.TestCase):
    def test_thresholds(self):
        self.assertEqual(insanity_thresholds(55).temporary, 5)
        self.assertEqual(insanity_thresholds(55).indefinite, 11)
        self.assertEqual(insanity_thresholds(20).indefinite, 4)


class TestImprovement(unittest.TestCase):
    def test_increases(self):
        self.assertTrue(improvement_increases(50, 51))
        self.assertFalse(improvement_increases(50, 50))

    def test_improve(self):
        self.assertEqual(improve(50, 60, 7), 57)   # 成长 +7
        self.assertEqual(improve(50, 50, 7), 50)   # 未成长
        self.assertEqual(improve(95, 96, 10), 99)  # 上限 99


class TestSkillDefault(unittest.TestCase):
    def test_static_defaults(self):
        self.assertEqual(skill_default("侦查"), 25)
        self.assertEqual(skill_default("信用评级"), 0)

    def test_derived_defaults(self):
        self.assertEqual(skill_default("闪避", {"DEX": 45}), 22)  # DEX/2
        self.assertEqual(skill_default("母语", {"EDU": 75}), 75)  # EDU

    def test_unknown_is_zero(self):
        self.assertEqual(skill_default("不存在的技能"), 0)

    def test_default_skills_populated(self):
        self.assertGreater(len(DEFAULT_SKILLS), 40)


if __name__ == "__main__":
    unittest.main()
