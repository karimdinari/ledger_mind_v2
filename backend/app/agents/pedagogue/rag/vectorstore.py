"""Embedded ChromaDB vector store (persisted on disk, no separate server)."""
from __future__ import annotations

import chromadb

from app.config import settings

_client = None
_collection = None


def reset() -> None:
    """Drop in-memory client so the next call reopens from disk (e.g. after seed)."""
    global _client, _collection
    _client = None
    _collection = None


def get_collection():
    global _client, _collection
    if _collection is None:
        _client = chromadb.PersistentClient(path=settings.pedagogue_chroma_dir)
        _collection = _client.get_or_create_collection(
            name=settings.pedagogue_chroma_collection,
            metadata={"hnsw:space": "cosine"},
        )
    return _collection


def _is_stale_index_error(exc: BaseException) -> bool:
    msg = str(exc).lower()
    return "nothing found on disk" in msg or "hnsw" in msg


def upsert(ids, embeddings, documents, metadatas):
    try:
        get_collection().upsert(
            ids=ids, embeddings=embeddings, documents=documents, metadatas=metadatas
        )
    except Exception as exc:
        if not _is_stale_index_error(exc):
            raise
        reset()
        get_collection().upsert(
            ids=ids, embeddings=embeddings, documents=documents, metadatas=metadatas
        )


def query(embedding, n_results: int = 6, where: dict | None = None):
    def _do():
        return get_collection().query(
            query_embeddings=[embedding],
            n_results=n_results,
            where=where,
            include=["documents", "metadatas", "distances"],
        )

    try:
        return _do()
    except Exception as exc:
        if not _is_stale_index_error(exc):
            raise
        reset()
        return _do()


def count() -> int:
    try:
        return get_collection().count()
    except Exception as exc:
        if not _is_stale_index_error(exc):
            raise
        reset()
        return get_collection().count()
