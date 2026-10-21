"""Offline language boundaries using public-only contexts; no model or .env calls."""

from copy import deepcopy
import unittest

from kp_agent.models import DemoPlanner


def _target(target_id, name, actions, aliases=(), **extra):
    return {"id": target_id, "name": name, "description": "已经公开的场景信息。",
            "aliases": list(aliases), "actions": list(actions), "completed_actions": [], **extra}


def _station(*, spent_key=False):
    key = {"id": "locker_key", "name": "17号柜黄铜钥匙", "aliases": ["黄铜钥匙", "柜子钥匙"],
           "description": "管家已经交给你的钥匙。", "quantity": 0 if spent_key else 1}
    bandage = {"id": "bandage", "name": "简易止血包", "aliases": ["绷带", "止血包"],
               "description": "已经持有的止血材料。", "quantity": 1}
    suggestions = [
        {"intent": "move", "target_id": "exit", "label": "前往地下档案室", "priority": 90},
        {"intent": "move", "target_id": "back_exit", "label": "返回旧书房", "priority": 5},
        {"intent": "finish", "target_id": "exit", "label": "停止调查并撤退", "priority": -100},
        {"intent": "use_item", "target_id": "self", "item_id": "bandage", "label": "用简易止血包包扎擦伤", "priority": 1},
    ]
    if not spent_key:
        suggestions.append({"intent": "use_item", "target_id": "locker", "item_id": "locker_key",
                            "label": "用黄铜钥匙打开17号柜", "priority": 100})
    return {
        "status": "playing", "scene": {"scene_id": "station", "title": "旧车站"},
        "targets": [
            _target("room", "候车区", ["look"], ["候车室", "大厅"]),
            _target("locker", "寄存铁柜", ["look", "investigate"] + ([] if spent_key else ["use_item"]),
                    ["柜子", "铁柜", "17号柜"], completed_item_uses=["locker_key"] if spent_key else []),
            _target("platform", "旧站台", ["look", "investigate"], ["站台", "站台边缘"]),
            _target("exit", "前进的通道", ["look", "move", "leave", "finish"],
                    ["出口", "离开车站", "地下档案室", "档案室"]),
            _target("back_exit", "返回书房的路", ["look", "move", "leave"],
                    ["返回旧书房", "返回书房", "回书房", "旧书房", "书房", "来路"]),
            _target("self", "自己", ["look", "use_item"], ["自己", "伤口", "擦伤", "包扎"]),
            _target("item_locker_key", "17号柜黄铜钥匙", ["look"], ["黄铜钥匙", "柜子钥匙"]),
            _target("item_bandage", "简易止血包", ["look"], ["绷带", "止血包"]),
        ],
        "inventory": {"locker_key": key, "bandage": bandage},
        "destinations": [
            {"target_id": "exit", "scene_id": "archive", "name": "地下档案室"},
            {"target_id": "back_exit", "scene_id": "study", "name": "旧书房"},
        ],
        "action_suggestions": suggestions,
    }


class LanguageV2Tests(unittest.TestCase):
    def setUp(self):
        self.planner = DemoPlanner()

    def plan(self, text, context):
        before = deepcopy(context)
        result = self.planner.plan(text, context)
        self.assertEqual(context, before, "规划不能提前改动角色、库存或场景")
        return result

    def test_dynamic_aliases_support_new_objects_and_npcs(self):
        context = {"targets": [
            _target("notice_board", "公告栏", ["look", "investigate"], ["告示牌", "布告栏"]),
            _target("station_clerk", "站务员", ["look", "talk"], ["值班员"]),
        ]}
        for text, intent, target_id in (
            ("我检查告示牌", "investigate", "notice_board"),
            ("问问值班员", "talk", "station_clerk"),
        ):
            with self.subTest(text=text):
                result = self.plan(text, context)
                self.assertEqual((result.intent, result.target_id), (intent, target_id))

    def test_acquired_letter_and_photo_are_read_without_new_investigation(self):
        context = _station()
        context["targets"].extend([
            _target("clue_letter", "旧来信", ["look"], ["来信", "信件"]),
            _target("clue_photograph", "车站照片", ["look"], ["照片", "相片"]),
        ])
        for text, target_id in (("阅读来信", "clue_letter"), ("阅读照片背面", "clue_photograph")):
            with self.subTest(text=text):
                result = self.plan(text, context)
                self.assertEqual((result.intent, result.target_id), ("look", target_id))

    def test_future_or_previous_physical_target_is_not_inferred(self):
        result = self.plan("检查书桌", _station())
        self.assertNotEqual(result.target_id, "desk")
        self.assertIn(result.intent, {"clarify", "unsupported"})

    def test_generic_departure_with_two_directions_asks_first(self):
        for text in ("离开这里", "我离开车站"):
            with self.subTest(text=text):
                result = self.plan(text, _station())
                self.assertEqual(result.intent, "clarify")

    def test_archive_departure_distinguishes_return_and_ending(self):
        context = _station()
        context["targets"] = [
            _target("exit", "街面安全出口", ["look", "leave", "finish"], ["出口", "离开", "安全出口"]),
            _target("back_exit", "返回车站的楼梯", ["look", "move", "leave"], ["返回车站", "回车站", "车站", "楼梯"]),
        ]
        context["destinations"] = [{"target_id": "back_exit", "scene_id": "station", "name": "旧车站"}]
        context["action_suggestions"] = [
            {"intent": "move", "target_id": "back_exit", "label": "返回车站", "priority": 5},
            {"intent": "leave", "target_id": "exit", "label": "离开并结束调查", "priority": 20},
        ]
        result = self.plan("离开这里", context)
        self.assertEqual(result.intent, "clarify")

    def test_forward_and_return_aliases_choose_the_right_route(self):
        for text, target_id in (
            ("前往地下档案室", "exit"), ("返回旧书房", "back_exit"), ("回书房", "back_exit"),
        ):
            with self.subTest(text=text):
                result = self.plan(text, _station())
                self.assertEqual((result.intent, result.target_id), ("move", target_id))

    def test_explicit_ending_accepts_natural_wording(self):
        for text in ("结束本次调查", "我要结束这次调查"):
            with self.subTest(text=text):
                result = self.plan(text, _station())
                self.assertEqual((result.intent, result.target_id), ("finish", "exit"))

    def test_asking_how_to_end_does_not_end_or_move(self):
        for text in ("怎么结束调查", "我想知道如何完成调查"):
            with self.subTest(text=text):
                result = self.plan(text, _station())
                self.assertNotIn(result.intent, {"finish", "leave", "move"})

    def test_negated_item_or_ending_request_is_not_executed(self):
        for text in ("我不想使用绷带", "先不结束调查"):
            with self.subTest(text=text):
                result = self.plan(text, _station())
                self.assertNotIn(result.intent, {"use_item", "finish", "leave", "move"})

    def test_item_is_not_redirected_to_a_different_usable_target(self):
        result = self.plan("用黄铜钥匙打开站台", _station())
        self.assertNotEqual(result.intent, "use_item")

    def test_nonexistent_key_is_not_replaced_with_bandage(self):
        context = _station()
        del context["inventory"]["locker_key"]
        context["targets"] = [target for target in context["targets"] if target["id"] != "item_locker_key"]
        context["action_suggestions"] = [suggestion for suggestion in context["action_suggestions"]
                                         if suggestion.get("item_id") != "locker_key"]
        result = self.plan("用钥匙给自己包扎", context)
        self.assertNotEqual(result.intent, "use_item")
        self.assertEqual(context["inventory"]["bandage"]["quantity"], 1)

    def test_held_item_alias_can_select_its_actual_legal_pair(self):
        result = self.plan("使用绷带", _station())
        self.assertEqual((result.intent, result.target_id, result.item_id), ("use_item", "self", "bandage"))

    def test_item_usage_question_reads_description_without_consuming(self):
        result = self.plan("绷带怎么用", _station())
        self.assertEqual((result.intent, result.target_id), ("look", "item_bandage"))

    def test_spent_item_can_only_restate_its_exact_completed_pair(self):
        context = _station(spent_key=True)
        result = self.plan("再用黄铜钥匙打开柜子", context)
        self.assertEqual((result.intent, result.target_id, result.item_id), ("use_item", "locker", "locker_key"))
        self.assertEqual(context["inventory"]["locker_key"]["quantity"], 0)

    def test_spent_item_request_for_different_target_is_not_redirected(self):
        result = self.plan("再用黄铜钥匙打开站台", _station(spent_key=True))
        self.assertNotEqual(result.intent, "use_item")

    def test_first_reading_of_current_archive_can_investigate_but_acquired_evidence_only_looks(self):
        context = {"targets": [_target("ledger", "旧档案", ["look", "investigate"], ["档案", "记录", "册子"])],
                   "action_suggestions": [{"intent": "investigate", "target_id": "ledger", "label": "调查旧档案", "priority": 60}]}
        result = self.plan("阅读旧档案", context)
        self.assertEqual((result.intent, result.target_id), ("investigate", "ledger"))
        context["targets"].append(_target("clue_archive_record", "完整维护日志", ["look"], ["维护日志", "完整日志"]))
        result = self.plan("阅读维护日志", context)
        self.assertEqual((result.intent, result.target_id), ("look", "clue_archive_record"))


if __name__ == "__main__":
    unittest.main()
