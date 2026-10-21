"""Three-scene and tool integration checks; no .env, SDK call or paid API.

The planner is scripted, retrieval is empty, and every save lives in a temporary
directory. These verify control/state behavior, not natural-language quality.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from kp_agent.campaign import CampaignDefinition
from kp_agent.graph import KeeperService
from kp_agent.scene import SceneValidationError
from kp_agent.schemas import ActionPlan
from trpg import Character


ROOT = Path(__file__).resolve().parents[1]


def fixed_character() -> Character:
    return Character(
        name="理查德", age=30, occupation="研究员",
        attributes={"STR": 65, "CON": 45, "DEX": 45, "APP": 65,
                    "POW": 55, "INT": 75, "SIZ": 60, "EDU": 75},
        skills={"侦查": 55, "聆听": 60, "图书馆使用": 55},
        hp=10, hp_max=10, san=55, san_max=99, mp=11, mp_max=11, luck=50,
    )


class SequenceRandom:
    def __init__(self, values=()):
        self.values = iter(values)
        self.calls = 0

    def randint(self, low, high):
        value = next(self.values)
        if not low <= value <= high:
            raise AssertionError(f"测试骰子 {value} 不在 {low}–{high} 范围内")
        self.calls += 1
        return value


class NullRetrieval:
    def search(self, query, top_k=4):
        return []


class ScriptPlanner:
    mode = "offline-test"
    mode_label = "离线测试规划器，不是大模型"

    def __init__(self):
        self.next_plan = ActionPlan(intent="look", target_id="room")
        self.plan_calls = 0
        self.fail_next_narration = False

    def plan(self, text, context, history=(), pending_question=None):
        self.plan_calls += 1
        return self.next_plan

    def narrate(self, text, public_facts, history=()):
        if self.fail_next_narration:
            self.fail_next_narration = False
            raise RuntimeError("模拟已结算后的叙述失败")
        return public_facts["event"]["text"]


class CampaignFixture:
    def action(self, intent, target=None, *, item=None, passed=None):
        result = self.campaign.resolve_action(
            {"action_type": intent, "target_id": target, "item_id": item}, self.state, passed,
        )
        self.state = result["state"]
        return result

    def to_station(self, *, failed=False):
        self.action("investigate", "desk", passed=not failed)
        if failed:
            self.action("careful_search", "desk")
        self.action("talk", "butler")
        return self.action("move", "exit")

    def to_archive(self, *, failed=False):
        self.to_station(failed=failed)
        self.action("investigate", "locker", passed=not failed)
        if failed:
            self.action("careful_search", "locker")
        self.action("use_item", "locker", item="locker_key")
        self.action("use_item", "archive_gate", item="archive_key")
        return self.action("move", "exit")

    def seal_archive(self, *, failed=False):
        self.to_archive(failed=failed)
        self.action("investigate", "ledger", passed=not failed)
        if failed:
            self.action("careful_search", "ledger")
        self.action("talk", "scholar")
        return self.action("use_item", "seal_console", item="seal_token")


class TestCampaignState(CampaignFixture, unittest.TestCase):
    def setUp(self):
        self.campaign = CampaignDefinition.load(ROOT / "data/campaign.json")
        self.state = self.campaign.initial_state(san=55)

    def test_initial_context_contains_no_future_entities_or_hidden_item_uses(self):
        context = self.campaign.planning_context(self.state)
        self.assertEqual(["study"], [entry["id"] for entry in context["visited_scenes"]])
        self.assertEqual([], context["destinations"])
        targets = {target["id"] for target in context["targets"]}
        self.assertNotIn("ledger", targets)
        self.assertNotIn("scholar", targets)
        self.assertNotIn("clue_letter", targets)
        self.assertEqual({"bandage"}, set(context["inventory"]))
        rendered = json.dumps(context, ensure_ascii=False)
        for secret in ("requires_clues", "grant_items", '"effects"', "人为破坏", "seal_closed"):
            self.assertNotIn(secret, rendered)

    def test_successful_main_line_reaches_final_scene_and_complete_ending(self):
        self.seal_archive()
        self.assertEqual("playing", self.state["status"])
        self.assertEqual("archive", self.state["scene_id"])
        result = self.action("leave", "exit")
        self.assertEqual("ended", result["game_status"])
        self.assertEqual("complete", self.state["ending"])
        self.assertEqual(["study", "station", "archive"], self.state["visited_scenes"])
        for item_id in ("locker_key", "archive_key", "seal_token"):
            self.assertEqual(0, self.state["inventory"][item_id]["quantity"])

    def test_every_key_check_can_fail_without_softlocking_the_story(self):
        self.seal_archive(failed=True)
        self.assertEqual(30, self.state["elapsed_minutes"])
        self.assertIn("letter", self.state["revealed_clues"])
        self.assertIn("locker_location", self.state["revealed_clues"])
        self.assertIn("archive_record", self.state["revealed_clues"])
        self.action("leave", "exit")
        self.assertEqual("complete", self.state["ending"])

    def test_critical_failure_alternative_does_not_roll_or_repeat_time(self):
        self.action("investigate", "desk", passed=False)
        alternative = self.campaign.validate_plan({"action_type": "careful_search", "target_id": "desk"}, self.state)
        self.assertIsNone(alternative["check"])
        self.action("careful_search", "desk")
        repeated = self.action("careful_search", "desk")
        self.assertEqual(10, self.state["elapsed_minutes"])
        self.assertEqual([], repeated["clues"])
        self.assertEqual([], repeated["effects"])
        self.assertTrue(repeated["public_event"]["repeated"])

    def test_cannot_take_alternative_before_failure_or_after_first_success(self):
        plan = {"action_type": "careful_search", "target_id": "desk"}
        with self.assertRaises(SceneValidationError):
            self.campaign.validate_plan(plan, self.state)
        self.action("investigate", "desk", passed=True)
        with self.assertRaises(SceneValidationError):
            self.campaign.validate_plan(plan, self.state)

    def test_return_visits_keep_attempts_and_never_regrant_keys(self):
        self.to_station()
        self.action("investigate", "locker", passed=True)
        self.action("use_item", "locker", item="locker_key")
        inventory = copy.deepcopy(self.state["inventory"])
        self.action("move", "back_exit")
        talk = self.action("talk", "butler")
        self.assertEqual([], talk["public_event"]["new_items"])
        self.assertEqual(inventory, self.state["inventory"])
        repeated = self.campaign.validate_plan({"action_type": "investigate", "target_id": "desk"}, self.state)
        self.assertIsNone(repeated["check"])
        self.action("move", "exit")
        again = self.action("use_item", "locker", item="locker_key")
        self.assertEqual(inventory, self.state["inventory"])
        self.assertEqual([], again["public_event"]["new_items"])
        self.assertEqual([], again["public_event"]["consumed_items"])

    def test_backtracking_does_not_reset_sanity_event_or_fallback_cost(self):
        first = self.action("investigate", "fireplace")
        self.assertEqual(1, len(first["effects"]))
        self.to_station(failed=True)
        self.action("move", "back_exit")
        repeated = self.action("investigate", "fireplace")
        self.assertEqual([], repeated["effects"])
        self.action("careful_search", "desk")
        self.assertEqual(10, self.state["elapsed_minutes"])
        self.assertEqual(1, self.state["triggered_events"].count("fireplace_drawing"))

    def test_acquired_clues_and_items_are_read_only_in_every_scene(self):
        self.to_station()
        before = copy.deepcopy(self.state)
        read = self.action("look", "clue_letter")
        self.assertIn("保管箱", read["public_event"]["text"])
        self.assertEqual(before, self.state)
        read = self.action("look", "item_locker_key")
        self.assertIn("当前剩余数量", read["public_event"]["text"])
        self.assertEqual(before, self.state)
        for target in ("clue_letter", "item_locker_key"):
            with self.assertRaises(SceneValidationError):
                self.campaign.validate_plan({"action_type": "investigate", "target_id": target}, self.state)
        with self.assertRaises(SceneValidationError):
            self.campaign.validate_plan({"action_type": "look", "target_id": "clue_archive_record"}, self.state)

    def test_item_cannot_be_created_or_used_on_an_unapproved_target(self):
        before = copy.deepcopy(self.state)
        for plan in (
            {"action_type": "use_item", "target_id": "desk", "item_id": "locker_key"},
            {"action_type": "use_item", "target_id": "desk", "item_id": "bandage"},
            {"action_type": "use_item", "target_id": "self", "item_id": "bandage", "grant_items": ["seal_token"]},
        ):
            with self.assertRaises(SceneValidationError):
                self.campaign.validate_plan(plan, self.state)
        self.assertEqual(before, self.state)

    def test_exits_only_reveal_currently_reachable_destinations(self):
        with self.assertRaises(SceneValidationError):
            self.campaign.validate_plan({"action_type": "move", "target_id": "exit"}, self.state)
        self.to_station()
        self.assertEqual({"study"}, {entry["scene_id"] for entry in self.campaign.public_context(self.state)["destinations"]})
        self.action("investigate", "locker", passed=True)
        self.action("use_item", "locker", item="locker_key")
        self.assertNotIn("archive", {entry["scene_id"] for entry in self.campaign.public_context(self.state)["destinations"]})
        self.action("use_item", "archive_gate", item="archive_key")
        self.assertIn("archive", {entry["scene_id"] for entry in self.campaign.public_context(self.state)["destinations"]})

    def test_completing_requirements_does_not_teleport_an_exit_from_another_scene(self):
        self.seal_archive()
        self.action("move", "back_exit")
        self.action("move", "back_exit")
        self.action("finish", "exit")
        self.assertEqual("study", self.state["scene_id"])
        self.assertEqual("retreat", self.state["ending"])

    def test_final_information_insufficient_ending_and_campaign_review(self):
        self.to_archive()
        self.action("leave", "exit")
        self.assertEqual("incomplete", self.state["ending"])
        before = copy.deepcopy(self.state)
        review = self.campaign.review(self.state)
        self.assertIn("archive_record", {clue["id"] for clue in review["missed_clues"]})
        self.assertEqual(before, self.state)
        self.assertEqual("incomplete", review["ending"])

    def test_review_cannot_reveal_campaign_secrets_before_an_ending(self):
        for status in ("playing", "paused"):
            with self.assertRaises(SceneValidationError):
                self.campaign.review({**self.state, "status": status})

    def test_wrong_campaign_save_cannot_be_interpreted_as_this_story(self):
        with self.assertRaises(SceneValidationError):
            self.campaign.public_context({**self.state, "campaign_id": "some_other_story"})

    def test_revised_authored_rules_cannot_reuse_an_older_campaign_save(self):
        self.assertEqual(self.campaign.revision, self.state["campaign_revision"])
        changed_scenes = copy.deepcopy(self.campaign.scenes)
        changed_scenes["study"].definition["targets"]["desk"]["investigate"]["check"]["difficulty"] = "hard"
        changed = CampaignDefinition(copy.deepcopy(self.campaign.definition), changed_scenes)
        self.assertNotEqual(self.campaign.revision, changed.revision)
        with self.assertRaises(SceneValidationError):
            changed.validate_plan({"action_type": "investigate", "target_id": "desk"}, self.state)


class TestCampaignService(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / "campaign.sqlite3"
        self.services = []
        self.planner = ScriptPlanner()
        self.number = 0
        self.character_patch = patch("kp_agent.graph.default_character", side_effect=fixed_character)
        self.character_patch.start()
        self.addCleanup(self.character_patch.stop)

    def tearDown(self):
        for service in reversed(self.services):
            service.close()

    def make_service(self, values=()):
        service = KeeperService(db_path=self.db, planner=self.planner,
                                retrieval=NullRetrieval(), rng=SequenceRandom(values))
        self.services.append(service)
        service.start()
        return service

    def act(self, service, intent, target=None, *, item=None):
        self.number += 1
        self.planner.next_plan = ActionPlan(intent=intent, target_id=target, item_id=item)
        return service.handle_message(f"m{self.number}", f"离线动作{self.number}", service.get_game()["game_id"])

    def to_station(self, service):
        self.act(service, "investigate", "desk")
        self.act(service, "talk", "butler")
        return self.act(service, "move", "exit")

    def to_archive(self, service):
        self.to_station(service)
        self.act(service, "investigate", "locker")
        self.act(service, "use_item", "locker", item="locker_key")
        self.act(service, "use_item", "archive_gate", item="archive_key")
        return self.act(service, "move", "exit")

    def test_service_returns_transitions_and_full_campaign_ending(self):
        service = self.make_service([23, 23, 23])
        transition = self.to_archive(service)
        self.assertEqual({"from": "station", "to": "archive", "title": "地下档案室"}, transition["scene_transition"])
        self.act(service, "investigate", "ledger")
        self.act(service, "talk", "scholar")
        sealed = self.act(service, "use_item", "seal_console", item="seal_token")
        self.assertEqual([], sealed["changes"])
        ending = self.act(service, "leave", "exit")
        self.assertEqual("complete", ending["progress"]["ending"])
        self.assertEqual(3, service.tools.rng.calls)
        before = service.storage.get_game()
        review = service.handle_message("review", "/review", before["game_id"])
        self.assertEqual("review", review["reply_type"])
        self.assertEqual([], review["new_clues"])
        self.assertEqual(before, service.storage.get_game())

    def test_full_hp_healing_does_not_consume_the_bandage(self):
        service = self.make_service()
        result = self.act(service, "use_item", "self", item="bandage")
        self.assertEqual(1, result["progress"]["inventory"]["bandage"]["quantity"])
        self.assertEqual([], result["changes"])
        self.assertIn("没有消耗", result["reply"])
        self.assertNotIn("use_item:self:bandage", service.storage.get_game()["scene_state"]["attempts"])

    def test_station_damage_and_healing_use_existing_character_values_once(self):
        service = self.make_service([23, 99, 2])
        self.to_station(service)
        injured = self.act(service, "investigate", "platform")
        self.assertEqual(8, injured["character"]["hp"])
        healed = self.act(service, "use_item", "self", item="bandage")
        self.assertEqual(10, healed["character"]["hp"])
        self.assertEqual(0, healed["progress"]["inventory"]["bandage"]["quantity"])
        self.assertEqual(3, service.tools.rng.calls)
        duplicate = self.act(service, "use_item", "self", item="bandage")
        self.assertEqual([], duplicate["changes"])
        self.assertEqual(10, duplicate["character"]["hp"])
        self.assertEqual([], self.act(service, "investigate", "platform")["rolls"])

    def test_sanity_is_global_and_survives_return_and_process_restart(self):
        service = self.make_service([99, 2, 23])
        sanity = self.act(service, "investigate", "fireplace")
        self.assertEqual(53, sanity["character"]["san"])
        self.to_station(service)
        self.act(service, "move", "back_exit")
        repeated = self.act(service, "investigate", "fireplace")
        self.assertEqual([], repeated["rolls"])
        self.assertEqual(53, repeated["character"]["san"])
        restored = self.make_service()
        self.assertEqual(53, restored.get_character()["san"])
        self.assertEqual("study", restored.get_progress()["scene_id"])
        again = self.act(restored, "investigate", "fireplace")
        self.assertEqual([], again["rolls"])

    def test_narration_failure_after_key_reward_reuses_committed_inventory(self):
        service = self.make_service([23, 23])
        self.to_station(service)
        self.act(service, "investigate", "locker")
        self.planner.next_plan = ActionPlan(intent="use_item", target_id="locker", item_id="locker_key")
        self.planner.fail_next_narration = True
        gid = service.get_game()["game_id"]
        with self.assertRaises(RuntimeError):
            service.handle_message("key-turn", "打开已经找到的柜子", gid)
        before = service.storage.get_game()
        calls = self.planner.plan_calls
        result = service.handle_message("key-turn", "打开已经找到的柜子", gid)
        self.assertEqual(calls, self.planner.plan_calls)
        self.assertEqual(before, service.storage.get_game())
        self.assertEqual(1, result["progress"]["inventory"]["archive_key"]["quantity"])
        self.assertEqual(1, result["progress"]["inventory"]["seal_token"]["quantity"])
        self.assertEqual(0, result["progress"]["inventory"]["locker_key"]["quantity"])
        self.assertEqual(2, service.tools.rng.calls)

    def test_mixed_sanity_damage_restore_and_spend_are_idempotent(self):
        service = self.make_service([90, 2, 3])
        game = service.storage.get_game()
        character = Character.from_dict(game["character"])
        state = copy.deepcopy(game["scene_state"])
        effects = [
            {"type": "sanity", "success": "0", "failure": "1D3", "event_id": "mixed"},
            {"type": "damage", "expression": "1D3", "reason": "离线测试伤害"},
            {"type": "restore", "resource": "hp", "amount": 1},
            {"type": "spend", "resource": "mp", "amount": 2},
            {"type": "restore", "resource": "mp", "amount": 1},
        ]
        first = service.tools.apply_effects(game["game_id"], "mixed", character, state, effects)
        self.assertEqual((8, 53, 10), (character.hp, character.san, character.mp))
        before = copy.deepcopy(state)
        repeated = service.tools.apply_effects(game["game_id"], "mixed", character, state, effects)
        self.assertEqual(first, repeated)
        self.assertEqual((8, 53, 10), (character.hp, character.san, character.mp))
        self.assertEqual(before, state)
        self.assertEqual(3, service.tools.rng.calls)

    def test_failed_later_effect_does_not_half_apply_earlier_effects(self):
        service = self.make_service([90, 2])
        game = service.storage.get_game()
        character = Character.from_dict(game["character"])
        state = copy.deepcopy(game["scene_state"])
        before = copy.deepcopy(state)
        original_character = character.to_dict()
        effects = [{"type": "sanity", "success": "0", "failure": "1D3"},
                   {"type": "spend", "resource": "mp", "amount": 99}]
        with self.assertRaises(ValueError):
            service.tools.apply_effects(game["game_id"], "cannot-afford", character, state, effects)
        self.assertEqual(before, state)
        self.assertEqual(original_character, character.to_dict())
        with self.assertRaises(ValueError):
            service.tools.apply_effects(game["game_id"], "cannot-afford", character, state, effects)
        self.assertEqual(2, service.tools.rng.calls)

    def test_same_action_cannot_change_from_sanity_only_to_mixed_effects(self):
        service = self.make_service([90, 2])
        game = service.storage.get_game()
        character = Character.from_dict(game["character"])
        state = copy.deepcopy(game["scene_state"])
        sanity = {"type": "sanity", "success": "0", "failure": "1D3"}
        service.tools.apply_effects(game["game_id"], "effect-shape", character, state, [sanity])
        before = copy.deepcopy(state)
        original_character = character.to_dict()
        with self.assertRaises(ValueError):
            service.tools.apply_effects(game["game_id"], "effect-shape", character, state,
                                        [sanity, {"type": "restore", "resource": "hp", "amount": 1}])
        self.assertEqual(original_character, character.to_dict())
        self.assertEqual(before, state)
        self.assertEqual(2, service.tools.rng.calls)


if __name__ == "__main__":
    unittest.main()
