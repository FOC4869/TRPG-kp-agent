"""Small, dependency-free rules retrieval with optional cached embeddings.

Existing RuleStore APIs remain available. Markdown sections may carry JSON metadata:
    <!-- rule_meta: {"source": "rules.pdf", "pdf_page": 66, "edition": "COC7"} -->
Unknown page numbers stay null. The default search works offline; set_embedder() builds
vectors once, and save()/load() preserve them under an explicit embedding model name.
"""
from __future__ import annotations

import glob
import hashlib
import json
import math
import os
import re
import tempfile
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*$", re.MULTILINE)
_META_RE = re.compile(r"<!--\s*rule_meta:\s*(\{.*?\})\s*-->", re.DOTALL)
_ASCII_WORD_RE = re.compile(r"[a-z0-9]+")
_CJK_RUN_RE = re.compile(r"[\u4e00-\u9fff]+")
_QUERY_ALIASES = {
    "潜行": ("偷偷", "悄悄", "蹑手蹑脚", "躲藏", "不被发现", "不让人发现", "轻手轻脚", "绕到身后"),
    "侦查": ("检查", "翻找", "找找", "搜查", "搜索", "找线索", "仔细看", "观察", "查找"),
    "聆听": ("听听", "偷听", "听见", "听到", "贴着门", "耳朵", "声音", "听一下", "动静", "仔细听", "听一听", "倾听"),
    "理智": ("san", "精神", "吓", "恐怖", "掉san"),
    "临时性疯狂": ("掉五点", "掉5点", "损失5", "一次损失", "一次掉", "单次损失", "智力检定"),
    "孤注一骰": ("再试", "重试", "再来一次", "再找一次", "孤注一掷", "重投"),
    "成功等级": ("成功率", "掷骰", "判定", "困难成功", "极难成功"),
    "不定性疯狂": ("一天", "一天累计", "单日", "五分之一", "日初"),
    "奖励骰 惩罚骰": ("奖励", "惩罚", "有利", "不利"),
}
_QUERY_STOPWORDS = {"使用", "规则", "一下", "怎么", "什么", "我们", "可以", "需要",
                    "进行", "一个", "这个", "当前", "玩家", "角色", "场景", "相关",
                    "的话", "请问", "帮我", "我想"}


def tokenize(text: str) -> List[str]:
    """ASCII words and Chinese bigrams; don't invent bigrams across punctuation."""
    text = text.lower()
    tokens = _ASCII_WORD_RE.findall(text)
    for match in _CJK_RUN_RE.finditer(text):
        run = match.group()
        if len(run) == 1:
            tokens.append(run)
        else:
            tokens.extend(run[i:i + 2] for i in range(len(run) - 1))
    return tokens


def _expand_query(query: str) -> str:
    lowered = query.lower()
    return query + " " + " ".join(name for name, aliases in _QUERY_ALIASES.items()
                                    if any(alias in lowered for alias in aliases))


@dataclass
class RuleChunk:
    id: str
    title: str
    text: str
    source: str
    order: int
    pdf_page: Optional[int] = None       # one-based PDF page, not zero-based index
    printed_page: Optional[int] = None   # page printed inside the rulebook
    edition: str = ""
    section: str = ""
    aliases: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"id": self.id, "title": self.title, "text": self.text,
                "source": self.source, "order": self.order,
                "pdf_page": self.pdf_page, "printed_page": self.printed_page,
                "edition": self.edition, "section": self.section, "aliases": self.aliases}

    @classmethod
    def from_dict(cls, d: dict) -> "RuleChunk":
        return cls(**d)


@dataclass
class SearchResult:
    chunk: RuleChunk
    score: float


def _split_body(body: str, max_chars: int) -> List[str]:
    if max_chars <= 0:
        raise ValueError("max_chars must be positive")
    paras = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]
    result, buf = [], ""
    for p in paras:
        if buf and len(buf) + 1 + len(p) > max_chars:
            result.append(buf)
            buf = p
        else:
            buf = f"{buf}\n{p}" if buf else p
    if buf:
        result.append(buf)
    return [part[i:i + max_chars] for part in result for i in range(0, len(part), max_chars)]


def chunk_text(text: str, *, source: str = "", max_chars: int = 800,
               metadata: Optional[dict] = None) -> List[RuleChunk]:
    """Split by heading, preserving explicit per-section source metadata."""
    if max_chars <= 0:
        raise ValueError("max_chars must be positive")
    matches = list(_HEADING_RE.finditer(text))
    sections = []
    if matches:
        if text[:matches[0].start()].strip():
            sections.append(("", text[:matches[0].start()].strip()))
        for i, match in enumerate(matches):
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            sections.append((match.group(2).strip(), text[match.end():end].strip()))
    elif text.strip():
        sections.append(("", text.strip()))
    chunks = []
    for title, body in sections:
        meta = dict(metadata or {})
        for match in _META_RE.finditer(body):
            meta.update(json.loads(match.group(1)))
        body = _META_RE.sub("", body).strip()
        for page_field in ("pdf_page", "printed_page"):
            value = meta.get(page_field)
            if value is not None and (type(value) is not int or value < 1):
                raise ValueError(f"{page_field} must be a positive one-based page or null")
        for paragraph in _split_body(body, max_chars):
            idx = len(chunks)
            chunks.append(RuleChunk(
                id=str(idx), title=title, text=paragraph,
                source=meta.get("source", source), order=idx,
                pdf_page=meta.get("pdf_page"), printed_page=meta.get("printed_page"),
                edition=meta.get("edition", ""), section=meta.get("section", title),
                aliases=list(meta.get("aliases", [])),
            ))
    return chunks


def _cosine(a: List[float], b: List[float]) -> float:
    if len(a) != len(b):
        raise ValueError("embedding dimensions do not match")
    dot = sum(x * y for x, y in zip(a, b))
    na, nb = math.sqrt(sum(x * x for x in a)), math.sqrt(sum(x * x for x in b))
    return dot / (na * nb) if na and nb else 0.0


def _identity(chunk: RuleChunk) -> str:
    data = [chunk.source, chunk.edition, chunk.title, chunk.text,
            chunk.pdf_page, chunk.printed_page, chunk.aliases]
    return hashlib.sha256(json.dumps(data, ensure_ascii=False).encode()).hexdigest()


@dataclass
class RuleStore:
    chunks: Dict[str, RuleChunk] = field(default_factory=dict)
    order: List[str] = field(default_factory=list)
    _embedder: Optional[Callable[[str], List[float]]] = field(default=None, repr=False, compare=False)
    _embeddings: Dict[str, List[float]] = field(default_factory=dict, repr=False)
    _embedding_model: Optional[str] = field(default=None, repr=False)
    _embedding_dimension: Optional[int] = field(default=None, repr=False)
    cache_metadata: dict = field(default_factory=dict)

    def add_text(self, text: str, *, source: str = "", metadata: Optional[dict] = None) -> int:
        seen = {_identity(c) for c in self.chunks.values()}
        count = 0
        for chunk in chunk_text(text, source=source, metadata=metadata):
            identity = _identity(chunk)
            if identity in seen:
                continue
            seen.add(identity)
            cid = str(len(self.order))
            while cid in self.chunks:
                cid = str(int(cid) + 1)
            chunk.id, chunk.order = cid, len(self.order)
            self.chunks[cid] = chunk
            self.order.append(cid)
            count += 1
        if self._embedder is not None:
            self.build_embeddings()
        return count

    def add_file(self, path: str) -> int:
        with open(path, encoding="utf-8") as handle:
            return self.add_text(handle.read(), source=os.path.basename(path))

    def add_dir(self, directory: str) -> int:
        return sum(self.add_file(path) for path in sorted(
            glob.glob(os.path.join(directory, "*.md")) + glob.glob(os.path.join(directory, "*.txt"))))

    def get(self, cid: str) -> RuleChunk:
        return self.chunks[cid]

    def sources(self) -> List[str]:
        return list(dict.fromkeys(self.chunks[cid].source for cid in self.order if self.chunks[cid].source))

    def __len__(self) -> int:
        return len(self.chunks)

    def set_embedder(self, fn: Callable[[str], List[float]], *, model_id: Optional[str] = None) -> None:
        """Build all document vectors now; supply model_id to safely reuse persisted vectors.

        Without model_id, vectors are rebuilt on attachment, avoiding accidental reuse
        between two different callables or provider configurations.
        """
        model = model_id or "anonymous"
        if model_id is None or self._embedding_model != model:
            self._embeddings.clear()
            self._embedding_dimension = None
        self._embedding_model, self._embedder = model, fn
        self.build_embeddings()

    def _validate_vector(self, values) -> List[float]:
        vector = [float(value) for value in values]
        if not vector or any(not math.isfinite(value) for value in vector):
            raise ValueError("embedding must be a nonempty vector of finite numbers")
        if self._embedding_dimension is None:
            self._embedding_dimension = len(vector)
        elif len(vector) != self._embedding_dimension:
            raise ValueError("embedding dimensions do not match the cached model")
        return vector

    def build_embeddings(self) -> None:
        if self._embedder is None:
            return
        for cid in self.order:
            if cid not in self._embeddings:
                self._embeddings[cid] = self._validate_vector(self._embedder(self.chunks[cid].text))

    def search(self, query: str, *, top_k: int = 5) -> List[SearchResult]:
        if top_k <= 0 or not query.strip():
            return []
        if self._embedder is not None:
            return self._vector_search(query, top_k)
        return self._keyword_search(query, top_k)

    def _keyword_search(self, query: str, top_k: int) -> List[SearchResult]:
        query_tokens = set(tokenize(_expand_query(query))) - _QUERY_STOPWORDS
        if not query_tokens:
            return []
        indexed = [(self.chunks[cid], set(tokenize(self.chunks[cid].text + " " + self.chunks[cid].title
                    + " " + " ".join(self.chunks[cid].aliases)))) for cid in self.order]
        frequencies = {token: sum(token in tokens for _, tokens in indexed) for token in query_tokens}
        weights = {token: math.log(1 + (len(indexed) + 1) / (frequency + 1))
                   for token, frequency in frequencies.items()}
        denominator = sum(weights.values()) or 1
        scored = []
        for chunk, tokens in indexed:
            overlap = query_tokens & tokens
            if not overlap:
                continue
            title_tokens = set(tokenize(chunk.title + " " + " ".join(chunk.aliases)))
            score = sum(weights[token] * (1.5 if token in title_tokens else 1) for token in overlap) / denominator
            scored.append(SearchResult(chunk, float(score)))
        scored.sort(key=lambda item: (-item.score, item.chunk.order))
        return scored[:top_k]

    def _vector_search(self, query: str, top_k: int) -> List[SearchResult]:
        self.build_embeddings()
        query_vector = self._validate_vector(self._embedder(query))
        results = [SearchResult(self.chunks[cid], float(_cosine(query_vector, self._embeddings[cid])))
                   for cid in self.order]
        results.sort(key=lambda item: (-item.score, item.chunk.order))
        return [result for result in results[:top_k] if result.score > 0]

    def save(self, path: str) -> None:
        """Atomically replace an index, including optional vectors and provider identity."""
        data = {"schema_version": 2, "order": self.order,
                "chunks": [self.chunks[cid].to_dict() for cid in self.order],
                "embedding_model": self._embedding_model,
                "embedding_dimension": self._embedding_dimension,
                "embeddings": self._embeddings, "cache_metadata": self.cache_metadata}
        target = os.path.abspath(path)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(prefix=".rules-index-", suffix=".tmp", dir=os.path.dirname(target))
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                json.dump(data, handle, ensure_ascii=False, indent=2)
            os.replace(temporary, target)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    @classmethod
    def load(cls, path: str) -> "RuleStore":
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
        if not isinstance(data, dict) or not isinstance(data.get("chunks"), list):
            raise ValueError("invalid rule index document")
        if not isinstance(data.get("embeddings", {}), dict) or not isinstance(data.get("cache_metadata", {}), dict):
            raise ValueError("invalid rule index cache metadata")
        dimension = data.get("embedding_dimension")
        if dimension is not None and (type(dimension) is not int or dimension < 1):
            raise ValueError("invalid cached embedding dimension")
        store = cls()
        for raw in data["chunks"]:
            if not isinstance(raw, dict):
                raise ValueError("invalid rule chunk")
            chunk = RuleChunk.from_dict(raw)
            for page in (chunk.pdf_page, chunk.printed_page):
                if page is not None and (type(page) is not int or page < 1):
                    raise ValueError("invalid cached rule page")
            if chunk.id in store.chunks:
                raise ValueError("duplicate rule chunk ID")
            store.chunks[chunk.id] = chunk
        store.order = list(data.get("order", store.chunks))
        if set(store.order) != set(store.chunks) or len(store.order) != len(set(store.order)):
            raise ValueError("invalid rule index order")
        store._embedding_model = data.get("embedding_model")
        store._embedding_dimension = data.get("embedding_dimension")
        for cid, vector in data.get("embeddings", {}).items():
            if cid in store.chunks:
                store._embeddings[cid] = store._validate_vector(vector)
        store.cache_metadata = data.get("cache_metadata", {})
        return store
