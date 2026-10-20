"""规则库 RAG 检索：导入规则文本 → 按章节切块 → 检索引用。

零第三方依赖。检索默认用关键词打分（中文按字符二元组、ASCII 按词）；
注入 embedder 后 search() 自动切换到向量检索（余弦相似度）。

- 切块：按 Markdown 标题分节，节内按段落聚合成 ≤ max_chars 的块
- 持久化：JSON（chunks + order，source 元数据随块保存）
"""

from __future__ import annotations

import glob
import json
import math
import os
import re
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*$", re.MULTILINE)
_ASCII_WORD_RE = re.compile(r"[a-z0-9]+")
_CJK_RE = re.compile(r"[一-鿿]")


def tokenize(text: str) -> List[str]:
    """中文按字符二元组、ASCII 按词切 token。"""
    text = text.lower()
    tokens: List[str] = []
    for m in _ASCII_WORD_RE.finditer(text):
        tokens.append(m.group())
    cjk = "".join(_CJK_RE.findall(text))
    if len(cjk) == 1:
        tokens.append(cjk)
    for i in range(len(cjk) - 1):
        tokens.append(cjk[i:i + 2])
    return tokens


@dataclass
class RuleChunk:
    id: str
    title: str   # 所属章节标题（空 = 无标题）
    text: str
    source: str
    order: int

    def to_dict(self) -> dict:
        return {
            "id": self.id, "title": self.title, "text": self.text,
            "source": self.source, "order": self.order,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "RuleChunk":
        return cls(**d)


@dataclass
class SearchResult:
    chunk: RuleChunk
    score: float


def chunk_text(text: str, *, source: str = "", max_chars: int = 800) -> List[RuleChunk]:
    """按标题分节、节内按段落聚合成块。"""
    matches = list(_HEADING_RE.finditer(text))
    sections: List[tuple] = []  # (title, body)
    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        sections.append((m.group(2).strip(), text[start:end].strip()))
    if not matches and text.strip():
        sections.append(("", text.strip()))

    chunks: List[RuleChunk] = []
    idx = 0
    for title, body in sections:
        for para in _split_body(body, max_chars):
            chunks.append(RuleChunk(
                id=str(idx), title=title, text=para, source=source, order=idx,
            ))
            idx += 1
    return chunks


def _split_body(body: str, max_chars: int) -> List[str]:
    paras = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]
    chunks: List[str] = []
    buf = ""
    for p in paras:
        if buf and len(buf) + 1 + len(p) > max_chars:
            chunks.append(buf)
            buf = p
        else:
            buf = f"{buf}\n{p}" if buf else p
    if buf:
        chunks.append(buf)
    # 兜底：超长块按 max_chars 硬切
    final: List[str] = []
    for c in chunks:
        while len(c) > max_chars:
            final.append(c[:max_chars])
            c = c[max_chars:]
        if c:
            final.append(c)
    return final


def _cosine(a: List[float], b: List[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


@dataclass
class RuleStore:
    chunks: Dict[str, RuleChunk] = field(default_factory=dict)
    order: List[str] = field(default_factory=list)
    _embedder: Optional[Callable[[str], List[float]]] = field(default=None, repr=False, compare=False)

    # ---- 导入 ----

    def add_text(self, text: str, *, source: str = "") -> int:
        """导入规则文本，按章节切块。返回新增块数。"""
        new = chunk_text(text, source=source)
        for c in new:
            c.id = str(len(self.order))
            self.chunks[c.id] = c
            self.order.append(c.id)
        return len(new)

    def add_file(self, path: str) -> int:
        """导入规则文件（UTF-8），source = 文件名。返回新增块数。"""
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
        return self.add_text(text, source=os.path.basename(path))

    def add_dir(self, directory: str) -> int:
        """批量导入目录下所有 .md/.txt 规则文件。返回新增块数。"""
        total = 0
        for p in sorted(glob.glob(os.path.join(directory, "*.md"))
                        + glob.glob(os.path.join(directory, "*.txt"))):
            total += self.add_file(p)
        return total

    # ---- 查询 ----

    def get(self, cid: str) -> RuleChunk:
        return self.chunks[cid]

    def sources(self) -> List[str]:
        seen: set = set()
        out: List[str] = []
        for cid in self.order:
            s = self.chunks[cid].source
            if s and s not in seen:
                seen.add(s)
                out.append(s)
        return out

    def __len__(self) -> int:
        return len(self.chunks)

    # ---- 检索 ----

    def set_embedder(self, fn: Callable[[str], List[float]]) -> None:
        """注入向量化函数（text → 向量）；注入后 search 自动走向量检索。"""
        self._embedder = fn

    def search(self, query: str, *, top_k: int = 5) -> List[SearchResult]:
        if self._embedder is not None:
            return self._vector_search(query, top_k)
        return self._keyword_search(query, top_k)

    def _keyword_search(self, query: str, top_k: int) -> List[SearchResult]:
        q = set(tokenize(query))
        if not q:
            return []
        scored: List[tuple] = []
        for cid in self.order:
            c = self.chunks[cid]
            overlap = len(q & set(tokenize(c.text)))
            if overlap == 0:
                continue
            scored.append((overlap / len(q), c))
        scored.sort(key=lambda x: (-x[0], x[1].order))
        return [SearchResult(c, s) for s, c in scored[:top_k]]

    def _vector_search(self, query: str, top_k: int) -> List[SearchResult]:
        qv = self._embedder(query)
        scored: List[tuple] = []
        for cid in self.order:
            c = self.chunks[cid]
            scored.append((_cosine(qv, self._embedder(c.text)), c))
        scored.sort(key=lambda x: -x[0])
        return [SearchResult(c, s) for s, c in scored[:top_k] if s > 0]

    # ---- 持久化 ----

    def save(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as f:
            json.dump({
                "order": self.order,
                "chunks": [self.chunks[cid].to_dict() for cid in self.order],
            }, f, ensure_ascii=False, indent=2)

    @classmethod
    def load(cls, path: str) -> "RuleStore":
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        store = cls()
        for d in data["chunks"]:
            c = RuleChunk.from_dict(d)
            store.chunks[c.id] = c
        store.order = list(data.get("order", [c.id for c in store.chunks.values()]))
        return store
