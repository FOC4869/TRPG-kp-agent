"""TRPG 骰子与检定引擎（判定工具层 + 角色卡状态层 + 规则库）。

- 骰子表达式求值：dice.roll
- d100 奖惩骰：dice.roll_percentile
- 技能/属性检定与成功等级：check.coc_check
- 房规配置与导入：house_rules.CocHouseRules（缺省 = 标准规则书）
- 角色卡状态层：character.Character（HP/SAN/MP 事务更新 + 检定 + 存档）
- 多角色花名册：roster.Roster（批量导入 / 切换 / 目录存档）
- Excel 角色卡导入：excel_import.load_character_from_xlsx（依赖 openpyxl）
- 结构化规则库：rules（派生公式/伤害加值表/移动力/理智阈值/成长/默认技能）
- 规则 RAG 检索：rules_store.RuleStore（切块 / 关键词+向量检索 / JSON 持久化）
"""

from .dice import roll, roll_percentile, RollResult
from .check import coc_check, CheckResult
from .house_rules import CocHouseRules, CriticalRule, FumbleRule
from .character import Character, DamageResult, SanLossResult
from .roster import Roster
from .excel_import import load_character_from_xlsx
from .rules import (
    ATTRIBUTES,
    ATTRIBUTE_NAMES,
    DEFAULT_SKILLS,
    DerivedStats,
    InsanityThresholds,
    compute_derived,
    damage_bonus,
    improve,
    improvement_increases,
    insanity_thresholds,
    movement_rate,
    skill_default,
)
from .rules_store import RuleChunk, RuleStore, SearchResult, chunk_text, tokenize

__all__ = [
    "roll",
    "roll_percentile",
    "RollResult",
    "coc_check",
    "CheckResult",
    "CocHouseRules",
    "CriticalRule",
    "FumbleRule",
    "Character",
    "DamageResult",
    "SanLossResult",
    "Roster",
    "load_character_from_xlsx",
    "ATTRIBUTES",
    "ATTRIBUTE_NAMES",
    "DEFAULT_SKILLS",
    "DerivedStats",
    "InsanityThresholds",
    "compute_derived",
    "damage_bonus",
    "improve",
    "improvement_increases",
    "insanity_thresholds",
    "movement_rate",
    "skill_default",
    "RuleChunk",
    "RuleStore",
    "SearchResult",
    "chunk_text",
    "tokenize",
]
