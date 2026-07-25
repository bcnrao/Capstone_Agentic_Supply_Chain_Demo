"""ChromaDB-backed retriever for the Impact and Mitigation agents.

The other five collections stay on the local hash-vector store (``retriever.py``).
Impact + Mitigation use a real Chroma persistent collection with semantic
embeddings (Chroma's default all-MiniLM-L6-v2 ONNX model), so those two agents
do true embedding-based vector search.

Design notes
------------
* Documents are embedded once at build time and persisted under
  ``<data_dir>/chroma`` (``chromadb.PersistentClient``).  A content signature
  stored on the collection lets us skip re-embedding when nothing changed.
* Chroma metadata values must be scalars, but our documents carry list-valued
  fields (``products``, ``lanes``, ``best_for``).  We store only the scalar
  ``category`` / ``kind`` (for ``where`` filtering) plus the full original
  metadata as a JSON blob (``_meta_json``), and reconstruct the rich
  ``Document.metadata`` on the way out so the agents see it unchanged.
* Everything is best-effort: if chromadb is missing, disabled, or the model
  can't be fetched, the caller falls back to the local ``LocalRetriever``.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from pathlib import Path
from typing import Callable

from agentic_scd.config import get_settings
from agentic_scd.rag.retriever import Document, score_document, unique_documents

logger = logging.getLogger(__name__)

CHROMA_MODE = "chroma_semantic_minilm"


def chroma_enabled() -> bool:
    """True if chromadb is importable and not explicitly disabled."""
    if os.getenv("AGENTIC_SCD_USE_CHROMA", "1").strip().lower() in {"0", "false", "no", "off"}:
        return False
    try:
        import chromadb  # noqa: F401
    except Exception:
        return False
    return True


def _chroma_path() -> Path:
    settings = get_settings()
    base = Path(getattr(settings, "data_dir", Path.home() / ".agentic_scd"))
    path = base / "chroma"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _signature(documents: list[Document]) -> str:
    digest = hashlib.sha256()
    for doc in sorted(documents, key=lambda d: d.doc_id):
        digest.update(doc.doc_id.encode("utf-8"))
        digest.update(b"\x1f")
        digest.update(doc.text.encode("utf-8"))
        digest.update(b"\x1f")
        digest.update(json.dumps(doc.metadata, sort_keys=True, default=str).encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()[:16]


def _flatten_metadata(meta: dict) -> dict:
    """Scalar-only metadata Chroma can store, plus a JSON blob of the original."""
    return {
        "category": str(meta.get("category") or "none"),
        "kind": str(meta.get("kind") or "none"),
        "_meta_json": json.dumps(meta, default=str),
    }


class ChromaRetriever:
    """Drop-in replacement for LocalRetriever backed by a Chroma collection."""

    mode = CHROMA_MODE

    def __init__(self, collection_name: str, provider: Callable[[], list[Document]]) -> None:
        import chromadb  # imported after chroma_enabled() gate

        self.collection_name = collection_name
        self._provider = provider
        self._client = chromadb.PersistentClient(path=str(_chroma_path()))
        self._collection = self._build()  # eager: surfaces model/download errors now

    def _build(self):
        docs = [d for d in unique_documents(self._provider()) if (d.text or "").strip()]
        sig = _signature(docs)
        name = self.collection_name
        try:
            existing = self._client.get_collection(name)
            if (existing.metadata or {}).get("sig") == sig and existing.count() == len(docs):
                return existing
            self._client.delete_collection(name)
        except Exception:
            pass  # collection absent or unreadable — (re)create below
        collection = self._client.create_collection(name, metadata={"sig": sig})
        if docs:
            collection.add(
                ids=[d.doc_id for d in docs],
                documents=[d.text for d in docs],
                metadatas=[_flatten_metadata(d.metadata) for d in docs],
            )
        logger.info("chroma collection '%s' built with %d documents", name, len(docs))
        return collection

    def search(self, query: str, top_k: int = 4, category: str | None = None) -> list[Document]:
        text = (query or "").strip()
        if not text:
            return []
        where = {"category": category} if category else None
        try:
            res = self._collection.query(query_texts=[text], n_results=top_k, where=where)
        except Exception as exc:
            logger.warning("chroma query failed on '%s' (%s)", self.collection_name, exc)
            return []
        ids = (res.get("ids") or [[]])[0]
        texts = (res.get("documents") or [[]])[0]
        metas = (res.get("metadatas") or [[]])[0]
        out: list[Document] = []
        for doc_id, doc_text, meta in zip(ids, texts, metas, strict=False):
            blob = meta.get("_meta_json") if isinstance(meta, dict) else None
            try:
                original = json.loads(blob) if blob else {}
            except Exception:
                original = {}
            out.append(Document(doc_id=str(doc_id), text=str(doc_text), metadata=original))
        return out

    @property
    def documents(self) -> list[Document]:
        return unique_documents(self._provider())

    def score(self, query: str, document: Document) -> float:
        return score_document(query, document)
