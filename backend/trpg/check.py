"""COC 7 版技能/属性检定与成功等级判定。

移植自 trpg-dice-mcp 的 roll_check（coc7 预设），语义保持一致：
- 成功等级按固定优先级判定：大成功 → 极难 → 困难 → 常规 → 失败。
- 大失败在等级判定之后覆盖（自然 100 恒为大失败，即使技能 ≥ 100）。
- 大成功/大失败看自然出目 roll；极难/困难/常规看出目（无修正时二者相等）。
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import List, Optional

from .dice import roll_percentile
from .house_rules import CocHouseRules, CriticalRule, FumbleRule

_DEGREE_ZH = {
    "critical_success": "大成功",
    "extreme_success": "极难成功",
    "hard_success": "困难成功",
    "regular_success": "成功",
    "failure": "失败",
    "fumble": "大失败",
}

_SUCCESS_DEGREES = frozenset(
    ["critical_success", "extreme_success", "hard_success", "regular_success"]
)


@dataclass
class CheckResult:
    skill: int
    roll: int
    degree: str
    margin: int
    bonus_dice: int = 0
    candidates: Optional[List[int]] = None
    house_rules: Optional[CocHouseRules] = None

    @property
    def success(self) -> bool:
        return self.degree in _SUCCESS_DEGREES

    @property
    def summary(self) -> str:
        bonus = ""
        if self.bonus_dice != 0:
            kind = "奖励" if self.bonus_dice > 0 else "惩罚"
            bonus = f"（{kind}骰 {abs(self.bonus_dice)}，候选 {self.candidates}）"
        return f"🎲 1d100 = {self.roll} vs {self.skill} → {_DEGREE_ZH[self.degree]}{bonus}"


def coc_check(
    skill: int,
    *,
    bonus_dice: int = 0,
    house_rules: Optional[CocHouseRules] = None,
    rng: Optional[random.Random] = None,
) -> CheckResult:
    """执行一次 COC 技能/属性检定。

    Args:
        skill: 技能值（或属性值），≥ 1。
        bonus_dice: 奖惩骰数量，正 = 奖励、负 = 惩罚。
        house_rules: 房规，缺省为标准规则书。
        rng: 随机源（可注入 seed 以便测试复现）。
    """
    hr = house_rules or CocHouseRules.standard()
    rng = rng or random.Random()
    if skill < 1:
        raise ValueError(f"技能值必须 ≥ 1，得到 {skill}")

    value, candidates = roll_percentile(rng, bonus_dice)
    degree = _determine_degree(value, skill, hr)
    return CheckResult(
        skill=skill,
        roll=value,
        degree=degree,
        margin=skill - value,
        bonus_dice=bonus_dice,
        candidates=candidates,
        house_rules=hr,
    )


def _determine_degree(roll: int, skill: int, hr: CocHouseRules) -> str:
    if _is_critical(roll, skill, hr):
        degree = "critical_success"
    elif roll <= skill // hr.extreme_divisor:
        degree = "extreme_success"
    elif roll <= skill // hr.hard_divisor:
        degree = "hard_success"
    elif roll <= skill:
        degree = "regular_success"
    else:
        degree = "failure"
    # 大失败在等级判定之后覆盖
    if _is_fumble(roll, skill, hr):
        degree = "fumble"
    return degree


def _is_critical(roll: int, skill: int, hr: CocHouseRules) -> bool:
    if hr.critical is CriticalRule.ROLL_1:
        return roll == 1
    if hr.critical is CriticalRule.ROLL_LE_5:
        return roll <= 5
    if hr.critical is CriticalRule.ROLL_LE_SKILL_DIV_5:
        return roll <= skill // 5
    raise ValueError(f"未知大成功规则：{hr.critical}")


def _is_fumble(roll: int, skill: int, hr: CocHouseRules) -> bool:
    if hr.fumble is FumbleRule.STANDARD:
        return (skill < 50 and roll >= 96) or roll == 100
    if hr.fumble is FumbleRule.ROLL_GE_96:
        return roll >= 96
    if hr.fumble is FumbleRule.ROLL_100:
        return roll == 100
    raise ValueError(f"未知大失败规则：{hr.fumble}")
