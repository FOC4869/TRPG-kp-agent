"""Provider, citation and audit tests use only fake clients and temporary files."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from kp_agent.models import (
    DeepSeekResponsesPlanner, ModelCallError, ModelConfigurationError,
    create_planner, model_request_context,
)
from kp_agent.schemas import ActionPlan, Narration


def response(parsed, status="completed"):
    return SimpleNamespace(
        output_parsed=parsed, status=status, model="deepseek-flash",
        usage=SimpleNamespace(input_tokens=120, output_tokens=30, total_tokens=150,
                              input_tokens_details=SimpleNamespace(cached_tokens=80),
                              output_tokens_details=SimpleNamespace(reasoning_tokens=0)),
    )


class Responses:
    def __init__(self, *outputs):
        self.outputs = iter(outputs)
        self.calls = []

    def parse(self, **kwargs):
        self.calls.append(kwargs)
        item = next(self.outputs)
        if isinstance(item, Exception):
            raise item
        return item


class CreateResponses:
    def __init__(self, *outputs):
        self.outputs = iter(outputs)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return next(self.outputs)


def json_response(text):
    result = response(None)
    result.output_text = text
    return result


def planner(*outputs, **kwargs):
    responses = Responses(*outputs)
    instance = DeepSeekResponsesPlanner(client=SimpleNamespace(responses=responses), **kwargs)
    return instance, responses


class DeepSeekModelsTests(unittest.TestCase):
    def test_stage_token_limits_and_reasoning_are_sent_to_responses(self):
        instance, fake = planner(response(ActionPlan(intent="look", target_id="room")), response(Narration(text="书房很安静。")))
        instance.plan("看看房间", {"targets": [{"id": "room", "actions": ["look"]}]})
        instance.narrate("看看房间", {"event": "书房很安静。"})
        self.assertEqual(fake.calls[0]["reasoning"], {"effort": "none"})
        self.assertEqual(fake.calls[0]["max_output_tokens"], 1024)
        self.assertEqual(fake.calls[1]["max_output_tokens"], 2048)
        self.assertIs(fake.calls[0]["text_format"], ActionPlan)
        self.assertIs(fake.calls[1]["text_format"], Narration)

    def test_official_url_and_no_sdk_background_retry(self):
        with patch("openai.OpenAI") as sdk:
            DeepSeekResponsesPlanner(api_key="fake-test-key")
        self.assertEqual(sdk.call_args.kwargs["base_url"], "https://api.deepseek.com")
        self.assertEqual(sdk.call_args.kwargs["max_retries"], 0)

    def test_invalid_reasoning_and_token_options_are_rejected_before_request(self):
        for kwargs in ({"reasoning_effort": "medium"}, {"plan_max_tokens": 0}, {"narration_max_tokens": True}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ModelConfigurationError):
                planner(**kwargs)

    def test_deepseek_never_falls_back_to_openai_key(self):
        with patch("kp_agent.models.load_local_env"), patch.dict("os.environ", {
            "KP_MODEL_MODE": "deepseek", "OPENAI_API_KEY": "fake-openai-only",
        }, clear=True):
            with self.assertRaises(ModelConfigurationError):
                create_planner()

    def test_online_careful_search_cannot_bypass_public_availability(self):
        instance, _ = planner(response(ActionPlan(intent="careful_search", target_id="desk")))
        with self.assertRaises(ModelCallError) as caught:
            instance.plan("细查书桌", {"targets": [{"id": "desk", "actions": ["investigate"]}]})
        self.assertEqual(caught.exception.code, "action_not_available")

    def test_repeat_careful_search_is_a_known_scene_action_even_if_model_says_unsupported(self):
        instance, _ = planner(response(ActionPlan(intent="unsupported", question="需要真人接管。")))
        result = instance.plan("再花十分钟仔细检查书桌", {
            "targets": [{"id": "desk", "actions": ["look"], "completed_actions": ["careful_search"]}],
        })
        self.assertEqual((result.intent, result.target_id), ("careful_search", "desk"))
        self.assertIsNone(result.question)

    def test_known_repeat_does_not_override_an_additional_unsupported_action(self):
        instance, _ = planner(response(ActionPlan(intent="unsupported")))
        result = instance.plan("再花十分钟仔细检查书桌，然后杀死管家", {
            "targets": [{"id": "desk", "actions": ["look"], "completed_actions": ["careful_search"]}],
        })
        self.assertEqual(result.intent, "unsupported")

    def test_old_history_citations_are_removed_but_current_evidence_stays(self):
        instance, fake = planner(response(Narration(text="检定成功不损失理智。[current_rule]", evidence_ids=["current_rule"])))
        result = instance.narrate("解释[old_rule]", {
            "event": "检定成功不损失理智。",
            "evidence": [{"evidence_id": "current_rule", "text": "成功损失0，失败损失1D6。"}],
        }, [{"role": "assistant", "content": "旧说明[old_rule]；本次依据[current_rule]"}])
        sent = fake.calls[0]["input"]
        self.assertNotIn("old_rule", sent)
        self.assertIn("current_rule", sent)
        self.assertIn("[current_rule]", result)

    def test_unknown_citation_is_still_rejected_after_history_cleanup(self):
        instance, _ = planner(response(Narration(text="说明[old_rule]", evidence_ids=["old_rule"])))
        with self.assertRaises(ModelCallError) as caught:
            instance.narrate("解释", {"event": "说明", "evidence": []}, [{"role": "assistant", "content": "旧引用[old_rule]"}])
        self.assertEqual(caught.exception.code, "unknown_evidence_id")


class AuditLogTests(unittest.TestCase):
    def test_request_ids_link_turns_and_manual_recovery_has_new_attempts(self):
        with TemporaryDirectory() as temp:
            path = Path(temp) / "calls.jsonl"
            instance, _ = planner(
                response(ActionPlan(intent="look", target_id="room")),
                response(Narration(text="书房很安静。")),
                response(Narration(text="书房依旧安静。")),
                metrics_path=path,
            )
            with model_request_context(game_id="g1", message_id="m1", action_id="a1"):
                instance.plan("看看", {"targets": ["room"]})
                instance.narrate("看看", {"event": "书房很安静。"})
            with model_request_context(game_id="g1", message_id="m1", action_id="a1"):
                instance.narrate("看看", {"event": "书房很安静。"})
            rows = [json.loads(line) for line in path.read_text().splitlines()]
        self.assertTrue(all(row["outcome"] == "accepted" and row["parsed"] for row in rows))
        self.assertTrue(all((row["game_id"], row["message_id"], row["action_id"]) == ("g1", "m1", "a1") for row in rows))
        self.assertEqual(rows[1]["request_id"], rows[2]["request_id"])
        self.assertNotEqual(rows[0]["request_id"], rows[1]["request_id"])
        self.assertEqual(len({row["call_id"] for row in rows}), 3)
        self.assertEqual(len({row["attempt_id"] for row in rows}), 3)

    def test_local_citation_rejection_is_not_reported_as_accepted(self):
        with TemporaryDirectory() as temp:
            path = Path(temp) / "calls.jsonl"
            instance, _ = planner(response(Narration(text="说明[unknown]", evidence_ids=["unknown"])), metrics_path=path)
            with self.assertRaises(ModelCallError):
                instance.narrate("解释", {"event": "说明", "evidence": []})
            row = json.loads(path.read_text())
        self.assertEqual(row["outcome"], "validation_rejected")
        self.assertTrue(row["parsed"])
        self.assertEqual(row["error_code"], "unknown_evidence_id")
        self.assertEqual(row["response_status"], "completed")
        self.assertEqual(row["total_tokens"], 150)

    def test_http_failure_logs_controlled_metadata_without_private_body(self):
        class FakeRateLimitError(RuntimeError):
            status_code = 429

        with TemporaryDirectory() as temp:
            path = Path(temp) / "calls.jsonl"
            instance, fake = planner(FakeRateLimitError("fake-secret-key and raw-private-prompt"), metrics_path=path)
            with self.assertRaises(ModelCallError) as caught:
                instance.plan("private-action", {"targets": ["room"]})
            raw = path.read_text()
            row = json.loads(raw)
        self.assertEqual(len(fake.calls), 1)
        self.assertEqual(row["outcome"], "failed")
        self.assertFalse(row["parsed"])
        self.assertEqual(row["http_status"], 429)
        self.assertEqual(row["error_code"], "provider_rate_limit")
        self.assertEqual(row["error_type"], "FakeRateLimitError")
        self.assertIsNone(row["total_tokens"])
        self.assertNotIn("fake-secret-key", raw + str(caught.exception))
        self.assertNotIn("raw-private-prompt", raw + str(caught.exception))
        self.assertNotIn("private-action", raw)

    def test_schema_rejection_has_a_different_code_from_provider_failure(self):
        with TemporaryDirectory() as temp:
            path = Path(temp) / "calls.jsonl"
            instance, _ = planner(response({"intent": "investigate", "damage": 4}), metrics_path=path)
            with self.assertRaises(ModelCallError):
                instance.plan("检查", {"targets": ["room"]})
            row = json.loads(path.read_text())
        self.assertEqual(row["outcome"], "validation_rejected")
        self.assertFalse(row["parsed"])
        self.assertEqual(row["error_code"], "invalid_structured_output")

    def test_request_context_is_restored_after_exit(self):
        with TemporaryDirectory() as temp:
            path = Path(temp) / "calls.jsonl"
            instance, _ = planner(response(ActionPlan(intent="look")), response(ActionPlan(intent="look")), metrics_path=path)
            with model_request_context(game_id="private-game"):
                instance.plan("看看", {"targets": ["room"]})
            instance.plan("看看", {"targets": ["room"]})
            rows = [json.loads(line) for line in path.read_text().splitlines()]
        self.assertEqual(rows[0]["game_id"], "private-game")
        self.assertIsNone(rows[1]["game_id"])


class RawResponsesTests(unittest.TestCase):
    def test_real_sdk_contract_uses_create_with_explicit_strict_schema(self):
        fake = CreateResponses(json_response('{"intent":"look","target_id":"room","query":null,"question":null}'))
        instance = DeepSeekResponsesPlanner(client=SimpleNamespace(responses=fake))
        result = instance.plan("看看房间", {"targets": ["room"]})
        self.assertEqual(result.intent, "look")
        call = fake.calls[0]
        self.assertNotIn("text_format", call)
        output_format = call["text"]["format"]
        self.assertEqual(output_format["type"], "json_schema")
        self.assertTrue(output_format["strict"])
        self.assertEqual(set(output_format["schema"]["required"]), {"intent", "target_id", "query", "question"})
        self.assertFalse(output_format["schema"]["additionalProperties"])
        self.assertIn("只输出一个合法JSON对象", call["instructions"])

    def test_invalid_json_preserves_usage_and_logs_only_safe_error_location_type(self):
        with TemporaryDirectory() as temp:
            path = Path(temp) / "calls.jsonl"
            fake = CreateResponses(json_response("private-response-not-json"))
            instance = DeepSeekResponsesPlanner(client=SimpleNamespace(responses=fake), metrics_path=path)
            with self.assertRaises(ModelCallError):
                instance.narrate("公开问题", {"event": "公开事件", "reply_type": "narration"})
            raw = path.read_text()
            row = json.loads(raw)
        self.assertEqual(row["outcome"], "validation_rejected")
        self.assertEqual(row["response_status"], "completed")
        self.assertEqual(row["total_tokens"], 150)
        self.assertEqual(row["validation_errors"], [{"loc": [], "type": "json_invalid"}])
        self.assertNotIn("private-response-not-json", raw)

    def test_field_errors_do_not_log_unknown_keys_or_private_values(self):
        with TemporaryDirectory() as temp:
            path = Path(temp) / "calls.jsonl"
            fake = CreateResponses(json_response('{"text":17,"evidence_ids":null,"private-extra-key":"private-value"}'))
            instance = DeepSeekResponsesPlanner(client=SimpleNamespace(responses=fake), metrics_path=path)
            with self.assertRaises(ModelCallError):
                instance.narrate("说明", {"event": "公开结果"})
            raw = path.read_text()
            row = json.loads(raw)
        self.assertCountEqual(row["validation_errors"], [
            {"loc": ["text"], "type": "string_type"},
            {"loc": ["evidence_ids"], "type": "list_type"},
            {"loc": ["<unknown>"], "type": "extra_forbidden"},
        ])
        self.assertNotIn("private-extra-key", raw)
        self.assertNotIn("private-value", raw)

    def test_narration_payload_distinguishes_rule_explanation_and_story(self):
        fake = CreateResponses(json_response('{"text":"你平复呼吸。","evidence_ids":[]}'))
        instance = DeepSeekResponsesPlanner(client=SimpleNamespace(responses=fake))
        instance.narrate("继续", {"event": "你平复呼吸。", "reply_type": "narration"})
        call = fake.calls[0]
        self.assertEqual(json.loads(call["input"])["public_facts"]["reply_type"], "narration")
        self.assertIn("不能反推", call["instructions"])
        self.assertIn('"text"', call["instructions"])

    def test_rule_explanation_requires_current_source_and_logs_specific_error(self):
        with TemporaryDirectory() as temp:
            path = Path(temp) / "calls.jsonl"
            fake = CreateResponses(json_response('{"text":"检定成功不损失理智。","evidence_ids":[]}'))
            instance = DeepSeekResponsesPlanner(client=SimpleNamespace(responses=fake), metrics_path=path)
            with self.assertRaises(ModelCallError) as caught:
                instance.narrate("怎么判", {
                    "reply_type": "rule_explanation", "event": "解释规则",
                    "evidence": [{"evidence_id": "san_rule", "text": "成功损失0。"}],
                })
            row = json.loads(path.read_text())
        self.assertEqual(caught.exception.code, "missing_evidence_citation")
        self.assertEqual(row["outcome"], "validation_rejected")
        self.assertTrue(row["parsed"])
        self.assertEqual(row["total_tokens"], 150)

    def test_rule_explanation_accepts_matching_source_sets(self):
        fake = CreateResponses(json_response('{"text":"成功时不损失理智。[san_rule]","evidence_ids":["san_rule"]}'))
        instance = DeepSeekResponsesPlanner(client=SimpleNamespace(responses=fake))
        result = instance.narrate("怎么判", {
            "reply_type": "rule_explanation", "event": "解释规则",
            "evidence": [{"evidence_id": "san_rule", "text": "成功损失0。"}],
        })
        self.assertIn("[san_rule]", result)

    def test_rule_explanation_rejects_mismatched_declared_and_text_sources(self):
        fake = CreateResponses(json_response('{"text":"说明。[rule_a]","evidence_ids":["rule_a","rule_b"]}'))
        instance = DeepSeekResponsesPlanner(client=SimpleNamespace(responses=fake))
        with self.assertRaises(ModelCallError) as caught:
            instance.narrate("怎么判", {"reply_type": "rule_explanation", "event": "解释",
                "evidence": [{"id": "rule_a", "text": "甲"}, {"id": "rule_b", "text": "乙"}]})
        self.assertEqual(caught.exception.code, "citation_set_mismatch")


if __name__ == "__main__":
    unittest.main()
