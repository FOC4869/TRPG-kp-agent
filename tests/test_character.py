import unittest

from trpg.character import Character

from ._utils import FakeRng


def make_char() -> Character:
    return Character(
        name="测试", age=30, occupation="",
        attributes={"STR": 65, "CON": 45, "DEX": 45, "APP": 65, "POW": 55, "INT": 75, "SIZ": 60, "EDU": 75},
        skills={"侦查": 55, "聆听": 60, "闪避": 22, "克苏鲁神话": 0},
        hp=10, hp_max=10, san=55, san_max=99, mp=11, mp_max=11, luck=50, mov=8, db="+1D4", build=1,
    )


class TestDamage(unittest.TestCase):
    def test_damage_reduces_hp(self):
        c = make_char()
        r = c.apply_damage(3)
        self.assertEqual(c.hp, 7)
        self.assertFalse(r.major_wound)

    def test_damage_clamps_at_zero(self):
        c = make_char()
        c.apply_damage(20)
        self.assertEqual(c.hp, 0)

    def test_major_wound_threshold(self):
        # hp_max=10 -> 重伤阈值 5
        self.assertTrue(make_char().apply_damage(5).major_wound)
        self.assertFalse(make_char().apply_damage(4).major_wound)

    def test_dying_flag(self):
        c = make_char()
        c.apply_damage(5)  # hp=5，重伤但未归零
        r = c.apply_damage(5)  # hp=0，重伤
        self.assertTrue(r.unconscious)
        self.assertTrue(r.dying)


class TestSanity(unittest.TestCase):
    def test_san_loss(self):
        c = make_char()
        r = c.apply_san_loss(6)
        self.assertEqual(c.san, 49)
        self.assertTrue(r.possible_temporary_insanity)

    def test_san_clamps_at_zero(self):
        c = make_char()
        c.apply_san_loss(100)
        self.assertEqual(c.san, 0)


class TestRestore(unittest.TestCase):
    def test_restore_hp_clamps_at_max(self):
        c = make_char()
        c.apply_damage(3)
        c.restore_hp(100)
        self.assertEqual(c.hp, 10)

    def test_restore_san(self):
        c = make_char()
        c.apply_san_loss(10)
        c.restore_san(5)
        self.assertEqual(c.san, 50)


class TestResolveAndCheck(unittest.TestCase):
    def test_resolve_attribute(self):
        c = make_char()
        self.assertEqual(c.resolve("力量"), 65)
        self.assertEqual(c.resolve("STR"), 65)
        self.assertEqual(c.resolve("灵感"), 75)  # 智力别名

    def test_resolve_skill(self):
        self.assertEqual(make_char().resolve("侦查"), 55)

    def test_resolve_alias(self):
        self.assertEqual(make_char().resolve("侦察"), 55)  # 别名

    def test_resolve_zero_skill(self):
        self.assertEqual(make_char().resolve("克苏鲁神话"), 0)  # 存在但值为 0

    def test_resolve_unknown_is_none(self):
        self.assertIsNone(make_char().resolve("不存在的技能"))

    def test_check_uses_skill_value(self):
        c = make_char()
        r = c.check("侦查", rng=FakeRng([55]))  # 55 ≤ 55
        self.assertEqual(r.degree, "regular_success")
        self.assertEqual(r.skill, 55)

    def test_check_unknown_raises(self):
        with self.assertRaises(ValueError):
            make_char().check("不存在的技能")

    def test_luck_resolve(self):
        self.assertEqual(make_char().resolve("幸运"), 50)


class TestPersistence(unittest.TestCase):
    def test_roundtrip(self):
        c = make_char()
        c.apply_damage(3)
        c.apply_san_loss(6)
        c2 = Character.from_dict(c.to_dict())
        self.assertEqual(c2.hp, 7)
        self.assertEqual(c2.san, 49)
        self.assertEqual(c2.skills["侦查"], 55)
        self.assertEqual(c2.attributes["STR"], 65)


if __name__ == "__main__":
    unittest.main()
