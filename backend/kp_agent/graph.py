"""One Keeper, explicit LangGraph steps, deterministic scene/tool execution."""

from __future__ import annotations

import copy
import hashlib
import threading
import warnings
from pathlib import Path
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from trpg import Character, load_character_from_xlsx

from .models import create_planner, model_request_context
from .embeddings import retrieval_from_env
from .scene import SceneDefinition, SceneValidationError
from .campaign import CampaignDefinition
from .schemas import ActionPlan
from .storage import Storage, StorageError, StaleGameError
from .tools import CharacterTools
from .guidance import build_guidance

ROOT = Path(__file__).resolve().parents[1]


def _asks_for_review(text: str) -> bool:
    """Only used after the scene has ended; it never opens secrets mid-game."""
    return text.strip().lower() == "/review" or any(word in text for word in (
        "复盘", "总结", "遗漏", "没找到", "没有找到", "没找全", "没拿到", "没有拿到",
        "什么信息", "哪些信息", "结局", "线索", "来信", "照片", "为什么", "发生了什么",
    ))


class TurnState(TypedDict, total=False):
    game_id: str
    message_id: str
    action_id: str
    text: str
    game: dict
    history: list[dict]
    draft: dict | None
    plan: dict
    evidence: list[dict]
    validated: dict
    public_facts: dict
    response: dict
    resume_action: bool
    trace: list[str]


def default_character() -> Character:
    paths = sorted((ROOT / "characters").glob("*.xlsx"))
    if len(paths) != 1:
        raise RuntimeError("当前演示要求 characters/ 中恰好一张固定角色卡。")
    # The upstream reader opens data_only; it does not rewrite the original file.
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message=".*extension is not supported.*", category=UserWarning)
        char = load_character_from_xlsx(str(paths[0]))
    if not char.name or char.hp_max <= 0 or char.san <= 0 or char.resolve("侦查") is None:
        raise RuntimeError("角色卡缺少必要的缓存数值，请先核对角色卡。")
    return char


def public_character(character: dict, scene_state: dict) -> dict:
    result = copy.deepcopy(character)
    result["conditions"] = list(scene_state.get("conditions", []))
    result["san_lost_today"] = scene_state.get("san_lost_today", 0)
    return result


class KeeperService:
    """Synchronous entry point for a future FastAPI/React wrapper.

    `handle_message` either returns a completed public reply or raises a typed
    error. It never returns hidden scene definitions or model reasoning.
    """

    def __init__(
        self, db_path: str | Path | None = None, scene_path: str | Path | None = None,
        *, campaign_path: str | Path | None = None,
        planner: Any = None, retrieval: Any = None, rng: Any = None,
    ):
        if scene_path is not None and campaign_path is not None:
            raise ValueError("scene_path 与 campaign_path 只能指定一个。")
        self.scene = (SceneDefinition.load(scene_path) if scene_path is not None
                      else CampaignDefinition.load(campaign_path or ROOT / "data" / "campaign.json"))
        if scene_path is not None and self.scene.definition.get("exits"):
            raise ValueError("这个地点需要完整故事的物品和出口逻辑，请使用 --campaign；旧书房单独调试用 data/scenes/study_legacy.json。")
        self.planner = planner if planner is not None else create_planner()
        database = db_path if db_path is not None else ROOT / "saves" / "keeper.sqlite3"
        cache_path = None if str(database) == ":memory:" else Path(database).parent / "rules_index.json"
        self.retrieval = retrieval if retrieval is not None else retrieval_from_env(cache_path=cache_path)
        # Invalid model/retrieval settings must not leave an open SQLite handle.
        self.storage = Storage(database)
        self.tools = CharacterTools(self.storage, rng=rng)
        self._lock = threading.Lock()
        self.graph = self._build_graph()

    @property
    def mode(self) -> str:
        return getattr(self.planner, "mode", "custom")

    def close(self) -> None:
        self.storage.close()

    def _planning_context(self, character: dict, scene_state: dict) -> dict:
        context = self.scene.planning_context(scene_state)
        context["character"] = public_character(character, scene_state)
        return context

    def _public_game(self, game: dict, *, opening: bool = False) -> dict:
        # Never silently interpret a v1 room save as a v2 campaign save.
        if isinstance(self.scene, CampaignDefinition):
            if game["scene_state"].get("campaign_id") != self.scene.campaign_id:
                raise StorageError("这个存档不属于当前故事版本，请使用新版独立存档，或明确重新开始。")
        last_event = None
        reply_type = "narration"
        messages = self.storage.list_messages(game["game_id"])
        if messages:
            last_event = {}  # An existing game is not a fresh room introduction.
            last_message = messages[-1]
            if last_message["status"] != "completed":
                reply_type = "takeover"
            elif last_message.get("reply"):
                reply_type = last_message["reply"].get("reply_type", "narration")
        guidance = build_guidance(
            self._planning_context(game["character"], game["scene_state"]), last_event, reply_type,
        )
        result = {
            "game_id": game["game_id"], "game_status": game["status"],
            "version": game["version"], "mode": self.mode,
            "character": public_character(game["character"], game["scene_state"]),
            "progress": self.scene.public_context(game["scene_state"]),
            **guidance,
        }
        if opening:
            result["opening"] = self.scene.opening
        return result

    def start(self) -> dict:
        existing = self.storage.get_game()
        if existing is not None:
            result = self._public_game(existing)
            status = existing["status"]
            messages = self.storage.list_messages(existing["game_id"])
            pending = messages[-1] if messages and messages[-1]["status"] != "completed" else None
            if pending is not None and status == "ended":
                message = "已读取上次存档：这一局已经结束，但最后一条回复尚未完成。输入 /retry 取回结束结果，或 /restart 开始新一局。"
            elif pending is not None and status == "paused":
                message = "已读取上次存档：这一局已暂停，最后一条回复尚未完成。输入 /retry 取回处理结果，之后由真人检查，或 /restart 重开。"
            elif status == "ended":
                message = "已读取上次存档：这一局已经结束。可以问我复盘或遗漏的信息，也可以输入 /review 查看复盘、/restart 开始新一局。"
            elif status == "paused":
                message = "已读取上次存档：这一局已暂停，需要真人检查后才能继续。可用 /status 查看状态，或 /restart 重开。"
            else:
                if pending is not None:
                    message = "已读取上次存档：还有一条消息未处理完。输入 /retry 恢复原消息，或 /restart 重开。"
                elif messages and (messages[-1].get("reply") or {}).get("reply_type") == "question":
                    message = "已读取上次存档，正在等待你的回答。\nKP：" + messages[-1]["reply"]["reply"]
                else:
                    message = "已读取上次存档，接着之前的进度继续。\n" + result["progress"]["description"]
            return {**result, "resumed": True, "opening": "", "startup_message": message,
                    "pending_message_id": pending["message_id"] if pending else None}
        character = default_character()
        game = self.storage.start_game(character.to_dict(), self.scene.initial_state(san=character.san))
        result = self._public_game(game, opening=True)
        return {**result, "resumed": False, "startup_message": result["opening"]}

    def restart(self) -> dict:
        if not self._lock.acquire(blocking=False):
            raise StorageError("当前消息尚未处理完，稍后再重新开始。")
        try:
            character = default_character()
            game = self.storage.restart_game(character.to_dict(), self.scene.initial_state(san=character.san))
            result = self._public_game(game, opening=True)
            return {**result, "resumed": False, "startup_message": result["opening"]}
        finally:
            self._lock.release()

    def get_game(self) -> dict:
        game = self.storage.get_game()
        return {"exists": False, "game_status": "not_started"} if game is None else {"exists": True, **self._public_game(game)}

    def get_character(self) -> dict:
        return self.get_game().get("character", {})

    def get_progress(self) -> dict:
        return self.get_game().get("progress", {})

    def get_inventory(self) -> dict | list:
        """Return only acquired items, without their private scene effects."""
        return copy.deepcopy(self.get_progress().get("inventory", {}))

    def get_clues(self) -> list[dict]:
        return copy.deepcopy(self.get_progress().get("revealed_clues", []))

    def get_rolls(self) -> list[dict]:
        """Read committed public rolls; never expose private action drafts."""
        result = []
        for row in self.storage.list_events():
            facts = row.get("event", {}).get("public_facts", {})
            for outcome in facts.get("rolls", []):
                result.append({**copy.deepcopy(outcome), "action_id": row["action_id"]})
        return result

    def list_messages(self) -> list[dict]:
        # Whitelist public fields: drafts may contain private tool parameters.
        return [{key: row.get(key) for key in ("message_id", "text", "status", "reply", "created_at")}
                for row in self.storage.list_messages()]

    def get_message(self, message_id: str) -> dict | None:
        game = self.storage.get_game()
        if game is None:
            return None
        row = self.storage.get_message(game["game_id"], message_id)
        if row is None:
            return None
        return {key: row.get(key) for key in ("message_id", "status", "reply")}

    def handle_message(self, message_id: str, text: str, game_id: str | None = None) -> dict:
        if not isinstance(text, str) or not text.strip() or len(text) > 4000:
            raise ValueError("请输入 1–4000 字的玩家消息。")
        if not isinstance(message_id, str) or not message_id or len(message_id) > 128:
            raise ValueError("消息编号长度必须为 1–128。")
        if not self._lock.acquire(blocking=False):
            raise StorageError("上一条消息仍在处理中，请稍后重试原消息。")
        active_id = None
        try:
            game = self.storage.get_game()
            if game is None:
                raise StorageError("请先开始游戏。")
            active_id = game["game_id"]
            if game_id is not None and game_id != active_id:
                raise StaleGameError("游戏已重新开始，请重新读取游戏编号。")
            row = self.storage.begin_message(active_id, message_id, text)
            if row["status"] == "completed":
                return row["reply"]
            action_id = hashlib.sha256(f"{active_id}:{message_id}".encode()).hexdigest()[:24]
            with model_request_context(game_id=active_id, message_id=message_id, action_id=action_id):
                result = self.graph.invoke({
                    "game_id": active_id, "message_id": message_id, "action_id": action_id,
                    "text": text, "trace": [],
                })
            saved = self.storage.save_reply(active_id, message_id, result["response"])
            return saved["reply"]
        except Exception:
            # Persist a recoverable failure without serializing credentials or
            # raw provider error messages into the player-facing history.
            if active_id and self.storage.get_message(active_id, message_id):
                self.storage.fail_message(active_id, message_id, "本次处理未完成，请用相同消息编号恢复或让开发者检查。")
            raise
        finally:
            self._lock.release()

    def _build_graph(self, state_schema=TurnState):
        # Web adapters reuse this exact owned workflow with another persistence
        # boundary; the original CLI keeps its existing TurnState unchanged.
        builder = StateGraph(state_schema)
        for name, fn in (
            ("load_context", self._load), ("plan_action", self._plan),
            ("retrieve_rules", self._retrieve), ("validate_action", self._validate),
            ("execute_tools", self._execute), ("commit_state", self._commit),
            ("narrate", self._narrate), ("closed_game", self._closed_game),
        ):
            builder.add_node(name, fn)
        builder.add_edge(START, "load_context")
        builder.add_conditional_edges("load_context", self._route_loaded)
        builder.add_edge("closed_game", END)
        builder.add_edge("plan_action", "retrieve_rules")
        builder.add_edge("retrieve_rules", "validate_action")
        builder.add_edge("validate_action", "execute_tools")
        builder.add_edge("execute_tools", "commit_state")
        builder.add_edge("commit_state", "narrate")
        builder.add_edge("narrate", END)
        # Durable game/message/dice state lives in Storage. This graph is
        # reconstructed per service and never claims to persist it separately.
        return builder.compile()

    @staticmethod
    def _route_loaded(state: TurnState) -> str:
        # An action may already have ended/paused the game before narration
        # failed. Recover that exact saved outcome before handling closed state.
        if state["resume_action"]:
            return "narrate"
        if state["game"]["status"] != "playing":
            return "closed_game"
        return "plan_action"

    def _closed_game(self, state: TurnState) -> dict:
        game = state["game"]
        review = None
        if game["status"] == "ended":
            if _asks_for_review(state["text"]):
                review = self.scene.review(game["scene_state"])
                reply = review["text"]
                reply_type = "review"
            else:
                reply = "本局已经结束。可以问我复盘或遗漏的信息，输入 /review 查看复盘、/restart 开始新一局，或用 /history 查看记录。"
                reply_type = "narration"
        else:
            reply = "本局已暂停，需要真人检查后才能继续。可用 /status 查看状态，或 /restart 重开。"
            reply_type = "takeover"
        response = {
            "game_id": state["game_id"], "message_id": state["message_id"], "action_id": None,
            "status": "completed", "reply_type": reply_type, "reply": reply,
            "rolls": [], "changes": [], "new_clues": [], "evidence": [],
            "character": public_character(game["character"], game["scene_state"]),
            "progress": self.scene.public_context(game["scene_state"]),
            "game_status": game["status"], "version": game["version"], "mode": self.mode,
            "suggested_actions": [], "guidance": "",
            "scene_transition": None, "new_items": [],
        }
        if review is not None:
            # Revealing a post-game explanation never awards in-game clues.
            response["review"] = review
        return {"response": response}

    def _load(self, state: TurnState) -> dict:
        game = self.storage.get_game(state["game_id"])
        messages = self.storage.list_messages(state["game_id"])
        history = []
        for row in messages:
            if row["status"] == "completed":
                history.append({"role": "user", "content": row["text"]})
                history.append({"role": "assistant", "content": row["reply"]["reply"]})
        row = self.storage.get_message(state["game_id"], state["message_id"])
        prior = self.storage.get_action(state["game_id"], state["action_id"])
        loaded = {"game": game, "history": history[-16:], "draft": row.get("draft"),
                  "resume_action": prior is not None, "trace": ["get_character", "get_scene_state"]}
        if prior is not None:
            loaded["public_facts"] = prior["event"]["public_facts"]
            loaded["game"] = prior["game"]
            loaded["plan"] = prior["event"]["plan"]
            loaded["evidence"] = prior["event"].get("evidence", [])
            loaded["trace"].append("resume_committed_action")
        return loaded

    def _plan(self, state: TurnState) -> dict:
        if state.get("draft") is not None:
            return {"plan": state["draft"]["plan"], "evidence": state["draft"].get("evidence", []),
                    "trace": state["trace"] + ["resume_saved_plan"]}
        context = self._planning_context(state["game"]["character"], state["game"]["scene_state"])
        context["scene"] = self.scene.public_context(state["game"]["scene_state"])
        context["character"] = public_character(state["game"]["character"], state["game"]["scene_state"])
        messages = self.storage.list_messages(state["game_id"])
        previous = [r for r in messages if r["status"] == "completed"]
        pending = None
        if previous and previous[-1]["reply"].get("reply_type") == "question":
            pending = previous[-1]["reply"]["reply"]
        plan = self.planner.plan(state["text"], context, state["history"], pending_question=pending)
        plan = ActionPlan.model_validate(plan).model_dump()
        return {"plan": plan, "trace": state["trace"] + ["plan_action"]}

    def _retrieve(self, state: TurnState) -> dict:
        plan = state["plan"]
        if state.get("draft") is not None:
            return {"evidence": state["draft"].get("evidence", [])}
        query = plan.get("query")
        # The actual skill is read from the validated authored action below.
        # A new scene's investigation is not necessarily a Spot Hidden check.
        if plan["intent"] == "rule_question" and not query:
            query = state["text"]
        evidence = self.retrieval.search(query) if query else []
        self.storage.save_message_draft(state["game_id"], state["message_id"], {"plan": plan, "evidence": evidence})
        return {"evidence": evidence, "trace": state["trace"] + (["search_rules"] if query else [])}

    def _validate(self, state: TurnState) -> dict:
        plan = state["plan"]
        if state["game"]["status"] != "playing":
            return {"validated": {"kind": "unsupported", "text": "本局已结束或暂停，请重新开始或让开发者处理。"}}
        if plan["intent"] == "clarify":
            return {"validated": {"kind": "question", "text": plan.get("question") or "你想检查哪个对象？"}}
        if plan["intent"] == "unsupported":
            return {"validated": {"kind": "takeover", "text": "这个行动超出当前故事支持范围，请换一种做法，或让真人接管。"}}
        if plan["intent"] == "rule_question":
            explanation = "当前资料没有找到足够依据，请让真人核对规则。"
            if state["evidence"]:
                explanation = "\n\n".join(
                    f"[{e['evidence_id']}] {e['title']}\n{e['text']}"
                    for e in state["evidence"]
                )
            topic = (plan.get("query") or "") + " " + state["text"]
            grade_source = next((item for item in state["evidence"]
                                 if item.get("title") == "技能检定与成功等级"), None)
            if grade_source and any(word in topic for word in ("常规成功", "困难成功", "极难成功", "成功等级")):
                character = Character.from_dict(state["game"]["character"])
                named = [name for name in character.skills if name in topic]
                skill = max(named, key=len) if named else "侦查"
                example = self.tools.success_example(character, skill)
                return {"validated": {"kind": "rule_explanation", "text": example["text"] + f" [{grade_source['evidence_id']}]",
                                      "rule_example": example},
                        "trace": state["trace"] + ["explain_success_levels"]}
            return {"validated": {"kind": "rule_explanation", "text": explanation}}
        try:
            validated = self.scene.validate_plan({
                "action_type": plan["intent"], "target_id": plan.get("target_id"),
                "item_id": plan.get("item_id"),
            }, state["game"]["scene_state"])
        except SceneValidationError as error:
            context = self._planning_context(state["game"]["character"], state["game"]["scene_state"])
            guidance = build_guidance(context).get("guidance", "")
            return {"validated": {"kind": "question", "text": f"{error}\n{guidance}".strip()}}
        return {"validated": {"kind": "action", **validated}, "trace": state["trace"] + ["validate_action"]}

    def _execute(self, state: TurnState) -> dict:
        validated = state["validated"]
        game = state["game"]
        character = Character.from_dict(game["character"])
        rolls, changes, notices, clues = [], [], [], []
        scene_state = copy.deepcopy(game["scene_state"])
        evidence = list(state["evidence"])
        trace = list(state["trace"])
        kind = validated["kind"]
        if kind == "action":
            check = validated.get("check")
            passed = None
            if check:
                rule_query = f"{check['skill']} 技能检定 成功等级"
                present = {item["evidence_id"] for item in evidence}
                evidence.extend(item for item in self.retrieval.search(rule_query)
                                if item["evidence_id"] not in present)
                trace.append("search_rules")
                outcome = self.tools.skill_check(state["game_id"], state["action_id"], character, check)
                rolls.append(outcome)
                passed = outcome["passed"]
                trace.append("skill_check")
            resolution = self.scene.resolve_action(validated, scene_state, passed)
            scene_state = resolution["state"]
            event = resolution["public_event"]
            clues = resolution["clues"]
            effects = resolution["effects"]
            if validated.get("action_type") == "use_item" and effects and all(
                effect.get("type") == "restore"
                and effect.get("resource") in {"hp", "mp"}
                and getattr(character, effect["resource"]) >= getattr(character, f"{effect['resource']}_max")
                for effect in effects
            ):
                # A healing item is not wasted when all affected resources are
                # already full. Reject the whole scene patch, including its
                # item consumption marker, before committing anything.
                scene_state = copy.deepcopy(game["scene_state"])
                event = {"text": "你的相应状态已经是满值，这次没有消耗物品。", "new_clues": [], "new_items": []}
                clues, effects = [], []
            if effects:
                extra, changes, notices = self.tools.apply_effects(state["game_id"], state["action_id"], character, scene_state, effects)
                rolls.extend(extra)
                effect_types = {effect.get("type") for effect in effects}
                trace.append("apply_scene_effects")
                effect_query = "理智检定 理智损失 临时疯狂" if "sanity" in effect_types else ""
                sanity_evidence = self.retrieval.search(effect_query) if effect_query else []
                existing = {e["evidence_id"] for e in evidence}
                evidence.extend(e for e in sanity_evidence if e["evidence_id"] not in existing)
                trace.append("search_rules")
                if notices:
                    scene_state["status"] = "paused"
            reply_type = "takeover" if notices else "narration"
        else:
            event = {"text": validated["text"], "new_clues": []}
            if validated.get("rule_example") is not None:
                event["rule_example"] = copy.deepcopy(validated["rule_example"])
            reply_type = kind if kind in {"question", "rule_explanation", "takeover"} else "narration"
            if kind == "takeover":
                # Unsupported actions stay playable; no silent arbitrary effects.
                event["requires_takeover"] = True
        public_facts = {
            "event": event, "rolls": rolls, "changes": changes, "new_clues": clues,
            "notices": notices, "reply_type": reply_type,
            "character": public_character(character.to_dict(), scene_state),
            "progress": self.scene.public_context(scene_state),
            "evidence": evidence, "game_status": scene_state["status"],
            **build_guidance(self._planning_context(character.to_dict(), scene_state), event, reply_type),
        }
        return {"public_facts": public_facts,
                "game": {**game, "character": character.to_dict(), "scene_state": scene_state},
                "trace": trace, "evidence": evidence}

    def _commit(self, state: TurnState) -> dict:
        facts = state["public_facts"]
        game = self.storage.commit_action(
            state["game_id"], state["message_id"], state["action_id"], state["game"]["version"],
            state["game"]["character"], state["game"]["scene_state"],
            {"plan": state["plan"], "evidence": state["evidence"], "public_facts": facts, "trace": state["trace"]},
            roll_ids=[r["request_id"] for r in facts["rolls"]],
        )
        return {"game": game, "trace": state["trace"] + ["commit_action"]}

    def _narrate(self, state: TurnState) -> dict:
        facts = state["public_facts"]
        # A clarification is a question, not an invitation to generate outcomes.
        if facts["reply_type"] in {"question", "takeover"} or facts["event"].get("rule_example") is not None:
            reply = facts["event"]["text"]
            if facts.get("notices"):
                reply += "\n" + "\n".join(facts["notices"])
        else:
            reply = self.planner.narrate(state["text"], copy.deepcopy(facts), state["history"])
        if not isinstance(reply, str) or not reply.strip():
            raise ValueError("模型未返回可显示的叙述，请恢复本次消息。")
        return {"response": {
            "game_id": state["game_id"], "message_id": state["message_id"], "action_id": state["action_id"],
            "status": "completed", "reply_type": facts["reply_type"], "reply": reply,
            "rolls": facts["rolls"], "changes": facts["changes"],
            "character": facts["character"], "new_clues": facts["new_clues"],
            "evidence": facts["evidence"], "progress": facts["progress"],
            "game_status": facts["game_status"], "version": state["game"]["version"], "mode": self.mode,
            "suggested_actions": facts.get("suggested_actions", []),
            "guidance": facts.get("guidance", ""),
            "scene_transition": facts["event"].get("scene_transition"),
            "new_items": facts["event"].get("new_items", []),
        }}
