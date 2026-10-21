"""Exercise production post-model guards with fake Responses, never a network."""
import json
from types import SimpleNamespace
import unittest

from kp_agent.campaign import CampaignDefinition
from kp_agent.graph import ROOT
from kp_agent.models import DeepSeekResponsesPlanner, ModelCallError
from scripts.generalization_eval import build_fixtures, public_context
from tests.test_campaign_v2 import fixed_character


class ModelGuardsV2Tests(unittest.TestCase):
    def setUp(self):
        self.campaign = CampaignDefinition.load(ROOT / "data/campaign.json")
        self.character = fixed_character().to_dict()
        self.fixtures = build_fixtures(self.campaign, self.character)

    def plan(self, text, fixture, intent, target=None, item=None, query=None):
        raw = {"intent": intent, "target_id": target, "item_id": item,
               "query": query, "question": None}
        response = SimpleNamespace(status="completed", output_text=json.dumps(raw),
                                   model="fake-test-response", usage=None)
        client = SimpleNamespace(responses=SimpleNamespace(create=lambda **kwargs: response))
        planner = DeepSeekResponsesPlanner(client=client)
        context = public_context(self.campaign, self.fixtures[fixture], self.character)
        return planner.plan(text, context, [])

    def test_model_cannot_replace_a_named_physical_target(self):
        result = self.plan("用黄铜钥匙打开站台", "station_located", "use_item", "locker", "locker_key")
        self.assertEqual("clarify", result.intent)

    def test_model_cannot_replace_a_named_held_item(self):
        result = self.plan("用黄铜钥匙给自己包扎", "study_ready", "use_item", "self", "bandage")
        self.assertEqual("clarify", result.intent)

    def test_how_to_finish_reads_the_exit_instead_of_rule_rag(self):
        result = self.plan("这里怎么结束本次调查", "study_start", "rule_question", query="结束调查规则")
        self.assertEqual(("look", "exit", None), (result.intent, result.target_id, result.query))

    def test_negated_finish_cannot_execute_an_erroneous_model_plan(self):
        result = self.plan("先不结束调查", "archive_start", "finish", "exit")
        self.assertEqual("clarify", result.intent)

    def test_asking_item_usage_does_not_consume(self):
        result = self.plan("能否介绍绷带怎么用", "study_start", "use_item", "self", "bandage")
        self.assertEqual(("look", "item_bandage"), (result.intent, result.target_id))

    def test_spent_pair_only_allows_the_existing_repeat_explanation(self):
        result = self.plan("再用黄铜钥匙打开17号柜", "station_two_routes", "use_item", "locker", "locker_key")
        self.assertEqual(("use_item", "locker", "locker_key"), (result.intent, result.target_id, result.item_id))

    def test_future_target_is_rejected(self):
        with self.assertRaises(ModelCallError) as error:
            self.plan("去未来地点", "study_start", "look", "scholar")
        self.assertEqual("target_not_available", error.exception.code)

    def test_matching_words_do_not_make_an_invalid_item_pair_legal(self):
        with self.assertRaises(ModelCallError):
            self.plan("用黄铜钥匙打开站台", "station_located", "use_item", "platform", "locker_key")


if __name__ == "__main__":
    unittest.main()
