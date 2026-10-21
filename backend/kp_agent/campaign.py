"""Authored three-scene campaign; models propose actions, never state changes.

The flat current-scene fields remain compatible with KeeperService. Per-scene
attempts are parked on transitions; inventory, effects and clues are global.
Only public_context / planning_context / public_event are model-facing.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

from .scene import SceneDefinition, SceneValidationError


class CampaignDefinition:
    def __init__(self, definition: dict[str, Any], scenes: dict[str, SceneDefinition]):
        self.definition = copy.deepcopy(definition)
        self.campaign_id = definition["id"]
        self.title = definition["title"]
        self.scene_id = definition["start_scene"]
        self.scenes = scenes
        authored = {"campaign": self.definition,
                    "scenes": {key: scene.definition for key, scene in scenes.items()}}
        self.revision = hashlib.sha256(json.dumps(authored, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        self._items = copy.deepcopy(definition.get("items", {}))
        self._clues: dict[str, dict[str, Any]] = {}
        for scene_id, scene in scenes.items():
            for clue_id, clue in scene.definition.get("clues", {}).items():
                if clue_id in self._clues:
                    raise ValueError("场景配置中存在重复线索编号。")
                self._clues[clue_id] = {**copy.deepcopy(clue), "scene_id": scene_id}
        if self.scene_id not in scenes:
            raise ValueError("故事缺少起始地点。")

    @classmethod
    def load(cls, path: str | Path) -> "CampaignDefinition":
        path = Path(path)
        definition = json.loads(path.read_text(encoding="utf-8"))
        scenes = {scene_id: SceneDefinition.load(path.parent / relative)
                  for scene_id, relative in definition["scenes"].items()}
        for scene_id, scene in scenes.items():
            if scene.scene_id != scene_id:
                raise ValueError("场景文件与故事中的地点编号不一致。")
        return cls(definition, scenes)

    @property
    def opening(self) -> str:
        return self.scenes[self.scene_id].opening

    def _item(self, item_id: str, quantity: int) -> dict[str, Any]:
        item = self._items[item_id]
        return {"id": item_id, "name": item["name"],
                "description": item["description"], "quantity": quantity,
                "aliases": list(item.get("aliases", []))}

    def initial_state(self, san: int | None = None) -> dict[str, Any]:
        state = self.scenes[self.scene_id].initial_state(san=san)
        state.update({
            "campaign_id": self.campaign_id,
            "campaign_revision": self.revision,
            "visited_scenes": [self.scene_id],
            "scene_states": {self.scene_id: {"attempts": {}, "npc_state": {}}},
            "inventory": {item_id: self._item(item_id, quantity)
                          for item_id, quantity in self.definition.get("initial_inventory", {}).items()},
            "effect_applications": {},
        })
        return state

    def _require_state(self, state: dict[str, Any], *, playing: bool = False) -> None:
        if state.get("campaign_id") != self.campaign_id:
            raise SceneValidationError("这份存档不属于当前故事，请保留旧存档并新开一局。")
        if state.get("campaign_revision") != self.revision:
            raise SceneValidationError("故事配置已更新，请保留旧存档并重新开始，避免把旧检定用于新的事件。")
        if state.get("scene_id") not in self.scenes:
            raise SceneValidationError("存档中的当前位置无效，请让开发者检查。")
        if playing and state.get("status") != "playing":
            raise SceneValidationError("本局已经结束或暂停，不能继续执行行动。")

    def _scene(self, state: dict[str, Any]) -> dict[str, Any]:
        return self.scenes[state["scene_id"]].definition

    @staticmethod
    def _meets(config: dict[str, Any], state: dict[str, Any]) -> bool:
        known = set(state.get("revealed_clues", []))
        return (set(config.get("requires_clues", [])).issubset(known)
                and set(config.get("requires_visited", [])).issubset(state.get("visited_scenes", [])))

    def _fallback_available(self, target_id: str, state: dict[str, Any]) -> bool:
        target = self._scene(state)["targets"].get(target_id, {})
        config = target.get("careful_search")
        if not config or state.get("status") != "playing":
            return False
        attempts = state.get("attempts", {})
        failed = attempts.get(f"{config.get('after_failed_action', 'investigate')}:{target_id}", {})
        rewards = config.get("success", {}).get("reveal", [])
        return (failed.get("passed") is False
                and f"careful_search:{target_id}" not in attempts
                and not any(clue in state.get("revealed_clues", []) for clue in rewards))

    def _uses_for(self, target_id: str, state: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
        result = []
        for item_id, item in state.get("inventory", {}).items():
            if item_id not in self._items or item.get("quantity", 0) <= 0:
                continue
            for use in self._items[item_id].get("uses", []):
                if use.get("scene_id") not in {"*", state["scene_id"]} or use["target_id"] != target_id:
                    continue
                key = f"use_item:{target_id}:{item_id}"
                if self._meets(use, state) and key not in state.get("attempts", {}):
                    result.append((item_id, use))
        return result

    def _exit(self, target_id: str, state: dict[str, Any]) -> dict[str, Any] | None:
        return self._scene(state).get("exits", {}).get(target_id)

    def _actions(self, target_id: str, state: dict[str, Any]) -> list[str]:
        if state.get("status") != "playing":
            return []
        target = self._scene(state)["targets"][target_id]
        actions = [action for action in target.get("actions", [])
                   if action in {"look", "investigate", "talk"}]
        if self._fallback_available(target_id, state):
            actions.append("careful_search")
        if self._uses_for(target_id, state):
            actions.append("use_item")
        connection = self._exit(target_id, state)
        if connection:
            if connection.get("ends_campaign"):
                actions.append("leave")
            elif self._meets(connection, state):
                actions.extend(["move", "leave"])
            if connection.get("can_finish"):
                actions.append("finish")
        return list(dict.fromkeys(actions))

    def _public_target(self, target_id: str, target: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
        result = {"id": target_id, "name": target["name"], "description": target["description"],
                  "aliases": list(target.get("aliases", []))}
        matched_variant = False
        for variant in target.get("public_states", []):
            if self._meets(variant, state):
                matched_variant = True
                for field in ("name", "description"):
                    if field in variant:
                        result[field] = variant[field]
        if target_id == "self":
            # A static character description must not invent an injury or keep
            # claiming that a consumed item is still held. Resource values are
            # supplied separately by KeeperService; inventory is known here.
            held = [f"{self._items[item_id]['name']} × {entry['quantity']}"
                    for item_id, entry in state.get("inventory", {}).items()
                    if item_id in self._items and entry.get("quantity", 0) > 0]
            result["description"] = "你可以查看自己的当前状态。" + (
                "当前随身物品：" + "、".join(held) + "。" if held else "当前没有剩余的随身物品。"
            )
        elif not matched_variant:
            # If an investigation has already exposed its evidence, show that
            # public result instead of the untouched object's old description.
            # Only acquired clues from a successful local attempt may be used.
            known = set(state.get("revealed_clues", []))
            discovered = []
            for action in ("investigate", "careful_search"):
                attempt = state.get("attempts", {}).get(f"{action}:{target_id}", {})
                if attempt.get("passed") is not True:
                    continue
                for clue_id in target.get(action, {}).get("success", {}).get("reveal", []):
                    if clue_id in known and clue_id in self._clues and clue_id not in discovered:
                        discovered.append(clue_id)
            if discovered:
                result["description"] = "你已经查明的信息：" + " ".join(
                    self._clues[clue_id]["description"] for clue_id in discovered
                )
        connection = self._exit(target_id, state)
        if connection and connection.get("to") and self._meets(connection, state):
            destination = self.scenes[connection["to"]]
            result["aliases"].extend([destination.title, *connection.get("aliases", [])])
        return result

    def _readable_objects(self, state: dict[str, Any]) -> dict[str, dict[str, Any]]:
        """Already acquired evidence/items can be reread in every location."""
        result = {}
        for clue_id in state.get("revealed_clues", []):
            clue = self._clues.get(clue_id)
            if clue:
                target_id = f"clue_{clue_id}"
                result[target_id] = {"id": target_id, "name": clue["name"],
                                     "description": clue["description"],
                                     "aliases": [clue["name"], *clue.get("aliases", [])],
                                     "actions": ["look"], "completed_actions": []}
        for item_id, entry in state.get("inventory", {}).items():
            if item_id not in self._items:
                continue
            item = self._items[item_id]
            target_id = f"item_{item_id}"
            result[target_id] = {"id": target_id, "name": item["name"],
                                 "description": f"{item['description']} 当前剩余数量：{entry.get('quantity', 0)}。",
                                 "aliases": [item["name"], *item.get("aliases", [])],
                                 "actions": ["look"], "completed_actions": []}
        return result

    def public_context(self, state: dict[str, Any]) -> dict[str, Any]:
        self._require_state(state)
        scene = self._scene(state)
        destinations, seen = [], set()
        for target_id, connection in scene.get("exits", {}).items():
            destination = connection.get("to")
            if (state.get("status") == "playing" and destination
                    and self._meets(connection, state) and destination not in seen):
                destinations.append({"target_id": target_id, "scene_id": destination,
                                     "name": self.scenes[destination].title, "label": connection["label"]})
                seen.add(destination)
        inventory = {item_id: self._item(item_id, item.get("quantity", 0))
                     for item_id, item in state.get("inventory", {}).items() if item_id in self._items}
        ended = state.get("status") == "ended"
        description = (self.definition["endings"].get(state.get("ending"), "本局调查已经结束。")
                       if ended else scene["public_description"])
        return {
            "campaign_id": self.campaign_id, "campaign_title": self.title,
            "scene_id": state["scene_id"], "title": scene["title"], "description": description,
            "targets": [] if ended else [self._public_target(key, target, state) for key, target in scene["targets"].items()],
            "revealed_clues": [{"id": key, **copy.deepcopy(self._clues[key])}
                               for key in state.get("revealed_clues", []) if key in self._clues],
            "inventory": inventory,
            "visited_scenes": [{"id": scene_id, "name": self.scenes[scene_id].title}
                               for scene_id in state.get("visited_scenes", []) if scene_id in self.scenes],
            "destinations": destinations, "status": state["status"], "ending": state.get("ending"),
            "elapsed_minutes": state.get("elapsed_minutes", 0),
        }

    def planning_context(self, state: dict[str, Any]) -> dict[str, Any]:
        context = self.public_context(state)
        suggestions = []
        attempts = state.get("attempts", {})
        for target in context["targets"]:
            target_id = target["id"]
            raw = self._scene(state)["targets"][target_id]
            target["actions"] = self._actions(target_id, state)
            target["completed_actions"] = [action for action in ("investigate", "talk", "careful_search")
                                           if f"{action}:{target_id}" in attempts]
            prefix = f"use_item:{target_id}:"
            target["completed_item_uses"] = [key[len(prefix):] for key in attempts if key.startswith(prefix)]
            if "careful_search" in raw:
                available = self._fallback_available(target_id, state)
                target["fallback_available"] = available
                if available:
                    fallback = raw["careful_search"]
                    target["fallback_minutes"] = fallback["minutes"]
                    target["fallback_description"] = fallback["public_hint"]
            for action in target["actions"]:
                if action in target["completed_actions"]:
                    continue
                if action == "use_item":
                    for item_id, use in self._uses_for(target_id, state):
                        suggestion = {"intent": action, "target_id": target_id, "item_id": item_id,
                                      "label": use["label"], "priority": use.get("priority", 95)}
                        effects = use.get("success", {}).get("effects", [])
                        if effects and all(effect.get("type") == "restore" for effect in effects):
                            suggestion["needed_resources"] = list(dict.fromkeys(
                                effect["resource"] for effect in effects if effect.get("resource") in {"hp", "mp"}
                            ))
                        suggestions.append(suggestion)
                elif action == "careful_search":
                    suggestions.append({"intent": action, "target_id": target_id,
                                        "label": raw["careful_search"]["label"], "priority": 110})
                elif action == "move":
                    connection = self._exit(target_id, state)
                    if connection.get("suggest", True):
                        suggestions.append({"intent": action, "target_id": target_id,
                                            "label": connection["label"], "priority": connection.get("priority", 90)})
                elif action == "leave":
                    if self._exit(target_id, state).get("ends_campaign"):
                        suggestions.append({"intent": action, "target_id": target_id,
                                            "label": "带着当前证据离开，结束调查", "priority": 20})
                elif action == "finish":
                    # Final exits already offer `leave`, which runs the same
                    # ending logic. Do not duplicate it as a misleading retreat.
                    if not self._exit(target_id, state).get("ends_campaign"):
                        suggestions.append({"intent": action, "target_id": target_id,
                                            "label": "停止调查并撤退", "priority": -100})
                elif action in {"investigate", "talk"}:
                    suggestions.append({"intent": action, "target_id": target_id,
                                        "label": raw.get("labels", {}).get(action, ("调查" if action == "investigate" else "询问") + raw["name"]),
                                        "priority": raw.get("priority", 60)})
                elif action == "look" and target_id == "room":
                    suggestions.append({"intent": action, "target_id": target_id,
                                        "label": "观察周围", "priority": 10})
        context["targets"].extend(self._readable_objects(state).values())
        context["supported_actions"] = sorted({action for target in context["targets"] for action in target["actions"]})
        context["action_suggestions"] = sorted(suggestions, key=lambda item: -item["priority"])
        return context

    def validate_plan(self, plan: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
        self._require_state(state, playing=True)
        if hasattr(plan, "model_dump"):
            plan = plan.model_dump()
        action = plan.get("action_type", plan.get("intent"))
        if action not in {"look", "investigate", "careful_search", "talk", "move", "leave", "use_item", "finish"}:
            raise SceneValidationError("这个行动超出当前故事支持范围，请描述观察、调查、交谈或使用已有物品。")
        target_id = plan.get("target_id") or ("room" if action == "look" else "exit" if action in {"leave", "move", "finish"} else None)
        target = self._scene(state)["targets"].get(target_id)
        if any(plan.get(key) for key in ("effects", "on_success", "on_failure", "grant_items", "reveal")):
            raise SceneValidationError("行动的结果由现场情况决定，不能直接指定奖励或数值变化。")
        readable = self._readable_objects(state).get(target_id)
        if readable:
            if action != "look" or plan.get("check") is not None:
                raise SceneValidationError("已获得的信息可以阅读，但不能靠重复调查它产生新物品或线索。")
            return {"action_type": action, "target_id": target_id, "item_id": None,
                    "check": None, "repeated": False}
        if not target:
            raise SceneValidationError("这里没有你提到的对象。请先看看当前环境。")
        item_id = plan.get("item_id")
        repeated = False
        check = None
        if action == "use_item":
            if not item_id or item_id not in state.get("inventory", {}):
                raise SceneValidationError("你没有这件物品，请先查看随身物品。")
            key = f"use_item:{target_id}:{item_id}"
            repeated = key in state.get("attempts", {})
            if not repeated and not any(candidate == item_id for candidate, _ in self._uses_for(target_id, state)):
                raise SceneValidationError("这件物品目前不能用在这里，或已经用完。")
        elif action in {"move", "leave"}:
            connection = self._exit(target_id, state)
            if not connection:
                raise SceneValidationError("这里不是可以通行的出口。")
            if connection.get("ends_campaign") and action == "move":
                raise SceneValidationError("若要回到上一处地点，请选择回程通道；若结束调查，请明确说离开或结束。")
            if not connection.get("ends_campaign") and not self._meets(connection, state):
                raise SceneValidationError(connection.get("blocked_text", "你还没有找到可以安全前进的路线，请继续调查当前地点。"))
        elif action == "finish":
            if not (self._exit(target_id, state) or {}).get("can_finish"):
                raise SceneValidationError("如果要结束调查，请明确选择出口。")
        else:
            key = f"{action}:{target_id}"
            repeated = key in state.get("attempts", {}) and action in {"investigate", "talk", "careful_search"}
            fallback_repeat = action == "careful_search" and repeated and "careful_search" in target
            if action not in self._actions(target_id, state) and not fallback_repeat:
                raise SceneValidationError("当前不能这样调查这个对象。可以尝试眼前其他行动，或查看已经找到的信息。")
            config = target.get(action, {})
            check = None if repeated else copy.deepcopy(config.get("check"))
        if plan.get("check") is not None and plan["check"] != check:
            raise SceneValidationError("检定方式由场景规则确定，不能更改技能、难度或骰子结果。")
        return {"action_type": action, "target_id": target_id, "item_id": item_id,
                "check": check, "repeated": repeated}

    @staticmethod
    def _save_local(state: dict[str, Any]) -> None:
        state.setdefault("scene_states", {})[state["scene_id"]] = {
            "attempts": copy.deepcopy(state.get("attempts", {})),
            "npc_state": copy.deepcopy(state.get("npc_state", {})),
        }

    def _apply_outcome(self, outcome: dict[str, Any], state: dict[str, Any], clues: list, items: list, effects: list) -> None:
        for clue_id in outcome.get("reveal", []):
            if clue_id not in state["revealed_clues"]:
                state["revealed_clues"].append(clue_id)
                clues.append({"id": clue_id, **copy.deepcopy(self._clues[clue_id])})
        for item_id in outcome.get("grant_items", []):
            current = state["inventory"].get(item_id, {}).get("quantity", 0)
            state["inventory"][item_id] = self._item(item_id, current + 1)
            items.append(self._item(item_id, 1))
        for effect in outcome.get("effects", []):
            event_id = effect.get("event_id")
            if event_id and event_id in state["triggered_events"]:
                continue
            effects.append(copy.deepcopy(effect))
            if event_id:
                state["triggered_events"].append(event_id)

    def _end(self, state: dict[str, Any], action: str) -> str:
        ending = self.definition["endings"]
        known = set(state["revealed_clues"])
        if (state["scene_id"] == self.definition["final_scene"]
                and set(ending["required_clues"]).issubset(known)):
            key = "complete"
        elif state["scene_id"] == self.definition["final_scene"] and action == "leave" and not set(ending["evidence_clues"]).issubset(known):
            key = "incomplete"
        else:
            key = "retreat"
        state["status"], state["ending"] = "ended", key
        return ending[key]

    def resolve_action(self, plan: dict[str, Any], state: dict[str, Any], passed: bool | None = None) -> dict[str, Any]:
        plan = self.validate_plan(plan, state)
        current = copy.deepcopy(state)
        defaults = self.initial_state(san=state.get("san_day_start"))
        for key, value in defaults.items():
            current.setdefault(key, copy.deepcopy(value))
        action, target_id, item_id = plan["action_type"], plan["target_id"], plan["item_id"]
        target = self._scene(current)["targets"].get(target_id)
        readable = self._readable_objects(current).get(target_id)
        clues, items, effects, consumed = [], [], [], []
        minutes, transition = 0, None
        if readable:
            text = readable["description"]
        elif action == "look":
            text = self._public_target(target_id, target, current)["description"]
        elif action == "finish":
            text = self._end(current, action)
        elif action in {"move", "leave"}:
            connection = self._exit(target_id, current)
            if connection.get("ends_campaign"):
                text = self._end(current, action)
            else:
                self._save_local(current)
                previous, destination = current["scene_id"], connection["to"]
                revisiting = destination in current["visited_scenes"]
                current["scene_id"] = destination
                local = current["scene_states"].get(destination, {"attempts": {}, "npc_state": {}})
                current["attempts"] = copy.deepcopy(local["attempts"])
                current["npc_state"] = copy.deepcopy(local["npc_state"])
                if not revisiting:
                    current["visited_scenes"].append(destination)
                scene = self._scene(current)
                text = scene.get("returning", "你回到这里。" + scene["public_description"]) if revisiting else scene["opening"]
                transition = {"from": previous, "to": destination, "title": scene["title"]}
        elif action == "use_item":
            if plan["repeated"]:
                text = "这件物品已经在这里使用过，不会再次消耗或产生新的结果。"
            else:
                use = next(use for candidate, use in self._uses_for(target_id, current) if candidate == item_id)
                self._apply_outcome(use["success"], current, clues, items, effects)
                if use.get("consume", True):
                    current["inventory"][item_id]["quantity"] -= 1
                    consumed.append({"id": item_id, "name": self._items[item_id]["name"], "quantity": 1})
                current["attempts"][f"use_item:{target_id}:{item_id}"] = {"passed": True}
                text = use["success"]["text"]
        else:
            config = target[action]
            if plan["repeated"]:
                text = config["repeat"]
                if action == "investigate" and self._fallback_available(target_id, current):
                    text += " " + target["careful_search"]["public_hint"]
            else:
                if plan["check"] and not isinstance(passed, bool):
                    raise SceneValidationError("需要真实检定结果后才能确定这次行动的结果。")
                success = passed if plan["check"] else True
                outcome = copy.deepcopy(config["success" if success else "failure"])
                if success and config.get("effect"):
                    outcome.setdefault("effects", []).append(config["effect"])
                self._apply_outcome(outcome, current, clues, items, effects)
                minutes = config.get("minutes", 0)
                current["elapsed_minutes"] += minutes
                current["attempts"][f"{action}:{target_id}"] = {"passed": success, "minutes_spent": minutes}
                if action == "talk":
                    current["npc_state"][target_id] = {"spoken": True}
                text = outcome["text"]
        self._save_local(current)
        event = {"action_type": action, "target_id": target_id, "item_id": item_id,
                 "text": text, "repeated": plan["repeated"], "new_clues": clues,
                 "new_items": items, "consumed_items": consumed,
                 "minutes_spent": minutes, "elapsed_minutes": current["elapsed_minutes"]}
        if transition:
            event["scene_transition"] = transition
        return {"state": current, "scene_state": current, "public_event": event,
                "effects": effects, "clues": clues, "game_status": current["status"]}

    def review(self, state: dict[str, Any]) -> dict[str, Any]:
        self._require_state(state)
        if state.get("status") != "ended":
            raise SceneValidationError("故事结束后才能复盘；现在只会说明已经发现的信息。")
        known = set(state.get("revealed_clues", []))
        discovered, missed = [], []
        for clue_id, clue in self._clues.items():
            item = {"id": clue_id, **copy.deepcopy(clue)}
            (discovered if clue_id in known else missed).append(item)
        labels = {"complete": "完整结局", "retreat": "主动撤退", "incomplete": "信息不足的结局"}
        lines = ["本次调查复盘", f"结果：{labels.get(state.get('ending'), '调查结束')}。", self.definition["review_summary"]]
        lines.append("已发现的信息：")
        lines.extend(f"- {item['name']}：{item['description']}" for item in discovered)
        if not discovered:
            lines.append("- 无。")
        lines.append("遗漏的信息：")
        lines.extend(f"- {item['name']}：{item['description']}" for item in missed)
        if not missed:
            lines.append("- 没有遗漏。")
        lines.append("关键调查失败后，本故事提供花时间换方法细查的路线；这属于本故事的约定，不是所有 COC 检定都能花时间自动成功。")
        lines.append(f"额外调查共花费 {state.get('elapsed_minutes', 0)} 分钟。")
        return {"text": "\n".join(lines), "missed_clues": missed,
                "discovered_clues": discovered, "ending": state.get("ending")}
