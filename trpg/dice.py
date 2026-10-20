"""骰子表达式求值与 d100 奖惩骰。

移植自 trpg-dice-mcp（Komeiji-Shiki）的判定语义，裁剪为 COC 7 版所需的最小集：
- 支持 NdM / dM / d%，以及 + - 常数修正（如 3d6+2、1d100、d%）。
- 暂不支持 keep/drop、爆炸、重骰等（COC 不需要，D&D 才用），后续可扩展。
"""

from __future__ import annotations

import random
import re
from dataclasses import dataclass
from typing import List, Optional, Tuple

_DIE_TERM = re.compile(r"^(?P<count>\d*)d(?P<sides>%|\d+)$")


@dataclass
class RollResult:
    expression: str
    total: int
    faces: List[int]
    detail: str

    def __str__(self) -> str:
        return f"{self.expression} = {self.detail} = {self.total}"


def roll(expr: str, rng: Optional[random.Random] = None) -> RollResult:
    """掷骰表达式，支持 NdM / dM / d% 及 + - 常数修正。

    例：roll("3d6")、roll("1d100")、roll("d%")、roll("1d4+2")、roll("2d6-1")。
    """
    rng = rng or random.Random()
    normalized = expr.replace(" ", "")
    total = 0
    faces: List[int] = []
    parts: List[str] = []

    for term in _split_terms(normalized):
        sign, body = _sign_and_body(term)
        m = _DIE_TERM.match(body)
        if m:
            count = int(m.group("count")) if m.group("count") else 1
            sides = 100 if m.group("sides") == "%" else int(m.group("sides"))
            if count < 1 or sides < 1:
                raise ValueError(f"非法骰子表达式：{term!r}")
            group = [rng.randint(1, sides) for _ in range(count)]
            subtotal = sum(group)
            faces.extend(group)
            total += sign * subtotal
            parts.append(f"{'-' if sign < 0 else ''}{body}[{','.join(map(str, group))}]")
        else:
            try:
                const = int(body)
            except ValueError:
                raise ValueError(f"无法解析的项：{term!r}") from None
            total += sign * const
            parts.append(f"{'-' if sign < 0 else ''}{body}")

    return RollResult(expression=expr, total=total, faces=faces, detail=" ".join(parts))


def roll_percentile(
    rng: random.Random, bonus_dice: int = 0
) -> Tuple[int, Optional[List[int]]]:
    """掷 d100，返回 (结果 1-100, 候选值列表)。

    bonus_dice > 0 为奖励骰（取最低 = 最好）；< 0 为惩罚骰（取最高 = 最差）；0 为普通。
    个位骰共享掷一次，十位骰掷 |bonus_dice| + 1 次；00（十位 0 且个位 0）映射为 100。
    """
    if bonus_dice == 0:
        return rng.randint(1, 100), None

    units = rng.randint(0, 9)
    tens = [rng.randint(0, 9) * 10 for _ in range(abs(bonus_dice) + 1)]
    candidates = [(t + units) or 100 for t in tens]
    result = min(candidates) if bonus_dice > 0 else max(candidates)
    return result, candidates


def _split_terms(expr: str) -> List[str]:
    """按 +/- 拆分表达式，保留符号。如 "3d6+2-1d4" -> ["3d6", "+2", "-1d4"]。"""
    terms: List[str] = []
    start = 0
    for i in range(1, len(expr)):
        if expr[i] in "+-":
            terms.append(expr[start:i])
            start = i
    terms.append(expr[start:])
    return terms


def _sign_and_body(term: str) -> Tuple[int, str]:
    if term.startswith("+"):
        return 1, term[1:]
    if term.startswith("-"):
        return -1, term[1:]
    return 1, term
