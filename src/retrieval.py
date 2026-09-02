"""Retrieve unique, source-attributed chunks from the local Chroma index."""

from __future__ import annotations

import argparse
from typing import Any

from src import config
from src.embeddings import CollectionMismatchError, effective_max_tokens


class QueryTooLongError(ValueError):
    """Raised when a query exceeds the embedding model's token window."""


def _verify_query_collection(
    collection: Any,
    model: Any,
    expected_model_name: str,
    max_tokens: int,
) -> None:
    metadata = collection.metadata or {}
    expected = {
        "embedding_model": expected_model_name,
        "embedding_dimension": int(model.get_sentence_embedding_dimension()),
        "max_tokens": max_tokens,
    }
    mismatches = [key for key, value in expected.items() if metadata.get(key) != value]
    if mismatches:
        raise CollectionMismatchError(
            f"collection is incompatible with this query ({', '.join(mismatches)}); "
            "use the model and configuration that built the index"
        )


def _embedding_list(embedding: Any) -> list[list[float]]:
    converted = embedding.tolist() if hasattr(embedding, "tolist") else embedding
    return [list(vector) for vector in converted]


def retrieve(
    query: str,
    model: Any,
    collection: Any,
    *,
    top_k: int = config.N_RESULTS,
    expected_model_name: str = config.EMBEDDING_MODEL,
    max_tokens: int | None = config.EMBEDDING_MAX_TOKENS,
) -> list[dict[str, str | int | float]]:
    """Return the closest unique original chunks, deduplicating vector windows."""
    max_tokens = effective_max_tokens(model, max_tokens)
    if top_k <= 0:
        raise ValueError("top_k must be positive")
    if not query.strip():
        raise ValueError("query must not be empty")
    query_tokens = model.tokenizer.encode(query, add_special_tokens=True)
    if len(query_tokens) > max_tokens:
        raise QueryTooLongError(
            f"query has {len(query_tokens)} tokens and exceeds the {max_tokens}-token limit"
        )
    _verify_query_collection(collection, model, expected_model_name, max_tokens)

    query_embedding = _embedding_list(
        model.encode(
            [query],
            show_progress_bar=False,
            convert_to_numpy=True,
            normalize_embeddings=True,
        )
    )
    total_records = collection.count()
    if total_records == 0:
        return []

    candidate_count = min(total_records, max(top_k * 2, top_k))
    unique: dict[str, dict[str, str | int | float]] = {}
    while True:
        raw = collection.query(
            query_embeddings=query_embedding,
            n_results=candidate_count,
            include=["documents", "metadatas", "distances"],
        )
        ids = raw["ids"][0]
        documents = raw["documents"][0]
        metadatas = raw["metadatas"][0]
        distances = raw["distances"][0]
        unique.clear()
        for _record_id, document, metadata, distance in zip(ids, documents, metadatas, distances):
            chunk_id = metadata["chunk_id"]
            if chunk_id not in unique:
                unique[chunk_id] = {
                    "chunk_id": chunk_id,
                    "source": metadata["source"],
                    "position": int(metadata["position"]),
                    "chunk_txt": document,
                    "distance": float(distance),
                }
        if len(unique) >= top_k or candidate_count == total_records:
            break
        candidate_count = min(total_records, candidate_count * 2)
    return list(unique.values())[:top_k]


def format_result(rank: int, result: dict[str, str | int | float]) -> str:
    """Format one retrieved chunk for direct terminal inspection."""
    return (
        f"{rank}. {result['source']} (chunk {result['position']}, "
        f"chunk_id {result['chunk_id']}, distance {result['distance']:.4f})\n"
        f"{result['chunk_txt']}"
    )


def _load_runtime() -> tuple[Any, Any]:
    try:
        import chromadb
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise SystemExit("Install project dependencies with: pip install -r requirements.txt") from exc
    model = SentenceTransformer(config.EMBEDDING_MODEL)
    client = chromadb.PersistentClient(path=str(config.CHROMA_PATH))
    try:
        collection = client.get_collection(name=config.CHROMA_COLLECTION, embedding_function=None)
    except Exception as exc:
        raise SystemExit("No vector index found. Run: python3 -m src.embeddings index") from exc
    return model, collection


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query")
    parser.add_argument("--top-k", type=int, default=config.N_RESULTS)
    args = parser.parse_args()

    model, collection = _load_runtime()
    results = retrieve(args.query, model, collection, top_k=args.top_k)
    for rank, result in enumerate(results, start=1):
        print(format_result(rank, result))
        print()


if __name__ == "__main__":
    main()
