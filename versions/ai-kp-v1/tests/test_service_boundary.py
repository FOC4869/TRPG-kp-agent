"""Service and real subprocess CLI boundaries; all model traffic is mocked."""

import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from kp_agent.graph import KeeperService, ROOT
from kp_agent.models import DeepSeekResponsesPlanner, DemoPlanner, ModelConfigurationError
from kp_agent.retrieval import RetrievalService
from kp_agent.schemas import ActionPlan, Narration
from kp_agent.storage import MessageConflict, StorageError


class ServiceBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def service(self, planner=None):
        return KeeperService(
            db_path=self.root / "game.sqlite3", planner=planner or DemoPlanner(),
            retrieval=RetrievalService(cache_path=self.root / "rules.json"),
        )

    def test_invalid_model_configuration_does_not_create_a_database(self):
        with patch("kp_agent.graph.create_planner", side_effect=ModelConfigurationError("无配置")):
            with self.assertRaises(ModelConfigurationError):
                KeeperService(db_path=self.root / "not_created.sqlite3")
        self.assertFalse((self.root / "not_created.sqlite3").exists())

    def test_model_log_correlates_both_stages_with_the_saved_message(self):
        class Responses:
            def parse(self, **kwargs):
                result = ActionPlan(intent="look", target_id="room") if kwargs["text_format"] is ActionPlan else Narration(text="你环顾书房。")
                return SimpleNamespace(output_parsed=result, status="completed", model="deepseek-flash", usage=None)

        path = self.root / "calls.jsonl"
        planner = DeepSeekResponsesPlanner(client=SimpleNamespace(responses=Responses()), metrics_path=path)
        service = self.service(planner)
        try:
            game = service.start()
            reply = service.handle_message("trace-me", "看看房间", game["game_id"])
            records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(2, len(records))
            self.assertEqual({"plan", "narrate"}, {r["stage"] for r in records})
            self.assertTrue(all(r["outcome"] == "accepted" for r in records))
            self.assertTrue(all(r["game_id"] == game["game_id"] for r in records))
            self.assertTrue(all(r["message_id"] == "trace-me" for r in records))
            self.assertTrue(all(r["action_id"] == reply["action_id"] for r in records))
            self.assertEqual(2, len({r["call_id"] for r in records}))
            self.assertNotIn("看看房间", path.read_text(encoding="utf-8"))
        finally:
            service.close()

    def test_same_message_payload_collision_does_not_break_the_completed_reply(self):
        service = self.service()
        try:
            service.start()
            original = service.handle_message("same", "看看房间")
            with self.assertRaises(MessageConflict):
                service.handle_message("same", "离开房间")
            self.assertEqual("completed", service.get_message("same")["status"])
            self.assertEqual(original, service.handle_message("same", "看看房间"))
        finally:
            service.close()

    def test_parallel_input_and_restart_are_rejected_during_a_turn(self):
        entered, release = threading.Event(), threading.Event()

        class SlowPlanner(DemoPlanner):
            def plan(self, *args, **kwargs):
                entered.set()
                if not release.wait(5):
                    raise RuntimeError("测试线程未释放")
                return super().plan(*args, **kwargs)

        service = self.service(SlowPlanner())
        failures = []

        def worker():
            try:
                service.handle_message("first", "看看房间")
            except Exception as exc:
                failures.append(type(exc).__name__)

        try:
            service.start()
            thread = threading.Thread(target=worker)
            thread.start()
            self.assertTrue(entered.wait(5))
            with self.assertRaises(StorageError):
                service.handle_message("second", "离开房间")
            with self.assertRaises(StorageError):
                service.restart()
            release.set()
            thread.join(5)
            self.assertFalse(thread.is_alive())
            self.assertEqual([], failures)
            self.assertIsNone(service.get_message("second"))
        finally:
            release.set()
            service.close()

    def test_subprocess_cli_commands_resume_and_review(self):
        db = self.root / "cli.sqlite3"
        command = [sys.executable, "-m", "kp_agent", "--mode", "demo", "--db", str(db)]
        run = subprocess.run(
            command, input="/status\n/review\n看看房间\n/history\n离开\n/review\n/quit\n",
            text=True, capture_output=True, cwd=ROOT, timeout=30,
            env={**os.environ, "KP_RETRIEVAL_MODE": "keyword"},
        )
        self.assertEqual(0, run.returncode, run.stdout + run.stderr)
        self.assertIn('"game_status": "playing"', run.stdout)
        self.assertIn("还没有结束", run.stdout)
        self.assertIn("本场景复盘", run.stdout)
        resumed = subprocess.run(command, input="/restart\n/quit\n", text=True, capture_output=True, cwd=ROOT, timeout=30,
                                 env={**os.environ, "KP_RETRIEVAL_MODE": "keyword"})
        self.assertEqual(0, resumed.returncode, resumed.stdout + resumed.stderr)
        self.assertIn("状态：已结束", resumed.stdout)
        self.assertIn("状态：进行中", resumed.stdout)

    def test_subprocess_json_reply_is_parseable_and_idempotent(self):
        command = [sys.executable, "-m", "kp_agent", "--mode", "demo", "--db", str(self.root / "json.sqlite3"),
                   "--message", "看看房间", "--message-id", "repeat-id", "--json"]
        environment = {**os.environ, "KP_RETRIEVAL_MODE": "keyword"}
        first = subprocess.run(command, text=True, capture_output=True, cwd=ROOT, timeout=30, env=environment)
        second = subprocess.run(command, text=True, capture_output=True, cwd=ROOT, timeout=30, env=environment)
        self.assertEqual(0, first.returncode, first.stdout + first.stderr)
        self.assertEqual(0, second.returncode, second.stdout + second.stderr)
        self.assertEqual(json.loads(first.stdout), json.loads(second.stdout))


if __name__ == "__main__":
    unittest.main()
