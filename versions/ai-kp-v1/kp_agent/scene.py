"""Small, authored scene rules; the model cannot invent checks or rewards.

This module deliberately separates model planning metadata from hidden outcomes.
Only ``public_context`` / ``public_event`` belong in a player-facing response.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any


class SceneValidationError(ValueError):
    """The action is not supported by this authored scene."""


class SceneDefinition:
    def __init__(self, definition: dict[str, Any]):
        self.definition = copy.deepcopy(definition)
        self.scene_id = definition["id"]
        self.title = definition["title"]
        self._targets = definition["targets"]
        self._clues = definition.get("clues", {})

    @classmethod
    def load(cls, path: str | Path) -> "SceneDefinition":
        return cls(json.loads(Path(path).read_text(encoding="utf-8")))

    @property
    def opening(self) -> str:
        return self.definition["opening"]

    def initial_state(self, san: int | None = None) -> dict[str, Any]:
        return {
            "scene_id": self.scene_id,
            "status": "playing",
            "revealed_clues": [],
            "attempts": {},
            "triggered_events": [],
            "npc_state": {},
            "conditions": [],
            "san_day_start": san,
            "san_lost_today": 0,
            "elapsed_minutes": 0,
            "ending": None,
        }

    def public_context(self, state: dict[str, Any]) -> dict[str, Any]:
        """Exclude unrevealed clue contents, checks, and hidden effect specs."""
        return {
            "scene_id": self.scene_id,
            "title": self.title,
            "description": self.definition["public_description"],
            "targets": [
                {"id": key, "name": value["name"], "description": value["description"]}
                for key, value in self._targets.items()
            ],
            "revealed_clues": [
                {"id": key, **copy.deepcopy(self._clues[key])}
                for key in state.get("revealed_clues", []) if key in self._clues
            ],
            "status": state.get("status", "playing"),
            "ending": state.get("ending"),
            "elapsed_minutes": state.get("elapsed_minutes", 0),
        }

    def _careful_search_available(self, state: dict[str, Any]) -> bool:
        """The fallback is this authored scene's rule, not a general COC rule."""
        config = self._targets.get("desk", {}).get("careful_search")
        if not config or state.get("status", "playing") != "playing":
            return False
        attempts = state.get("attempts", {})
        first_attempt = attempts.get("investigate:desk", {})
        rewards = config.get("success", {}).get("reveal", [])
        return (
            first_attempt.get("passed") is False
            and "careful_search:desk" not in attempts
            and not any(clue in state.get("revealed_clues", []) for clue in rewards)
        )

    def planning_context(self, state: dict[str, Any]) -> dict[str, Any]:
        """Only target metadata; secret conditions and outcomes stay in code."""
        context = self.public_context(state)
        for target in context["targets"]:
            source = self._targets[target["id"]]
            target["actions"] = list(source["actions"])
            target["completed_actions"] = [
                action for action in source["actions"]
                if f"{action}:{target['id']}" in state.get("attempts", {})
            ]
            if target["id"] == "desk":
                available = self._careful_search_available(state)
                target["fallback_available"] = available
                if available:
                    target["actions"].append("careful_search")
                    config = source["careful_search"]
                    target["fallback_minutes"] = config["minutes"]
                    target["fallback_description"] = config["public_hint"]
                if "careful_search:desk" in state.get("attempts", {}):
                    target["completed_actions"].append("careful_search")
        context["supported_actions"] = ["look", "investigate", "talk", "leave"]
        if self._careful_search_available(state):
            context["supported_actions"].append("careful_search")
        return context

    def validate_plan(self, plan: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
        """Fill checks from scene data, rejecting any altered tool parameters."""
        if hasattr(plan, "model_dump"):
            plan = plan.model_dump()
        if state.get("scene_id", self.scene_id) != self.scene_id:
            raise SceneValidationError("场景编号不匹配。")
        if state.get("status", "playing") != "playing":
            raise SceneValidationError("本局已经结束，请重新开始。")
        action = plan.get("action_type")
        if action not in {"look", "investigate", "careful_search", "talk", "leave"}:
            raise SceneValidationError("本场景不支持这个行动。")
        target_id = plan.get("target_id") or ("room" if action == "look" else "exit" if action == "leave" else None)
        target = self._targets.get(target_id)
        key = f"{action}:{target_id}"
        completed = key in state.get("attempts", {})
        fallback = (
            action == "careful_search" and target_id == "desk" and target
            and "careful_search" in target
            and (self._careful_search_available(state) or completed)
        )
        if not target or (action not in target["actions"] and not fallback):
            raise SceneValidationError("目标不存在或不支持这个行动，请选择当前场景中的对象。")
        if plan.get("effects") or plan.get("on_success") or plan.get("on_failure"):
            raise SceneValidationError("行动结果必须来自已定义场景，不能由模型指定。")
        repeated = completed and action in {"investigate", "careful_search", "talk"}
        config = target.get(action, {})
        check = None if repeated else copy.deepcopy(config.get("check"))
        proposed = plan.get("check")
        if proposed is not None and proposed != check:
            raise SceneValidationError("检定技能、难度和奖励／惩罚骰必须使用场景设定。")
        return {"action_type": action, "target_id": target_id, "check": check, "repeated": repeated}

    def resolve_action(
        self, plan: dict[str, Any], state: dict[str, Any], passed: bool | None = None
    ) -> dict[str, Any]:
        normalized = self.validate_plan(plan, state)
        action, target_id = normalized["action_type"], normalized["target_id"]
        target = self._targets[target_id]
        new_state = copy.deepcopy(state)
        for field, default in self.initial_state().items():
            new_state.setdefault(field, copy.deepcopy(default))
        effects: list[dict[str, Any]] = []
        new_clues: list[dict[str, Any]] = []
        minutes_spent = 0
        if action == "look":
            text = target["description"]
        elif action == "leave":
            ending = self.definition["ending"]
            complete = set(ending["required_clues"]).issubset(new_state["revealed_clues"])
            new_state["status"] = "ended"
            new_state["ending"] = "complete" if complete else "incomplete"
            text = ending[new_state["ending"]]
        else:
            config = target[action]
            if normalized["repeated"]:
                text = config["repeat"]
                if action == "investigate" and target_id == "desk" and self._careful_search_available(state):
                    text += " " + target["careful_search"]["public_hint"]
            else:
                if normalized["check"] and not isinstance(passed, bool):
                    raise SceneValidationError("需要真实检定结果后才能结算行动。")
                success = passed if normalized["check"] else True
                outcome = config["success" if success else "failure"]
                text = outcome["text"]
                if action == "careful_search":
                    minutes_spent = config["minutes"]
                    new_state["elapsed_minutes"] += minutes_spent
                for clue_id in outcome.get("reveal", []):
                    if clue_id not in new_state["revealed_clues"]:
                        new_state["revealed_clues"].append(clue_id)
                        new_clues.append({"id": clue_id, **copy.deepcopy(self._clues[clue_id])})
                new_state["attempts"][f"{action}:{target_id}"] = {"passed": success}
                if minutes_spent:
                    new_state["attempts"][f"{action}:{target_id}"]["minutes_spent"] = minutes_spent
                if action == "talk":
                    new_state["npc_state"][target_id] = {"spoken": True}
                effect = config.get("effect")
                if effect and success and effect["event_id"] not in new_state["triggered_events"]:
                    effects.append(copy.deepcopy(effect))
                    new_state["triggered_events"].append(effect["event_id"])
        event = {
            "action_type": action, "target_id": target_id, "text": text,
            "new_clues": new_clues, "repeated": normalized["repeated"],
            "minutes_spent": minutes_spent,
            "elapsed_minutes": new_state["elapsed_minutes"],
        }
        return {
            "state": new_state, "scene_state": new_state,
            "public_event": event, "effects": effects, "clues": new_clues,
            "game_status": new_state["status"],
        }

    def review(self, state: dict[str, Any]) -> dict[str, Any]:
        """Reveal only this room's authored clues, and only after it has ended."""
        if state.get("status") != "ended":
            raise SceneValidationError("本场景结束后才能复盘；进行中或暂停时不会揭示未发现的内容。")
        if state.get("scene_id", self.scene_id) != self.scene_id:
            raise SceneValidationError("场景编号不匹配。")
        revealed = set(state.get("revealed_clues", []))
        discovered, missed = [], []
        for clue_id, clue in self._clues.items():
            item = {"id": clue_id, **copy.deepcopy(clue)}
            (discovered if clue_id in revealed else missed).append(item)
        ending = state.get("ending")
        if ending not in {"complete", "incomplete"}:
            ending = "complete" if not missed else "incomplete"
        lines = ["本场景复盘", "你已经收集到全部必需线索，没有遗漏。" if not missed else "你离开时，还有线索没有发现。"]
        lines.append("已发现的线索：")
        lines.extend(f"- {clue['name']}：{clue['description']}" for clue in discovered)
        if not discovered:
            lines.append("- 无。")
        lines.append("未发现的线索：")
        lines.extend(f"- {clue['name']}：{clue['description']}" for clue in missed)
        if not missed:
            lines.append("- 无。")
        if "letter" in {clue["id"] for clue in missed}:
            lines.append("书桌的首次调查需要侦查检定。如果失败，本场景还允许花十分钟换方法细查，不重掷骰子；这是这间书房的场景约定，不能推及所有 COC 检定。")
        if "photograph" in {clue["id"] for clue in missed}:
            lines.append("管家保管的照片可以通过与他交谈取得。")
        if state.get("elapsed_minutes", 0):
            lines.append(f"你为进一步调查额外花费了 {state['elapsed_minutes']} 分钟。")
        return {"text": "\n".join(lines), "missed_clues": missed, "discovered_clues": discovered, "ending": ending}
