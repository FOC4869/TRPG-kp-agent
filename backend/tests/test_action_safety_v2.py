"""Negations and action questions cannot execute via demo or fake model plans."""
from copy import deepcopy
import json
from types import SimpleNamespace
import unittest

from kp_agent.campaign import CampaignDefinition
from kp_agent.graph import ROOT
from kp_agent.models import DemoPlanner, DeepSeekResponsesPlanner
from tests.fixtures_common import build_fixtures, public_context
from tests.test_campaign_v2 import fixed_character


class ActionSafetyV2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.campaign = CampaignDefinition.load(ROOT / "data/campaign.json")
        cls.character = fixed_character().to_dict()
        cls.fixtures = build_fixtures(cls.campaign, cls.character)

    def context(self, fixture):
        return public_context(self.campaign, self.fixtures[fixture], self.character)

    def model_plan(self, text, fixture, intent, target=None, item=None, *, query=None, history=(), captured=None):
        raw = {"intent": intent, "target_id": target, "item_id": item,
               "query": query, "question": None}
        response = SimpleNamespace(status="completed", output_text=json.dumps(raw),
                                   model="offline-fake", usage=None)
        def create(**kwargs):
            if captured is not None:
                captured.update(json.loads(kwargs["input"]))
            return response
        client = SimpleNamespace(responses=SimpleNamespace(create=create))
        return DeepSeekResponsesPlanner(client=client).plan(text, self.context(fixture), history)

    def test_negations_guard_demo_and_erroneous_model_actions(self):
        cases = [
            ("我不去车站", "study_ready", "move", "exit", None),
            ("我不想现在去车站", "study_ready", "move", "exit", None),
            ("我不去书房", "station_start", "move", "back_exit", None),
            ("我不检查壁炉", "study_start", "investigate", "fireplace", None),
            ("我不是要检查站台", "station_start", "investigate", "platform", None),
            ("我不打算马上调查书桌", "study_start", "investigate", "desk", None),
            ("先别急着调查书桌", "study_start", "investigate", "desk", None),
            ("我还没决定去车站", "study_ready", "move", "exit", None),
            ("这次不用黄铜钥匙打开柜子", "station_located", "use_item", "locker", "locker_key"),
            ("先不要带我走", "study_ready", "move", "exit", None),
            ("不要问管家", "study_start", "talk", "butler", None),
            ("先不结束调查", "archive_start", "finish", "exit", None),
        ]
        for text, fixture, intent, target, item in cases:
            with self.subTest(text=text):
                context = self.context(fixture)
                before = deepcopy(context)
                self.assertEqual("clarify", DemoPlanner().plan(text, context).intent)
                self.assertEqual(context, before)
                self.assertEqual("clarify", self.model_plan(text, fixture, intent, target, item).intent)

    def test_hypothetical_or_permission_questions_never_roll_or_move(self):
        cases = [
            ("如果我检查壁炉会怎样", "study_start", "investigate", "fireplace"),
            ("假如我检查站台呢", "station_start", "investigate", "platform"),
            ("我只是想知道调查书桌会怎样", "study_start", "investigate", "desk"),
            ("书桌需要调查吗", "study_start", "investigate", "desk"),
            ("能不能先检查站台", "station_start", "investigate", "platform"),
            ("靠近检查松动的站台（有失足风险）是什么意思", "station_start", "investigate", "platform"),
            ("你说前往旧车站是什么意思", "study_ready", "move", "exit"),
            ("可以前往旧车站吗", "study_ready", "move", "exit"),
            ("我去车站可以吗", "study_ready", "move", "exit"),
            ("假设我前往车站", "study_ready", "move", "exit"),
            ("前往旧书房有什么风险", "station_start", "move", "back_exit"),
        ]
        for text, fixture, intent, target in cases:
            with self.subTest(text=text):
                self.assertEqual("clarify", DemoPlanner().plan(text, self.context(fixture)).intent)
                self.assertEqual("clarify", self.model_plan(text, fixture, intent, target).intent)

    def test_direct_and_conditional_instructions_are_still_actions(self):
        cases = [
            ("如果没问题就前往车站", "study_ready", "move", "exit"),
            ("我不想留在这里，去车站", "study_ready", "move", "exit"),
            ("现在实际检查站台", "station_start", "investigate", "platform"),
            ("仔细调查书桌", "study_start", "investigate", "desk"),
            ("返回旧书房", "station_start", "move", "back_exit"),
            ("结束本次调查", "archive_start", "finish", "exit"),
        ]
        for text, fixture, intent, target in cases:
            with self.subTest(text=text):
                demo = DemoPlanner().plan(text, self.context(fixture))
                online = self.model_plan(text, fixture, intent, target)
                self.assertEqual((intent, target), (demo.intent, demo.target_id))
                self.assertEqual((intent, target), (online.intent, online.target_id))

    def test_question_to_npc_is_talk_but_cannot_execute_mentioned_risk(self):
        text = "问问管家，如果我检查壁炉会怎样"
        demo = DemoPlanner().plan(text, self.context("study_start"))
        online_talk = self.model_plan(text, "study_start", "talk", "butler")
        online_wrong = self.model_plan(text, "study_start", "investigate", "fireplace")
        self.assertEqual(("talk", "butler"), (demo.intent, demo.target_id))
        self.assertEqual(("talk", "butler"), (online_talk.intent, online_talk.target_id))
        self.assertEqual("clarify", online_wrong.intent)

    def test_asking_about_talking_does_not_start_rewarding_npc_dialogue(self):
        for text in ("如果我问管家会怎样", "我只是想知道询问管家会获得什么", "我问问管家可以吗"):
            with self.subTest(text=text):
                self.assertEqual("clarify", DemoPlanner().plan(text, self.context("study_start")).intent)
                self.assertEqual("clarify", self.model_plan(text, "study_start", "talk", "butler").intent)

    def test_existing_item_and_ending_explanations_stay_read_only(self):
        for text, fixture, intent, target, item, expected in [
            ("绷带怎么用", "study_start", "use_item", "self", "bandage", "item_bandage"),
            ("这里怎么结束本次调查", "study_start", "finish", "exit", None, "exit"),
        ]:
            with self.subTest(text=text):
                demo = DemoPlanner().plan(text, self.context(fixture))
                online = self.model_plan(text, fixture, intent, target, item)
                self.assertEqual(("look", expected), (demo.intent, demo.target_id))
                self.assertEqual(("look", expected), (online.intent, online.target_id))

    def test_short_target_reply_does_not_turn_old_hypothesis_into_execution(self):
        history = [{"role": "user", "content": "如果我检查书桌会怎样"},
                   {"role": "assistant", "content": "这次先不执行，你想了解哪个行动？"}]
        plan = DemoPlanner().plan("书桌", self.context("study_start"), history,
                                  pending_question=history[-1]["content"])
        self.assertEqual("clarify", plan.intent)

    def test_unclear_negated_compound_request_conservatively_asks(self):
        # There are two action clauses. This guard does not try to rewrite the
        # request into just its positive half; the player can answer explicitly.
        text = "我不检查壁炉，改去车站"
        self.assertEqual("clarify", DemoPlanner().plan(text, self.context("study_ready")).intent)
        self.assertEqual("clarify", self.model_plan(text, "study_ready", "move", "exit").intent)

    def test_new_object_or_action_does_not_inherit_old_rule_topic(self):
        history = [{"role": "user", "content": "什么是理智检定"},
                   {"role": "assistant", "content": "理智检定使用D100，成功和失败会有不同的理智损失。"}]
        cases = [
            ("我问问管家信里这句话是什么意思", "talk", "butler"),
            ("我查看照片，看看号码是什么意思", "look", "clue_photograph"),
            ("我检查书桌，再举个例子", "investigate", "desk"),
            ("我准备观察，先说通俗一些", "look", "room"),
        ]
        for text, intent, target in cases:
            with self.subTest(text=text):
                demo = DemoPlanner().plan(text, self.context("study_ready"), history)
                captured = {}
                online = self.model_plan(text, "study_ready", intent, target,
                                         history=history, captured=captured)
                self.assertEqual((intent, target), (demo.intent, demo.target_id))
                self.assertEqual((intent, target), (online.intent, online.target_id))
                self.assertIsNone(captured["rule_followup_query"])

    def test_pure_rule_followup_keeps_recent_topic(self):
        history = [{"role": "user", "content": "什么是理智检定"},
                   {"role": "assistant", "content": "理智检定使用D100，成功和失败会有不同的理智损失。"}]
        for text in ("说得通俗一些", "举个例子", "没看懂", "这个呢"):
            with self.subTest(text=text):
                demo = DemoPlanner().plan(text, self.context("study_ready"), history)
                captured = {}
                online = self.model_plan(text, "study_ready", "rule_question",
                                         query="理智检定的通俗说明", history=history, captured=captured)
                self.assertEqual("rule_question", demo.intent)
                self.assertIn("理智检定", demo.query)
                self.assertIn("理智检定", captured["rule_followup_query"])
                self.assertEqual("rule_question", online.intent)

    def test_generic_rule_usage_question_is_not_inventory_usage(self):
        for text in ("奖励骰怎么用", "理智规则如何使用"):
            with self.subTest(text=text):
                self.assertEqual("rule_question", DemoPlanner().plan(text, self.context("study_start")).intent)

    def test_plot_followup_without_rule_history_does_not_inherit_a_rule(self):
        history = [{"role": "user", "content": "观察书房"},
                   {"role": "assistant", "content": "管家站在门边，窗外下着雨。"}]
        for text in ("这个呢", "什么意思"):
            with self.subTest(text=text):
                self.assertNotEqual("rule_question", DemoPlanner().plan(text, self.context("study_start"), history).intent)


if __name__ == "__main__":
    unittest.main()
