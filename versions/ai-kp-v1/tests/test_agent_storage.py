from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from kp_agent.storage import MessageConflict, StaleGameError, Storage, StorageError, VersionConflict


class TestGameStorage(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.path = Path(self.temp.name) / "game.db"
        self.store = Storage(self.path)
        self.character = {"name": "固定角色", "hp": 10, "san": 55}
        self.state = {"scene_id": "study", "status": "playing", "revealed_clues": [], "attempts": {}, "conditions": [], "san_day_start": 55, "san_lost_today": 0}
        self.game = self.store.start_game(self.character, self.state)
        self.gid = self.game["game_id"]

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def test_start_is_not_restart(self):
        self.assertEqual(self.store.start_game({"hp": 1}, {})["game_id"], self.gid)
        self.assertEqual(self.store.load_character()["hp"], 10)

    def test_message_retry_is_idempotent_but_payload_collision_is_not_allowed(self):
        self.store.begin_message(self.gid, "m1", "我看看书桌")
        self.store.save_reply(self.gid, "m1", {"reply": "一张书桌。"})
        message = self.store.begin_message(self.gid, "m1", "我看看书桌")
        self.assertEqual(message["reply"]["reply"], "一张书桌。")
        self.assertEqual(len(self.store.list_messages()), 1)
        with self.assertRaises(MessageConflict):
            self.store.begin_message(self.gid, "m1", "换一个行动")

    def test_processing_message_blocks_another_but_failed_message_can_retry(self):
        self.store.begin_message(self.gid, "m1", "看看")
        with self.assertRaises(MessageConflict):
            self.store.begin_message(self.gid, "m2", "离开")
        self.store.fail_message(self.gid, "m1", "模型超时")
        message = self.store.begin_message(self.gid, "m1", "看看")
        self.assertEqual(message["status"], "processing")
        self.assertIsNone(message["error"])

    def test_failed_message_blocks_new_actions_until_original_reply_is_recovered(self):
        self.store.begin_message(self.gid, "m1", "调查书桌")
        updated_scene = {**self.state, "revealed_clues": ["letter"]}
        first = self.store.commit_action(self.gid, "m1", "a1", 0, self.character, updated_scene, {"text": "找到信"})
        self.store.fail_message(self.gid, "m1", "叙述失败，但行动已经保存")
        with self.assertRaisesRegex(MessageConflict, "m1"):
            self.store.begin_message(self.gid, "m2", "询问管家")
        self.assertEqual(self.store.get_game()["version"], 1)
        self.assertIsNone(self.store.get_message(self.gid, "m2"))
        recovered = self.store.begin_message(self.gid, "m1", "调查书桌")
        self.assertEqual(recovered["status"], "processing")
        self.assertEqual(self.store.get_action(self.gid, "a1")["game"], first)
        self.store.save_reply(self.gid, "m1", {"reply": "找到信", "version": 1})
        self.store.begin_message(self.gid, "m2", "询问管家")
        self.assertEqual(self.store.get_message(self.gid, "m2")["status"], "processing")

    def test_first_plan_and_dice_survive_retry_without_overwrite(self):
        self.store.begin_message(self.gid, "m1", "调查书桌")
        self.store.save_message_draft(self.gid, "m1", {"target_id": "desk"})
        result = self.store.save_message_draft(self.gid, "m1", {"target_id": "fireplace"})
        self.assertEqual(result["draft"]["target_id"], "desk")
        self.store.record_roll(self.gid, "m1:skill", {"roll": 87})
        same = self.store.record_roll(self.gid, "m1:skill", {"roll": 1})
        self.assertEqual(same, {"roll": 87})
        self.assertEqual(self.store.get_roll(self.gid, "m1:skill"), {"roll": 87})

    def test_atomic_commit_and_duplicate_action_do_not_apply_twice(self):
        self.store.begin_message(self.gid, "m1", "调查壁炉")
        self.store.record_roll(self.gid, "m1:san", {"loss": 3})
        changed = {**self.character, "san": 52}
        scene = {**self.state, "triggered_events": ["fireplace_drawing"], "san_lost_today": 3}
        result = self.store.commit_action(self.gid, "m1", "a1", 0, changed, scene, {"public_facts": ["看到涂画", "SAN损失3"]}, ["m1:san"])
        repeated = self.store.commit_action(self.gid, "m1", "a1", 0, {"san": 49}, {}, {})
        self.assertEqual(repeated, result)
        self.assertEqual(self.store.get_game()["character"]["san"], 52)
        self.assertEqual(self.store.get_game()["scene_state"]["san_lost_today"], 3)
        self.assertEqual(self.store.get_game()["version"], 1)
        self.assertEqual(len(self.store.list_events()), 1)
        self.assertEqual(self.store.get_action(self.gid, "a1")["event"]["public_facts"][1], "SAN损失3")

    def test_version_conflict_and_missing_roll_leave_no_partial_changes(self):
        self.store.begin_message(self.gid, "m1", "看看")
        with self.assertRaises(VersionConflict):
            self.store.commit_action(self.gid, "m1", "a1", 99, {"hp": 0}, {"status": "ended"}, {})
        with self.assertRaises(StorageError):
            self.store.commit_action(self.gid, "m1", "a1", 0, {"hp": 0}, {"status": "ended"}, {}, ["not_saved"])
        self.assertEqual(self.store.get_game()["version"], 0)
        self.assertEqual(self.store.load_character()["hp"], 10)
        self.assertEqual(self.store.list_events(), [])

    def test_process_restart_restores_snapshot_message_draft_and_random_result(self):
        self.store.begin_message(self.gid, "m1", "调查")
        self.store.save_message_draft(self.gid, "m1", {"target_id": "desk"})
        self.store.record_roll(self.gid, "r1", {"roll": 23})
        self.store.commit_action(self.gid, "m1", "a1", 0, self.character, {**self.state, "revealed_clues": ["letter"]}, {"text": "找到信"})
        self.store.close()
        self.store = Storage(self.path)
        self.assertEqual(self.store.get_game()["game_id"], self.gid)
        self.assertEqual(self.store.get_game()["scene_state"]["revealed_clues"], ["letter"])
        self.assertEqual(self.store.get_message(self.gid, "m1")["draft"], {"target_id": "desk"})
        self.assertEqual(self.store.get_roll(self.gid, "r1"), {"roll": 23})
        self.assertEqual(self.store.get_action(self.gid, "a1")["event"], {"text": "找到信"})

    def test_restart_game_restores_initial_data_and_rejects_old_inflight_writes(self):
        self.store.begin_message(self.gid, "m1", "看看")
        new = self.store.restart_game()
        self.assertNotEqual(new["game_id"], self.gid)
        self.assertEqual(new["character"], self.character)
        self.assertEqual(new["scene_state"], self.state)
        for operation in (
            lambda: self.store.begin_message(self.gid, "m2", "旧消息"),
            lambda: self.store.record_roll(self.gid, "r1", {"roll": 1}),
            lambda: self.store.commit_action(self.gid, "m1", "a1", 0, {}, {}, {}),
            lambda: self.store.save_reply(self.gid, "m1", {"reply": "旧回复"}),
        ):
            with self.assertRaises(StaleGameError):
                operation()
        self.assertEqual(self.store.get_game()["version"], 0)
        self.assertEqual(self.store.list_messages(), [])


if __name__ == "__main__":
    unittest.main()
