import json
from pathlib import Path
import unittest

from kp_agent.scene import SceneDefinition, SceneValidationError


SCENE = Path(__file__).resolve().parents[1] / "data" / "scenes" / "study.json"


class TestAuthoredScene(unittest.TestCase):
    def setUp(self):
        self.scene = SceneDefinition.load(SCENE)
        self.state = self.scene.initial_state(san=55)

    def test_planning_and_public_context_do_not_contain_unrevealed_secrets(self):
        for context in (self.scene.planning_context(self.state), self.scene.public_context(self.state)):
            rendered = json.dumps(context, ensure_ascii=False)
            self.assertNotIn("保管箱号码17", rendered)
            self.assertNotIn("0/1D3", rendered)
            self.assertNotIn("fireplace_drawing", rendered)
            self.assertNotIn("reveal", rendered.replace("revealed_clues", ""))

    def test_model_cannot_change_check_or_create_effect(self):
        with self.assertRaises(SceneValidationError):
            self.scene.validate_plan({"action_type": "investigate", "target_id": "desk", "check": {"skill": "幸运"}}, self.state)
        with self.assertRaises(SceneValidationError):
            self.scene.validate_plan({"action_type": "look", "target_id": "desk", "effects": [{"hp": -1}]}, self.state)

    def test_investigate_requires_real_roll_result(self):
        plan = self.scene.validate_plan({"action_type": "investigate", "target_id": "desk"}, self.state)
        self.assertEqual(plan["check"]["skill"], "侦查")
        with self.assertRaises(SceneValidationError):
            self.scene.resolve_action(plan, self.state)

    def test_failure_does_not_reveal_or_damage_and_cannot_farm_rerolls(self):
        result = self.scene.resolve_action({"action_type": "investigate", "target_id": "desk"}, self.state, passed=False)
        self.assertEqual(result["clues"], [])
        self.assertEqual(result["effects"], [])
        again = self.scene.validate_plan({"action_type": "investigate", "target_id": "desk"}, result["state"])
        self.assertTrue(again["repeated"])
        self.assertIsNone(again["check"])
        repeated = self.scene.resolve_action(again, result["state"])
        self.assertEqual(repeated["clues"], [])

    def test_success_only_reveals_its_own_clue(self):
        result = self.scene.resolve_action({"action_type": "investigate", "target_id": "desk"}, self.state, passed=True)
        self.assertEqual(result["state"]["revealed_clues"], ["letter"])
        public = self.scene.public_context(result["state"])
        self.assertEqual([x["id"] for x in public["revealed_clues"]], ["letter"])
        self.assertNotIn("保管箱号码17", json.dumps(public, ensure_ascii=False))

    def test_optional_sanity_event_only_triggers_once(self):
        look = self.scene.resolve_action({"action_type": "look", "target_id": "fireplace"}, self.state)
        self.assertEqual(look["effects"], [])
        first = self.scene.resolve_action({"action_type": "investigate", "target_id": "fireplace"}, self.state)
        self.assertEqual(first["effects"], [{"type": "sanity", "event_id": "fireplace_drawing", "success": "0", "failure": "1D3"}])
        again = self.scene.resolve_action({"action_type": "investigate", "target_id": "fireplace"}, first["state"])
        self.assertEqual(again["effects"], [])
        self.assertEqual(again["state"]["triggered_events"], ["fireplace_drawing"])

    def test_conversation_is_once_and_exit_uses_actual_discovered_clues(self):
        desk = self.scene.resolve_action({"action_type": "investigate", "target_id": "desk"}, self.state, True)
        talk = self.scene.resolve_action({"action_type": "talk", "target_id": "butler"}, desk["state"])
        self.assertEqual(talk["state"]["revealed_clues"], ["letter", "photograph"])
        repeated = self.scene.resolve_action({"action_type": "talk", "target_id": "butler"}, talk["state"])
        self.assertEqual(repeated["clues"], [])
        ending = self.scene.resolve_action({"action_type": "leave"}, talk["state"])
        self.assertEqual(ending["state"]["ending"], "complete")
        self.assertEqual(ending["game_status"], "ended")
        with self.assertRaises(SceneValidationError):
            self.scene.validate_plan({"action_type": "look"}, ending["state"])

    def test_unknown_target_and_wrong_action_are_rejected(self):
        for plan in ({"action_type": "investigate", "target_id": "secret_door"}, {"action_type": "talk", "target_id": "desk"}):
            with self.assertRaises(SceneValidationError):
                self.scene.validate_plan(plan, self.state)


if __name__ == "__main__":
    unittest.main()
