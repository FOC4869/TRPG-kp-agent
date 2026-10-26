"""Web-facing tools around our original three-scene campaign and rule tools.

This module contains no model, prompt or graph. CampaignDefinition remains the
only authority for story conditions, rewards, item consumption and endings;
CharacterTools remains the only authority for checks and resource effects.
"""
from __future__ import annotations

import copy
from pathlib import Path

from trpg import Character
from .campaign import CampaignDefinition
from .scene import SceneValidationError
from .tools import CharacterTools
from .guidance import build_guidance
from .game_tools.content import GameError, digest
from app.services.catalogue import safe_file, equipment_items

ROOT = Path(__file__).resolve().parents[1]
DEGREES = {"critical_success": "大成功", "extreme_success": "极难成功",
           "hard_success": "困难成功", "regular_success": "常规成功",
           "failure": "失败", "fumble": "大失败"}


def _inventory(state):
    return [{"id": key, "name": item["name"], "quantity": item["quantity"],
             "kind": "carried", "note": item.get("description", ""),
             "aliases": list(item.get("aliases", []))}
            for key, item in state.get("inventory", {}).items()
            if item.get("quantity") is None or item.get("quantity", 0) > 0]


def template_inventory(raw):
    """Flatten carried equipment once, preserving IDs, unknowns and ownership."""
    result = {}
    def add(items, owned=False, container=''):
        for item in items:
            is_owned = owned or item.get('placement') == 'owned_asset'
            if not is_owned:
                entry = equipment_items([{**item, 'contents': []}], container)[0]
                result[item['id']] = {'id': item['id'], 'name': item['name'],
                    'quantity': item.get('quantity'), 'description': entry.note,
                    'aliases': item.get('aliases', [])}
            add(item.get('contents', []), is_owned,
                f'{container} / {item["name"]}' if container else item['name'])
    add(raw.get('starting_equipment', []))
    return result


def _sync(game, campaign):
    """Project our source character/state without inventing a second state."""
    state, character = game["campaignState"], game["character"]
    public = campaign.public_context(state)
    detail = game["investigator"]
    detail["attributes"] = copy.deepcopy(character["attributes"])
    detail["skills"] = [{"name": name, "value": value, "highlighted": False}
                        for name, value in character["skills"].items()]
    detail["resources"] = {"hp": character["hp"], "hpMax": character["hp_max"],
                           "san": character["san"], "sanMax": character["san_max"],
                           "mp": character["mp"], "mpMax": character["mp_max"],
                           "luck": character["luck"]}
    game["sceneId"] = state["scene_id"]
    game["visited"] = list(state["visited_scenes"])
    game["inventory"] = _inventory(state)
    game["facts"] = [{"id": clue["id"], "title": clue["name"], "text": clue["description"],
                      "aliases": list(clue.get("aliases", []))}
                     for clue in public["revealed_clues"]]
    game["campaignEnding"] = state.get("ending")
    game["ending"] = {"complete": "completed", "retreat": "retreated",
                      "incomplete": "retreated"}.get(state.get("ending"))
    game["paused"] = state.get("status") == "paused"
    return game


class CampaignContent:
    def __init__(self, catalogue, publication):
        self.catalogue = catalogue
        self.publication = publication
        self.campaign = CampaignDefinition.load(safe_file(catalogue.root, publication.campaignFile))
        self.npc_scenes = {target_id: scene_id for scene_id, scene in self.campaign.scenes.items()
                           for target_id, target in scene.definition['targets'].items()
                           if 'talk' in target.get('actions', [])}
        self.critical_items = {key for key, item in self.campaign.definition.get('items', {}).items()
                               if any(use.get('target_id') != 'self' for use in item.get('uses', []))}
        self.profile = {"id": publication.id, "scenes": {
            scene_id: {"name": scene.title, "public": scene.definition["public_description"],
                       "region": scene.title, "background": scene_id, "keeper": ""}
            for scene_id, scene in self.campaign.scenes.items()
        }, "npcs": {key: {"name": self.campaign.scenes[scene].definition["targets"][key]["name"],
                          "sprite": key}
                    for key, scene in self.npc_scenes.items()}}

    def initialize(self, game_id, request_id, module_id, investigator_id):
        if investigator_id not in self.publication.playableInvestigatorIds:
            raise GameError("investigator_preview_only", "这位人物目前只供查看，请选择已开放的人物。", 409)
        _, raw = self.catalogue.character(module_id, investigator_id)
        detail = self.catalogue.investigator(module_id, investigator_id).model_dump()
        from trpg.rules import DEFAULT_SKILLS, skill_default, compute_derived
        attributes = raw['attributes']
        known = {name: value for name, value in raw['skills'].items() if type(value) is int}
        skills = {name: known.get(name, skill_default(name, attributes)) for name in set(DEFAULT_SKILLS) | set(known)}
        derived = compute_derived(attributes, age=raw.get('age') or 0, cthulhu_mythos=skills.get('克苏鲁神话', 0))
        values, authored = raw['initial_resources'], raw['authored_derived']
        character = Character(name=raw['name'], age=raw.get('age') or 0, occupation=raw['occupation'],
                              attributes=attributes, skills=skills, hp=values['hp'], hp_max=authored['hp_max'],
                              san=values['san'], san_max=authored.get('san_max', derived.san_max),
                              mp=values['mp'], mp_max=authored['mp_max'], luck=values['luck'],
                              mov=authored.get('mov', derived.mov), db=authored.get('db', derived.db),
                              build=authored.get('build', derived.build)).to_dict()
        state = self.campaign.initial_state(san=character["san"])
        for key, item in template_inventory(raw).items():
            state['inventory'].setdefault(key, item)
        game = {"schemaVersion": 1, "gameId": game_id, "version": 1,
                "creation": {"requestId": request_id, "moduleId": module_id,
                             "investigatorId": investigator_id},
                "module": {"id": module_id, "title": self.campaign.title, "englishTitle": None},
                "campaignState": state, "character": character,
                "initialCharacter": copy.deepcopy(character),
                "templateEquipmentIds": list(template_inventory(raw)),
                "investigator": detail, "initialInvestigator": copy.deepcopy(detail),
                "messages": [{"id": "opening", "kind": "keeper", "speaker": "守秘人",
                              "text": self.campaign.opening}],
                "turns": [], "pendingExit": False, "pendingAction": None,
                "groundItems": [], "npcItems": {}}
        return _sync(game, self.campaign)

    def validate(self, game):
        try:
            if game["creation"]["moduleId"] != self.publication.id or game['creation']['investigatorId'] not in self.publication.investigatorIds:
                raise ValueError("Unknown owned campaign")
            self.campaign.public_context(game["campaignState"])
            state = game["campaignState"]
            if (state.get("status") not in {"playing", "paused", "ended"}
                    or not isinstance(state.get("visited_scenes"), list)
                    or any(scene not in self.profile["scenes"] for scene in state["visited_scenes"])):
                raise ValueError("Malformed campaign progress")
            if not isinstance(state.get("inventory"), dict) or any(
                not isinstance(item, dict) or (item.get('quantity') is not None
                    and (type(item.get("quantity")) is not int or item["quantity"] < 0))
                for item in state["inventory"].values()
            ):
                raise ValueError("Malformed inventory")
            character = Character.from_dict(game["character"])
            for resource in ("hp", "mp"):
                value, ceiling = getattr(character, resource), getattr(character, resource + "_max")
                if type(value) is not int or type(ceiling) is not int or not 0 <= value <= ceiling:
                    raise ValueError("Resource out of range")
            if type(character.san) is not int or type(character.san_max) is not int or not 0 <= character.san <= character.san_max:
                raise ValueError("SAN out of range")
            if not isinstance(game["turns"], list) or not isinstance(game["messages"], list):
                raise ValueError("Malformed records")
            if type(game["version"]) is not int or game["version"] < 1:
                raise ValueError("Invalid version")
            from .game_tools.schema import ExecutionRequest
            for turn in game["turns"]:
                if not isinstance(turn["id"], str) or not isinstance(turn["rolls"], list) or type(turn["committed"]) is not bool:
                    raise ValueError("Malformed turn")
                if turn["plan"] is not None:
                    ExecutionRequest.model_validate(turn["plan"])
        except SceneValidationError as error:
            raise GameError("version_incompatible", str(error)) from None
        except (KeyError, TypeError, ValueError, AttributeError):
            raise GameError("save_invalid", "调查存档结构无效；原文件已保留。", 503) from None
        _sync(game, self.campaign)

    def for_game(self, game):
        return self

    def entities(self, game):
        context = self.campaign.planning_context(game["campaignState"])
        return {target["id"]: {"name": target["name"], "public": target["description"],
                                "aliases": target.get("aliases", [])}
                for target in context["targets"] if target["id"] not in {"room", "self", *self.npc_scenes}}

    def visible_npcs(self, game):
        state = game["campaignState"]
        if state.get("status") == "ended":
            return {}
        targets = {target["id"]: target for target in self.campaign.public_context(state)["targets"]}
        return {key: {"name": targets[key]["name"], "public": targets[key]["description"],
                      "role": targets[key].get('role', '在场人物'), "sprite": key,
                      "aliases": targets[key].get("aliases", [])}
                for key, scene in self.npc_scenes.items() if state["scene_id"] == scene and key in targets}

    def knowledge(self, game):
        known = {fact["id"]: fact["text"] for fact in game["facts"]}
        result = []
        for key, npc in self.visible_npcs(game).items():
            scene = self.campaign.scenes[self.npc_scenes[key]].definition
            revealed = scene["targets"][key].get("talk", {}).get("success", {}).get("reveal", [])
            result.append({"id": key, "name": npc["name"], "public": npc["public"],
                           "knowledge": [known[clue] for clue in revealed if clue in known]})
        return result

    def asset(self, game, asset_id):
        allowed = set(game["campaignState"]["visited_scenes"])
        allowed.update(key for key, scene in self.npc_scenes.items() if scene in allowed)
        if asset_id not in allowed or asset_id not in {*self.profile["scenes"], *self.npc_scenes}:
            raise GameError("asset_unavailable", "素材尚不可见。", 404)
        path = safe_file(self.catalogue.root, self.publication.campaignAssetDirectory + '/' + asset_id + '.svg')
        return path, "image/svg+xml"


class Content:
    """One keeper, any declared campaign and character; preview data stays inert."""
    def __init__(self, catalogue):
        self.catalogue, self.loaded = catalogue, {}

    def for_module(self, module_id):
        publication = self.catalogue.publication(module_id)
        if not publication.campaignFile:
            raise GameError('module_preview_only', '这个故事目前只供查看，暂未开放游玩。', 409)
        if module_id not in self.loaded:
            self.loaded[module_id] = CampaignContent(self.catalogue, publication)
        return self.loaded[module_id]

    def for_game(self, game):
        return self.for_module(game['creation']['moduleId'])

    def initialize(self, game_id, request_id, module_id, investigator_id):
        return self.for_module(module_id).initialize(game_id, request_id, module_id, investigator_id)

    def validate(self, game):
        return self.for_game(game).validate(game)

    def asset(self, game, asset_id):
        return self.for_game(game).asset(game, asset_id)


def scene_description(content, game):
    content = content.for_game(game)
    return content.campaign.public_context(game["campaignState"])["description"]


def public_pending(game):
    pending = game.get("pendingAction")
    return {"id": pending["id"], "prompt": pending["prompt"]} if pending else None


def tool_choices(content, game):
    content = content.for_game(game)
    state = game["campaignState"]
    if state["status"] != "playing":
        return []
    context = content.campaign.planning_context(state)
    targets = {target["id"]: target for target in context["targets"]}
    choices = []
    for suggestion in context["action_suggestions"]:
        intent, target = suggestion["intent"], suggestion["target_id"]
        if intent in {"finish", "leave"}:
            continue  # The owning Keeper supplies explicit ending actions.
        name = {"look": "observe", "investigate": "inspect", "careful_search": "inspect"}.get(intent, intent)
        option = intent if intent in {"investigate", "careful_search"} else None
        check = None
        if intent == "investigate":
            raw = content.campaign.scenes[state["scene_id"]].definition["targets"][target]
            check = raw.get("investigate", {}).get("check")
        row = {"tool": name, "target": target, "option": option,
               "label": suggestion["label"], "description": targets[target]["description"],
               "methods": {"skills": [check["skill"]], "aids": []} if check else None}
        if suggestion.get("item_id"):
            row["item"] = suggestion["item_id"]
        choices.append(row)
    for item in game["inventory"]:
        if item["id"] not in content.critical_items:
            choices.append({"tool": "drop", "target": item["id"], "option": None,
                            "label": "放下" + item["name"], "description": "留在当前地点，可回来拾取。", "methods": None})
            for npc_id, npc in content.visible_npcs(game).items():
                choices.append({"tool": "give", "target": npc_id, "option": None, "item": item["id"],
                                "label": "把" + item["name"] + "交给" + npc["name"],
                                "description": "明确交出这件非关键随身物品。", "methods": None})
    for entry in game.get("groundItems", []):
        if entry["sceneId"] == game["sceneId"]:
            choices.append({"tool": "take", "target": entry["item"]["id"], "option": None,
                            "label": "拿起" + entry["item"]["name"], "description": "拾回留在此处的物品。", "methods": None})
    return choices


class _RollJournal:
    """Use our CharacterTools retry protocol with a JSON-turn checkpoint."""
    def __init__(self, game_id, turn, persist):
        self.game_id, self.turn, self.persist = game_id, turn, persist

    def get_roll(self, game_id, request_id):
        if game_id != self.game_id:
            raise ValueError("Cross-game dice request")
        return copy.deepcopy(self.turn.setdefault("journal", {}).get(request_id))

    def record_roll(self, game_id, request_id, outcome):
        existing = self.get_roll(game_id, request_id)
        if existing is not None:
            if existing != outcome:
                raise ValueError("Dice checkpoint changed")
            return existing
        self.turn["journal"][request_id] = copy.deepcopy(outcome)
        self.persist()
        return copy.deepcopy(outcome)


def _check_card(raw, reason):
    details = []
    if raw.get("kind") == "sanity" and raw.get("loss", 0) > 0:
        details.append({"resource": "san", "dice": raw["loss_roll"]["expression"].upper(), "amount": raw["loss"]})
    return {"checkId": raw["request_id"], "skill": raw["skill"], "target": raw["skill_value"],
            "roll": raw["roll"], "success": raw["passed"],
            "result": DEGREES.get(raw.get("success_level"), "成功" if raw["passed"] else "失败"),
            "reason": reason, "details": details,
            "degree": raw.get("success_level"), "difficulty": raw.get("difficulty", "regular")}


def execute(content, game, turn, persist_roll, rng=None):
    content = content.for_game(game)
    current = copy.deepcopy(game)
    state = current["campaignState"]
    turn["response"], turn["executedTool"] = None, None
    turn["outcome"] = turn["plan"]["kind"]
    if turn["plan"]["kind"] != "tool":
        return current, []
    if state["status"] != "playing":
        turn["response"] = "本次调查已结束或暂停，不能再执行行动。"
        turn["outcome"] = "rejected"
        return current, [turn["response"]]
    call = copy.deepcopy(turn["plan"]["tool"])
    name, target = call["name"], call["target"]
    if name == "confirm_action":
        pending = current.get("pendingAction")
        if not pending or pending["id"] != target:
            turn["response"] = "这条确认已经失效，请重新选择行动。"
            turn["outcome"] = "rejected"
            return current, [turn["response"]]
        if call.get("option") == "cancel":
            current["pendingAction"], current["pendingExit"] = None, False
            turn["response"] = "已取消结束调查，继续当前进度。"
            turn["outcome"] = "cancelled"
            return current, [turn["response"]]
        if call.get("option") != "confirm":
            turn["response"] = "请明确选择确认或取消。"
            turn["outcome"] = "rejected"
            return current, [turn["response"]]
        call = {"name": "finish", "target": "investigation", "option": "confirm",
                "skill": None, "item": None, "approach": call.get("approach", "")}
        name, target = "finish", "investigation"
    if name == "finish":
        option = call.get("option") or "request"
        if option == "cancel":
            current["pendingExit"], current["pendingAction"] = False, None
            turn["response"] = "已取消结束调查，继续当前进度。"
            turn["outcome"] = "cancelled"
            return current, [turn["response"]]
        if option == "request":
            prompt = "要结束本次调查吗？会按你实际获得的信息结案，尚未完成的事情不会自动解决。"
            current["pendingExit"] = True
            current["pendingAction"] = {"id": turn["id"], "prompt": prompt}
            turn["response"], turn["outcome"] = prompt, "confirmation"
            return current, [prompt]
        if option != "confirm" or not current.get("pendingExit"):
            turn["response"] = "请先明确提出结束调查，再确认这次决定。"
            turn["outcome"] = "rejected"
            return current, [turn["response"]]
        action = {"action_type": "leave" if state["scene_id"] == content.campaign.definition["final_scene"] else "finish",
                  "target_id": "exit", "item_id": None}
    elif name in {"drop", "give", "take"}:
        item_id = target if name in {"drop", "take"} else call.get("item")
        entry = state["inventory"].get(item_id)
        if name == "take":
            ground = next((row for row in current.get("groundItems", [])
                           if row["sceneId"] == current["sceneId"] and row["item"]["id"] == item_id), None)
            if ground:
                state["inventory"][item_id] = copy.deepcopy(ground["sourceItem"])
                current["groundItems"].remove(ground)
                turn["outcome"] = "executed"
                current["pendingExit"], current["pendingAction"] = False, None
                return _sync(current, content.campaign), ["你拾回了" + ground["item"]["name"] + "。"]
        elif item_id in content.critical_items:
            turn["response"] = "这件物品关系到后续调查，当前先由你保管。你仍可查看它或按已查明的用途使用。"
        elif entry and (entry.get('quantity') is None or entry.get("quantity", 0) > 0):
            if name == "give" and target not in content.visible_npcs(current):
                turn["response"] = "这里没有你要交给的在场人物。"
            else:
                item = next(item for item in _inventory(state) if item["id"] == item_id)
                source_item = copy.deepcopy(entry)
                entry["quantity"] = 0
                if name == "drop":
                    current.setdefault("groundItems", []).append({"sceneId": current["sceneId"], "item": item, "sourceItem": source_item})
                    text = "你把" + item["name"] + "放在这里，仍可回来拾取。"
                else:
                    current.setdefault("npcItems", {}).setdefault(target, []).append(item)
                    text = "你把" + item["name"] + "交给了" + content.visible_npcs(current)[target]["name"] + "。"
                current["pendingExit"], current["pendingAction"] = False, None
                turn["outcome"] = "executed"
                return _sync(current, content.campaign), [text]
        turn["outcome"] = "rejected"
        turn["response"] = turn["response"] or "当前没有这件可以这样取放的随身物品。"
        return current, [turn["response"]]
    else:
        if name == "observe":
            action_type = "look"
            if target in {game["sceneId"], "room"}:
                target = "room"
        elif name == "inspect":
            action_type = "careful_search" if call.get("option") == "careful_search" else "investigate"
        else:
            action_type = {"interact": "investigate"}.get(name, name)
        if action_type == "move":
            destinations = content.campaign.public_context(state)["destinations"]
            target = next((row["target_id"] for row in destinations if row["scene_id"] == target), target)
            if (content.campaign._exit(target, state) or {}).get("ends_campaign"):
                action_type = "leave"
        action = {"action_type": action_type, "target_id": target, "item_id": call.get("item")}
    try:
        validated = content.campaign.validate_plan(action, state)
        expected = (validated.get("check") or {}).get("skill")
        if call.get("skill") is not None and call["skill"] != expected:
            raise SceneValidationError("这次检定的技能由实际调查对象确定，不能擅自替换。")
        journal = _RollJournal(game["gameId"], turn, persist_roll)
        tools = CharacterTools(journal, rng=rng)
        character = Character.from_dict(current["character"])
        raw_rolls, changes, notices = [], [], []
        passed = None
        if validated.get("check"):
            raw = tools.skill_check(game["gameId"], turn["id"], character, validated["check"])
            raw_rolls.append(raw)
            passed = raw["passed"]
        resolution = content.campaign.resolve_action(validated, state, passed)
        state = resolution["state"]
        effects, event = resolution["effects"], resolution["public_event"]
        if action["action_type"] == "use_item" and effects and all(
            effect.get("type") == "restore" and effect.get("resource") in {"hp", "mp"}
            and getattr(character, effect["resource"]) >= getattr(character, effect["resource"] + "_max")
            for effect in effects
        ):
            state = copy.deepcopy(game["campaignState"])
            effects = []
            event = {"text": "你的相应状态已经是满值，这次没有消耗物品。"}
        if effects:
            extra, changes, notices = tools.apply_effects(game["gameId"], turn["id"], character, state, effects)
            raw_rolls.extend(extra)
            if notices:
                state["status"] = "paused"
        current["campaignState"], current["character"] = state, character.to_dict()
        current["pendingExit"], current["pendingAction"] = False, None
        turn["rawRolls"] = copy.deepcopy(raw_rolls)
        turn["changes"] = copy.deepcopy(changes)
        turn["notices"] = notices
        turn["campaignEvent"] = copy.deepcopy(event)
        turn["rolls"] = [_check_card(raw, "本次" + raw.get("skill", "") + "检定")
                         for raw in raw_rolls if "roll" in raw]
        turn["damageRolls"] = []
        for raw in raw_rolls:
            if raw.get("kind") != "expression":
                continue
            change = next((row for row in changes if row["field"] == "hp" and row["after"] < row["before"]), None)
            if change:
                turn["damageRolls"].append({"key": raw["request_id"], "effectId": raw["request_id"],
                    "resource": "hp", "dice": raw["expression"].upper(), "amount": raw["total"],
                    "before": change["before"], "after": change["after"], "reason": change["reason"]})
        for card in turn["rolls"]:
            current["messages"].append({"id": card["checkId"], "kind": "check", "speaker": "规则检定",
                                        "text": card["reason"], "check": copy.deepcopy(card)})
        for card in turn["damageRolls"]:
            current["messages"].append({"id": card["effectId"], "kind": "effect", "speaker": "行动结果",
                                        "text": card["reason"], "effect": {k: v for k, v in card.items() if k != "key"}})
        turn["outcome"], turn["executedTool"] = "executed", copy.deepcopy(call)
        text = event["text"]
        if notices:
            turn["response"] = text + "\n" + "\n".join(notices)
        return _sync(current, content.campaign), [text, *notices]
    except SceneValidationError as error:
        turn["outcome"], turn["response"] = "rejected", str(error)
        return current, [str(error)]


def projection(content, game):
    content = content.for_game(game)
    state = game["campaignState"]
    context = content.campaign.planning_context(state)
    context["character"] = copy.deepcopy(game["character"])
    messages = game["messages"]
    guidance = build_guidance(context, {} if len(messages) > 1 else None)
    pending_turn = next((turn for turn in reversed(game["turns"]) if turn["stage"] != "completed"), None)
    pending_action = public_pending(game)
    suggestions = ["确认执行", "取消这次行动"] if pending_action else guidance["suggested_actions"]
    base = f"/api/games/{game['gameId']}/assets/"
    npcs = [{"id": key, "name": npc["name"], "role": npc["role"], "spriteUrl": base + key}
            for key, npc in content.visible_npcs(game).items()]
    ending_summary = next((message["text"] for message in reversed(messages) if message.get("final")), None)
    return {"gameId": game["gameId"], "version": game["version"], "module": game["module"],
            "investigator": copy.deepcopy(game["investigator"]),
            "scene": {"id": game["sceneId"], "name": content.profile["scenes"][game["sceneId"]]["name"],
                      "region": content.publication.location, "backgroundUrl": base + game["sceneId"]},
            "npc": npcs[-1] if npcs else None, "npcs": npcs,
            "inventory": copy.deepcopy(game["inventory"]), "facts": copy.deepcopy(game["facts"]),
            "messages": copy.deepcopy(messages), "suggestions": suggestions,
            "guidance": guidance["guidance"], "ended": bool(game["ending"]),
            "ending": game["ending"], "campaignEnding": state.get("ending"),
            "endingSummary": ending_summary, "status": "ended" if game["ending"] else "active",
            "paused": game.get("paused", False), "pendingAction": pending_action,
            "nearbyItems": [row["item"] for row in game.get("groundItems", []) if row["sceneId"] == game["sceneId"]],
            "pendingTurn": {"requestId": pending_turn["id"], "text": pending_turn["text"], "stage": pending_turn["stage"],
                            **({"confirmationId": pending_turn["confirmationId"]} if pending_turn.get("confirmationId") else {})} if pending_turn else None,
            "progress": content.campaign.public_context(state)}
