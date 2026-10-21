"""Small, optional next-step hints built exclusively from public scene data.

No LLM or hidden outcome is needed. Suggestions describe legal actions, never
promise discoveries, and are not an exhaustive menu of what a player can try.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


_ACTIONS = {
    "room": ("look", "观察房间", 10),
    "desk": ("investigate", "调查书桌", 80),
    "butler": ("talk", "与管家交谈", 70),
    "bookshelf": ("investigate", "调查书架", 60),
    "fireplace": ("investigate", "调查壁炉", 50),
    "exit": ("leave", "离开书房", 0),
}


def build_guidance(
    context: Mapping[str, Any], last_event: Mapping[str, Any] | None = None,
    reply_type: str = "narration", *, max_actions: int = 3,
) -> dict[str, Any]:
    """Use planning_context's public targets/actions/completed_actions only.

    Fixed target names match this project's one authored room. Unknown targets
    and malformed data are ignored rather than generating speculative choices.
    """
    empty = {"suggested_actions": [], "guidance": ""}
    if context.get("status") != "playing" or reply_type not in {"narration", "rule_explanation"}:
        return empty
    if type(max_actions) is not int or max_actions <= 0:
        return empty
    targets = context.get("targets")
    if not isinstance(targets, list):
        return empty
    known = {target.get("id"): target for target in targets
             if isinstance(target, Mapping) and isinstance(target.get("id"), str)}
    completed_any = any(target.get("completed_actions") for target in known.values())

    # A link to an NPC can be highlighted only after the corresponding text
    # was actually revealed. The still-hidden clue collection is never read.
    public_clues = context.get("revealed_clues", [])
    mentioned_butler = False
    mentioned_photo = False
    for clue in public_clues if isinstance(public_clues, list) else []:
        if not isinstance(clue, Mapping):
            continue
        description = clue.get("description", "")
        if isinstance(description, str) and "管家" in description:
            mentioned_butler = True
            mentioned_photo = mentioned_photo or "照片" in description

    candidates: list[tuple[int, str]] = []
    for target_id, (action, label, priority) in _ACTIONS.items():
        target = known.get(target_id)
        if target is None:
            continue
        allowed = target.get("actions", [])
        completed = target.get("completed_actions", [])
        if not isinstance(allowed, list) or not isinstance(completed, list):
            continue
        if action not in allowed or action in completed:
            continue
        # Observation is useful at the opening. Later, do not pad a depleted
        # action list with the same generic room description every turn.
        if target_id == "room":
            if last_event is not None or completed_any:
                continue
            priority = 100
        if target_id == "butler" and mentioned_butler:
            priority = 110
            if mentioned_photo:
                label = "向管家询问来信提到的照片"
        # Looking at a particular object may naturally lead to investigating it.
        if (last_event or {}).get("action_type") == "look" and (last_event or {}).get("target_id") == target_id:
            priority += 25
        candidates.append((priority, label))
    desk = known.get("desk")
    if desk is not None:
        allowed, completed = desk.get("actions", []), desk.get("completed_actions", [])
        if (
            isinstance(allowed, list) and isinstance(completed, list)
            and "careful_search" in allowed and "careful_search" not in completed
            and desk.get("fallback_available") is not False
        ):
            candidates.append((150, "花十分钟仔细检查书桌"))
    candidates.sort(key=lambda item: -item[0])
    actions = [label for _, label in candidates[:min(max_actions, 3)]]
    if not actions:
        return empty
    if len(actions) == 1:
        text = f"接下来可以{actions[0]}，也可以描述其他想做的事。"
    elif len(actions) == 2:
        text = f"接下来，你想{actions[0]}，还是{actions[1]}？也可以描述自己的做法。"
    else:
        text = f"接下来，你想{actions[0]}、{actions[1]}，还是{actions[2]}？也可以描述自己的做法。"
    return {"suggested_actions": actions, "guidance": text}
