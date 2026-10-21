"""Public descriptions and next steps must agree with saved facts.

All service checks use a temporary database and scripted planner. No .env,
player saves, random real rolls or network requests are used.
"""
from __future__ import annotations

import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from kp_agent.campaign import CampaignDefinition
from kp_agent.graph import KeeperService, ROOT
from kp_agent.guidance import build_guidance
from kp_agent.models import DemoPlanner
from kp_agent.retrieval import RetrievalService
from kp_agent.schemas import ActionPlan
from tests import test_campaign_v2 as fixtures


class GuidanceContextTests(fixtures.CampaignFixture, unittest.TestCase):
    def setUp(self):
        self.campaign = CampaignDefinition.load(ROOT / "data/campaign.json")
        self.state = self.campaign.initial_state(san=55)
        self.character = fixtures.fixed_character().to_dict()

    def context(self):
        return {**self.campaign.planning_context(self.state),
                "character": copy.deepcopy(self.character)}

    def recovery_only(self):
        context = self.context()
        context["action_suggestions"] = [row for row in context["action_suggestions"]
                                         if row.get("item_id") == "bandage"]
        return context

    def test_full_hp_never_recommends_bandage(self):
        self.assertEqual([], build_guidance(self.recovery_only())["suggested_actions"])

    def test_missing_hp_does_not_assume_an_injury(self):
        context = self.recovery_only()
        del context["character"]
        self.assertEqual([], build_guidance(context)["suggested_actions"])

    def test_malformed_hp_does_not_recommend_treatment(self):
        for value in (None, "8", True, -1, 11):
            with self.subTest(value=value):
                context = self.recovery_only()
                context["character"]["hp"] = value
                self.assertEqual([], build_guidance(context)["suggested_actions"])

    def test_actual_deficit_allows_recovery_advice(self):
        self.character["hp"] = 8
        advice = build_guidance(self.recovery_only())["suggested_actions"]
        self.assertEqual(1, len(advice))
        self.assertIn("止血包", advice[0])

    def test_empty_inventory_never_recommends_recovery(self):
        self.character["hp"] = 8
        context = self.recovery_only()
        context["inventory"]["bandage"]["quantity"] = 0
        self.assertEqual([], build_guidance(context)["suggested_actions"])

    def test_recovery_filter_does_not_remove_explicit_legal_item_use(self):
        context = self.context()
        self.assertIn("use_item", next(t for t in context["targets"] if t["id"] == "self")["actions"])
        self.campaign.validate_plan({"action_type": "use_item", "target_id": "self", "item_id": "bandage"}, self.state)

    def test_full_hp_self_description_does_not_invent_a_wound(self):
        result = self.action("look", "self")
        self.assertNotIn("擦伤", result["public_event"]["text"])

    def test_spent_bandage_is_not_described_as_still_held(self):
        self.state["inventory"]["bandage"]["quantity"] = 0
        result = self.action("look", "self")
        self.assertNotIn("带着一份", result["public_event"]["text"])
        self.assertIn("没有", result["public_event"]["text"])

    def test_room_look_not_repeated_as_filler(self):
        context = self.context()
        context["action_suggestions"] = [{"intent": "look", "target_id": "room", "label": "观察周围"}]
        self.assertEqual([], build_guidance(context, {"action_type": "look", "target_id": "room"})["suggested_actions"])

    def test_completed_actions_are_not_recommended_after_reopening(self):
        self.action("investigate", "desk", passed=True)
        self.action("talk", "butler")
        self.action("investigate", "bookshelf")
        self.action("investigate", "fireplace")
        advice = build_guidance(self.context())["suggested_actions"]
        self.assertIn("前往旧车站", advice)
        self.assertFalse(any(word in text for text in advice for word in ("止血包", "观察周围", "询问管家", "调查书桌")))

    def test_failed_check_recommends_alternative_instead_of_repeat(self):
        self.action("investigate", "desk", passed=False)
        advice = build_guidance(self.context())["suggested_actions"]
        self.assertTrue(any("十分钟" in text for text in advice))
        self.assertNotIn("调查书桌", advice)

    def test_reading_solved_ledger_uses_known_result(self):
        self.to_archive()
        self.action("investigate", "ledger", passed=True)
        result = self.action("look", "ledger")
        self.assertNotIn("页码错乱", result["public_event"]["text"])
        self.assertIn("维护日志", result["public_event"]["text"])

    def test_fallback_solved_ledger_also_uses_known_result(self):
        self.to_archive()
        self.action("investigate", "ledger", passed=False)
        self.action("careful_search", "ledger")
        result = self.action("look", "ledger")
        self.assertNotIn("页码错乱", result["public_event"]["text"])
        self.assertIn("维护日志", result["public_event"]["text"])

    def test_unknown_ledger_facts_are_not_revealed_early(self):
        self.to_archive()
        text = self.action("look", "ledger")["public_event"]["text"]
        self.assertIn("页码错乱", text)
        self.assertNotIn("人为破坏", text)

    def test_complete_ending_not_labelled_as_retreat_or_duplicated(self):
        self.seal_archive()
        context = self.context()
        ending_advice = [row for row in context["action_suggestions"]
                         if row["intent"] in {"leave", "finish"}]
        self.assertEqual(1, len(ending_advice))
        self.assertFalse(any("撤退" in row["label"] for row in ending_advice))
        self.assertEqual("complete", self.action("finish", "exit")["state"]["ending"])

    def test_ended_panel_describes_the_ending_instead_of_an_active_room(self):
        self.seal_archive()
        self.action("leave", "exit")
        context = self.campaign.public_context(self.state)
        self.assertIn("调查结束", context["description"])
        self.assertIn("走出安全出口", context["description"])
        self.assertEqual([], context["targets"])
        self.assertEqual([], context["destinations"])
        self.assertTrue(context["revealed_clues"])

    def test_retreat_panel_does_not_reveal_unacquired_ending_information(self):
        self.action("finish", "exit")
        context = self.campaign.public_context(self.state)
        self.assertIn("撤退", context["description"])
        self.assertNotIn("机械", context["description"])
        self.assertEqual([], context["targets"])

    def test_ended_and_paused_games_have_no_next_action_advice(self):
        for status in ("ended", "paused"):
            with self.subTest(status=status):
                self.state["status"] = status
                self.assertEqual({"guidance": "", "suggested_actions": []}, build_guidance(self.context()))

    def test_question_and_takeover_do_not_get_automatic_advice(self):
        for reply_type in ("question", "takeover", "review"):
            with self.subTest(reply_type=reply_type):
                self.assertEqual([], build_guidance(self.context(), reply_type=reply_type)["suggested_actions"])


class GuidanceServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / "guidance.sqlite3"
        self.planner = fixtures.ScriptPlanner()
        self.services = []
        self.serial = 0
        self.char_patch = patch("kp_agent.graph.default_character", side_effect=fixtures.fixed_character)
        self.char_patch.start()
        self.addCleanup(self.char_patch.stop)

    def tearDown(self):
        for service in reversed(self.services):
            service.close()

    def service(self, rolls=()):
        result = KeeperService(db_path=self.db, planner=self.planner,
                               retrieval=fixtures.NullRetrieval(), rng=fixtures.SequenceRandom(rolls))
        self.services.append(result)
        result.start()
        return result

    def act(self, service, intent, target, item=None):
        self.serial += 1
        self.planner.next_plan = ActionPlan(intent=intent, target_id=target, item_id=item)
        return service.handle_message(f"hint-{self.serial}", f"离线测试{self.serial}")

    def prepare_study(self, service):
        self.act(service, "investigate", "desk")
        self.act(service, "talk", "butler")
        self.act(service, "investigate", "bookshelf")
        return self.act(service, "investigate", "fireplace")

    def test_screenshot_sanity_success_has_zero_loss_and_no_bandage_advice(self):
        service = self.service([23, 38])
        reply = self.prepare_study(service)
        self.assertEqual((10, 55), (reply["character"]["hp"], reply["character"]["san"]))
        self.assertEqual(38, reply["rolls"][0]["roll"])
        self.assertFalse(any("止血包" in text or "观察周围" in text for text in reply["suggested_actions"]))
        resumed = self.service().start()
        self.assertEqual(reply["suggested_actions"], resumed["suggested_actions"])

    def test_post_damage_and_post_heal_advice_uses_new_hp(self):
        service = self.service([23, 99, 2])
        self.act(service, "investigate", "desk")
        self.act(service, "talk", "butler")
        self.act(service, "move", "exit")
        injury = self.act(service, "investigate", "platform")
        self.assertEqual(8, injury["character"]["hp"])
        self.assertTrue(any("止血包" in text for text in injury["suggested_actions"]))
        healed = self.act(service, "use_item", "self", "bandage")
        self.assertEqual(10, healed["character"]["hp"])
        self.assertEqual(0, healed["progress"]["inventory"]["bandage"]["quantity"])
        self.assertFalse(any("止血包" in text for text in healed["suggested_actions"]))
        self.act(service, "move", "back_exit")
        description = self.act(service, "look", "self")["reply"]
        self.assertNotIn("带着一份", description)

    def test_invalid_action_feedback_also_uses_real_hp(self):
        service = self.service([23, 38])
        self.prepare_study(service)
        reply = self.act(service, "investigate", "nonexistent")
        self.assertEqual("question", reply["reply_type"])
        self.assertNotIn("止血包", reply["reply"])
        self.assertNotIn("观察周围", reply["reply"])

    def test_hypothetical_fireplace_question_never_rolls_sanity(self):
        service = self.service()
        service.planner = DemoPlanner()
        before = service.storage.get_game()
        reply = service.handle_message("hypothetical", "如果我检查壁炉会怎样")
        self.assertEqual([], reply["rolls"])
        self.assertEqual(before["character"], service.storage.get_game()["character"])
        self.assertEqual(before["scene_state"], service.storage.get_game()["scene_state"])
        self.assertEqual(0, service.tools.rng.calls)

    def test_negated_movement_leaves_character_in_the_same_scene(self):
        service = self.service([23])
        self.act(service, "investigate", "desk")
        self.act(service, "talk", "butler")
        service.planner = DemoPlanner()
        before = service.storage.get_game()
        reply = service.handle_message("negated-move", "我不想现在去车站")
        self.assertEqual("study", reply["progress"]["scene_id"])
        self.assertIsNone(reply["scene_transition"])
        self.assertEqual(before["scene_state"], service.storage.get_game()["scene_state"])

    def test_asking_about_platform_risk_does_not_roll_or_hurt(self):
        service = self.service([23])
        self.act(service, "investigate", "desk")
        self.act(service, "talk", "butler")
        self.act(service, "move", "exit")
        service.planner = DemoPlanner()
        before = service.storage.get_game()
        reply = service.handle_message("risk-question", "靠近检查松动的站台（有失足风险）是什么意思")
        self.assertEqual([], reply["rolls"])
        self.assertEqual(before["character"], service.storage.get_game()["character"])
        self.assertEqual(before["scene_state"], service.storage.get_game()["scene_state"])
        self.assertEqual(1, service.tools.rng.calls)  # Only the earlier desk check.

    def test_new_npc_question_after_rule_explanation_is_not_hijacked(self):
        service = self.service()
        service.planner = DemoPlanner()
        service.retrieval = RetrievalService()
        explanation = service.handle_message("san-rule", "什么是理智检定")
        self.assertEqual("rule_explanation", explanation["reply_type"])
        reply = service.handle_message("new-npc", "我问问管家信里这句话是什么意思")
        self.assertEqual("narration", reply["reply_type"])
        self.assertIn("photograph", {clue["id"] for clue in reply["new_clues"]})
        self.assertEqual(1, reply["progress"]["inventory"]["locker_key"]["quantity"])
        self.assertEqual([], reply["rolls"])


if __name__ == "__main__":
    unittest.main()
