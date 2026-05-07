"""ChromaDB vector store for semantic matching of raw materials and rules."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import chromadb
from chromadb.config import Settings as ChromaSettings

from app.core.config import get_settings

# Collection names
RAW_MATERIAL_COLLECTION = "raw_material_embeddings"
RULE_COLLECTION = "rule_embeddings"


def _get_chroma_client():
    """Create or return a persistent ChromaDB client."""
    settings = get_settings()
    path = Path(settings.chroma_persist_path)
    path.mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(
        path=str(path),
        settings=ChromaSettings(anonymized_telemetry=False),
    )


def _get_embedding_function():
    """
    Return embedding function. Prefer OpenAI if API key is set, else default (all-MiniLM-L6-v2).
    """
    settings = get_settings()
    if settings.openai_api_key:
        from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction
        return OpenAIEmbeddingFunction(
            api_key=settings.openai_api_key,
            model_name="text-embedding-3-small",
        )
    # Default: sentence-transformers all-MiniLM-L6-v2 (local, no API)
    from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
    return SentenceTransformerEmbeddingFunction(
        model_name="all-MiniLM-L6-v2",
    )


_client: Optional[chromadb.PersistentClient] = None


def get_client() -> chromadb.PersistentClient:
    """Lazily initialize and return ChromaDB client."""
    global _client
    if _client is None:
        _client = _get_chroma_client()
    return _client


def get_raw_material_collection():
    """Get or create the raw_material_embeddings collection."""
    client = get_client()
    try:
        return client.get_collection(
            name=RAW_MATERIAL_COLLECTION,
            embedding_function=_get_embedding_function(),
        )
    except Exception:
        return client.create_collection(
            name=RAW_MATERIAL_COLLECTION,
            embedding_function=_get_embedding_function(),
            metadata={"description": "Raw material descriptions for semantic matching"},
        )


def get_rule_collection():
    """Get or create the rule_embeddings collection."""
    client = get_client()
    try:
        return client.get_collection(
            name=RULE_COLLECTION,
            embedding_function=_get_embedding_function(),
        )
    except Exception:
        return client.create_collection(
            name=RULE_COLLECTION,
            embedding_function=_get_embedding_function(),
            metadata={"description": "Taxonomy rule conditions for retrieval"},
        )


# --- Upsert helpers ---


def upsert_raw_material(record_id: str, document: str, metadata: Optional[dict] = None) -> None:
    """Add or update a raw material in the vector store."""
    col = get_raw_material_collection()
    col.upsert(
        ids=[record_id],
        documents=[document],
        metadatas=[metadata or {}],
    )


def upsert_raw_materials_batch(
    ids: list[str],
    documents: list[str],
    metadatas: Optional[list[dict]] = None,
) -> None:
    """Batch upsert raw materials."""
    col = get_raw_material_collection()
    metas = metadatas if metadatas is not None else [{}] * len(ids)
    col.upsert(ids=ids, documents=documents, metadatas=metas)


def upsert_rule(record_id: str, document: str, metadata: Optional[dict] = None) -> None:
    """Add or update a rule in the rule_embeddings collection."""
    col = get_rule_collection()
    col.upsert(
        ids=[record_id],
        documents=[document],
        metadatas=[metadata or {}],
    )


def upsert_rules_batch(
    ids: list[str],
    documents: list[str],
    metadatas: Optional[list[dict]] = None,
) -> None:
    """Batch upsert rules."""
    col = get_rule_collection()
    metas = metadatas if metadatas is not None else [{}] * len(ids)
    col.upsert(ids=ids, documents=documents, metadatas=metas)


# --- Query helpers ---


def query_raw_materials(
    query_text: str,
    n_results: int = 5,
    where: Optional[dict] = None,
) -> dict[str, Any]:
    """
    Query raw_material_embeddings by semantic similarity.
    Returns ids, distances, metadatas, documents.
    """
    col = get_raw_material_collection()
    return col.query(
        query_texts=[query_text],
        n_results=n_results,
        where=where,
        include=["documents", "metadatas", "distances"],
    )


def query_rules(
    query_text: str,
    n_results: int = 5,
    where: Optional[dict] = None,
) -> dict[str, Any]:
    """
    Query rule_embeddings by semantic similarity.
    Returns ids, distances, metadatas, documents.
    """
    col = get_rule_collection()
    return col.query(
        query_texts=[query_text],
        n_results=n_results,
        where=where,
        include=["documents", "metadatas", "distances"],
    )


def delete_raw_material(record_id: str) -> None:
    """Remove a raw material from the vector store."""
    col = get_raw_material_collection()
    col.delete(ids=[record_id])


def delete_rule(record_id: str) -> None:
    """Remove a rule from the vector store."""
    col = get_rule_collection()
    col.delete(ids=[record_id])
