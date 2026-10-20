"""角色卡状态层：属性/派生/技能 + HP/SAN/MP 事务更新与检定入口。

COC 7 版角色卡：
- 属性（8）：力量 STR / 体质 CON / 敏捷 DEX / 外貌 APP / 意志 POW / 智力 INT / 体型 SIZ / 教育 EDU
- 派生：HP、SAN、MP、幸运 Luck、移动力 MOV、伤害加值 DB、体格 Build
- 技能：侦查、聆听、图书馆使用……（技能名 → 成功率）

状态层是「单一数据源」：所有 HP/SAN/MP 的增减都走这里的事务方法，
检定通过 check() 委托给 check.coc_check，属性增减由本类事务性完成并落库（save/load）。
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Dict, Optional

from .check import CheckResult, coc_check
from .house_rules import CocHouseRules

# 属性别名 → 规范键（ascii 键一律小写）
ATTR_ALIASES = {
    "力量": "STR", "str": "STR",
    "体质": "CON", "con": "CON",
    "敏捷": "DEX", "dex": "DEX",
    "外貌": "APP", "app": "APP", "外观": "APP",
    "意志": "POW", "pow": "POW",
    "智力": "INT", "int": "INT", "灵感": "INT",
    "体型": "SIZ", "siz": "SIZ",
    "教育": "EDU", "edu": "EDU", "知识": "EDU",
    "幸运": "LUCK", "运气": "LUCK", "luck": "LUCK",
}

# 技能别名 → 规范技能名（取自角色卡工具的「别名」表）
SKILL_ALIASES = {
    "侦察": "侦查",
    "图书馆": "图书馆使用", "图馆": "图书馆使用",
    "信用": "信用评级", "信誉": "信用评级",
    "计算机": "计算机使用", "电脑": "计算机使用",
    "驾驶": "汽车驾驶",
    "开锁": "锁匠", "撬锁": "锁匠",
    "自然学": "博物学",
    "领航": "导航",
    "重型操作": "操作重型机械", "重型机械": "操作重型机械", "重型": "操作重型机械",
    "克苏鲁": "克苏鲁神话", "cm": "克苏鲁神话",
    "格斗": "斗殴",
    "射击": "手枪",
}


@dataclass
class DamageResult:
    amount: int
    hp_before: int
    hp_after: int
    major_wound: bool    # 单次伤害 ≥ HP 上限的一半
    unconscious: bool    # HP 归零
    dying: bool          # HP 归零且重伤


@dataclass
class SanLossResult:
    amount: int
    san_before: int
    san_after: int
    possible_temporary_insanity: bool  # 单次损失 ≥ 5，需智力检定判定临时疯狂


@dataclass
class Character:
    name: str
    age: int = 0
    occupation: str = ""
    attributes: Dict[str, int] = field(default_factory=dict)  # STR/CON/.../EDU
    skills: Dict[str, int] = field(default_factory=dict)       # 技能名 → 值
    hp: int = 0
    hp_max: int = 0
    san: int = 0
    san_max: int = 0
    mp: int = 0
    mp_max: int = 0
    luck: int = 0
    mov: int = 8
    db: str = "0"
    build: int = 0
    armor: int = 0

    @property
    def major_wound_threshold(self) -> int:
        return self.hp_max // 2

    # ---- 事务更新 ----

    def apply_damage(self, amount: int) -> DamageResult:
        """扣除 HP（受伤害）。返回结果含重伤/昏迷/濒死标记。"""
        amount = max(0, int(amount))
        before = self.hp
        major = amount >= self.major_wound_threshold
        self.hp = max(0, self.hp - amount)
        return DamageResult(amount, before, self.hp, major, self.hp == 0, self.hp == 0 and major)

    def apply_san_loss(self, amount: int) -> SanLossResult:
        """扣除 SAN（理智损失）。"""
        amount = max(0, int(amount))
        before = self.san
        self.san = max(0, self.san - amount)
        return SanLossResult(amount, before, self.san, amount >= 5)

    def restore_hp(self, amount: Optional[int] = None) -> int:
        """恢复 HP，默认回满，封顶 hp_max。"""
        if amount is None:
            amount = self.hp_max
        self.hp = min(self.hp_max, self.hp + int(amount))
        return self.hp

    def restore_san(self, amount: Optional[int] = None) -> int:
        """恢复 SAN，默认回满，封顶 san_max。"""
        if amount is None:
            amount = self.san_max
        self.san = min(self.san_max, self.san + int(amount))
        return self.san

    def restore_mp(self, amount: Optional[int] = None) -> int:
        """恢复 MP，默认回满，封顶 mp_max。"""
        if amount is None:
            amount = self.mp_max
        self.mp = min(self.mp_max, self.mp + int(amount))
        return self.mp

    # ---- 检定 ----

    def resolve(self, name: str) -> Optional[int]:
        """按名字解析可检定值：先属性、再幸运、再技能。找不到返回 None。"""
        key = name.strip()
        if key.isascii():
            key = key.lower()
        attr_key = ATTR_ALIASES.get(key, key)
        if attr_key in self.attributes:
            return self.attributes[attr_key]
        if attr_key == "LUCK":
            return self.luck
        skill_key = SKILL_ALIASES.get(key, key)
        if skill_key in self.skills:
            return self.skills[skill_key]
        return None

    def check(
        self,
        skill: str,
        *,
        bonus_dice: int = 0,
        house_rules: Optional[CocHouseRules] = None,
        rng: Optional[random.Random] = None,
    ) -> CheckResult:
        """对某个技能/属性做检定（委托给 coc_check）。"""
        value = self.resolve(skill)
        if value is None:
            raise ValueError(f"角色「{self.name}」没有「{skill}」这项技能/属性")
        return coc_check(value, bonus_dice=bonus_dice, house_rules=house_rules, rng=rng)

    # ---- 存取（存档为 JSON） ----

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "age": self.age,
            "occupation": self.occupation,
            "attributes": dict(self.attributes),
            "skills": dict(self.skills),
            "hp": self.hp, "hp_max": self.hp_max,
            "san": self.san, "san_max": self.san_max,
            "mp": self.mp, "mp_max": self.mp_max,
            "luck": self.luck, "mov": self.mov,
            "db": self.db, "build": self.build, "armor": self.armor,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Character":
        return cls(
            name=d["name"],
            age=d.get("age", 0),
            occupation=d.get("occupation", ""),
            attributes=dict(d.get("attributes", {})),
            skills=dict(d.get("skills", {})),
            hp=d.get("hp", 0), hp_max=d.get("hp_max", 0),
            san=d.get("san", 0), san_max=d.get("san_max", 0),
            mp=d.get("mp", 0), mp_max=d.get("mp_max", 0),
            luck=d.get("luck", 0), mov=d.get("mov", 8),
            db=d.get("db", "0"), build=d.get("build", 0), armor=d.get("armor", 0),
        )

    def save(self, path: str) -> None:
        import json
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)

    @classmethod
    def load(cls, path: str) -> "Character":
        import json
        with open(path, "r", encoding="utf-8") as f:
            return cls.from_dict(json.load(f))
