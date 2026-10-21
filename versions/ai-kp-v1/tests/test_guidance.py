import copy
import json
import tempfile
import unittest
from pathlib import Path

from kp_agent.graph import KeeperService, ROOT
from kp_agent.guidance import build_guidance
from kp_agent.models import DemoPlanner
from kp_agent.scene import SceneDefinition
from .test_keeper_flow import FailingNarrator, SequenceRandom


class TestPublicGuidance(unittest.TestCase):
    def setUp(self):
        self.scene = SceneDefinition.load(ROOT / "data/scenes/study.json")
        self.state = self.scene.initial_state(san=55)

    def finish(self, intent, target, passed=None):
        result = self.scene.resolve_action({"action_type": intent, "target_id": target}, self.state, passed)
        self.state = result["state"]
        return result["public_event"]

    def suggestions(self, event=None, reply_type="narration"):
        return build_guidance(self.scene.planning_context(self.state), event, reply_type)

    def test_opening_mentions_public_actions_only(self):
        result = self.suggestions()
        self.assertGreaterEqual(len(result["suggested_actions"]), 2)
        self.assertLessEqual(len(result["suggested_actions"]), 3)
        self.assertIn("观察房间", result["suggested_actions"])
        text = json.dumps(result, ensure_ascii=False)
        for secret in ("信", "照片", "夹层", "保管箱", "17", "涂画"):
            self.assertNotIn(secret, text)

    def test_failed_search_is_not_suggested_again(self):
        event = self.finish("investigate", "desk", False)
        result = self.suggestions(event)
        self.assertNotIn("调查书桌", result["suggested_actions"])
        self.assertEqual("花十分钟仔细检查书桌", result["suggested_actions"][0])
        self.assertIn("与管家交谈", result["suggested_actions"])
        self.assertNotIn("来信", result["guidance"])
        self.assertNotIn("照片", result["guidance"])

    def test_revealed_letter_can_point_to_butler(self):
        event = self.finish("investigate", "desk", True)
        result = self.suggestions(event)
        self.assertEqual("向管家询问来信提到的照片", result["suggested_actions"][0])
        self.assertNotIn("调查书桌", result["suggested_actions"])
        self.assertNotIn("17", result["guidance"])

    def test_already_spoken_butler_and_sanity_event_are_excluded(self):
        self.finish("investigate", "desk", True)
        self.finish("talk", "butler")
        event = self.finish("investigate", "fireplace")
        text = json.dumps(self.suggestions(event), ensure_ascii=False)
        self.assertNotIn("询问", text)
        self.assertNotIn("交谈", text)
        self.assertNotIn("调查壁炉", text)
        self.assertIn("调查书架", text)

    def test_depleted_scene_only_suggests_leaving(self):
        self.finish("investigate", "desk", False)
        self.finish("careful_search", "desk")
        self.finish("talk", "butler")
        self.finish("investigate", "bookshelf")
        event = self.finish("investigate", "fireplace")
        result = self.suggestions(event)
        self.assertEqual(["离开书房"], result["suggested_actions"])
        self.assertIn("其他想做的事", result["guidance"])

    def test_careful_search_is_only_suggested_while_available(self):
        self.assertNotIn("花十分钟仔细检查书桌", self.suggestions()["suggested_actions"])
        event = self.finish("investigate", "desk", False)
        self.assertIn("花十分钟仔细检查书桌", self.suggestions(event)["suggested_actions"])
        event = self.finish("careful_search", "desk")
        self.assertNotIn("花十分钟仔细检查书桌", self.suggestions(event)["suggested_actions"])
        self.assertNotIn("调查书桌", self.suggestions(event)["suggested_actions"])

    def test_legal_careful_action_does_not_require_saved_fallback_flag(self):
        self.finish("investigate", "desk", False)
        context = self.scene.planning_context(self.state)
        desk = next(target for target in context["targets"] if target["id"] == "desk")
        desk.pop("fallback_available")
        self.assertEqual("花十分钟仔细检查书桌", build_guidance(context)["suggested_actions"][0])

    def test_finished_paused_question_and_takeover_have_no_menu(self):
        for status in ("ended", "paused", "not_started"):
            context = self.scene.planning_context({**self.state, "status": status})
            self.assertEqual({"suggested_actions": [], "guidance": ""}, build_guidance(context))
        for reply_type in ("question", "takeover"):
            self.assertEqual([], self.suggestions(reply_type=reply_type)["suggested_actions"])

    def test_actions_not_allowed_or_missing_are_never_invented(self):
        context = self.scene.planning_context(self.state)
        context["targets"] = [{"id": "desk", "actions": ["look"], "completed_actions": []},
                              {"id": "secret_door", "actions": ["investigate"], "completed_actions": []}]
        self.assertEqual([], build_guidance(context)["suggested_actions"])
        self.assertEqual([], build_guidance({"status": "playing"})["suggested_actions"])

    def test_hidden_outcome_changes_do_not_change_public_guidance(self):
        definition = copy.deepcopy(self.scene.definition)
        definition["targets"]["desk"]["investigate"]["success"]["text"] = "SECRET_REPLACEMENT"
        definition["clues"]["letter"]["description"] = "SECRET_REPLACEMENT"
        second = SceneDefinition(definition)
        self.assertEqual(self.suggestions(), build_guidance(second.planning_context(self.state)))

    def test_rule_explanation_can_return_player_to_scene(self):
        result = self.suggestions(event={"text": "规则解释"}, reply_type="rule_explanation")
        self.assertTrue(result["suggested_actions"])
        self.assertNotIn("观察房间", result["suggested_actions"])


class TestGuidanceFlow(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.service = KeeperService(db_path=Path(self.temp.name) / "game.sqlite3", planner=DemoPlanner(), rng=SequenceRandom([23]))
        self.service.start()

    def tearDown(self):
        self.service.close()
        self.temp.cleanup()

    def test_reply_start_replay_and_resume_have_guidance(self):
        self.assertTrue(self.service.start()["guidance"])
        result = self.service.handle_message("m1", "检查书桌")
        self.assertEqual("向管家询问来信提到的照片", result["suggested_actions"][0])
        self.assertEqual(result, self.service.handle_message("m1", "检查书桌"))
        self.assertTrue(self.service.get_game()["guidance"])
        self.assertEqual(result["guidance"], self.service.get_message("m1")["reply"]["guidance"])

    def test_question_and_ending_suppress_hints(self):
        result = self.service.handle_message("m1", "检查一下")
        self.assertEqual("question", result["reply_type"])
        self.assertEqual([], result["suggested_actions"])
        self.assertEqual("", self.service.get_game()["guidance"])
        result = self.service.handle_message("m2", "不检查了，我离开书房")
        self.assertEqual("ended", result["game_status"])
        self.assertEqual("", result["guidance"])
        self.assertEqual([], self.service.get_game()["suggested_actions"])

    def test_narration_failure_keeps_committed_guidance_for_retry(self):
        self.service.planner = FailingNarrator()
        with self.assertRaises(RuntimeError):
            self.service.handle_message("m1", "检查书桌")
        saved = self.service.storage.list_events()[0]["event"]["public_facts"]["guidance"]
        self.assertEqual("", self.service.get_game()["guidance"])
        result = self.service.handle_message("m1", "检查书桌")
        self.assertEqual(saved, result["guidance"])
        self.assertEqual(1, self.service.tools.rng.calls)


if __name__ == "__main__":
    unittest.main()
