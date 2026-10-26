"""Deterministic adapters around the group's existing character/dice code.

These functions run server-side. A model cannot supply character values, roll
outcomes, or arbitrary HP deltas. Every random result is stored before use.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
import secrets
from dataclasses import asdict
from typing import Any

from trpg import Character, roll
from trpg.check import _determine_degree
from trpg.house_rules import CocHouseRules


DEGREES = {
    "fumble": -1,
    "failure": 0,
    "regular_success": 1,
    "hard_success": 2,
    "extreme_success": 3,
    "critical_success": 4,
}
REQUIRED = {"regular": 1, "hard": 2, "extreme": 3}
_EXPR = re.compile(r"(?:(\d{1,2})?d(\d{1,3})([+-]\d{1,3})?|([0-9]{1,3}))\Z")


def bounded_expression(expression: str) -> str:
    if not isinstance(expression, str) or len(expression) > 32:
        raise ValueError("骰子表达式必须是长度不超过32的文字")
    expression = expression.lower().replace(" ", "")
    match = _EXPR.fullmatch(expression)
    if not match:
        raise ValueError("仅支持常数或 nDm+k 骰子表达式")
    count, sides, _, constant = match.groups()
    if constant is None and not (1 <= int(count or 1) <= 20 and 1 <= int(sides) <= 100):
        raise ValueError("骰子数量或面数超出本演示支持范围")
    return expression


def maximum(expression: str) -> int:
    match = _EXPR.fullmatch(bounded_expression(expression))
    count, sides, modifier, constant = match.groups()
    return int(constant) if constant is not None else int(count or 1) * int(sides) + int(modifier or 0)


def minimum(expression: str) -> int:
    match = _EXPR.fullmatch(bounded_expression(expression))
    count, _, modifier, constant = match.groups()
    return int(constant) if constant is not None else int(count or 1) + int(modifier or 0)


def _sanity_spec(effect: dict) -> dict:
    if not isinstance(effect, dict) or effect.get("type") != "sanity":
        raise ValueError("当前仅支持已定义场景中的理智效果")
    try:
        success = bounded_expression(effect["success"])
        failure = bounded_expression(effect["failure"])
    except KeyError:
        raise ValueError("理智效果必须包含成功和失败损失") from None
    if minimum(success) < 0 or minimum(failure) < 0:
        raise ValueError("理智损失表达式不能产生负值")
    event_id = effect.get("event_id")
    if event_id is not None and not isinstance(event_id, str):
        raise ValueError("理智事件编号必须是文字")
    return {"type": "sanity", "event_id": event_id, "success": success, "failure": failure}


class CharacterTools:
    def __init__(self, storage: Any, rng: Any = None):
        self.storage = storage
        self.rng = rng if rng is not None else secrets.SystemRandom()

    @staticmethod
    def bonus_dice_example() -> dict:
        """A teaching fixture through the real percentile combiner, no live roll."""
        from trpg.dice import roll_percentile
        class ExampleDigits:
            def __init__(self): self.values = iter((5, 1, 8))
            def randint(self, low, high): return next(self.values)
        reward, candidates = roll_percentile(ExampleDigits(), 1)
        penalty, _ = roll_percentile(ExampleDigits(), -1)
        return {'candidates': candidates, 'reward': reward, 'penalty': penalty,
                'text': f'COC 的 D100 检定数值越低越好。奖励骰和惩罚骰都额外掷十位骰，所有十位骰共用同一个个位骰；'
                        f'奖励骰取最低结果，惩罚骰取最高结果。\n'
                        f'例如，假设个位是5、两个十位分别是1和8，候选结果为15和85：奖励骰取{reward}，惩罚骰取{penalty}。'
                        '000 组合算100，不能算0。奖惩骰会互相抵消，通常最多使用两个同类额外骰。'
                        '\n这是假想数字示例，没有实际掷骰，也没有改变角色状态。'}

    @staticmethod
    def success_example(character: Character, skill: str = "侦查") -> dict:
        """Explain hypothetical grades using the existing engine, without rolls.

        These examples are teaching data, never random outcomes or game events.
        Rendering them directly prevents a narrator from rewriting arithmetic.
        """
        value = character.resolve(skill)
        if type(value) is not int or value < 1:
            raise ValueError("讲解示例需要角色已有的正整数技能或属性")
        rules = CocHouseRules.standard()
        thresholds = {"regular": value, "hard": value // rules.hard_divisor,
                      "extreme": value // rules.extreme_divisor}
        labels = {"regular_success": "常规成功", "hard_success": "困难成功",
                  "extreme_success": "极难成功", "critical_success": "大成功",
                  "failure": "失败", "fumble": "大失败"}
        samples, lines = [], [
            f"以你的{skill} {value}为例：常规成功上限是{value}，"
            f"困难成功上限是{thresholds['hard']}，极难成功上限是{thresholds['extreme']}；半值和五分之一值向下取整。",
        ]
        for raw in (30, 20, 10):
            degree = _determine_degree(raw, value, rules)
            passes = {difficulty: DEGREES[degree] >= required for difficulty, required in REQUIRED.items()}
            samples.append({"roll": raw, "success_level": degree, "passes": passes})
            lines.append(f"假设出目是{raw}：属于{labels[degree]}，"
                         f"{'可以' if passes['hard'] else '不能'}通过要求困难成功的任务。")
        lines.append("这些是讲解用的假想出目，没有实际掷骰，也没有改变角色状态。")
        return {"skill": skill, "skill_value": value, "thresholds": thresholds,
                "samples": samples, "text": "\n".join(lines)}

    def skill_check(self, game_id: str, action_id: str, character: Character, spec: dict) -> dict:
        request_id = f"{action_id}:skill"
        if not isinstance(spec, dict) or not isinstance(spec.get("skill"), str):
            raise ValueError("检定必须指定角色已有的技能或属性")
        skill = spec["skill"]
        difficulty = spec.get("difficulty", "regular")
        if difficulty not in REQUIRED:
            raise ValueError("未知检定难度")
        bonus = spec.get("bonus_dice", 0)
        if type(bonus) is not int or abs(bonus) > 2:
            raise ValueError("奖励/惩罚骰必须是 -2 至 2 的整数")
        value = character.resolve(skill)
        if type(value) is not int or value < 1:
            raise ValueError("检定值必须是角色已有的正整数技能或属性")
        existing = self.storage.get_roll(game_id, request_id)
        if existing is not None:
            expected = {"skill": skill, "difficulty": difficulty, "bonus_dice": bonus, "skill_value": value}
            if any(existing.get(key) != expected_value for key, expected_value in expected.items()):
                raise ValueError("同一检定编号不能更换技能、难度、奖惩骰或角色数值")
            return existing
        result = character.check(skill, bonus_dice=bonus, rng=self.rng)
        threshold = value // {"regular": 1, "hard": 2, "extreme": 5}[difficulty]
        degree = result.degree
        # The upstream helper does not accept difficulty. Use the requested
        # success threshold for the standard core-rule fumble boundary.
        if result.roll == 100 or (threshold < 50 and result.roll >= 96):
            degree = "fumble"
        outcome = {
            "request_id": request_id,
            "kind": "skill",
            "skill": skill,
            "skill_value": value,
            "difficulty": difficulty,
            "threshold": threshold,
            "roll": result.roll,
            "candidates": result.candidates,
            "bonus_dice": bonus,
            "success_level": degree,
            "passed": DEGREES[degree] >= REQUIRED[difficulty],
        }
        return self.storage.record_roll(game_id, request_id, outcome)

    def expression(self, game_id: str, action_id: str, label: str, expression: str) -> dict:
        expression = bounded_expression(expression)
        request_id = f"{action_id}:{label}"
        existing = self.storage.get_roll(game_id, request_id)
        if existing is not None:
            if existing["expression"] != expression:
                raise ValueError("同一掷骰编号不能更换表达式")
            return existing
        result = roll(expression, rng=self.rng)
        return self.storage.record_roll(game_id, request_id, {
            "request_id": request_id, "kind": "expression", **asdict(result),
        })

    def apply_effects(
        self, game_id: str, action_id: str, character: Character,
        scene_state: dict, effects: list[dict],
    ) -> tuple[list[dict], list[dict], list[str]]:
        """Bind authored effects to the existing character/dice implementation.

        This adapter does not invent combat or first-aid rules. Amounts must
        come from the authored story, never from model output. Mutations are
        staged on copies and committed together by KeeperService/Storage.
        """
        if not isinstance(effects, list):
            raise ValueError("场景效果必须是列表")
        normalized = []
        for effect in effects:
            if not isinstance(effect, dict):
                raise ValueError("场景效果必须是对象")
            kind = effect.get("type")
            if kind == "sanity":
                _sanity_spec(effect)
            elif kind == "damage":
                expression = bounded_expression(effect.get("expression"))
                if minimum(expression) < 0:
                    raise ValueError("伤害表达式不能产生负数")
            elif kind in {"restore", "spend"}:
                resource, amount = effect.get("resource"), effect.get("amount")
                allowed = {"hp", "mp"} if kind == "restore" else {"mp"}
                if resource not in allowed or type(amount) is not int or not 1 <= amount <= 99:
                    raise ValueError("资源效果必须指定受支持的资源和1至99的整数数量")
            else:
                raise ValueError("未支持的场景效果，请让负责角色工具的同学补充接口")
            normalized.append(copy.deepcopy(effect))
        batches = scene_state.get("effect_batches", {})
        if not isinstance(batches, dict):
            raise ValueError("场景效果批次记录格式不正确")
        batch_signature = hashlib.sha256(json.dumps(normalized, sort_keys=True).encode()).hexdigest()
        if action_id in batches and batches[action_id] != batch_signature:
            raise ValueError("同一行动不能更换效果集合，请恢复原来的场景配置")
        # Preserve the original SAN-only request IDs and recovery semantics.
        if all(effect["type"] == "sanity" for effect in normalized):
            working = Character.from_dict(character.to_dict())
            updated = copy.deepcopy(scene_state)
            result = self._apply_sanity_effects(game_id, action_id, working, updated, normalized)
            updated.setdefault("effect_batches", {})[action_id] = batch_signature
            character.san = working.san
            scene_state.clear()
            scene_state.update(updated)
            return result
        for resource in ("hp", "mp"):
            value, ceiling = getattr(character, resource), getattr(character, f"{resource}_max")
            if type(value) is not int or type(ceiling) is not int or not 0 <= value <= ceiling:
                raise ValueError("角色资源值不在允许范围内")
        if not isinstance(scene_state.get("effect_applications", {}), dict):
            raise ValueError("场景效果记录格式不正确")
        if not isinstance(scene_state.get("conditions", []), list):
            raise ValueError("角色状态必须是列表")
        working = Character.from_dict(character.to_dict())
        updated = copy.deepcopy(scene_state)
        updated.setdefault("effect_applications", {})
        updated.setdefault("conditions", [])
        rolls, changes, notices = [], [], []
        for index, effect in enumerate(normalized):
            if effect["type"] == "sanity":
                extra, delta, note = self._apply_sanity_effects(
                    game_id, f"{action_id}:effect:{index}", working, updated, [effect],
                )
                rolls.extend(extra)
                changes.extend(delta)
                notices.extend(note)
                continue
            request_id = f"{action_id}:resource:{index}"
            signature = hashlib.sha256(json.dumps(effect, sort_keys=True).encode()).hexdigest()
            prior = updated["effect_applications"].get(request_id)
            if prior is not None:
                if prior.get("signature") != signature:
                    raise ValueError("同一资源效果编号不能更换场景效果")
                rolls.extend(copy.deepcopy(prior["rolls"]))
                changes.extend(copy.deepcopy(prior["changes"]))
                notices.extend(prior["notices"])
                continue
            effect_rolls, effect_notices = [], []
            resource = "hp" if effect["type"] == "damage" else effect["resource"]
            before = getattr(working, resource)
            if effect["type"] == "damage":
                outcome = self.expression(game_id, action_id, f"damage:{index}", effect["expression"])
                effect_rolls.append(outcome)
                damage = working.apply_damage(outcome["total"])
                if damage.major_wound or damage.unconscious:
                    condition = "dying" if damage.dying else "unconscious" if damage.unconscious else "major_wound"
                    if condition not in updated["conditions"]:
                        updated["conditions"].append(condition)
                    effect_notices.append("伤势需要进一步处理，自动行动暂停，请让真人检查。")
            elif effect["type"] == "restore":
                getattr(working, f"restore_{resource}")(effect["amount"])
            else:
                if working.mp < effect["amount"]:
                    raise ValueError("当前MP不足，不能执行这个已定义的场景效果")
                # The upstream Character has no spend_mp method. Keep this
                # narrowly bounded scene cost here; it is not a spell engine.
                working.mp -= effect["amount"]
            after = getattr(working, resource)
            delta = [{"field": resource, "before": before, "after": after,
                      "delta": after - before, "reason": effect.get("reason", "已定义的场景效果")}]
            updated["effect_applications"][request_id] = {
                "signature": signature, "rolls": copy.deepcopy(effect_rolls),
                "changes": copy.deepcopy(delta), "notices": list(effect_notices),
            }
            rolls.extend(effect_rolls)
            changes.extend(delta)
            notices.extend(effect_notices)
        character.hp, character.san, character.mp = working.hp, working.san, working.mp
        updated.setdefault("effect_batches", {})[action_id] = batch_signature
        scene_state.clear()
        scene_state.update(updated)
        return rolls, changes, notices

    def _apply_sanity_effects(
        self, game_id: str, action_id: str, character: Character,
        scene_state: dict, effects: list[dict],
    ) -> tuple[list[dict], list[dict], list[str]]:
        """Apply authored SAN effects atomically to the supplied in-memory state.

        Persisted rolls alone do not mean an effect was applied: a failed action
        must replay its cached rolls against the old database snapshot once.
        effect_applications markers live in the scene snapshot, so replaying the
        same action against its already-updated state returns the original event
        without another deduction. This is separate from Storage's commit guard.
        """
        if type(character.san) is not int or not 0 <= character.san <= 99:
            raise ValueError("角色SAN必须是0至99的整数")
        if not isinstance(effects, list):
            raise ValueError("场景效果必须是列表")
        normalized = [_sanity_spec(effect) for effect in effects]
        if type(scene_state.get("san_lost_today", 0)) is not int or scene_state.get("san_lost_today", 0) < 0:
            raise ValueError("当日理智损失必须是非负整数")
        day_start = scene_state.get("san_day_start")
        if day_start is not None and (type(day_start) is not int or not 0 <= day_start <= 99):
            raise ValueError("日初SAN必须是0至99的整数或尚未设置")
        if not isinstance(scene_state.get("conditions", []), list):
            raise ValueError("角色状态必须是列表")
        if not isinstance(scene_state.get("effect_applications", {}), dict):
            raise ValueError("场景效果记录格式不正确")
        # Work on copies. Validation/provider/storage failures leave caller state
        # untouched; any already-saved random values are reused on the next try.
        working = Character.from_dict(character.to_dict())
        updated = copy.deepcopy(scene_state)
        conditions = updated.setdefault("conditions", [])
        applications = updated.setdefault("effect_applications", {})
        rolls, changes, notices = [], [], []
        for index, spec in enumerate(normalized):
            request_id = f"{action_id}:sanity:{index}"
            signature = hashlib.sha256(json.dumps(spec, sort_keys=True).encode()).hexdigest()
            prior = applications.get(request_id)
            if prior is not None:
                if prior.get("signature") != signature:
                    raise ValueError("同一理智效果编号不能更换场景效果")
                rolls.extend(copy.deepcopy(prior["rolls"]))
                changes.extend(copy.deepcopy(prior["changes"]))
                notices.extend(prior["notices"])
                continue
            effect_rolls, effect_changes, effect_notices = [], [], []
            before = working.san
            if updated.get("san_day_start") is None:
                updated["san_day_start"] = before
            if before == 0:
                if "permanent_insanity" not in conditions:
                    conditions.append("permanent_insanity")
                effect_notices.append("理智已经为0，角色不能继续检定，需要真人处理。")
            else:
                result = self.storage.get_roll(game_id, request_id)
                if result is not None and result.get("effect_signature", signature) != signature:
                    raise ValueError("同一理智检定编号不能更换损失表达式")
                if result is None:
                    raw = self.rng.randint(1, 100)
                    passed = raw <= before and raw != 100
                    fumble = raw == 100 or (before < 50 and raw >= 96)
                    expression = spec["success"] if passed else spec["failure"]
                    if fumble:
                        loss_roll = {"expression": expression, "total": maximum(expression),
                                     "faces": [], "maximum_loss": True}
                    else:
                        loss_roll = asdict(roll(expression, rng=self.rng))
                    result = self.storage.record_roll(game_id, request_id, {
                        "request_id": request_id, "effect_signature": signature,
                        "kind": "sanity", "skill": "理智", "skill_value": before,
                        "roll": raw, "passed": passed,
                        "success_level": "regular_success" if passed else "fumble" if fumble else "failure",
                        "loss": loss_roll["total"], "loss_roll": loss_roll,
                    })
                if result["skill_value"] != before:
                    raise ValueError("理智检定的初始SAN与存档不一致，请恢复原状态")
                effect_rolls.append(result)
                working.apply_san_loss(result["loss"])
                actual_loss = before - working.san
                effect_changes.append({"field": "san", "before": before, "delta": -actual_loss,
                                       "after": working.san, "reason": effects[index].get("reason", "场景理智事件")})
                updated["san_lost_today"] = updated.get("san_lost_today", 0) + actual_loss
                # SAN zero takes precedence; no further INT roll is meaningful.
                if working.san == 0:
                    if "permanent_insanity" not in conditions:
                        conditions.append("permanent_insanity")
                    effect_notices.append("理智降至0，角色停止自动行动，需要真人处理。")
                else:
                    if actual_loss >= 5:
                        value = working.attributes.get("INT")
                        if type(value) is not int or value < 1:
                            raise ValueError("处理临时性疯狂需要角色已有的正整数智力值")
                        int_id = f"{action_id}:sanity_int:{index}"
                        intelligence = self.storage.get_roll(game_id, int_id)
                        if intelligence is None:
                            raw = self.rng.randint(1, 100)
                            intelligence = self.storage.record_roll(game_id, int_id, {
                                "request_id": int_id, "kind": "intelligence", "skill": "智力",
                                "skill_value": value, "roll": raw, "passed": raw <= value and raw != 100,
                            })
                        effect_rolls.append(intelligence)
                        if intelligence["passed"] and "temporary_insanity" not in conditions:
                            conditions.append("temporary_insanity")
                            effect_notices.append("智力检定成功，触发临时性疯狂；具体发作需真人接管。")
                    day_start = updated["san_day_start"]
                    if day_start > 0 and updated["san_lost_today"] * 5 >= day_start:
                        if "indefinite_insanity" not in conditions:
                            conditions.append("indefinite_insanity")
                            effect_notices.append("当日累计理智损失达到日初理智的五分之一，触发不定性疯狂。")
            applications[request_id] = {"signature": signature, "rolls": copy.deepcopy(effect_rolls),
                                        "changes": copy.deepcopy(effect_changes), "notices": list(effect_notices)}
            rolls.extend(effect_rolls)
            changes.extend(effect_changes)
            notices.extend(effect_notices)
        character.san = working.san
        scene_state.clear()
        scene_state.update(updated)
        return rolls, changes, notices
