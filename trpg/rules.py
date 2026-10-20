"""结构化规则库：COC 7e 的可机读硬规则（公式/表格/默认值）。

设计原则（见 DESIGN.md）：能变成公式/表格的规则尽量结构化，作为判定与状态层的
正确性依据；只有模糊叙述才走 RAG 检索（见 rules_store.py）。

已结构化内容：
- 派生公式：HP / MP / SAN / 移动力 / 伤害加值 / 体格 / 重伤阈值
- 伤害加值（DB）与体格（Build）表：STR+SIZ → DB/Build
- 移动力修正（力量/敏捷/体型 + 年龄）
- 理智损失阈值：临时疯狂 / 不定期疯狂
- 成长检定（improvement）
- 默认技能表（未加点时的基础成功率）

> 成功等级判定、奖惩骰已在 dice.py / check.py 实现，不在此重复。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple

# ---- 属性 ----

ATTRIBUTES = ("STR", "CON", "DEX", "APP", "POW", "INT", "SIZ", "EDU")

ATTRIBUTE_NAMES = {
    "STR": "力量", "CON": "体质", "DEX": "敏捷", "APP": "外貌",
    "POW": "意志", "INT": "智力", "SIZ": "体型", "EDU": "教育",
}


@dataclass(frozen=True)
class DerivedStats:
    hp_max: int
    mp_max: int
    san_start: int       # 起始理智 = POW
    san_max: int         # 理智上限 = 99 - 克苏鲁神话
    mov: int
    db: str              # 伤害加值
    build: int
    major_wound: int     # 重伤阈值 = hp_max // 2


def compute_derived(attributes: Dict[str, int], *, age: int = 0, cthulhu_mythos: int = 0) -> DerivedStats:
    """由 8 属性计算派生值（标准规则书）。attributes 缺键视为 0。"""
    str_ = int(attributes.get("STR", 0))
    con = int(attributes.get("CON", 0))
    dex = int(attributes.get("DEX", 0))
    pow_ = int(attributes.get("POW", 0))
    siz = int(attributes.get("SIZ", 0))

    hp_max = (con + siz) // 10
    mp_max = pow_ // 5
    db, build = damage_bonus(str_, siz)
    return DerivedStats(
        hp_max=hp_max,
        mp_max=mp_max,
        san_start=pow_,
        san_max=max(0, 99 - int(cthulhu_mythos)),
        mov=movement_rate(str_, dex, siz, age),
        db=db,
        build=build,
        major_wound=hp_max // 2,
    )


# ---- 伤害加值 / 体格（COC 7e 表） ----

# (STR+SIZ 下限, 上限, DB, Build)
_DB_TABLE = [
    (0, 64, "-2", -2),
    (65, 84, "-1", -1),
    (85, 124, "0", 0),
    (125, 164, "+1D4", 1),
    (165, 204, "+1D6", 2),
    (205, 284, "+2D6", 3),
    (285, 364, "+3D6", 4),
    (365, None, "+4D6", 5),
]


def damage_bonus(str_: int, siz: int) -> Tuple[str, int]:
    """STR+SIZ → (伤害加值, 体格)。"""
    total = int(str_) + int(siz)
    for _lo, hi, db, build in _DB_TABLE:
        if hi is None or total <= hi:
            return db, build
    return "+4D6", 5


# ---- 移动力 ----

def movement_rate(str_: int, dex: int, siz: int, age: int = 0) -> int:
    """基础 8；STR、DEX 均 > SIZ 则 +1、均 < SIZ 则 -1；年龄每十岁（40 起）-1。下限 1。"""
    str_, dex, siz = int(str_), int(dex), int(siz)
    mov = 8
    if str_ > siz and dex > siz:
        mov += 1
    elif str_ < siz and dex < siz:
        mov -= 1
    age = int(age)
    if age >= 40:
        mov -= (age - 30) // 10  # 40~49 → -1，50~59 → -2 …
    return max(1, mov)


# ---- 理智损失阈值 ----

@dataclass(frozen=True)
class InsanityThresholds:
    temporary: int   # 单次损失 ≥ 5 → 临时疯狂
    indefinite: int  # 单日损失 ≥ 当前 SAN/5 → 不定期疯狂


def insanity_thresholds(san_current: int) -> InsanityThresholds:
    san = max(1, int(san_current))
    return InsanityThresholds(temporary=5, indefinite=san // 5)


# ---- 成长检定 ----

def improvement_increases(skill: int, d100_roll: int) -> bool:
    """成长检定：d100 出目 > 当前技能值则成长。"""
    return int(d100_roll) > int(skill)


def improve(skill: int, d100_roll: int, d10_gain: int) -> int:
    """成长：若 d100 > 技能，则 +d10（上限 99），否则不变。"""
    if improvement_increases(skill, d100_roll):
        return min(99, int(skill) + int(d10_gain))
    return int(skill)


# ---- 默认技能表（未加点的基础成功率） ----

DEFAULT_SKILLS = {
    "会计": 5, "人类学": 1, "估价": 5, "考古学": 1, "取悦": 15, "攀爬": 20,
    "计算机使用": 5, "信用评级": 0, "克苏鲁神话": 0, "乔装": 5,
    "汽车驾驶": 20, "电气维修": 10, "电子学": 1, "话术": 5, "斗殴": 25,
    "急救": 30, "历史": 5, "恐吓": 15, "跳跃": 20, "法律": 5,
    "图书馆使用": 20, "聆听": 20, "锁匠": 1, "机械维修": 10, "医学": 1,
    "博物学": 10, "导航": 10, "神秘学": 5, "操作重型机械": 1, "说服": 10,
    "精神分析": 1, "心理学": 10, "骑术": 5, "妙手": 10, "侦查": 25,
    "潜行": 20, "生存": 10, "游泳": 20, "投掷": 20, "追踪": 10,
    "驯兽": 5, "潜水": 1, "爆破": 1, "读唇": 1, "催眠": 1, "炮术": 1,
}


def skill_default(name: str, attributes: Optional[Dict[str, int]] = None) -> int:
    """某技能的默认成功率。闪避=DEX/2、母语=EDU，其余查 DEFAULT_SKILLS，未知 0。"""
    if name == "闪避":
        return int((attributes or {}).get("DEX", 0)) // 2
    if name == "母语":
        return int((attributes or {}).get("EDU", 0))
    return DEFAULT_SKILLS.get(name, 0)
