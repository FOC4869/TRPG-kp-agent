"""Run with: python -m kp_agent --mode demo"""

from __future__ import annotations

import argparse
import json
import uuid
from pathlib import Path

from .config import load_local_env
from .graph import KeeperService, ROOT
from .models import create_planner

LABELS = {"regular_success": "常规成功", "hard_success": "困难成功", "extreme_success": "极难成功",
          "critical_success": "大成功", "failure": "失败", "fumble": "大失败"}


def _print_guidance(result: dict, *, already_shown: str = "") -> None:
    """Print one optional hint, without turning free input into a fixed menu."""
    guidance = result.get("guidance")
    if not isinstance(guidance, str) or not guidance.strip():
        return
    guidance = guidance.strip()
    if "".join(guidance.split()) in "".join(already_shown.split()):
        return
    print(f"\n{guidance}")


def _print_character(character: dict | None) -> None:
    if not isinstance(character, dict):
        return
    parts = []
    for field, label in (("hp", "HP"), ("san", "SAN"), ("mp", "MP")):
        if field in character:
            parts.append(f"{label} {character[field]}/{character.get(field + '_max', '?')}")
    if parts:
        print("  " + " | ".join(parts))


def show_start(game: dict) -> None:
    """Show the saved game's real status instead of replaying a fresh opening."""
    status = game.get("game_status", "playing")
    labels = {"playing": "进行中", "ended": "已结束", "paused": "已暂停"}
    print(f"游戏编号：{game['game_id']}\n状态：{labels.get(status, status)}")
    message = game.get("startup_message")
    if not isinstance(message, str) or not message.strip():
        if status == "ended":
            message = "本局已结束。可以问我复盘，或输入 /restart 重新开始。"
        elif status == "paused":
            message = "本局已暂停，需要真人处理，或输入 /restart 重新开始。"
        else:
            message = game.get("opening", "")
    if message:
        print(message)
    _print_character(game.get("character"))
    if status == "playing":
        _print_guidance(game, already_shown=message)
        print("输入 /status 看状态，/history 看记录，/retry 恢复未完成消息，/restart 重开，/quit 保存退出。")
    elif status == "ended":
        print("输入 /review 看复盘，/restart 重新开始，/history 看记录，/quit 退出。")
    else:
        print("输入 /status 看状态，/history 看记录，/restart 重开，/quit 退出。")


def show(reply: dict) -> None:
    evidence = reply.get("evidence", [])
    display_text = reply["reply"]
    cited = []
    for index, item in enumerate(evidence, 1):
        evidence_id = item.get("evidence_id", item.get("id"))
        if evidence_id and f"[{evidence_id}]" in display_text:
            display_text = display_text.replace(f"[{evidence_id}]", f"【规则{index}】")
            cited.append((index, item))
    print(f"\nKP：{display_text}")
    for result in reply.get("rolls", []):
        if "roll" in result:
            degree = LABELS.get(result.get("success_level"), "通过" if result.get("passed") else "未通过")
            print(f"  骰子：{result.get('skill', '检定')} {result['roll']}/{result.get('skill_value', '?')}，{degree}")
    for change in reply.get("changes", []):
        print(f"  变化：{change['field']} {change['before']} → {change['after']}（{change['reason']}）")
    for clue in reply.get("new_clues", []):
        print(f"  新线索：{clue['name']}\n  {clue['description']}")
    if cited:
        print("  规则依据：" + "；".join(
            f"【规则{index}】{item['title']}（{item['source']}，PDF第{item['pdf_page']}页）" for index, item in cited
        ))
    progress = reply.get("progress", {})
    if progress.get("elapsed_minutes", 0):
        print(f"  额外调查耗时：{progress['elapsed_minutes']} 分钟")
    _print_character(reply.get("character"))
    _print_guidance(reply, already_shown=reply["reply"])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="单场景 COC AI KP 原型；demo 不是大模型。")
    parser.add_argument("--mode", choices=("demo", "openai", "deepseek"), default=None,
                        help="优先使用此参数，否则读 KP_MODEL_MODE；未设置则 demo。在线模式需要配置对应账号。")
    parser.add_argument("--db", type=Path, default=ROOT / "saves" / "keeper.sqlite3")
    parser.add_argument("--restart", action="store_true", help="明确重新开始，恢复固定角色初态")
    parser.add_argument("--message", help="发送一条消息后退出，适合检查或接其他程序")
    parser.add_argument("--message-id", help="重试同一消息时必须使用原编号")
    parser.add_argument("--json", action="store_true", help="单条消息输出 JSON，供前端同学参考")
    args = parser.parse_args(argv)
    service = None
    try:
        load_local_env()
        service = KeeperService(db_path=args.db, planner=create_planner(args.mode))
        game = service.restart() if args.restart else service.start()
        if args.message:
            reply = service.handle_message(args.message_id or uuid.uuid4().hex, args.message, game["game_id"])
            if args.json:
                print(json.dumps(reply, ensure_ascii=False, indent=2))
            else:
                print(service.planner.mode_label)
                show(reply)
            return 0
        print(service.planner.mode_label)
        show_start(game)
        retry: tuple[str, str] | None = None
        while True:
            try:
                text = input("\n你：").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n已保存，退出。")
                return 0
            if not text:
                continue
            if text == "/quit":
                return 0
            if text == "/status":
                print(json.dumps(service.get_game(), ensure_ascii=False, indent=2))
                continue
            if text == "/history":
                for row in service.list_messages():
                    print("你：" + row["text"])
                    if row["reply"]:
                        print("KP：" + row["reply"]["reply"])
                    else:
                        print(f"[{row['status']}] 可用 /retry 恢复同一条消息。")
                continue
            if text == "/review" and service.get_game().get("game_status") != "ended":
                print("这局还没有结束，结束后可以查看复盘。现在可以用 /history 看已经发生的事。")
                continue
            if text == "/restart":
                game = service.restart()
                retry = None
                show_start(game)
                continue
            if text == "/retry":
                # The saved unfinished message is authoritative. A new request
                # rejected as busy may never have been registered in storage.
                pending = [row for row in service.list_messages() if row["status"] != "completed"]
                if pending:
                    retry = pending[-1]["message_id"], pending[-1]["text"]
                if retry is None:
                    print("没有待恢复的消息。")
                    continue
                message_id, text = retry
            else:
                message_id = uuid.uuid4().hex
            try:
                show(service.handle_message(message_id, text, game["game_id"]))
                retry = None
            except Exception as error:
                registered = service.get_message(message_id)
                if registered is not None and registered["status"] != "completed":
                    retry = (message_id, text)
                print(f"处理未完成：{error}\n输入 /retry 恢复这条消息，或 /restart 重开。")
    except Exception as error:
        print(f"无法启动或完成请求：{error}")
        return 1
    finally:
        if service is not None:
            service.close()
