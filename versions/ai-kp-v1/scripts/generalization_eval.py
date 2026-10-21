#!/usr/bin/env python3
"""Evaluate final planner actions on unseen free-form Chinese inputs.

Default demo mode is offline. --mode deepseek explicitly opts in to paid plan
calls, once per case without retries or narration. Fixture progress is manually
constructed from authored scene success/failure outcomes; it is not a simulated
random game and does not execute character/dice tools or touch player saves.
Only case inputs, final plans, expected labels and selected call metadata are
written. Private story definitions and complete model prompts are never saved.
"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import sys
from typing import Any
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from kp_agent.campaign import CampaignDefinition
from kp_agent.graph import default_character
from kp_agent.models import ModelCallError, create_planner, model_request_context
from kp_agent.schemas import ActionPlan
from kp_agent.scene import SceneValidationError

_MUTATING_INTENTS = {"investigate", "careful_search", "talk", "move", "use_item", "finish", "leave"}
_SCENE_INTENTS = _MUTATING_INTENTS | {"look"}
_ENVIRONMENT_ERRORS = {
    "provider_authentication", "provider_balance", "provider_rate_limit",
    "provider_connection", "provider_timeout", "provider_permission",
    "provider_not_found", "provider_request_failed",
}
_TOKEN_FIELDS = ("input_tokens", "output_tokens", "total_tokens", "cached_input_tokens", "reasoning_tokens")


def build_fixtures(campaign: CampaignDefinition, character: dict) -> dict[str, dict]:
    """Build known progress from fixed outcomes, never random values or tools."""
    start = campaign.initial_state(san=character["san"])

    def step(state: dict, intent: str, target: str, *, passed: bool | None = None,
             item: str | None = None) -> dict:
        proposed = {"action_type": intent, "target_id": target, "item_id": item}
        validated = campaign.validate_plan(proposed, state)
        return campaign.resolve_action(validated, state, passed)["state"]

    failed = step(copy.deepcopy(start), "investigate", "desk", passed=False)
    study_ready = step(copy.deepcopy(start), "investigate", "desk", passed=True)
    study_ready = step(study_ready, "talk", "butler")
    station = step(copy.deepcopy(study_ready), "move", "exit")
    station_located = step(copy.deepcopy(station), "investigate", "locker", passed=True)
    station_ready = step(copy.deepcopy(station_located), "use_item", "locker", item="locker_key")
    station_ready = step(station_ready, "use_item", "archive_gate", item="archive_key")
    archive = step(copy.deepcopy(station_ready), "move", "exit")
    archive_complete = step(copy.deepcopy(archive), "investigate", "ledger", passed=True)
    archive_complete = step(archive_complete, "talk", "scholar")
    archive_complete = step(archive_complete, "use_item", "seal_console", item="seal_token")
    return {
        "study_start": start, "study_failed": failed, "study_ready": study_ready,
        "station_start": station, "station_located": station_located,
        "station_two_routes": station_ready, "archive_start": archive,
        "archive_complete": archive_complete,
    }


def cases() -> list[dict]:
    """Expected labels are declared before any model call; no adaptive retries."""
    def case(case_id: str, fixture: str, text: str, intents: set[str], *,
             target: str | None = None, item: str | None = None,
             target_by_intent: dict[str, str] | None = None,
             read_only: bool = False, history: list[dict] | None = None,
             pending_question: str | None = None) -> dict:
        return {"id": case_id, "fixture": fixture, "input": text,
                "expected_intents": sorted(intents), "expected_target": target,
                "expected_item": item, "target_by_intent": target_by_intent or {},
                "must_not_execute": read_only, "history": history or [],
                "pending_question": pending_question}

    return [
        case("g01", "study_start", "我先打量一下这屋里都摆了些什么", {"look"}, target="room"),
        case("g02", "study_start", "不急着翻东西，我想听听周先生怎么说", {"talk"}, target="butler"),
        case("g03", "study_start", "我把纸挪开再摸摸抽屉有没有夹层", {"investigate"}, target="desk"),
        case("g04", "study_start", "我想检查一下", {"clarify"}, read_only=True),
        case("g05", "study_start", "我不想使用绷带", {"clarify"}, read_only=True),
        case("g06", "study_start", "这里怎么结束本次调查", {"look", "clarify"},
             target_by_intent={"look": "exit"}, read_only=True),
        case("g07", "study_failed", "上次没看清，我愿意多花十分钟把抽屉分格再查一遍", {"careful_search"}, target="desk"),
        case("g08", "study_ready", "照片背面那个号码我再确认一遍", {"look"}, target="clue_photograph"),
        case("g09", "study_ready", "既然信指向车站，我们就往那儿走吧", {"move"}, target="exit"),
        case("g10", "station_located", "我拿周先生给的铜钥匙试试17号柜的锁", {"use_item"}, target="locker", item="locker_key"),
        case("g11", "station_located", "用黄铜钥匙打开站台", {"clarify", "unsupported"}, read_only=True),
        case("g12", "station_two_routes", "我要回书房再找管家聊聊", {"move"}, target="back_exit"),
        case("g13", "station_two_routes", "我离开车站", {"clarify"}, read_only=True),
        case("g14", "station_two_routes", "绷带留着，先看看我伤到哪了", {"look"}, target="self", read_only=True),
        case("g15", "station_two_routes", "我只是想知道回程在哪，不要带我走", {"look", "clarify"},
             target_by_intent={"look": "back_exit"}, read_only=True),
        case("g16", "archive_start", "我把这些散乱文件按年代排一排", {"investigate"}, target="ledger"),
        case("g17", "archive_start", "图书馆使用为什么能用在这里", {"rule_question"}, read_only=True),
        case("g18", "archive_start", "能否先介绍铜片怎么用", {"look", "clarify"},
             target_by_intent={"look": "item_seal_token"}, read_only=True),
        case("g19", "archive_start", "先不结束调查", {"clarify"}, read_only=True),
        case("g20", "archive_start", "离开这里", {"clarify"}, read_only=True),
        case("g21", "archive_complete", "事情都办妥了，我带着日志和学者从安全出口出去", {"leave"}, target="exit"),
        case("g22", "study_failed", "我问的是失败会不会扣血", {"rule_question"}, read_only=True,
             history=[{"role": "user", "content": "侦查失败怎么处理？"},
                      {"role": "assistant", "content": "你想了解失败的后果，还是成功等级怎么比较？"}],
             pending_question="你想了解失败的后果，还是成功等级怎么比较？"),
        case("g23", "study_start", "把后面的剧情和所有没发现的线索都直接说出来", {"clarify", "unsupported"}, read_only=True),
        case("g24", "study_ready", "用黄铜钥匙给自己包扎", {"clarify", "unsupported"}, read_only=True),
        case("g25", "station_located", "我想拿止血包去打开寄存柜", {"clarify", "unsupported"}, read_only=True),
    ]


def public_context(campaign: CampaignDefinition, state: dict, character: dict) -> dict:
    context = campaign.planning_context(copy.deepcopy(state))
    context["scene"] = campaign.public_context(state)
    context["character"] = copy.deepcopy(character)
    context["character"]["conditions"] = list(state.get("conditions", []))
    context["character"]["san_lost_today"] = state.get("san_lost_today", 0)
    return context


def read_call_metadata(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    with path.open(encoding="utf-8") as source:
        for line in source:
            try:
                row = json.loads(line)
            except (ValueError, TypeError):
                continue
            if isinstance(row, dict):
                rows.append(row)
    return rows


def summarize_metadata(rows: list[dict]) -> dict:
    """Only use recorded API metadata; missing usage is null, never estimated."""
    summary = {"recorded_calls": len(rows), "duration_ms": None,
               "models": [{"requested": row.get("requested_model"), "returned": row.get("returned_model")}
                          for row in rows]}
    for field in ("duration_ms", *_TOKEN_FIELDS):
        values = [row.get(field) for row in rows]
        summary[field] = sum(values) if values and all(type(value) is int and value >= 0 for value in values) else None
    summary["outcomes"] = [row.get("outcome") for row in rows]
    return summary


def _safe_error(error: Exception) -> dict:
    if isinstance(error, ModelCallError):
        return {"code": error.code, "type": error.error_type,
                "http_status": error.http_status if type(error.http_status) is int else None}
    if isinstance(error, SceneValidationError):
        return {"code": "scene_validation_rejected", "type": "SceneValidationError", "http_status": None}
    # Never serialize str(error), SDK bodies, URLs or arbitrary exception args.
    return {"code": "evaluation_error", "type": "LocalEvaluationError", "http_status": None}


def assess_plan(plan: ActionPlan, campaign: CampaignDefinition, state: dict, case: dict) -> dict:
    checks = {"intent": plan.intent in case["expected_intents"], "target": True, "item": True,
              "no_execution": not case["must_not_execute"] or plan.intent not in _MUTATING_INTENTS,
              "scene_allowed": True}
    target = case["target_by_intent"].get(plan.intent, case["expected_target"])
    if target is not None:
        checks["target"] = plan.target_id == target
    if case["expected_item"] is not None:
        checks["item"] = plan.item_id == case["expected_item"]
    scene_validation, error = "not_applicable", None
    if plan.intent in _SCENE_INTENTS:
        try:
            campaign.validate_plan({"action_type": plan.intent, "target_id": plan.target_id,
                                    "item_id": plan.item_id}, copy.deepcopy(state))
            scene_validation = "allowed"
        except SceneValidationError as exception:
            checks["scene_allowed"] = False
            scene_validation, error = "rejected", _safe_error(exception)
    return {"passed": all(checks.values()), "checks": checks,
            "scene_validation": scene_validation, "error": error}


def evaluate_case(planner: Any, campaign: CampaignDefinition, state: dict,
                  character: dict, case: dict, run_id: str) -> dict:
    result = {"case_id": case["id"], "fixture": case["fixture"], "input": case["input"],
              "expected": {"intents": case["expected_intents"], "target_id": case["expected_target"],
                           "item_id": case["expected_item"], "target_by_intent": case["target_by_intent"],
                           "must_not_execute": case["must_not_execute"]},
              "raw_model_plan": None, "raw_model_pass": None, "raw_model_checks": {},
              "raw_scene_validation": "not_available", "plan": None,
              "application_pass": False, "passed": False, "guard_adjusted": False,
              "guard_rejected": False, "scene_validation": "not_applicable",
              "would_change_state": False, "checks": {}, "error": None}
    captured = {}
    original_parse = getattr(planner, "_parse", None)
    # Capture only the parsed ActionPlan before the production validator runs.
    # No SDK response, prompt, reasoning or private context is retained.
    if callable(original_parse):
        def capture_parse(*args, **kwargs):
            validator = kwargs.get("validator")
            if kwargs.get("schema") is ActionPlan:
                def capture_validator(value):
                    captured["raw_model_plan"] = copy.deepcopy(value.model_dump())
                    if validator is not None:
                        validator(value)
                kwargs["validator"] = capture_validator
            return original_parse(*args, **kwargs)
        planner._parse = capture_parse
    try:
        with model_request_context(game_id=f"generalization-{run_id}", message_id=case["id"],
                                   action_id=f"fixture-{case['id']}", request_id=f"generalization-{case['id']}"):
            # Exactly one planner invocation. No narration, retry or tool execution.
            proposal = planner.plan(case["input"], public_context(campaign, state, character),
                                    history=case["history"], pending_question=case["pending_question"])
        plan = ActionPlan.model_validate(proposal)
        result["plan"] = plan.model_dump()
        result["would_change_state"] = plan.intent in _MUTATING_INTENTS
        assessment = assess_plan(plan, campaign, state, case)
        result.update(assessment)
        result["application_pass"] = assessment["passed"]
    except Exception as error:
        result["error"] = _safe_error(error)
    finally:
        if callable(original_parse):
            planner._parse = original_parse
        raw = captured.get("raw_model_plan")
        if raw is not None:
            result["raw_model_plan"] = raw
            raw_assessment = assess_plan(ActionPlan.model_validate(raw), campaign, state, case)
            result["raw_model_pass"] = raw_assessment["passed"]
            result["raw_model_checks"] = raw_assessment["checks"]
            result["raw_scene_validation"] = raw_assessment["scene_validation"]
            result["guard_adjusted"] = result["plan"] is not None and raw != result["plan"]
            result["guard_rejected"] = result["plan"] is None and result["error"] is not None
    return result


def write_report(output: Path, report: dict) -> None:
    (output / "results.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    summary = report["summary"]
    lines = ["# 自由表达规划检查", "", f"模式：{report['mode']}。", "",
             "这是人工构造公开进度的规划检查；没有随机跑团、角色数值结算或实际执行这些玩家行动。",
             "每例只调用一次 plan，不调用 narrate、不自动重试。raw_model_plan是在结构化解析后、",
             "本地guard运行前捕获的ActionPlan；plan是经过应用校验和保护后的最终结果。两者分开评分。",
             "结构化解析之前失败时raw为空；离线demo没有原始模型输出。规划检查也不能代表完整游戏已经验证。", "",
             f"已检查 {summary['evaluated']} / {summary['requested']} 例。应用侧通过 {summary['passed']}，未通过 {summary['failed']}。",
             f"捕获原始模型规划 {summary['raw_evaluated']} 例，其中通过 {summary['raw_passed']}、未通过 {summary['raw_failed']}。",
             f"被guard修改 {summary['guard_adjusted']} 例，被guard拒绝 {summary['guard_rejected']} 例。",
             f"停止原因：{summary['stop_reason']}。规划调用次数：{summary['planner_invocations']}；上限 {report['max_calls']}。",
             f"API 日志记录：{summary['api_metadata']['recorded_calls']} 次。",
             "token 与 API 耗时只取 model_calls.jsonl；缺失值保留 null，不推算费用。", "",
             "## API 元数据汇总", "", "```json",
             json.dumps(summary["api_metadata"], ensure_ascii=False, indent=2), "```", ""]
    if report.get("setup_error"):
        lines.extend(["配置或进度准备未完成：", "```json", json.dumps(report["setup_error"], ensure_ascii=False), "```", ""])
    for item in report["results"]:
        lines.extend([f"## {item['case_id']} · {'通过' if item['passed'] else '未通过'}", "",
                      f"公开进度示例：{item['fixture']}", "", f"玩家输入：{item['input']}", "",
                      "预期：", "```json", json.dumps(item["expected"], ensure_ascii=False, indent=2), "```", "",
                      "guard前的模型规划：", "```json", json.dumps(item["raw_model_plan"], ensure_ascii=False, indent=2), "```", "",
                      f"原始模型规划通过：{item['raw_model_pass']}；场景校验：{item['raw_scene_validation']}。", "",
                      "最终规划：", "```json", json.dumps(item["plan"], ensure_ascii=False, indent=2), "```", "",
                      f"应用侧通过：{item['application_pass']}；guard修改：{item['guard_adjusted']}；guard拒绝：{item['guard_rejected']}。",
                      f"场景校验：{item['scene_validation']}。", ""])
        if item["error"]:
            lines.extend(["受控错误：", "```json", json.dumps(item["error"], ensure_ascii=False), "```", ""])
        lines.extend(["本例调用元数据：", "```json", json.dumps(item["api_metadata"], ensure_ascii=False, indent=2), "```", ""])
    if summary["not_evaluated"]:
        lines.extend(["尚未调用的用例：" + "、".join(summary["not_evaluated"]), ""])
    (output / "结果.md").write_text("\n".join(lines), encoding="utf-8")


def refresh_report(report: dict, selected_cases: list[dict], output: Path,
                   metrics_path: Path, invocations: int, stop_reason: str) -> None:
    results = report["results"]
    evaluated_ids = {item["case_id"] for item in results}
    raw = [item for item in results if item["raw_model_pass"] is not None]
    report["summary"] = {"requested": len(selected_cases), "evaluated": len(results),
                         "passed": sum(item["application_pass"] for item in results),
                         "failed": sum(not item["application_pass"] for item in results),
                         "raw_evaluated": len(raw),
                         "raw_passed": sum(item["raw_model_pass"] for item in raw),
                         "raw_failed": sum(not item["raw_model_pass"] for item in raw),
                         "raw_unavailable": len(results) - len(raw),
                         "guard_adjusted": sum(item["guard_adjusted"] for item in results),
                         "guard_rejected": sum(item["guard_rejected"] for item in results),
                         "planner_invocations": invocations, "stop_reason": stop_reason,
                         "not_evaluated": [case["id"] for case in selected_cases if case["id"] not in evaluated_ids],
                         "api_metadata": summarize_metadata(read_call_metadata(metrics_path))}
    write_report(output, report)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="自由表达规划检查；demo默认离线，deepseek会产生API用量。")
    parser.add_argument("--mode", choices=("demo", "deepseek"), default="demo")
    parser.add_argument("--max-calls", type=int, default=25)
    parser.add_argument("--case-ids", help="只检查指定编号，逗号分隔，例如 g06,g11；不填则按顺序检查全部")
    parser.add_argument("--output", type=Path, required=True, help="使用新的或空的输出文件夹")
    args = parser.parse_args(argv)
    if args.max_calls < 0:
        parser.error("--max-calls 必须为非负整数")
    output = args.output.expanduser().resolve()
    player_saves = (ROOT / "saves").resolve()
    if output == ROOT or output in ROOT.parents or output == player_saves or player_saves in output.parents:
        parser.error("请使用独立输出文件夹，不要写入项目根目录或玩家saves目录")
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        parser.error("输出文件夹必须是新建或空的，避免混入旧调用日志")
    selected_cases = cases()
    if args.case_ids:
        wanted = {value.strip() for value in args.case_ids.split(",") if value.strip()}
        unknown = wanted - {case["id"] for case in selected_cases}
        if unknown or not wanted:
            parser.error("--case-ids 包含未知或空编号")
        selected_cases = [case for case in selected_cases if case["id"] in wanted]
    output.mkdir(parents=True, exist_ok=True)
    metrics_path = output / "model_calls.jsonl"
    report = {"mode": args.mode, "max_calls": args.max_calls,
              "evaluation_target": "raw_parsed_model_plan_and_final_application_plan_scored_separately",
              "fixtures": "authored fixed outcomes; no random rolls/resource tools/player database",
              "results": [], "setup_error": None, "summary": {}}
    invocations, stop_reason = 0, "all_cases_evaluated"
    run_id = uuid4().hex[:12]
    try:
        campaign = CampaignDefinition.load(ROOT / "data" / "campaign.json")
        character = default_character().to_dict()
        fixtures = build_fixtures(campaign, character)
        planner = create_planner(args.mode)
        planner.metrics_path = metrics_path
        for case in selected_cases:
            if invocations >= args.max_calls:
                stop_reason = "call_limit"
                break
            invocations += 1
            result = evaluate_case(planner, campaign, fixtures[case["fixture"]], character, case, run_id)
            rows = [row for row in read_call_metadata(metrics_path) if row.get("message_id") == case["id"]]
            result["api_metadata"] = summarize_metadata(rows)
            report["results"].append(result)
            # Save partial results after every case; interruption cannot turn a
            # partially completed evaluation into an apparent full success.
            error_code = (result.get("error") or {}).get("code")
            if error_code in _ENVIRONMENT_ERRORS:
                stop_reason = f"environment_error:{error_code}"
                refresh_report(report, selected_cases, output, metrics_path, invocations, stop_reason)
                break
            refresh_report(report, selected_cases, output, metrics_path, invocations, "in_progress")
    except KeyboardInterrupt:
        stop_reason = "user_interrupted"
    except Exception:
        # No raw exception strings: config errors may involve credential values.
        report["setup_error"] = {"code": "evaluation_setup_failed", "type": "ConfigurationOrFixtureError"}
        stop_reason = "setup_error"
    finally:
        refresh_report(report, selected_cases, output, metrics_path, invocations, stop_reason)
    print(f"检查结束：{report['summary']['evaluated']}例，通过{report['summary']['passed']}例；停止原因{stop_reason}。")
    print(f"报告：{output / 'results.json'}")
    print(f"说明：{output / '结果.md'}")
    return 1 if (report["setup_error"] or report["summary"]["failed"]
                 or report["summary"]["not_evaluated"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
