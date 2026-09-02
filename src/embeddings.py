"""Create and manage a token-safe, source-attributed Chroma index."""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

from src import config


INDEX_SCHEMA_VERSION = 1
COMPATIBILITY_METADATA_KEYS = (
    "schema_version",
    "embedding_model",
    "embedding_dimension",
    "max_tokens",
    "window_overlap_tokens",
    "minimum_window_tokens",
    "source_title_prefix",
)
STATE_METADATA_KEYS = ("chunk_count", "embedding_record_count", "index_fingerprint")


class CollectionMismatchError(RuntimeError):
    """Raised when a persisted collection was built with different settings."""


@dataclass(frozen=True)
class EmbeddingRecord:
    """One token-safe vector record derived from an original reviewed chunk."""

    record_id: str
    parent_chunk_id: str
    source: str
    position: int
    document: str
    embedding_text: str
    token_count: int
    part: int
    parts: int


@dataclass(frozen=True)
class IndexReport:
    """Summary of an indexing run."""

    chunk_count: int
    embedding_record_count: int
    split_chunk_count: int
    max_embedding_tokens: int
    reused: bool


def load_chunks_jsonl(path: str | Path) -> list[dict[str, str]]:
    """Load and validate chunk dictionaries from a UTF-8 JSONL artifact."""
    chunks: list[dict[str, str]] = []
    required = {"chunk_id", "source", "chunk_txt"}
    with Path(path).open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                chunk = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid JSON on line {line_number}: {exc.msg}") from exc
            if not isinstance(chunk, dict) or set(chunk) != required:
                raise ValueError(
                    f"invalid chunk on line {line_number}: expected exactly {sorted(required)}"
                )
            if not all(isinstance(chunk[key], str) and chunk[key].strip() for key in required):
                raise ValueError(f"invalid chunk on line {line_number}: fields must be non-empty strings")
            parse_chunk_position(chunk["chunk_id"])
            chunks.append(chunk)
    if not chunks:
        raise ValueError(f"no chunks found in {path}")
    return chunks


def parse_chunk_position(chunk_id: str) -> int:
    """Return the source-local numeric position encoded after ``::``."""
    try:
        _source, suffix = chunk_id.rsplit("::", 1)
    except ValueError as exc:
        raise ValueError(f"invalid chunk_id {chunk_id!r}: expected '<source>::<position>'") from exc
    if not _source or not suffix.isdigit():
        raise ValueError(f"invalid chunk_id {chunk_id!r}: position must be numeric")
    return int(suffix)


def book_title(source: str) -> str:
    """Convert a source filename to the title used only during embedding."""
    return Path(source).stem.strip().replace("_", " ")


def _token_ids(tokenizer: Any, text: str, *, special_tokens: bool) -> list[int]:
    return list(tokenizer.encode(text, add_special_tokens=special_tokens, verbose=False))


def _decode(tokenizer: Any, token_ids: Sequence[int]) -> str:
    return tokenizer.decode(
        list(token_ids),
        skip_special_tokens=True,
        clean_up_tokenization_spaces=True,
    ).strip()


def effective_max_tokens(model: Any, configured_max_tokens: int | None) -> int:
    """Use the model's sequence limit unless configuration requests a smaller one."""
    model_limit = int(model.max_seq_length)
    if model_limit <= 0:
        raise ValueError("embedding model must expose a positive max_seq_length")
    if configured_max_tokens is None:
        return model_limit
    if configured_max_tokens > model_limit:
        raise ValueError(
            f"configured token limit {configured_max_tokens} exceeds model limit {model_limit}"
        )
    if configured_max_tokens <= 0:
        raise ValueError("configured token limit must be positive")
    return configured_max_tokens


def prepare_embedding_records(
    chunks: Iterable[dict[str, str]],
    tokenizer: Any,
    *,
    max_tokens: int | None = config.EMBEDDING_MAX_TOKENS,
    window_overlap_tokens: int = config.EMBEDDING_WINDOW_OVERLAP_TOKENS,
    minimum_window_tokens: int = config.MIN_EMBEDDING_WINDOW_TOKENS,
) -> list[EmbeddingRecord]:
    """Create title-prefixed records without allowing tokenizer truncation."""
    special_token_count = int(tokenizer.num_special_tokens_to_add(pair=False))
    if max_tokens is None:
        max_tokens = int(getattr(tokenizer, "model_max_length", 0))
    if max_tokens <= 0:
        raise ValueError("max_tokens must be a positive integer")
    records: list[EmbeddingRecord] = []

    for chunk in chunks:
        parent_id = chunk["chunk_id"]
        source = chunk["source"]
        document = chunk["chunk_txt"]
        prefix = f"{book_title(source)} — "
        prefix_ids = _token_ids(tokenizer, prefix, special_tokens=False)
        body_ids = _token_ids(tokenizer, document, special_tokens=False)
        body_budget = max_tokens - special_token_count - len(prefix_ids)
        if body_budget <= 0:
            raise ValueError(f"source-title prefix for {source!r} leaves no token budget")
        if window_overlap_tokens < 0 or window_overlap_tokens >= body_budget:
            raise ValueError("window overlap must be non-negative and smaller than the body budget")

        full_text = f"{prefix}{document}"
        full_token_count = special_token_count + len(prefix_ids) + len(body_ids)
        if full_token_count <= max_tokens:
            windows = [body_ids]
            embedding_texts = [full_text]
        else:
            step = body_budget - window_overlap_tokens
            starts = list(range(0, len(body_ids), step))
            tail_floor = min(minimum_window_tokens, body_budget)
            if len(starts) > 1 and len(body_ids) - starts[-1] < tail_floor:
                starts[-1] = max(0, len(body_ids) - body_budget)
            windows = [body_ids[start : start + body_budget] for start in starts]
            windows = [window for window in windows if window]
            embedding_texts = [f"{prefix}{_decode(tokenizer, window)}" for window in windows]

        total_parts = len(windows)
        for part_index, embedding_text in enumerate(embedding_texts, start=1):
            token_count = len(_token_ids(tokenizer, embedding_text, special_tokens=True))
            if token_count > max_tokens:
                raise ValueError(
                    f"token window {parent_id} part {part_index} has {token_count} tokens; "
                    f"limit is {max_tokens}"
                )
            records.append(
                EmbeddingRecord(
                    record_id=f"{parent_id}::part{part_index:02d}",
                    parent_chunk_id=parent_id,
                    source=source,
                    position=parse_chunk_position(parent_id),
                    document=document,
                    embedding_text=embedding_text,
                    token_count=token_count,
                    part=part_index,
                    parts=total_parts,
                )
            )
    return records


def _index_fingerprint(
    chunks: Iterable[dict[str, str]],
    *,
    model_name: str,
    max_tokens: int,
    window_overlap_tokens: int,
    minimum_window_tokens: int,
) -> str:
    digest = hashlib.sha256()
    settings = {
        "schema_version": INDEX_SCHEMA_VERSION,
        "embedding_model": model_name,
        "max_tokens": max_tokens,
        "window_overlap_tokens": window_overlap_tokens,
        "minimum_window_tokens": minimum_window_tokens,
        "source_title_prefix": True,
    }
    digest.update(json.dumps(settings, sort_keys=True).encode("utf-8"))
    for chunk in chunks:
        digest.update(json.dumps(chunk, ensure_ascii=False, sort_keys=True).encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()


def collection_metadata(
    chunks: Sequence[dict[str, str]],
    records: Sequence[EmbeddingRecord],
    *,
    model_name: str,
    embedding_dimension: int,
    max_tokens: int,
    window_overlap_tokens: int,
    minimum_window_tokens: int = config.MIN_EMBEDDING_WINDOW_TOKENS,
) -> dict[str, str | int]:
    """Return the compatibility stamp for a persistent collection."""
    return {
        "schema_version": INDEX_SCHEMA_VERSION,
        "embedding_model": model_name,
        "embedding_dimension": embedding_dimension,
        "max_tokens": max_tokens,
        "window_overlap_tokens": window_overlap_tokens,
        "minimum_window_tokens": minimum_window_tokens,
        "source_title_prefix": "<book title> — ",
        "chunk_count": len(chunks),
        "embedding_record_count": len(records),
        "index_fingerprint": _index_fingerprint(
            chunks,
            model_name=model_name,
            max_tokens=max_tokens,
            window_overlap_tokens=window_overlap_tokens,
            minimum_window_tokens=minimum_window_tokens,
        ),
    }


def verify_collection_metadata(
    actual: dict[str, Any] | None,
    expected: dict[str, str | int],
    collection_name: str,
) -> None:
    """Reject a collection whose vectors are incompatible with this run."""
    actual = actual or {}
    mismatches = [
        key for key in COMPATIBILITY_METADATA_KEYS if actual.get(key) != expected.get(key)
    ]
    if mismatches:
        fields = ", ".join(mismatches)
        raise CollectionMismatchError(
            f"collection {collection_name!r} does not match the current index ({fields}); "
            "run 'python3 -m src.embeddings reset' before rebuilding"
        )


def _state_matches(actual: dict[str, Any] | None, expected: dict[str, str | int]) -> bool:
    actual = actual or {}
    return all(actual.get(key) == expected[key] for key in STATE_METADATA_KEYS)


def _collection_ids(collection: Any) -> set[str]:
    """Return every stored record ID so obsolete records are never left silently."""
    result = collection.get(include=[])
    return set(result["ids"])


def _as_lists(embeddings: Any) -> list[list[float]]:
    converted = embeddings.tolist() if hasattr(embeddings, "tolist") else embeddings
    return [list(vector) for vector in converted]


def build_index(
    chunks: Sequence[dict[str, str]],
    model: Any,
    client: Any,
    *,
    collection_name: str = config.CHROMA_COLLECTION,
    model_name: str = config.EMBEDDING_MODEL,
    max_tokens: int | None = config.EMBEDDING_MAX_TOKENS,
    window_overlap_tokens: int = config.EMBEDDING_WINDOW_OVERLAP_TOKENS,
    batch_size: int = config.EMBEDDING_BATCH_SIZE,
) -> IndexReport:
    """Build or safely reuse the configured persistent Chroma collection."""
    max_tokens = effective_max_tokens(model, max_tokens)
    records = prepare_embedding_records(
        chunks,
        model.tokenizer,
        max_tokens=max_tokens,
        window_overlap_tokens=window_overlap_tokens,
        minimum_window_tokens=config.MIN_EMBEDDING_WINDOW_TOKENS,
    )
    dimension = int(model.get_sentence_embedding_dimension())
    expected_metadata = collection_metadata(
        chunks,
        records,
        model_name=model_name,
        embedding_dimension=dimension,
        max_tokens=max_tokens,
        window_overlap_tokens=window_overlap_tokens,
        minimum_window_tokens=config.MIN_EMBEDDING_WINDOW_TOKENS,
    )
    collection = client.get_or_create_collection(
        name=collection_name,
        metadata=expected_metadata,
        configuration={"hnsw": {"space": "cosine"}},
        embedding_function=None,
    )
    verify_collection_metadata(collection.metadata, expected_metadata, collection_name)

    token_lengths = [record.token_count for record in records]
    split_count = len({record.parent_chunk_id for record in records if record.parts > 1})
    if _state_matches(collection.metadata, expected_metadata) and collection.count() == len(records):
        return IndexReport(len(chunks), len(records), split_count, max(token_lengths), True)

    current_ids = {record.record_id for record in records}
    stale_ids = _collection_ids(collection) - current_ids
    if stale_ids:
        raise CollectionMismatchError(
            f"collection {collection_name!r} has {len(stale_ids)} stale vector records; "
            "run 'python3 -m src.embeddings reset' before rebuilding"
        )

    embeddings = _as_lists(
        model.encode(
            [record.embedding_text for record in records],
            batch_size=batch_size,
            show_progress_bar=True,
            convert_to_numpy=True,
            normalize_embeddings=True,
        )
    )
    for start in range(0, len(records), batch_size):
        batch = records[start : start + batch_size]
        batch_embeddings = embeddings[start : start + batch_size]
        collection.upsert(
            ids=[record.record_id for record in batch],
            embeddings=batch_embeddings,
            documents=[record.document for record in batch],
            metadatas=[
                {
                    "chunk_id": record.parent_chunk_id,
                    "source": record.source,
                    "position": record.position,
                    "part": record.part,
                    "parts": record.parts,
                }
                for record in batch
            ],
        )

    if collection.count() != len(records):
        raise RuntimeError(
            f"collection contains {collection.count()} records; expected {len(records)}. "
            "Reset the collection before rebuilding."
        )
    collection.modify(metadata=expected_metadata)
    return IndexReport(len(chunks), len(records), split_count, max(token_lengths), False)


def reset_collection(client: Any, collection_name: str = config.CHROMA_COLLECTION) -> None:
    """Delete only the named Chroma collection."""
    client.delete_collection(name=collection_name)


def _load_model() -> Any:
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise SystemExit("Install project dependencies with: pip install -r requirements.txt") from exc
    return SentenceTransformer(config.EMBEDDING_MODEL)


def _load_chroma_client() -> Any:
    try:
        import chromadb
    except ImportError as exc:
        raise SystemExit("Install project dependencies with: pip install -r requirements.txt") from exc
    return chromadb.PersistentClient(path=str(config.CHROMA_PATH))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    index_parser = subparsers.add_parser("index", help="build or reuse the vector index")
    index_parser.add_argument("--chunks", type=Path, default=config.CHUNKS_PATH)
    reset_parser = subparsers.add_parser("reset", help="delete the configured collection")
    reset_parser.add_argument("--yes", action="store_true", help="skip the confirmation prompt")
    args = parser.parse_args()

    if args.command == "reset":
        client = _load_chroma_client()
        confirmed = args.yes or input(
            f"Delete Chroma collection {config.CHROMA_COLLECTION!r}? [y/N] "
        ).strip().lower() == "y"
        if not confirmed:
            print("Reset cancelled.")
            return
        reset_collection(client)
        print(f"Deleted collection {config.CHROMA_COLLECTION!r}.")
        return

    chunks = load_chunks_jsonl(args.chunks)
    model = _load_model()
    client = _load_chroma_client()
    report = build_index(chunks, model, client)
    action = "Reused" if report.reused else "Indexed"
    print(f"{action} {report.chunk_count:,} chunks as {report.embedding_record_count:,} vector records.")
    print(f"Split chunks: {report.split_chunk_count:,}; maximum embedding input: {report.max_embedding_tokens} tokens.")


if __name__ == "__main__":
    main()
