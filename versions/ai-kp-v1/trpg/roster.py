"""角色花名册：一队角色 + 当前操作指针，支持批量导入、切换、目录存档。

- 从 Excel 导入：id = 文件名 stem（保留中文，同文件重导 = 覆盖更新该卡）
- 手工 add：id = 名字 slug（ASCII 化，冲突追加 -2/-3，纯中文回退 char）
- 切换角色：改 active_id 指针，不动任何角色数据
- 存档：一个目录 = roster.json（active_id + order）+ 每角色 <id>.json
"""

from __future__ import annotations

import glob
import json
import os
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .character import Character
from .excel_import import load_character_from_xlsx


def _slug(name: str) -> str:
    """名字 → ASCII slug（去变音、非字母数字→-、小写）。纯中文回退 'char'。"""
    nfkd = unicodedata.normalize("NFKD", name)
    ascii_name = "".join(c for c in nfkd if not unicodedata.combining(c))
    ascii_name = ascii_name.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_name).strip("-").lower()
    return slug or "char"


def _unique(base: str, taken: Dict[str, Character]) -> str:
    """在已占用 id 中取不冲突者：base、base-2、base-3……"""
    if base not in taken:
        return base
    n = 2
    while f"{base}-{n}" in taken:
        n += 1
    return f"{base}-{n}"


@dataclass
class Roster:
    characters: Dict[str, Character] = field(default_factory=dict)
    active_id: Optional[str] = None
    order: List[str] = field(default_factory=list)

    # ---- 查询 ----

    @property
    def active(self) -> Optional[Character]:
        """当前操作角色（无则 None）。"""
        return self.characters.get(self.active_id) if self.active_id else None

    def get(self, cid: str) -> Character:
        if cid not in self.characters:
            raise KeyError(f"未知角色 id：{cid}")
        return self.characters[cid]

    def list(self) -> List[Tuple[str, str]]:
        """返回 [(id, 名字), ...]，按加入顺序。"""
        return [(cid, self.characters[cid].name) for cid in self.order]

    def __len__(self) -> int:
        return len(self.characters)

    def __contains__(self, cid: str) -> bool:
        return cid in self.characters

    # ---- 增删切换 ----

    def add(self, char: Character, cid: Optional[str] = None, *, activate: bool = True) -> str:
        """登记一个角色，返回其 id。cid 缺省由名字生成唯一 slug；显式 cid 同名覆盖。"""
        if cid is None:
            cid = _unique(_slug(char.name), self.characters)
        is_new = cid not in self.characters
        self.characters[cid] = char
        if is_new:
            self.order.append(cid)
        if activate or self.active_id is None:
            self.active_id = cid
        return cid

    def import_xlsx(self, path: str, *, activate: bool = True) -> str:
        """导入一张 Excel 角色卡，id = 文件名 stem；同名重导覆盖更新。"""
        char = load_character_from_xlsx(path)
        stem = os.path.splitext(os.path.basename(path))[0]
        return self.add(char, cid=stem, activate=activate)

    @classmethod
    def import_dir(cls, directory: str) -> "Roster":
        """批量导入目录下所有 .xlsx，激活第一张。"""
        roster = cls()
        for p in sorted(glob.glob(os.path.join(directory, "*.xlsx"))):
            roster.import_xlsx(p)
        return roster

    def switch(self, cid: str) -> Character:
        """切换当前操作角色，返回该角色。"""
        if cid not in self.characters:
            raise KeyError(f"未知角色 id：{cid}（可用 list() 查看）")
        self.active_id = cid
        return self.characters[cid]

    def remove(self, cid: str) -> Character:
        """移除角色；若移除的是当前角色，回退到队首。"""
        char = self.characters.pop(cid)
        if cid in self.order:
            self.order.remove(cid)
        if self.active_id == cid:
            self.active_id = self.order[0] if self.order else None
        return char

    # ---- 存档 ----

    def save(self, directory: str) -> None:
        """写 directory/roster.json + 每角色 <id>.json。"""
        os.makedirs(directory, exist_ok=True)
        with open(os.path.join(directory, "roster.json"), "w", encoding="utf-8") as f:
            json.dump({"active_id": self.active_id, "order": self.order}, f, ensure_ascii=False, indent=2)
        for cid, char in self.characters.items():
            with open(os.path.join(directory, f"{cid}.json"), "w", encoding="utf-8") as f:
                json.dump(char.to_dict(), f, ensure_ascii=False, indent=2)

    @classmethod
    def load(cls, directory: str) -> "Roster":
        """从目录恢复整队 + 当前操作角色。"""
        with open(os.path.join(directory, "roster.json"), "r", encoding="utf-8") as f:
            meta = json.load(f)
        roster = cls(active_id=meta.get("active_id"))
        for cid in meta.get("order", []):
            with open(os.path.join(directory, f"{cid}.json"), "r", encoding="utf-8") as f:
                roster.characters[cid] = Character.from_dict(json.load(f))
            roster.order.append(cid)
        # 目录里漏登记在 order 的 <id>.json 也一并载入
        for p in glob.glob(os.path.join(directory, "*.json")):
            cid = os.path.splitext(os.path.basename(p))[0]
            if cid == "roster" or cid in roster.characters:
                continue
            with open(p, "r", encoding="utf-8") as f:
                roster.characters[cid] = Character.from_dict(json.load(f))
            roster.order.append(cid)
        if roster.active_id and roster.active_id not in roster.characters:
            roster.active_id = roster.order[0] if roster.order else None
        return roster
