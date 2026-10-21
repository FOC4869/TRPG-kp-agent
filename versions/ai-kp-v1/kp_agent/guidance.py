"""Optional next actions derived exclusively from the current public context."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


_KNOWN_ACTIONS = {"look", "investigate", "careful_search", "talk", "move", "use_item", "finish", "leave"}
_ONCE_ACTIONS = {"investigate", "careful_search", "talk", "use_item"}
_LEGACY_PRIORITY = {"desk": 80, "butler": 70, "bookshelf": 60, "fireplace": 50, "exit": 0, "room": 10}


def _held_items(context: Mapping[str, Any]) -> set[str]:
    inventory = context.get("inventory", {})
    if isinstance(inventory, Mapping):
        entries = inventory.items()
    elif isinstance(inventory, list):
        entries = [(item.get("id", item.get("item_id")) if isinstance(item, Mapping) else item, item)
                   for item in inventory]
    else:
        return set()
    held = set()
    for item_id, value in entries:
        quantity = value.get("quantity", value.get("count", 1)) if isinstance(value, Mapping) else value if type(value) is int else 1
        if isinstance(item_id, str) and type(quantity) in {int, float} and quantity > 0:
            held.add(item_id)
    return held


def _fallback_suggestions(
    targets: Mapping[str, Mapping[str, Any]], context: Mapping[str, Any],
    last_event: Mapping[str, Any] | None,
) -> list[dict[str, Any]]:
    """Keep older room callers usable when they do not supply suggestions yet."""
    result = []
    completed_any = any(target.get("completed_actions") for target in targets.values())
    for target_id, target in targets.items():
        name = target.get("name")
        if not isinstance(name, str) or not name:
            continue
        for action in target.get("actions", []):
            if action not in _KNOWN_ACTIONS or action == "use_item":
                continue
            if action == "look" and (target_id != "room" or last_event is not None or completed_any):
                continue
            labels = {
                "look": "观察房间", "investigate": f"调查{name}",
                "careful_search": f"花时间仔细检查{name}", "talk": f"与{name}交谈",
                "move": f"前往{name}", "leave": f"离开{name}", "finish": "结束调查",
            }
            priority = _LEGACY_PRIORITY.get(target_id, 50)
            if action == "look":
                priority = 100
            elif action == "careful_search":
                priority = 150
                if target_id == "desk":
                    labels[action] = "花十分钟仔细检查书桌"
            elif action == "talk":
                clues = context.get("revealed_clues", [])
                mentions = [clue.get("description", "") for clue in clues if isinstance(clue, Mapping)] if isinstance(clues, list) else []
                if any(name in text for text in mentions if isinstance(text, str)):
                    priority += 40
                    if target_id == "butler" and any("照片" in text for text in mentions if isinstance(text, str)):
                        labels[action] = "向管家询问来信提到的照片"
            result.append({"intent": action, "target_id": target_id, "label": labels[action], "priority": priority})
    return result


def build_guidance(
    context: Mapping[str, Any], last_event: Mapping[str, Any] | None = None,
    reply_type: str = "narration", *, max_actions: int = 3,
) -> dict[str, Any]:
    """Recommend legal public actions without inspecting scene definitions.

    Suggestions are optional. A player may freely describe another action;
    repeated completed actions remain valid requests but are not recommended.
    """
    empty = {"suggested_actions": [], "guidance": ""}
    if context.get("status", context.get("game_status")) != "playing" or reply_type not in {"narration", "rule_explanation"}:
        return empty
    if type(max_actions) is not int or max_actions <= 0:
        return empty
    raw_targets = context.get("targets", [])
    if not isinstance(raw_targets, list):
        return empty
    targets = {target["id"]: target for target in raw_targets
               if isinstance(target, Mapping) and isinstance(target.get("id"), str)}
    source = context.get("action_suggestions")
    if source is None:
        source = _fallback_suggestions(targets, context, last_event)
    if not isinstance(source, list):
        return empty
    held = _held_items(context)
    character = context.get("character", {})
    completed_any = any(target.get("completed_actions") for target in targets.values())
    candidates = []
    for index, suggestion in enumerate(source):
        if not isinstance(suggestion, Mapping):
            continue
        action, target_id = suggestion.get("intent"), suggestion.get("target_id")
        target = targets.get(target_id)
        label = suggestion.get("label")
        if action not in _KNOWN_ACTIONS or target is None or not isinstance(label, str) or not label.strip():
            continue
        allowed, completed = target.get("actions", []), target.get("completed_actions", [])
        if not isinstance(allowed, list) or not isinstance(completed, list) or action not in allowed:
            continue
        if action in _ONCE_ACTIONS and action in completed:
            continue
        if action == "careful_search" and target.get("fallback_available") is False:
            continue
        if action == "use_item" and suggestion.get("item_id") not in held:
            continue
        needed = suggestion.get("needed_resources")
        if action == "use_item" and isinstance(needed, list) and needed:
            # Having an item does not mean that using it is currently useful.
            # Keep the legal use in planning_context for explicit requests, but
            # only recommend recovery when the public character has a deficit.
            if not isinstance(character, Mapping) or not any(
                resource in {"hp", "mp"}
                and type(character.get(resource)) is int
                and type(character.get(resource + "_max")) is int
                and 0 <= character[resource] < character[resource + "_max"]
                for resource in needed if isinstance(resource, str)
            ):
                continue
        if action == "look" and target_id == "room" and (last_event is not None or completed_any):
            continue
        priority = suggestion.get("priority", 50)
        priority = priority if type(priority) in {int, float} else 50
        if (last_event or {}).get("action_type") == "look" and (last_event or {}).get("target_id") == target_id and action == "investigate":
            priority += 25
        candidates.append((priority, -index, label.strip()[:160]))
    candidates.sort(key=lambda row: (-row[0], -row[1]))
    actions = list(dict.fromkeys(label for _, _, label in candidates))[:min(max_actions, 3)]
    if not actions:
        return empty
    if len(actions) == 1:
        text = f"接下来可以{actions[0]}，也可以描述其他想做的事。"
    elif len(actions) == 2:
        text = f"接下来，你想{actions[0]}，还是{actions[1]}？也可以描述自己的做法。"
    else:
        text = f"接下来，你想{actions[0]}、{actions[1]}，还是{actions[2]}？也可以描述自己的做法。"
    return {"suggested_actions": actions, "guidance": text}
