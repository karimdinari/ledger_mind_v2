"""Embeddings for guidance RAG — local sentence-transformers or Mistral API."""
from __future__ import annotations

import httpx

from app.config import settings

MISTRAL_BASE = "https://api.mistral.ai/v1"
_local_model = None


def _get_local_model():
    global _local_model
    if _local_model is None:
        from sentence_transformers import SentenceTransformer

        _local_model = SentenceTransformer(settings.pedagogue_local_embedding_model)
    return _local_model


def embed(texts: list[str], *, is_query: bool = False) -> list[list[float]]:
    if settings.pedagogue_embeddings_provider == "mistral":
        return _embed_mistral(texts)
    model = _get_local_model()
    prefix = "query: " if is_query else "passage: "
    prepared = [prefix + t for t in texts]
    return model.encode(prepared, normalize_embeddings=True).tolist()


def _embed_mistral(texts: list[str]) -> list[list[float]]:
    if not settings.mistral_api_key:
        raise RuntimeError(
            "MISTRAL_API_KEY is required when PEDAGOGUE_EMBEDDINGS_PROVIDER=mistral"
        )
    with httpx.Client(timeout=60) as client:
        r = client.post(
            f"{MISTRAL_BASE}/embeddings",
            headers={"Authorization": f"Bearer {settings.mistral_api_key}"},
            json={"model": "mistral-embed", "input": texts},
        )
        r.raise_for_status()
        return [d["embedding"] for d in r.json()["data"]]
