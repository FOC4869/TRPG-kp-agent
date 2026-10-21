"""COC 7 版房规配置与导入接口。

缺省（不导入房规）= 标准规则书：
- 大成功：自然出目 01
- 极难成功：出目 ≤ 技能 / 5（向下取整）
- 困难成功：出目 ≤ 技能 / 2（向下取整）
- 大失败：技能 < 50 时出目 96~100；技能 ≥ 50 时仅出目 100

导入方式（三种，等价）：
- CocHouseRules.from_dict(dict)
- CocHouseRules.from_json(str)
- CocHouseRules.from_json_file(path)

房规 JSON 只写需要覆盖的字段，未写的字段回退标准规则书：

    {
      "critical": "roll_le_5",       # 大成功 = 出目 ≤ 5
      "fumble": "roll_ge_96"         # 大失败 = 出目 ≥ 96
    }
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class CriticalRule(str, Enum):
    """大成功判定规则。"""

    ROLL_1 = "roll_1"  # 标准：出目 == 1
    ROLL_LE_5 = "roll_le_5"  # 出目 ≤ 5
    ROLL_LE_SKILL_DIV_5 = "roll_le_skill_div_5"  # 出目 ≤ 技能/5（向下取整）


class FumbleRule(str, Enum):
    """大失败判定规则。"""

    STANDARD = "standard"  # 标准：技能<50 → 96~100；技能≥50 → 100
    ROLL_GE_96 = "roll_ge_96"  # 出目 ≥ 96 恒为大失败
    ROLL_100 = "roll_100"  # 仅出目 == 100


@dataclass(frozen=True)
class CocHouseRules:
    """COC 检定房规。缺省构造即标准规则书。"""

    critical: CriticalRule = CriticalRule.ROLL_1
    fumble: FumbleRule = FumbleRule.STANDARD
    extreme_divisor: int = 5
    hard_divisor: int = 2

    def __post_init__(self) -> None:
        if not (self.extreme_divisor > self.hard_divisor > 0):
            raise ValueError(
                "需满足 extreme_divisor > hard_divisor > 0，否则成功等级会错序"
            )

    # ---- 导入 / 导出 ----

    @classmethod
    def standard(cls) -> "CocHouseRules":
        """标准规则书（缺省）。"""
        return cls()

    @classmethod
    def from_dict(cls, data: Optional[dict]) -> "CocHouseRules":
        """从 dict 导入房规；None 或空 dict 回退标准规则书。"""
        if not data:
            return cls()
        return cls(
            critical=CriticalRule(data.get("critical", "roll_1")),
            fumble=FumbleRule(data.get("fumble", "standard")),
            extreme_divisor=int(data.get("extreme_divisor", 5)),
            hard_divisor=int(data.get("hard_divisor", 2)),
        )

    @classmethod
    def from_json(cls, text: str) -> "CocHouseRules":
        """从 JSON 字符串导入房规。"""
        return cls.from_dict(json.loads(text))

    @classmethod
    def from_json_file(cls, path: str) -> "CocHouseRules":
        """从 JSON 文件导入房规。"""
        with open(path, "r", encoding="utf-8") as f:
            return cls.from_dict(json.load(f))

    def to_dict(self) -> dict:
        return {
            "critical": self.critical.value,
            "fumble": self.fumble.value,
            "extreme_divisor": self.extreme_divisor,
            "hard_divisor": self.hard_divisor,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)
