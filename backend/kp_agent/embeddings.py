"""Opt-in OpenAI embeddings for rule retrieval.

No embedding model has been selected for the group. The default mode is keyword
and makes no API calls. Setting KP_RETRIEVAL_MODE=openai_embeddings explicitly
opts in to indexing/query calls; OPENAI_EMBEDDING_MODEL must be supplied by the
user. This module never chooses a model or silently falls back after an API error.

SDK reference:
https://developers.openai.com/api/reference/python/resources/embeddings/methods/create
"""
from __future__ import annotations

import hashlib
import math
import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .config import load_local_env
from .retrieval import RetrievalService


class EmbeddingConfigurationError(ValueError):
    """The explicitly selected retrieval mode cannot start with this config."""


class EmbeddingCallError(RuntimeError):
    """A selected embedding provider failed or returned unusable data."""


class OpenAIEmbedder:
    """Callable text -> vector adapter; injected clients allow offline tests.

    Document and query vectors must have the same actual dimension. An optional
    dimensions value is forwarded to the API and verified against its response.
    No model names or dimensions are guessed.
    """

    def __init__(self, *, model: str, api_key: str | None = None,
                 base_url: str | None = None, dimensions: int | None = None,
                 client: Any | None = None) -> None:
        if not isinstance(model, str) or not model.strip():
            raise EmbeddingConfigurationError("请明确填写 OPENAI_EMBEDDING_MODEL；尚未替项目选择向量模型。")
        if dimensions is not None and (type(dimensions) is not int or dimensions <= 0):
            raise EmbeddingConfigurationError("OPENAI_EMBEDDING_DIMENSIONS 必须是正整数或留空。")
        self.model = model.strip()
        self.dimensions = dimensions
        self._actual_dimension = dimensions
        endpoint = (base_url or "https://api.openai.com/v1").rstrip("/")
        endpoint_hash = hashlib.sha256(endpoint.encode("utf-8")).hexdigest()[:16]
        # Include provider identity and requested dimensions so incompatible
        # embeddings with an identical model name cannot share a cached index.
        self.cache_key = f"openai_embeddings:{self.model}:{endpoint_hash}:dim={dimensions or 'default'}"
        if client is None:
            if not api_key or not api_key.strip():
                raise EmbeddingConfigurationError("向量模式需要 OPENAI_API_KEY。")
            try:
                from openai import OpenAI
            except ImportError:
                raise EmbeddingConfigurationError("请先安装 Agent 依赖中的 openai SDK。") from None
            options = {"api_key": api_key.strip(), "timeout": 30.0, "max_retries": 0}
            if base_url:
                options["base_url"] = base_url
            client = OpenAI(**options)
        self.client = client

    def __call__(self, text: str) -> list[float]:
        if not isinstance(text, str) or not text.strip():
            raise ValueError("不能为一个空问题或空规则生成向量。")
        request = {"input": text, "model": self.model, "encoding_format": "float"}
        if self.dimensions is not None:
            request["dimensions"] = self.dimensions
        try:
            response = self.client.embeddings.create(**request)
        except Exception:
            # Don't surface provider exception text, which can contain credentials
            # or request contents. No automatic fallback or second paid request.
            raise EmbeddingCallError("向量服务调用失败；未改用关键词模式，请检查网络、账号及向量模型设置。") from None
        try:
            if len(response.data) != 1:
                raise ValueError("expected exactly one vector")
            raw = response.data[0].embedding
            if isinstance(raw, (str, bytes)):
                raise ValueError("expected numeric vector")
            vector = [float(value) for value in raw]
            if not vector or any(not math.isfinite(value) for value in vector):
                raise ValueError("empty or nonfinite vector")
            if not any(vector):
                raise ValueError("zero vector")
        except (AttributeError, TypeError, ValueError, OverflowError):
            raise EmbeddingCallError("向量服务返回了无法使用的向量；未改用关键词模式。") from None
        if self._actual_dimension is None:
            self._actual_dimension = len(vector)
        elif len(vector) != self._actual_dimension:
            raise EmbeddingCallError("向量维度不一致；请核对模型和 dimensions 设置并重建索引。")
        return vector


def retrieval_from_env(cache_path: str | Path | None = None, *,
                       client: Any | None = None,
                       environ: Mapping[str, str] | None = None,
                       rule_path: str | Path | None = None) -> RetrievalService:
    """Build a rules service in keyword (default) or explicit vector mode.

    Keyword mode ignores API credentials and does not import/construct OpenAI.
    In vector mode initial construction embeds uncached documents and saves them
    when cache_path is supplied; repeated searches only embed the current query.
    client/environ/rule_path are injectable for tests; no real key is needed there.
    """
    if environ is None:
        load_local_env()
    values = os.environ if environ is None else environ
    mode = values.get("KP_RETRIEVAL_MODE", "keyword").strip().lower() or "keyword"
    if mode == "keyword":
        return RetrievalService(rule_path=rule_path, cache_path=cache_path)
    if mode != "openai_embeddings":
        raise EmbeddingConfigurationError("KP_RETRIEVAL_MODE 仅支持 keyword 或 openai_embeddings。")
    model = values.get("OPENAI_EMBEDDING_MODEL", "").strip()
    api_key = values.get("OPENAI_API_KEY", "").strip()
    if not model:
        raise EmbeddingConfigurationError("请明确填写 OPENAI_EMBEDDING_MODEL；尚未替项目选择向量模型。")
    if not api_key:
        raise EmbeddingConfigurationError("openai_embeddings 模式需要 OPENAI_API_KEY。")
    raw_dimensions = values.get("OPENAI_EMBEDDING_DIMENSIONS", "").strip()
    dimensions = None
    if raw_dimensions:
        try:
            dimensions = int(raw_dimensions)
        except ValueError:
            raise EmbeddingConfigurationError("OPENAI_EMBEDDING_DIMENSIONS 必须是正整数或留空。") from None
    embedder = OpenAIEmbedder(
        model=model, api_key=api_key,
        base_url=values.get("OPENAI_BASE_URL", "").strip() or None,
        dimensions=dimensions, client=client,
    )
    return RetrievalService(rule_path=rule_path, cache_path=cache_path,
                            embedder=embedder, embedding_model=embedder.cache_key)
