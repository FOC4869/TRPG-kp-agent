"""Scene-local recovery paths: a failed die must not permanently hide the plot."""
import copy
import json
from pathlib import Path
import unittest

from kp_agent.guidance import build_guidance
from kp_agent.scene import SceneDefinition, SceneValidationError


SCENE = Path(__file__).resolve().parents[1] / "data/scenes/study.json"


class TestDeskAlternative(unittest.TestCase):
    def setUp(self):
        self.scene = SceneDefinition.load(SCENE)
        self.initial = self.scene.initial_state(san=55)
        self.failed = self.scene.resolve_action({"action_type": "investigate", "target_id": "desk"}, self.initial, False)

    def test_first_failure_explains_public_alternative_without_revealing_reward(self):
        event = self.failed["public_event"]
        self.assertIn("十分钟", event["text"])
        self.assertIn("不再掷骰", event["text"])
        self.assertEqual([], event["new_clues"])
        context = self.scene.planning_context(self.failed["state"])
        desk = next(target for target in context["targets"] if target["id"] == "desk")
        self.assertTrue(desk["fallback_available"])
        self.assertEqual(10, desk["fallback_minutes"])
        self.assertIn("careful_search", desk["actions"])
        rendered = json.dumps({"event": event, "context": context}, ensure_ascii=False)
        # The public scene title already contains “来信”; protect the actual
        # undiscovered reward and its contents rather than that known title.
        for secret in ("夹层", "一封来信", "信中写着", "旧车站", "照片", "保管箱", "17"):
            self.assertNotIn(secret, rendered)

    def test_alternative_requires_first_failure(self):
        plan = {"action_type": "careful_search", "target_id": "desk"}
        with self.assertRaises(SceneValidationError):
            self.scene.validate_plan(plan, self.initial)
        success = self.scene.resolve_action({"action_type": "investigate", "target_id": "desk"}, self.initial, True)
        with self.assertRaises(SceneValidationError):
            self.scene.validate_plan(plan, success["state"])
        desk = next(target for target in self.scene.planning_context(success["state"])["targets"] if target["id"] == "desk")
        self.assertNotIn("careful_search", desk["actions"])

    def test_alternative_takes_ten_minutes_and_no_second_roll(self):
        plan = self.scene.validate_plan({"action_type": "careful_search", "target_id": "desk"}, self.failed["state"])
        self.assertIsNone(plan["check"])
        result = self.scene.resolve_action(plan, self.failed["state"])
        self.assertEqual(10, result["state"]["elapsed_minutes"])
        self.assertEqual(10, result["public_event"]["minutes_spent"])
        self.assertEqual(["letter"], result["state"]["revealed_clues"])
        self.assertEqual(["letter"], [clue["id"] for clue in result["clues"]])
        self.assertEqual([], result["effects"])
        self.assertEqual(10, self.scene.public_context(result["state"])["elapsed_minutes"])
        self.assertEqual(0, self.failed["state"]["elapsed_minutes"])

    def test_duplicate_alternative_does_not_charge_time_or_reveal_twice(self):
        plan = {"action_type": "careful_search", "target_id": "desk"}
        result = self.scene.resolve_action(plan, self.failed["state"])
        again = self.scene.resolve_action(plan, result["state"])
        self.assertTrue(again["public_event"]["repeated"])
        self.assertEqual(0, again["public_event"]["minutes_spent"])
        self.assertEqual(10, again["state"]["elapsed_minutes"])
        self.assertEqual([], again["clues"])
        self.assertEqual(["letter"], again["state"]["revealed_clues"])

    def test_repeated_original_search_is_not_another_attempt(self):
        plan = self.scene.validate_plan({"action_type": "investigate", "target_id": "desk"}, self.failed["state"])
        self.assertIsNone(plan["check"])
        repeated = self.scene.resolve_action(plan, self.failed["state"])
        self.assertEqual(0, repeated["state"]["elapsed_minutes"])
        self.assertEqual([], repeated["clues"])
        self.assertIn("十分钟", repeated["public_event"]["text"])

    def test_legacy_state_derives_alternative_from_recorded_failure(self):
        legacy = json.loads(json.dumps(self.failed["state"]))
        legacy.pop("elapsed_minutes")
        self.assertNotIn("fallback_available", legacy)
        context = self.scene.planning_context(legacy)
        self.assertEqual("花十分钟仔细检查书桌", build_guidance(context)["suggested_actions"][0])
        result = self.scene.resolve_action({"action_type": "careful_search", "target_id": "desk"}, legacy)
        self.assertEqual(10, result["state"]["elapsed_minutes"])

    def test_alternative_cannot_change_target_or_insert_a_check(self):
        for plan in (
            {"action_type": "careful_search", "target_id": "bookshelf"},
            {"action_type": "careful_search", "target_id": "desk", "check": {"skill": "幸运"}},
        ):
            with self.assertRaises(SceneValidationError):
                self.scene.validate_plan(plan, self.failed["state"])


class TestPostGameReview(unittest.TestCase):
    def setUp(self):
        self.scene = SceneDefinition.load(SCENE)
        self.initial = self.scene.initial_state(san=55)

    def test_review_is_for_ended_games_only(self):
        for status in ("playing", "paused", "not_started"):
            with self.assertRaises(SceneValidationError):
                self.scene.review({**self.initial, "status": status})

    def test_incomplete_review_lists_only_this_scenes_missing_clues(self):
        ended = self.scene.resolve_action({"action_type": "leave"}, self.initial)["state"]
        before = copy.deepcopy(ended)
        review = self.scene.review(ended)
        self.assertEqual("incomplete", review["ending"])
        self.assertEqual([], review["discovered_clues"])
        self.assertEqual({"letter", "photograph"}, {clue["id"] for clue in review["missed_clues"]})
        self.assertIn("十分钟", review["text"])
        self.assertIn("场景约定", review["text"])
        self.assertIn("旧来信", review["text"])
        self.assertIn("车站照片", review["text"])
        self.assertEqual(before, ended)

    def test_complete_review_has_no_missed_required_clues(self):
        state = self.scene.resolve_action({"action_type": "investigate", "target_id": "desk"}, self.initial, False)["state"]
        state = self.scene.resolve_action({"action_type": "careful_search", "target_id": "desk"}, state)["state"]
        state = self.scene.resolve_action({"action_type": "talk", "target_id": "butler"}, state)["state"]
        result = self.scene.resolve_action({"action_type": "leave"}, state)
        review = self.scene.review(result["state"])
        self.assertEqual("complete", review["ending"])
        self.assertEqual([], review["missed_clues"])
        self.assertEqual(2, len(review["discovered_clues"]))
        self.assertIn("没有遗漏", review["text"])
        self.assertIn("10 分钟", review["text"])
        self.assertIn("复盘", result["public_event"]["text"])


if __name__ == "__main__":
    unittest.main()
