import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from kp_agent.graph import KeeperService
from kp_agent.models import DemoPlanner
from trpg import Character
from .test_keeper_flow import FailingNarrator


class TestStartupAndClosedGame(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = Path(self.temp.name) / "game.sqlite3"
        self.services = []
        self.character = patch("kp_agent.graph.default_character", side_effect=lambda: Character(
            name="测试角色", attributes={"INT": 75}, skills={"侦查": 55},
            hp=10, hp_max=10, san=55, san_max=99, mp=11, mp_max=11,
        ))
        self.character.start()

    def tearDown(self):
        for service in self.services:
            service.close()
        self.character.stop()
        self.temp.cleanup()

    def service(self, planner=None):
        service = KeeperService(db_path=self.db, planner=planner or DemoPlanner())
        self.services.append(service)
        return service

    def test_fresh_start_and_running_resume_are_distinct(self):
        service = self.service()
        fresh = service.start()
        self.assertFalse(fresh["resumed"])
        self.assertEqual(service.scene.opening, fresh["startup_message"])
        service.handle_message("m1", "看看房间")
        resumed = service.start()
        self.assertTrue(resumed["resumed"])
        self.assertEqual("", resumed["opening"])
        self.assertIn("接着之前", resumed["startup_message"])
        self.assertEqual(fresh["game_id"], resumed["game_id"])
        self.assertNotIn(service.scene.opening, resumed["startup_message"])

    def test_completed_game_resume_does_not_replay_opening(self):
        service = self.service()
        service.start()
        service.handle_message("leave", "离开")
        restarted_process = self.service()
        resumed = restarted_process.start()
        self.assertEqual("ended", resumed["game_status"])
        self.assertIn("已经结束", resumed["startup_message"])
        self.assertIn("/restart", resumed["startup_message"])
        self.assertEqual("", resumed["opening"])
        self.assertEqual([], resumed["suggested_actions"])

    def test_ended_input_skips_model_rules_dice_and_state_commit(self):
        service = self.service()
        service.start()
        service.handle_message("leave", "离开")
        before = service.get_game()
        with patch.object(service.planner, "plan") as plan, \
             patch.object(service.planner, "narrate") as narrate, \
             patch.object(service.retrieval, "search") as search, \
             patch.object(service.tools, "skill_check") as check, \
             patch.object(service.storage, "commit_action") as commit:
            result = service.handle_message("after", "调查壁炉")
            for operation in (plan, narrate, search, check, commit):
                operation.assert_not_called()
        self.assertEqual(before["version"], result["version"])
        self.assertEqual(before["character"], result["character"])
        self.assertEqual([], result["rolls"])
        self.assertEqual([], result["evidence"])
        self.assertEqual([], result["suggested_actions"])
        self.assertIn("/restart", result["reply"])
        self.assertEqual(result, service.handle_message("after", "调查壁炉"))
        self.assertEqual(1, len(service.storage.list_events()))

    def test_paused_input_is_also_stopped_before_planning(self):
        service = self.service()
        character = Character(
            name="测试角色", attributes={"INT": 75}, hp=10, hp_max=10, san=55, san_max=99,
        )
        state = service.scene.initial_state(san=55)
        state["status"] = "paused"
        service.storage.start_game(character.to_dict(), state)
        with patch.object(service.planner, "plan") as plan:
            result = service.handle_message("m1", "怎么判侦查")
            plan.assert_not_called()
        self.assertEqual("takeover", result["reply_type"])
        self.assertEqual("paused", result["game_status"])
        self.assertEqual([], result["evidence"])
        self.assertEqual(0, result["version"])

    def test_ending_narration_failure_recovers_original_ending_after_process_restart(self):
        service = self.service(FailingNarrator())
        service.start()
        with self.assertRaises(RuntimeError):
            service.handle_message("leave", "离开")
        resumed_service = self.service()
        startup = resumed_service.start()
        self.assertEqual("ended", startup["game_status"])
        self.assertEqual("leave", startup["pending_message_id"])
        self.assertIn("/retry", startup["startup_message"])
        with patch.object(resumed_service.planner, "plan") as plan:
            result = resumed_service.handle_message("leave", "离开")
            plan.assert_not_called()
        self.assertEqual("ended", result["game_status"])
        self.assertIn("选择带着目前获得的信息离开", result["reply"])
        self.assertEqual(1, result["version"])
        self.assertEqual(1, len(resumed_service.storage.list_events()))

    def test_explicit_restart_makes_new_game_and_opening(self):
        service = self.service()
        first = service.start()
        service.handle_message("leave", "离开")
        second = service.restart()
        self.assertNotEqual(first["game_id"], second["game_id"])
        self.assertFalse(second["resumed"])
        self.assertEqual(0, second["version"])
        self.assertEqual("playing", second["game_status"])
        self.assertEqual(service.scene.opening, second["startup_message"])

    def test_pending_question_is_shown_when_resuming(self):
        service = self.service()
        service.start()
        question = service.handle_message("m1", "检查一下")["reply"]
        resumed = service.start()
        self.assertIn(question, resumed["startup_message"])
        self.assertEqual([], resumed["suggested_actions"])


if __name__ == "__main__":
    unittest.main()
