"""Web transport for the existing Keeper workflow and grounded rule retrieval.

The graph is inherited from our KeeperService. Scene content, dice, inventory
and JSON persistence are tools; none of them chooses or narrates an action.
"""
from __future__ import annotations

import asyncio
import copy
import os
import threading
import uuid
from collections import defaultdict
from functools import partial
from pathlib import Path

from trpg import Character
from .graph import KeeperService, TurnState
from .models import create_planner, model_request_context, ModelCallError, ModelConfigurationError, _asks_current_resource
from .retrieval import RetrievalService
from .schemas import WebActionPlan
from .tools import CharacterTools
from .game_tools import JsonStore, GameError, ExecutionRequest
from .owned_tools import Content, execute, projection, scene_description, tool_choices, public_pending


class WebTurnState(TurnState, total=False):
    turn: dict
    next_game: dict
    direct_reply: str | None


class ReplyStream:
    """A subscription may disconnect without cancelling the saved action."""
    def __init__(self, request_id: str):
        self.request_id = request_id
        self.events: list[dict] = []
        self.changed = asyncio.Event()
        self.task: asyncio.Task | None = None
        self.done = False
        self.loop = asyncio.get_running_loop()

    def emit(self, event_type: str, **fields):
        try:
            on_loop = asyncio.get_running_loop() is self.loop
        except RuntimeError:
            on_loop = False
        if not on_loop:
            self.loop.call_soon_threadsafe(partial(self.emit, event_type, **fields))
            return
        self.events.append({"type": event_type, "turnId": self.request_id,
                            "seq": len(self.events) + 1, **fields})
        self.changed.set()

    async def stream(self):
        cursor = 0
        while True:
            self.changed.clear()
            while cursor < len(self.events):
                yield self.events[cursor]
                cursor += 1
            if self.done:
                return
            try:
                await asyncio.wait_for(self.changed.wait(), 15)
            except TimeoutError:
                yield None


def character_snapshot(game: dict) -> dict:
    detail = game["investigator"]
    resource = detail["resources"]
    return {
        "name": detail["displayName"], "age": detail.get("age") or 0,
        "occupation": detail.get("occupation", ""),
        "attributes": copy.deepcopy(detail["attributes"]),
        "skills": {entry["name"]: entry["value"] for entry in detail["skills"]
                   if type(entry.get("value")) is int},
        "hp": resource["hp"], "hp_max": resource["hpMax"],
        "san": resource["san"], "san_max": resource.get("sanMax", 99),
        "mp": resource["mp"], "mp_max": resource["mpMax"],
        "luck": resource["luck"],
    }


class WebKeeperService(KeeperService):
    """Use our seven-step LangGraph with the webpage's public DTOs and saves."""
    def __init__(self, catalogue, root: str | Path, *, planner=None, retrieval=None):
        self.content = Content(catalogue)
        self.store = JsonStore(Path(root))
        self.planner = planner
        self.retrieval = retrieval or RetrievalService(cache_path=Path(root) / "rules_index.json")
        self.locks = defaultdict(asyncio.Lock)
        self.jobs: dict[tuple[str, str], ReplyStream] = {}
        self.graph = self._build_graph(WebTurnState)

    def _get_planner(self):
        if self.planner is None:
            # Creating or reading a game must not require an API account.
            from .config import load_local_env
            load_local_env()
            self.planner = create_planner(os.getenv("KP_WEB_MODEL_MODE", "deepseek"))
        return self.planner

    def read(self, game_id: str) -> dict:
        game = self.store.load(game_id)
        if game.get("keeperWorkflow") != "agent-rag-v3":
            raise GameError("version_incompatible", "这份存档不属于当前副本，请保留原存档并在本版新开调查。")
        self.content.validate(game)
        return game

    def get(self, game_id: str) -> dict:
        return projection(self.content, self.read(game_id))

    def review(self, game_id: str) -> dict:
        game = self.read(game_id)
        if not game["ending"]:
            raise GameError("review_unavailable", "本局结束后才能查看复盘；现在不会显示尚未发现的信息。")
        return self.content.campaign.review(game["campaignState"])

    def create(self, request_id: str, module_id: str, investigator_id: str) -> dict:
        game_id = uuid.uuid5(uuid.NAMESPACE_URL, "owned-keeper:" + request_id).hex
        with self.store.mutex:
            if self.store.path(game_id).exists():
                game = self.read(game_id)
                if game["creation"] != {"requestId": request_id, "moduleId": module_id,
                                         "investigatorId": investigator_id}:
                    raise GameError("request_conflict", "这条创建请求已用于另一名角色或案件。")
            else:
                game = self.content.initialize(game_id, request_id, module_id, investigator_id)
                game["keeperWorkflow"] = "agent-rag-v3"
                self.store.save(game)
        return projection(self.content, game)

    @staticmethod
    def _checkpoint(store, game: dict, turn: dict):
        game["turns"] = [turn if row["id"] == turn["id"] else row for row in game["turns"]]
        store.save(game)

    async def action(self, game_id, request_id, text, expected_version, confirmation_id=None):
        async with self.locks[game_id]:
            game = self.read(game_id)
            turn = next((row for row in game["turns"] if row["id"] == request_id), None)
            if turn is not None:
                if turn["text"] != text or turn.get("confirmationId") != confirmation_id:
                    raise GameError("request_conflict", "恢复原回合时，请保留原来的请求编号和内容。")
                existing = self.jobs.get((game_id, request_id))
                if existing and not existing.done:
                    return existing
                if turn["stage"] == "completed":
                    job = ReplyStream(request_id)
                    job.emit("state.updated", state=projection(self.content, game))
                    job.emit("turn.completed", state=projection(self.content, game))
                    job.done = True
                    return job
            else:
                if game["ending"]:
                    raise GameError("game_ended", "本次调查已结束，可以回看记录或开始新的调查。")
                if game.get("paused"):
                    raise GameError("game_paused", "本次调查已暂停，需要真人检查；当前记录和状态已保存。")
                if any(row["stage"] != "completed" for row in game["turns"]):
                    raise GameError("turn_pending", "上一回合还没完成，请先恢复原回合。")
                if expected_version != game["version"]:
                    raise GameError("version_conflict", "调查状态已更新，请重新读取后再行动。")
                pending = public_pending(game)
                if confirmation_id and (not pending or pending["id"] != confirmation_id):
                    raise GameError("confirmation_expired", "这条确认已经失效，请重新读取当前调查。")
                if confirmation_id and text not in ("确认执行", "取消这次行动"):
                    raise GameError("confirmation_invalid", "请选择继续或取消，也可以重新描述自己的行动。")
                turn = {"id": request_id, "text": text, "stage": "accepted", "plan": None,
                        "agentPlan": None, "rolls": [], "damageRolls": [], "committed": False,
                        "results": [], "metrics": [], "evidence": [], "retrieved": False,
                        "confirmationId": confirmation_id, "messageId": request_id + ":keeper"}
                game["turns"].append(turn)
                game["messages"].append({"id": request_id + ":player", "kind": "player",
                                         "speaker": game["investigator"]["displayName"], "text": text})
                self.store.save(game)
            job = ReplyStream(request_id)
            self.jobs[(game_id, request_id)] = job
            job.task = asyncio.create_task(self._run_turn(game_id, request_id, job))
            return job

    def _job(self, state):
        return self.jobs[(state["game_id"], state["message_id"])]

    def _public_context(self, game: dict) -> dict:
        content = self.content.for_game(game)
        choices = tool_choices(content, game)
        ending_choices = [{"tool": "finish", "target": "investigation", "option": "request",
                           "label": "明确结束本次调查", "description": "按当前已获信息结案。", "methods": None}]
        if game["pendingExit"]:
            ending_choices.extend({"tool": "finish", "target": "investigation", "option": option,
                                   "label": label, "description": label, "methods": None}
                                  for option, label in (("confirm", "确认结束调查"), ("cancel", "继续调查")))
        existing = {(choice["tool"], choice["target"], choice.get("option")) for choice in choices}
        choices.extend(choice for choice in ending_choices
                       if (choice["tool"], choice["target"], choice.get("option")) not in existing)
        scene = content.profile["scenes"][game["sceneId"]]
        targets: dict[str, dict] = {}

        def add(identifier, name, description, actions=(), aliases=()):
            row = targets.setdefault(identifier, {"id": identifier, "name": name,
                "description": description, "aliases": list(aliases), "actions": []})
            if name and (row["name"] == identifier or identifier in {"self", "investigation"}):
                row["name"] = name
            row["aliases"] = list(dict.fromkeys([*row["aliases"], *aliases]))
            row["actions"] = list(dict.fromkeys([*row["actions"], *actions]))

        add(game["sceneId"], scene["name"], scene_description(content, game),
            ["observe"], ["周围", "四周", "环境", "这里", "房间"])
        for identifier, entity in content.entities(game).items():
            if identifier.startswith(("clue_", "item_")):
                continue  # Acquired records are projected once below.
            add(identifier, entity["name"], entity["public"], ["observe"], entity.get("aliases", []))
        for identifier, npc in content.visible_npcs(game).items():
            add(identifier, npc["name"], npc["public"], ["observe", "talk"], npc.get("aliases", []))
        for choice in choices:
            target = choice["target"]
            destination = content.profile["scenes"].get(target)
            add(target, destination["name"] if destination else targets.get(target, {}).get("name", target),
                choice.get("description", ""), [choice["tool"]])
        for entry in game["inventory"]:
            add(entry["id"], entry["name"], entry.get("note", ""), ["observe", "drop"], entry.get("aliases", []))
        for entry in projection(self.content, game).get("nearbyItems", []):
            add(entry["id"], entry["name"], entry.get("note", ""), ["observe", "take"])
        for fact in game["facts"]:
            add(fact["id"], fact["title"], fact["text"], ["observe"], fact.get("aliases", []))
        add("self", "自己", "可以查看当前角色状态。", ["observe"], ["自己", "自身状态"])
        add("investigation", "本次调查", "明确结束会依当前调查结果结案。", ["finish"], ["结束调查", "结案", "撤离"])
        return {"status": "playing", "targets": list(targets.values()),
                "available_tools": choices, "inventory": copy.deepcopy(game["inventory"]),
                "character": character_snapshot(game), "facts": copy.deepcopy(game["facts"]),
                "scene": {"id": game["sceneId"], "title": scene["name"],
                          "description": scene_description(content, game)},
                "pending_action": public_pending(game), "pending_exit": game["pendingExit"],
                "nearby_items": projection(self.content, game)["nearbyItems"],
                "npc_knowledge": content.knowledge(game)}

    def _load(self, state):
        game = self.read(state["game_id"])
        turn = next(row for row in game["turns"] if row["id"] == state["message_id"])
        history = [{"role": "user" if m["kind"] == "player" else "assistant", "content": m["text"]}
                   for m in game["messages"] if m["kind"] in ("keeper", "npc", "player")
                   and m["id"] != state["message_id"] + ":player"][-16:]
        return {"game": game, "turn": turn, "text": turn["text"], "history": history,
                "resume_action": turn["committed"], "plan": turn.get("agentPlan") or {},
                "evidence": turn.get("evidence", []),
                "public_facts": turn.get("publicFacts", {}),
                "trace": ["load_context"]}

    @staticmethod
    def _route_loaded(state):
        return "narrate" if state["resume_action"] else "plan_action"

    async def _plan(self, state):
        turn = state["turn"]
        self._job(state).emit("turn.status", stage="understanding")
        if turn.get("agentPlan") is not None:
            plan = WebActionPlan.model_validate(turn["agentPlan"])
        elif turn.get("confirmationId"):
            plan = WebActionPlan(intent="confirm_action", target_id=turn["confirmationId"],
                                 option_id="confirm" if turn["text"] == "确认执行" else "cancel",
                                 approach=turn["text"])
        else:
            plan = await asyncio.to_thread(self._get_planner().plan_web,
                                          state["text"], self._public_context(state["game"]), state["history"])
            plan = WebActionPlan.model_validate(plan)
        turn["agentPlan"] = plan.model_dump()
        turn["stage"] = "planned"
        self._checkpoint(self.store, state["game"], turn)
        return {"plan": plan.model_dump(), "trace": state["trace"] + ["plan_action"]}

    def _retrieve(self, state):
        turn, plan = state["turn"], state["plan"]
        if not turn.get("retrieved"):
            query = plan.get("query") or (state["text"] if plan["intent"] == "rule_question" else None)
            turn["evidence"] = self.retrieval.search(query) if query else []
            turn["retrieved"] = True
            self._checkpoint(self.store, state["game"], turn)
        return {"evidence": turn["evidence"], "trace": state["trace"] + ["retrieve_rules"]}

    def _validate(self, state):
        plan, game = state["plan"], state["game"]
        intent = plan["intent"]
        target = plan.get("target_id")
        direct = None
        if intent in {"rule_question", "question", "clarify", "unsupported"}:
            request = {"kind": "question" if intent in {"rule_question", "question"} else intent, "tool": None}
            if intent == "clarify":
                direct = plan.get("question") or "你想怎样行动？可以再说清楚一点。"
            elif intent == "unsupported":
                direct = "这个行动的后果还无法可靠裁定。你可以说说具体想怎么做，或换一种方法。"
            elif intent == "rule_question" and not state["evidence"]:
                direct = "当前规则资料没有找到足够依据，我不能据此确定规则。可以换个问法，或请真人核对。"
            elif intent == "question" and _asks_current_resource(state["text"]):
                char = character_snapshot(game)
                direct = f"你当前的 HP 是 {char['hp']}/{char['hp_max']}，SAN 是 {char['san']}，MP 是 {char['mp']}/{char['mp_max']}。这些数值来自当前保存的角色状态。"
        else:
            names = {"look": "observe", "investigate": "inspect", "careful_search": "inspect", "leave": "move"}
            name = names.get(intent, intent)
            target = game["sceneId"] if target in {None, "room"} and name == "observe" else target
            readable = next((item for item in game["inventory"] if item["id"] == target), None)
            fact = next((item for item in game["facts"] if item["id"] == target), None)
            if name == "observe" and (readable or fact or target == "self"):
                request = {"kind": "question", "tool": None}
                if target == "self":
                    char = character_snapshot(game)
                    direct = f"你当前的 HP 是 {char['hp']}/{char['hp_max']}，SAN 是 {char['san']}，MP 是 {char['mp']}/{char['mp_max']}。"
                elif fact:
                    direct = fact["title"] + "：" + fact["text"]
                else:
                    quantity = readable.get("quantity")
                    direct = readable["name"] + (f"，数量 {quantity}" if quantity is not None else "，数量未标明") + "。" + readable.get("note", "")
            else:
                request = {"kind": "tool", "tool": {"name": name, "target": target,
                    "option": plan.get("option_id"), "skill": plan.get("skill"),
                    "item": plan.get("item_id"), "approach": plan.get("approach") or state["text"]}}
                if name == "finish":
                    request["tool"]["target"] = "investigation"
                    request["tool"]["option"] = plan.get("option_id") or "request"
                request = ExecutionRequest.model_validate(request).model_dump()
        turn = state["turn"]
        turn["plan"] = request
        turn["directReply"] = direct
        turn["stage"] = "validated"
        evidence = list(state["evidence"])
        skill = (request.get("tool") or {}).get("skill")
        if skill:
            seen = {row["evidence_id"] for row in evidence}
            evidence.extend(row for row in self.retrieval.search(f"{skill} 技能检定 成功等级") if row["evidence_id"] not in seen)
        turn["evidence"] = evidence
        # Numeric rule examples are generated by the same owned rule tool as CLI.
        if intent == "rule_question" and any(word in state["text"] + " " + (plan.get("query") or "")
                                            for word in ("困难成功", "极难成功", "常规成功", "成功等级")):
            source = next((row for row in evidence if row["title"] == "技能检定与成功等级"), None)
            if source:
                char = Character.from_dict(character_snapshot(game))
                named = [skill for skill in char.skills if skill in state["text"]]
                example = CharacterTools.success_example(char, max(named, key=len) if named else "侦查")
                turn["directReply"] = example["text"] + f" [{source['evidence_id']}]"
        self._checkpoint(self.store, game, turn)
        return {"validated": request, "evidence": evidence, "trace": state["trace"] + ["validate_action"]}

    def _execute(self, state):
        self._job(state).emit("turn.status", stage="resolving")
        game, turn = state["game"], state["turn"]
        updated, results = execute(self.content, game, turn,
                                   lambda: self._checkpoint(self.store, game, turn))
        turn["results"] = results
        turn["stage"] = "executed"
        evidence = list(state["evidence"])
        for roll in turn["rolls"]:
            query = "理智检定 理智损失" if roll["skill"] == "SAN" else f"{roll['skill']} 技能检定"
            known = {row["evidence_id"] for row in evidence}
            evidence.extend(row for row in self.retrieval.search(query) if row["evidence_id"] not in known)
        char = character_snapshot(updated)
        before = character_snapshot(game)
        changes = [{"field": key, "before": before[key], "after": char[key], "reason": "本次工具实际结果"}
                   for key in ("hp", "san", "mp") if before[key] != char[key]]
        content = self.content.for_game(updated)
        direct = turn.get("response") or turn.get("directReply")
        reply_type = "rule_explanation" if state["plan"]["intent"] == "rule_question" else "question" if state["plan"]["intent"] == "clarify" else "narration"
        public = projection(self.content, updated)
        facts = {"event": {"text": direct or "\n".join(results) or "请依据当前公开信息回答玩家。"},
                 "rolls": copy.deepcopy(turn["rolls"]), "changes": changes,
                 "character": char, "progress": {"scene_id": updated["sceneId"],
                     "title": content.profile["scenes"][updated["sceneId"]]["name"],
                     "description": scene_description(content, updated), "ending": updated["ending"],
                     "revealed_clues": copy.deepcopy(updated["facts"]), "inventory": copy.deepcopy(updated["inventory"])},
                 "evidence": evidence, "reply_type": reply_type, "outcome": turn.get("outcome"),
                 "npc_knowledge": content.knowledge(updated),
                 "visible_entities": [row["public"] for row in content.entities(updated).values()],
                 "guidance": "", "suggested_actions": public["suggestions"],
                 "game_status": "ended" if updated["ending"] else "playing"}
        turn["publicFacts"] = facts
        turn["evidence"] = evidence
        turn["directReply"] = direct
        return {"next_game": updated, "public_facts": facts, "evidence": evidence,
                "trace": state["trace"] + ["execute_tools"]}

    def _commit(self, state):
        game, turn = state["next_game"], state["turn"]
        game["version"] += 1
        turn["committed"] = True
        turn["stage"] = "committed"
        turn["trace"] = state["trace"] + ["commit_state"]
        self._checkpoint(self.store, game, turn)
        job = self._job(state)
        for result in turn["rolls"]:
            job.emit("check.started", check={key: result[key] for key in ("checkId", "skill", "target", "reason")})
            job.emit("check.resolved", check=result)
        for result in turn.get("damageRolls", []):
            job.emit("effect.resolved", effect={key: value for key, value in result.items() if key != "key"})
        job.emit("state.updated", state=projection(self.content, game))
        return {"game": game, "trace": turn["trace"]}

    async def _narrate(self, state):
        job, turn, game = self._job(state), state["turn"], state["game"]
        if state.get("resume_action"):
            # Restore durable UI results as well as text. Stable checkId and
            # effectId let clients avoid replaying already displayed results.
            for result in turn["rolls"]:
                job.emit("check.started", check={key: result[key] for key in ("checkId", "skill", "target", "reason")})
                job.emit("check.resolved", check=result)
            for result in turn.get("damageRolls", []):
                job.emit("effect.resolved", effect={key: value for key, value in result.items() if key != "key"})
            job.emit("state.updated", state=projection(self.content, game))
        evidence = state["public_facts"].get("evidence", [])
        turn["stage"] = "narrating"
        self._checkpoint(self.store, game, turn)
        job.emit("turn.status", stage="narrating")
        job.emit("message.started", message={"id": turn["messageId"], "kind": "keeper",
                                             "speaker": "守秘人", "text": "", "evidence": evidence})
        text = turn.get("directReply")
        if text:
            job.emit("message.delta", messageId=turn["messageId"], delta=text)
        else:
            queue: asyncio.Queue = asyncio.Queue()
            loop = asyncio.get_running_loop()
            stopped = threading.Event()

            def produce():
                iterator = None
                try:
                    iterator = self._get_planner().stream_web_narration(
                        state["text"], copy.deepcopy(state["public_facts"]), state["history"])
                    for chunk in iterator:
                        if stopped.is_set():
                            break
                        loop.call_soon_threadsafe(queue.put_nowait, ("text", chunk))
                except Exception as error:
                    loop.call_soon_threadsafe(queue.put_nowait, ("error", error))
                finally:
                    try:
                        if iterator is not None and hasattr(iterator, "close"):
                            iterator.close()
                    finally:
                        loop.call_soon_threadsafe(queue.put_nowait, ("done", None))

            worker = asyncio.create_task(asyncio.to_thread(produce))
            chunks = []
            try:
                while True:
                    kind, value = await queue.get()
                    if kind == "done":
                        break
                    if kind == "error":
                        raise value
                    if value:
                        chunks.append(value)
                        job.emit("message.delta", messageId=turn["messageId"], delta=value)
                await worker
            finally:
                stopped.set()
            text = "".join(chunks).strip()
        if not isinstance(text, str) or not text.strip():
            raise GameError("empty_reply", "这一回合还没有生成完整回复，请恢复原回合。", 503)
        message = {"id": turn["messageId"], "kind": "keeper", "speaker": "守秘人",
                   "text": text, "evidence": evidence, "final": bool(game["ending"])}
        game["messages"].append(message)
        turn["stage"] = "completed"
        self._checkpoint(self.store, game, turn)
        job.emit("message.completed", message=message)
        job.emit("turn.completed", state=projection(self.content, game))
        return {"trace": state["trace"] + ["narrate"]}

    async def _run_turn(self, game_id, request_id, job):
        job.emit("turn.started")
        try:
            with model_request_context(game_id=game_id, message_id=request_id, action_id=request_id):
                async with asyncio.timeout(180):
                    await self.graph.ainvoke({"game_id": game_id, "message_id": request_id,
                                             "action_id": request_id, "trace": []})
        except (Exception, asyncio.CancelledError) as error:
            code = error.code if isinstance(error, (GameError, ModelCallError)) else "turn_interrupted"
            message = str(error).replace("/retry", "页面上的“恢复本轮”") if isinstance(error, (GameError, ModelCallError)) else "回应未完成，请恢复原回合；已结算的结果会保留。"
            if isinstance(error, ModelConfigurationError):
                code, message = "model_unconfigured", str(error)
            try:
                game = self.read(game_id)
                turn = next(row for row in game["turns"] if row["id"] == request_id)
                turn["errorPhase"], turn["stage"] = turn["stage"], "failed"
                turn["errorCode"] = code
                self._checkpoint(self.store, game, turn)
            except Exception:
                pass
            job.emit("turn.failed", code=code, message=message)
        finally:
            job.done = True
            job.changed.set()
            self.jobs.pop((game_id, request_id), None)

    async def close(self):
        tasks = [job.task for job in self.jobs.values() if job.task and not job.task.done()]
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        client = getattr(self.planner, "client", None)
        if client is not None:
            await asyncio.to_thread(client.close)
        self.store.close()
