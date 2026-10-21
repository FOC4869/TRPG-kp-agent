"""CLI presents one hint after results and keeps an empty hint silent."""

import io
import unittest
from contextlib import redirect_stdout
from types import SimpleNamespace
from unittest.mock import patch

from kp_agent.cli import main, show, show_start


class GuidanceCliTests(unittest.TestCase):
    def render(self, **updates):
        reply = {
            "reply": "你仔细检查了书桌。",
            "rolls": [{"skill": "侦查", "roll": 23, "skill_value": 55,
                       "success_level": "hard_success", "passed": True}],
            "changes": [],
            "new_clues": [{"name": "旧信", "description": "一封已经公开的信。"}],
            "evidence": [],
            "character": {"hp": 10, "hp_max": 10, "san": 55, "san_max": 99,
                          "mp": 11, "mp_max": 11},
            "suggested_actions": ["询问管家"],
            "guidance": "接下来可以询问管家，也可以描述其他行动。",
        }
        reply.update(updates)
        output = io.StringIO()
        with redirect_stdout(output):
            show(reply)
        return output.getvalue()

    def test_hint_appears_once_after_results_clue_and_character_state(self):
        output = self.render()
        guidance = "接下来可以询问管家，也可以描述其他行动。"
        self.assertEqual(output.count(guidance), 1)
        self.assertLess(output.index("骰子："), output.index(guidance))
        self.assertLess(output.index("新线索："), output.index(guidance))
        self.assertLess(output.index("HP 10/10"), output.index(guidance))
        # The list is not printed a second time as a numbered menu.
        self.assertEqual(output.count("询问管家"), 1)

    def test_empty_guidance_does_not_print_suggested_actions_as_extra_hint(self):
        output = self.render(guidance="")
        self.assertNotIn("询问管家", output)
        self.assertNotIn("接下来", output)

    def test_missing_guidance_keeps_older_reply_compatible(self):
        output = self.render(guidance=None)
        self.assertIn("HP 10/10", output)
        self.assertNotIn("询问管家", output)

    def test_hint_already_in_reply_is_not_printed_twice(self):
        guidance = "接下来可以询问管家，也可以描述其他行动。"
        output = self.render(reply=f"你仔细检查了书桌。\n{guidance}")
        self.assertEqual(output.count(guidance), 1)


class StartupCliTests(unittest.TestCase):
    def render(self, **updates):
        game = {
            "game_id": "game_001",
            "game_status": "playing",
            "resumed": False,
            "opening": "旧版开场文字",
            "startup_message": "新的调查开始了。",
            "character": {"hp": 10, "hp_max": 10, "san": 55, "san_max": 99,
                          "mp": 11, "mp_max": 11},
            "guidance": "可以观察房间，也可以描述其他行动。",
        }
        game.update(updates)
        output = io.StringIO()
        with redirect_stdout(output):
            show_start(game)
        return output.getvalue()

    def test_start_uses_startup_message_and_current_character(self):
        output = self.render()
        self.assertIn("状态：进行中", output)
        self.assertIn("新的调查开始了。", output)
        self.assertNotIn("旧版开场文字", output)
        self.assertIn("HP 10/10 | SAN 55/99 | MP 11/11", output)
        self.assertIn("可以观察房间", output)
        self.assertIn("/retry", output)

    def test_resumed_ended_game_does_not_show_fresh_opening_or_play_guidance(self):
        output = self.render(
            resumed=True, game_status="ended",
            startup_message="已读取之前的存档，本局已经结束。",
        )
        self.assertIn("状态：已结束", output)
        self.assertIn("已读取之前的存档", output)
        self.assertNotIn("旧版开场文字", output)
        self.assertNotIn("可以观察房间", output)
        self.assertNotIn("/retry", output)
        self.assertIn("/restart", output)
        self.assertIn("/history", output)
        self.assertIn("/quit", output)

    def test_ended_game_with_old_payload_still_does_not_replay_opening(self):
        output = self.render(game_status="ended", startup_message=None)
        self.assertIn("本局已结束", output)
        self.assertNotIn("旧版开场文字", output)

    def test_playing_old_payload_can_fall_back_to_opening(self):
        output = self.render(startup_message=None, character=None)
        self.assertIn("旧版开场文字", output)
        self.assertNotIn("HP", output)

    def test_paused_game_does_not_show_ordinary_action_guidance(self):
        output = self.render(game_status="paused", startup_message="本局暂停，等待真人处理。")
        self.assertIn("状态：已暂停", output)
        self.assertIn("等待真人处理", output)
        self.assertNotIn("可以观察房间", output)


class RetryCliTests(unittest.TestCase):
    def test_busy_rejected_new_message_does_not_replace_saved_failed_message(self):
        class FakeService:
            def __init__(self):
                self.planner = SimpleNamespace(mode_label="测试模式")
                self.calls = []
                self.pending = None
                self.closed = False

            def start(self):
                return {"game_id": "game_test", "game_status": "playing",
                        "startup_message": "开始测试。", "character": {}}

            def handle_message(self, message_id, text, game_id):
                self.calls.append((message_id, text, game_id))
                if message_id == "m1" and self.pending is None:
                    self.pending = {"message_id": "m1", "text": "检查书桌", "status": "failed"}
                    raise RuntimeError("模拟第一次请求失败")
                if message_id == "m2":
                    raise RuntimeError("上一条消息未完成，新消息没有登记")
                if message_id == "m1":
                    self.pending = None
                    return {"reply": "原来的行动已经恢复。", "character": {}}
                raise AssertionError("不应发送其他消息")

            def get_message(self, message_id):
                return self.pending if self.pending and self.pending["message_id"] == message_id else None

            def list_messages(self):
                return [self.pending] if self.pending else []

            def close(self):
                self.closed = True

        service = FakeService()
        output = io.StringIO()
        with (
            patch("kp_agent.cli.KeeperService", return_value=service),
            patch("kp_agent.cli.create_planner", return_value=object()),
            patch("kp_agent.cli.uuid.uuid4", side_effect=[SimpleNamespace(hex="m1"), SimpleNamespace(hex="m2")]),
            patch("builtins.input", side_effect=["检查书桌", "观察房间", "/retry", "/quit"]),
            redirect_stdout(output),
        ):
            exit_code = main([])

        self.assertEqual(exit_code, 0)
        self.assertEqual(service.calls, [
            ("m1", "检查书桌", "game_test"),
            ("m2", "观察房间", "game_test"),
            ("m1", "检查书桌", "game_test"),
        ])
        self.assertIn("原来的行动已经恢复", output.getvalue())
        self.assertTrue(service.closed)


if __name__ == "__main__":
    unittest.main()
