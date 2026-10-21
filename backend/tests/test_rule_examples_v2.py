"""Computed rule examples are not live rolls or LLM arithmetic.

Uses a fixed character, scripted planner, real local keyword retrieval and a
temporary database. No .env loading, provider SDK request or paid API is used.
"""

from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from kp_agent.graph import KeeperService
from kp_agent.retrieval import RetrievalService
from kp_agent.schemas import ActionPlan
from kp_agent.tools import CharacterTools
from trpg import Character


def fixed_character():
    return Character(
        name="规则示例调查员", age=30, occupation="研究员",
        attributes={"STR": 65, "CON": 45, "DEX": 45, "APP": 65,
                    "POW": 55, "INT": 75, "SIZ": 60, "EDU": 75},
        skills={"侦查": 55, "图书馆使用": 55, "聆听": 60},
        hp=8, hp_max=10, san=55, san_max=99, mp=9, mp_max=11, luck=50,
    )


class NoRandom:
    def __init__(self):
        self.calls = 0

    def randint(self, low, high):
        self.calls += 1
        raise AssertionError("规则举例不能掷真实骰子")


class ScriptPlanner:
    mode = "offline-test"
    mode_label = "固定规则问答测试，不是大模型"

    def __init__(self, query):
        self.query = query
        self.plan_calls = 0
        self.narrate_calls = 0

    def plan(self, text, context, history=(), pending_question=None):
        self.plan_calls += 1
        return ActionPlan(intent="rule_question", query=self.query)

    def narrate(self, text, public_facts, history=()):
        self.narrate_calls += 1
        return "普通规则问题仍然交给叙述步骤解释。"


class SuccessExampleToolTests(unittest.TestCase):
    def test_skill55_thresholds_are_floored_to_55_27_11(self):
        example = CharacterTools.success_example(fixed_character(), "侦查")
        self.assertEqual(example["skill"], "侦查")
        self.assertEqual(example["skill_value"], 55)
        self.assertEqual(example["thresholds"], {"regular": 55, "hard": 27, "extreme": 11})

    def test_30_is_regular_20_is_hard_and_10_is_extreme(self):
        example = CharacterTools.success_example(fixed_character(), "侦查")
        samples = {sample["roll"]: sample for sample in example["samples"]}
        expected = {
            30: ("regular_success", {"regular": True, "hard": False, "extreme": False}),
            20: ("hard_success", {"regular": True, "hard": True, "extreme": False}),
            10: ("extreme_success", {"regular": True, "hard": True, "extreme": True}),
        }
        for value, (level, passes) in expected.items():
            with self.subTest(roll=value):
                self.assertEqual(samples[value]["success_level"], level)
                self.assertEqual(samples[value]["passes"], passes)
        self.assertNotRegex(example["text"], r"30\s*(?:不超过|≤|<=)\s*27")

    def test_examples_do_not_roll_or_change_the_character(self):
        character = fixed_character()
        before = deepcopy(character.to_dict())
        with (
            patch.object(Character, "check", side_effect=AssertionError("举例不能调用角色检定")),
            patch("kp_agent.tools.roll", side_effect=AssertionError("举例不能执行骰子表达式")),
        ):
            CharacterTools.success_example(character, "侦查")
        self.assertEqual(character.to_dict(), before)

    def test_a_different_existing_skill_uses_its_actual_value(self):
        example = CharacterTools.success_example(fixed_character(), "聆听")
        self.assertEqual(example["skill_value"], 60)
        self.assertEqual(example["thresholds"], {"regular": 60, "hard": 30, "extreme": 12})
        sample30 = next(sample for sample in example["samples"] if sample["roll"] == 30)
        self.assertEqual(sample30["success_level"], "hard_success")


class RuleExampleFlowTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.character_patch = patch("kp_agent.graph.default_character", side_effect=fixed_character)
        self.character_patch.start()

    def tearDown(self):
        self.character_patch.stop()
        self.temp.cleanup()

    def service(self, query):
        planner = ScriptPlanner(query)
        rng = NoRandom()
        keeper = KeeperService(
            db_path=self.root / "game.sqlite3", planner=planner, rng=rng,
            retrieval=RetrievalService(cache_path=self.root / "rules.json"),
        )
        self.addCleanup(keeper.close)
        game = keeper.start()
        return keeper, planner, rng, game

    def test_success_grade_question_calls_plan_once_and_skips_model_narration(self):
        keeper, planner, rng, game = self.service("技能检定与成功等级 常规成功 困难成功 极难成功")
        before = deepcopy(keeper.storage.load_character())
        reply = keeper.handle_message("grades", "困难成功和极难成功怎么区分？", game["game_id"])
        self.assertEqual(planner.plan_calls, 1)
        self.assertEqual(planner.narrate_calls, 0)
        self.assertEqual(reply["reply_type"], "rule_explanation")
        self.assertEqual(reply["rolls"], [])
        self.assertEqual(reply["changes"], [])
        self.assertEqual(keeper.storage.load_character(), before)
        self.assertEqual(rng.calls, 0)
        event = keeper.storage.get_action(game["game_id"], reply["action_id"])
        self.assertEqual(event["roll_ids"], [])
        example = event["event"]["public_facts"]["event"]["rule_example"]
        self.assertEqual(example["thresholds"], {"regular": 55, "hard": 27, "extreme": 11})
        self.assertEqual({sample["roll"]: sample["success_level"] for sample in example["samples"]}, {
            30: "regular_success", 20: "hard_success", 10: "extreme_success",
        })

    def test_computed_reply_cites_the_actual_retrieved_grade_source(self):
        keeper, _, _, game = self.service("技能检定与成功等级 常规成功 困难成功 极难成功")
        reply = keeper.handle_message("grade-source", "成功等级是什么意思？", game["game_id"])
        sources = [item for item in reply["evidence"] if item["title"] == "技能检定与成功等级"]
        self.assertTrue(sources, "真实关键词检索应找到成功等级来源")
        self.assertTrue(any(f"[{item['evidence_id']}]" in reply["reply"] for item in sources))
        self.assertNotRegex(reply["reply"], r"30\s*(?:不超过|≤|<=)\s*27")

    def test_grade_question_about_another_existing_skill_is_not_hardcoded_to_spot_hidden(self):
        keeper, planner, rng, game = self.service("聆听的常规成功 困难成功 极难成功 成功等级")
        reply = keeper.handle_message("listen-grades", "用聆听举个困难成功的例子。", game["game_id"])
        event = keeper.storage.get_action(game["game_id"], reply["action_id"])
        example = event["event"]["public_facts"]["event"]["rule_example"]
        self.assertEqual(example["skill"], "聆听")
        self.assertEqual(example["skill_value"], 60)
        self.assertEqual(example["thresholds"], {"regular": 60, "hard": 30, "extreme": 12})
        self.assertEqual(planner.narrate_calls, 0)
        self.assertEqual(rng.calls, 0)

    def test_other_rule_topics_still_call_narration_without_rolling(self):
        keeper, planner, rng, game = self.service("奖励骰与惩罚骰怎么使用")
        reply = keeper.handle_message("bonus-rule", "奖励骰怎么使用？", game["game_id"])
        self.assertEqual(planner.plan_calls, 1)
        self.assertEqual(planner.narrate_calls, 1)
        self.assertEqual(reply["reply"], "普通规则问题仍然交给叙述步骤解释。")
        self.assertEqual(reply["rolls"], [])
        self.assertEqual(reply["changes"], [])
        self.assertEqual(rng.calls, 0)


if __name__ == "__main__":
    unittest.main()
