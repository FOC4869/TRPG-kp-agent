"""Grounded rule evidence for the AI KP; no model key is required.

RetrievalService().search(query) returns JSON-friendly evidence dictionaries.
Use cache_path to persist a rules index. Attach an embedder and stable model name
(e.g. provider/model/dimension) to build/reuse embeddings once per corpus revision.
Scores are ranking signals, not probabilities of correctness.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Callable, Optional

from trpg.rules_store import RuleStore, _identity

_DEFAULT_RULES = Path(__file__).resolve().parents[1] / "data" / "agent_rules.md"
_INDEX_VERSION = "agent-rules-v2"


class RetrievalService:
    def __init__(self, rule_path: Optional[str | Path] = None,
                 cache_path: Optional[str | Path] = None,
                 embedder: Optional[Callable[[str], list[float]]] = None,
                 embedding_model: Optional[str] = None):
        self.rule_path = Path(rule_path) if rule_path is not None else _DEFAULT_RULES
        self.cache_path = Path(cache_path) if cache_path is not None else None
        self.embedder = embedder
        self.embedding_model = embedding_model
        self.store = RuleStore()
        self.rebuild(force=False)

    def _fingerprint(self) -> str:
        return hashlib.sha256(_INDEX_VERSION.encode() + self.rule_path.read_bytes()).hexdigest()

    def rebuild(self, *, force: bool = True) -> int:
        """Load an unchanged cache or rebuild after a source edit; returns chunk count."""
        fingerprint = self._fingerprint()
        loaded = False
        if not force and self.cache_path is not None and self.cache_path.exists():
            try:
                store = RuleStore.load(str(self.cache_path))
                if store.cache_metadata.get("document_fingerprint") == fingerprint:
                    self.store, loaded = store, True
            except (OSError, ValueError, TypeError, KeyError):
                # A corrupt or old cache can always be reconstructed from source.
                pass
        if not loaded:
            self.store = RuleStore()
            self.store.add_file(str(self.rule_path))
            self.store.cache_metadata["document_fingerprint"] = fingerprint
        if self.embedder is not None:
            self.store.set_embedder(self.embedder, model_id=self.embedding_model)
        if self.cache_path is not None:
            self.store.save(str(self.cache_path))
        return len(self.store)

    def search(self, query: str, top_k: int = 4) -> list[dict]:
        """Return evidence_id, text, title, source, page numbers, edition, and score.

        pdf_page and printed_page are one-based, or None when unverified. Stable
        evidence IDs are content-derived; empty/unmatched queries return [].
        This facade contains only rules, never scenario secrets or player state.
        """
        return [{
            "evidence_id": f"rule_{_identity(result.chunk)[:16]}",
            "text": result.chunk.text,
            "title": result.chunk.title,
            "source": result.chunk.source,
            "pdf_page": result.chunk.pdf_page,
            "printed_page": result.chunk.printed_page,
            "edition": result.chunk.edition,
            "score": result.score,
        } for result in self.store.search(query, top_k=top_k)]
