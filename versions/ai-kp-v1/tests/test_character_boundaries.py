import unittest

from trpg.character import Character
from trpg.rules import compute_derived, damage_bonus, improve, improvement_increases, insanity_thresholds


class CharacterBoundaryTests(unittest.TestCase):
    def test_negative_restoration_cannot_deal_damage(self):
        for field in ("hp", "san", "mp"):
            with self.subTest(field=field):
                character = Character(name="边界测试", hp=5, hp_max=11, san=10, san_max=99, mp=4, mp_max=11)
                before = getattr(character, field)
                self.assertEqual(before, getattr(character, "restore_" + field)(-999))
                self.assertEqual(before, getattr(character, field))

    def test_all_restoration_is_capped_and_default_means_full(self):
        character = Character(name="边界测试", hp=1, hp_max=11, san=1, san_max=89, mp=1, mp_max=11)
        for field, maximum in (("hp", 11), ("san", 89), ("mp", 11)):
            with self.subTest(field=field):
                self.assertEqual(maximum, getattr(character, "restore_" + field)())
                self.assertEqual(maximum, getattr(character, "restore_" + field)(999))

    def test_odd_hp_major_wound_uses_half_without_rounding_down(self):
        character = Character(name="边界测试", hp=11, hp_max=11)
        self.assertEqual(6, character.major_wound_threshold)
        self.assertFalse(character.apply_damage(5).major_wound)
        character.restore_hp()
        self.assertTrue(character.apply_damage(6).major_wound)
        self.assertEqual(6, compute_derived({"CON": 50, "SIZ": 60}).major_wound)

    def test_zero_damage_is_never_a_major_wound(self):
        self.assertFalse(Character(name="空角色").apply_damage(0).major_wound)

    def test_san_result_reports_actual_loss_at_zero_floor(self):
        character = Character(name="边界测试", san=3, san_max=99)
        result = character.apply_san_loss(10)
        self.assertEqual(0, result.san_after)
        self.assertEqual(3, result.amount)
        self.assertFalse(result.possible_temporary_insanity)

    def test_daily_sanity_loss_threshold_uses_ceiling(self):
        self.assertEqual(11, insanity_thresholds(54).indefinite)
        self.assertEqual(11, insanity_thresholds(51).indefinite)
        self.assertEqual(10, insanity_thresholds(50).indefinite)
        self.assertEqual(1, insanity_thresholds(1).indefinite)

    def test_improvement_above_95_and_no_artificial_99_cap(self):
        self.assertTrue(improvement_increases(120, 96))
        self.assertFalse(improvement_increases(120, 95))
        self.assertEqual(130, improve(120, 96, 10))
        self.assertEqual(105, improve(95, 96, 10))

    def test_improvement_rejects_impossible_die_faces(self):
        for value in (0, 101):
            with self.assertRaises(ValueError):
                improvement_increases(50, value)
        for value in (0, 11, -1):
            with self.assertRaises(ValueError):
                improve(50, 60, value)

    def test_damage_bonus_continues_beyond_first_monster_ranges(self):
        for total, dice, build in ((284, 2, 3), (285, 3, 4), (444, 4, 5), (445, 5, 6), (524, 5, 6), (525, 6, 7)):
            with self.subTest(total=total):
                self.assertEqual((f"+{dice}D6", build), damage_bonus(total, 0))


if __name__ == "__main__":
    unittest.main()
