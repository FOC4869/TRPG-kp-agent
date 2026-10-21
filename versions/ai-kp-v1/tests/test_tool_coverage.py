"""Offline boundary checks for deterministic tool execution; no .env or API use."""
import copy
from pathlib import Path
import tempfile
import unittest

from kp_agent.storage import Storage
from kp_agent.tools import CharacterTools, bounded_expression, maximum
from trpg import Character
from trpg.excel_import import load_character_from_xlsx


class SequenceRandom:
    def __init__(self, values=()):
        self.values = iter(values)
        self.calls = 0

    def randint(self, low, high):
        value = next(self.values)
        if not low <= value <= high:
            raise AssertionError((value, low, high))
        self.calls += 1
        return value


class TestCharacterToolBoundaries(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = Storage(Path(self.temp.name) / "tools.sqlite3")
        self.character = Character(name="工具测试角色", attributes={"INT": 75},
            skills={"侦查": 55, "潜行": 20}, hp=10, hp_max=10, san=55,
            san_max=99, mp=11, mp_max=11)
        self.state = {"conditions": [], "san_day_start": 55, "san_lost_today": 0, "status": "playing"}
        self.game_id = self.store.start_game(self.character.to_dict(), self.state)["game_id"]

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def tools(self, values=()):
        return CharacterTools(self.store, rng=SequenceRandom(values))

    @staticmethod
    def effect(success="0", failure="1D6"):
        return [{"type": "sanity", "event_id": "test_event", "success": success, "failure": failure}]

    def test_sanity_success_zero_does_not_roll_loss_or_change_other_resources(self):
        tools = self.tools([20])
        rolls, changes, notices = tools.apply_effects(self.game_id, "success", self.character, self.state, self.effect())
        self.assertTrue(rolls[0]["passed"])
        self.assertEqual(0, changes[0]["delta"])
        self.assertEqual((55, 10, 11), (self.character.san, self.character.hp, self.character.mp))
        self.assertEqual([], notices)
        self.assertEqual(1, tools.rng.calls)

    def test_sanity_failure_uses_failure_expression(self):
        rolls, changes, _ = self.tools([72, 3]).apply_effects(
            self.game_id, "failure", self.character, self.state, self.effect(success="1", failure="1D6"))
        self.assertFalse(rolls[0]["passed"])
        self.assertEqual(52, self.character.san)
        self.assertEqual(-3, changes[0]["delta"])
        self.assertEqual(3, self.state["san_lost_today"])

    def test_low_sanity_96_is_fumble_and_uses_maximum_without_loss_roll(self):
        self.character.san = self.state["san_day_start"] = 40
        tools = self.tools([96, 90])  # SAN fumble then failed INT; no D6 drawn
        rolls, _, _ = tools.apply_effects(self.game_id, "low-fumble", self.character, self.state, self.effect())
        self.assertEqual("fumble", rolls[0]["success_level"])
        self.assertTrue(rolls[0]["loss_roll"]["maximum_loss"])
        self.assertEqual(34, self.character.san)
        self.assertEqual(2, tools.rng.calls)

    def test_at_fifty_sanity_96_is_normal_failure(self):
        self.character.san = self.state["san_day_start"] = 50
        rolls, _, _ = self.tools([96, 2]).apply_effects(
            self.game_id, "fifty", self.character, self.state, self.effect())
        self.assertEqual("failure", rolls[0]["success_level"])
        self.assertEqual(48, self.character.san)

    def test_one_hundred_always_uses_maximum_loss(self):
        tools = self.tools([100, 90])
        rolls, _, _ = tools.apply_effects(self.game_id, "hundred", self.character, self.state, self.effect())
        self.assertEqual("fumble", rolls[0]["success_level"])
        self.assertEqual(6, rolls[0]["loss"])
        self.assertEqual(2, tools.rng.calls)

    def test_int_success_causes_temporary_insanity_and_failure_does_not(self):
        for int_roll, expected in ((20, True), (90, False)):
            with self.subTest(int_roll=int_roll):
                char = Character.from_dict(self.character.to_dict())
                state = copy.deepcopy(self.state)
                rolls, _, notices = self.tools([72, int_roll]).apply_effects(
                    self.game_id, f"int-{int_roll}", char, state, self.effect(failure="6"))
                self.assertEqual(expected, "temporary_insanity" in state["conditions"])
                self.assertEqual(expected, any("临时性疯狂" in message for message in notices))
                self.assertEqual(2, len(rolls))

    def test_daily_loss_uses_fixed_day_start_and_exact_fraction(self):
        self.character.san = 48
        self.state["san_lost_today"] = 7
        tools = self.tools([80, 80])
        tools.apply_effects(self.game_id, "day1", self.character, self.state, self.effect(failure="3"))
        self.assertEqual(10, self.state["san_lost_today"])
        self.assertNotIn("indefinite_insanity", self.state["conditions"])
        tools.apply_effects(self.game_id, "day2", self.character, self.state, self.effect(failure="1"))
        self.assertEqual(55, self.state["san_day_start"])
        self.assertEqual(11, self.state["san_lost_today"])
        self.assertIn("indefinite_insanity", self.state["conditions"])

    def test_reaching_zero_clamps_actual_loss_and_skips_int_check(self):
        self.character.san = 3
        tools = self.tools([100])
        rolls, changes, notices = tools.apply_effects(
            self.game_id, "zero", self.character, self.state, self.effect(failure="10"))
        self.assertEqual(0, self.character.san)
        self.assertEqual(-3, changes[0]["delta"])
        self.assertEqual(3, self.state["san_lost_today"])
        self.assertEqual(1, len(rolls))
        self.assertIn("permanent_insanity", self.state["conditions"])
        self.assertTrue(notices)
        self.assertEqual(1, tools.rng.calls)

    def test_already_zero_does_not_roll_again(self):
        self.character.san = 0
        tools = self.tools()
        rolls, changes, notices = tools.apply_effects(self.game_id, "already-zero", self.character, self.state, self.effect())
        self.assertEqual([], rolls)
        self.assertEqual([], changes)
        self.assertTrue(notices)
        self.assertEqual(0, tools.rng.calls)

    def test_reapplying_same_effect_to_updated_state_is_idempotent(self):
        tools = self.tools([72, 3])
        first = tools.apply_effects(self.game_id, "same", self.character, self.state, self.effect())
        saved_state = copy.deepcopy(self.state)
        second = tools.apply_effects(self.game_id, "same", self.character, self.state, self.effect())
        self.assertEqual(first, second)
        self.assertEqual(52, self.character.san)
        self.assertEqual(saved_state, self.state)
        self.assertEqual(2, tools.rng.calls)

    def test_cached_roll_replays_once_against_old_uncommitted_snapshot(self):
        tools = self.tools([72, 3])
        old_char = Character.from_dict(self.character.to_dict())
        old_state = copy.deepcopy(self.state)
        first = tools.apply_effects(self.game_id, "retry", self.character, self.state, self.effect())
        replay = tools.apply_effects(self.game_id, "retry", old_char, old_state, self.effect())
        self.assertEqual(first, replay)
        self.assertEqual(52, old_char.san)
        self.assertEqual(3, old_state["san_lost_today"])
        self.assertEqual(2, tools.rng.calls)

    def test_changed_effect_under_same_id_is_rejected_without_deduction(self):
        tools = self.tools([72, 3])
        tools.apply_effects(self.game_id, "same", self.character, self.state, self.effect())
        with self.assertRaisesRegex(ValueError, "更换"):
            tools.apply_effects(self.game_id, "same", self.character, self.state, self.effect(failure="2D6"))
        self.assertEqual(52, self.character.san)

    def test_invalid_later_effect_is_validated_before_any_roll(self):
        tools = self.tools()
        with self.assertRaises(ValueError):
            tools.apply_effects(self.game_id, "invalid", self.character, self.state,
                self.effect() + [{"type": "damage", "amount": 3}])
        self.assertEqual(55, self.character.san)
        self.assertEqual(0, tools.rng.calls)

    def test_missing_int_does_not_partially_mutate_caller_state(self):
        self.character.attributes = {}
        old_state = copy.deepcopy(self.state)
        tools = self.tools([72])
        with self.assertRaisesRegex(ValueError, "智力"):
            tools.apply_effects(self.game_id, "missing-int", self.character, self.state, self.effect(failure="6"))
        self.assertEqual(55, self.character.san)
        self.assertEqual(old_state, self.state)
        self.character.attributes["INT"] = 75
        tools.rng = SequenceRandom([90])
        tools.apply_effects(self.game_id, "missing-int", self.character, self.state, self.effect(failure="6"))
        self.assertEqual(49, self.character.san)
        self.assertEqual(1, tools.rng.calls)  # only INT; original SAN roll reused

    def test_invalid_resource_types_and_negative_loss_are_rejected_before_roll(self):
        for invalid in (True, -1, 100, 55.0, "55"):
            with self.subTest(invalid=invalid):
                self.character.san = invalid
                tools = self.tools()
                with self.assertRaises(ValueError):
                    tools.apply_effects(self.game_id, "bad", self.character, self.state, self.effect())
                self.assertEqual(0, tools.rng.calls)
        self.character.san = 55
        with self.assertRaisesRegex(ValueError, "负值"):
            self.tools().apply_effects(self.game_id, "negative", self.character, self.state, self.effect(failure="1D6-2"))

    def test_skill_difficulty_bonus_and_id_collision(self):
        tools = self.tools([23])
        result = tools.skill_check(self.game_id, "skill", self.character, {"skill": "侦查", "difficulty": "extreme"})
        self.assertEqual("hard_success", result["success_level"])
        self.assertFalse(result["passed"])
        self.assertEqual(result, tools.skill_check(self.game_id, "skill", self.character, {"skill": "侦查", "difficulty": "extreme"}))
        self.assertEqual(1, tools.rng.calls)
        with self.assertRaisesRegex(ValueError, "更换"):
            tools.skill_check(self.game_id, "skill", self.character, {"skill": "侦查", "difficulty": "regular"})
        for bonus in (True, 3, -3, 1.0):
            with self.subTest(bonus=bonus), self.assertRaises(ValueError):
                tools.skill_check(self.game_id, "bad-bonus", self.character, {"skill": "侦查", "bonus_dice": bonus})

    def test_bonus_penalty_share_units_and_treat_double_zero_as_hundred(self):
        bonus = self.tools([0, 0, 3]).skill_check(self.game_id, "bonus", self.character, {"skill": "侦查", "bonus_dice": 1})
        self.assertEqual([100, 30], bonus["candidates"])
        self.assertEqual(30, bonus["roll"])
        penalty = self.tools([0, 0, 3]).skill_check(self.game_id, "penalty", self.character, {"skill": "侦查", "bonus_dice": -1})
        self.assertEqual(100, penalty["roll"])
        self.assertEqual("fumble", penalty["success_level"])

    def test_expression_bounds_injection_and_same_id_changes(self):
        for invalid in (None, True, "__import__('os')", "1d6;print(1)", "1d6\n+1", "0d6", "21d6", "1d101", "9999", "9" * 1000):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                bounded_expression(invalid)
        self.assertEqual(2999, maximum("20d100+999"))
        tools = self.tools([6])
        first = tools.expression(self.game_id, "expression", "loss", "1D6")
        self.assertEqual(first, tools.expression(self.game_id, "expression", "loss", "1d6"))
        with self.assertRaisesRegex(ValueError, "更换"):
            tools.expression(self.game_id, "expression", "loss", "2d6")
        self.assertEqual(1, tools.rng.calls)


class TestFixedCharacterFile(unittest.TestCase):
    def test_fixed_character_values_and_aliases_are_usable(self):
        path = next((Path(__file__).resolve().parents[1] / "characters").glob("*.xlsx"))
        character = load_character_from_xlsx(str(path))
        self.assertEqual((10, 55, 11), (character.hp, character.san, character.mp))
        self.assertEqual(55, character.resolve("侦察"))
        self.assertEqual(55, character.resolve("图馆"))
        self.assertEqual(75, character.resolve("灵感"))
        self.assertEqual(20, character.resolve("潜行"))
        self.assertTrue(all(type(value) is int for value in character.attributes.values()))


if __name__ == "__main__":
    unittest.main()
