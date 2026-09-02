from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src.embeddings import (
    CollectionMismatchError,
    build_index,
    collection_metadata,
    effective_max_tokens,
    load_chunks_jsonl,
    parse_chunk_position,
    prepare_embedding_records,
    reset_collection,
)


class FakeTokenizer:
    def __init__(self) -> None:
        self.token_to_id: dict[str, int] = {}
        self.id_to_token: dict[int, str] = {}

    def encode(self, text: str, add_special_tokens: bool = True, **_: object) -> list[int]:
        ids = []
        for token in text.split():
            if token not in self.token_to_id:
                token_id = len(self.token_to_id) + 1000
                self.token_to_id[token] = token_id
                self.id_to_token[token_id] = token
            ids.append(self.token_to_id[token])
        return ([101] + ids + [102]) if add_special_tokens else ids

    def decode(self, token_ids: list[int], **_: object) -> str:
        return " ".join(self.id_to_token[token_id] for token_id in token_ids)

    def num_special_tokens_to_add(self, pair: bool = False) -> int:
        return 2


class FakeModel:
    max_seq_length = 10

    def __init__(self) -> None:
        self.tokenizer = FakeTokenizer()
        self.encoded_texts: list[str] = []

    def get_sentence_embedding_dimension(self) -> int:
        return 3

    def encode(self, texts: list[str], **_: object) -> list[list[float]]:
        self.encoded_texts.extend(texts)
        return [[float(index), 1.0, 2.0] for index, _text in enumerate(texts)]


class FakeCollection:
    def __init__(
        self,
        metadata: dict[str, str | int],
        count: int = 0,
        ids: list[str] | None = None,
    ) -> None:
        self.metadata = metadata
        self._count = count
        self.ids = ids or []
        self.upserts: list[dict[str, object]] = []
        self.modified_metadata: list[dict[str, str | int]] = []

    def count(self) -> int:
        return self._count

    def upsert(self, **payload: object) -> None:
        self.upserts.append(payload)
        for record_id in payload["ids"]:  # type: ignore[union-attr]
            if record_id not in self.ids:
                self.ids.append(record_id)
        self._count = len(self.ids)

    def get(self, **_: object) -> dict[str, list[str]]:
        return {"ids": self.ids}

    def modify(self, *, metadata: dict[str, str | int]) -> None:
        self.metadata = metadata
        self.modified_metadata.append(metadata)


class FakeClient:
    def __init__(self, collection: FakeCollection | None = None) -> None:
        self.collection = collection
        self.deleted: list[str] = []
        self.created_metadata: dict[str, str | int] | None = None

    def get_or_create_collection(self, **kwargs: object) -> FakeCollection:
        if self.collection is None:
            self.created_metadata = kwargs["metadata"]  # type: ignore[assignment]
            self.collection = FakeCollection(self.created_metadata)
        return self.collection

    def delete_collection(self, name: str) -> None:
        self.deleted.append(name)


def chunk(text: str = "one two three") -> dict[str, str]:
    return {
        "chunk_id": "Music Book.txt::00007",
        "source": "Music Book.txt",
        "chunk_txt": text,
    }


class EmbeddingPreparationTests(unittest.TestCase):
    def test_load_chunks_rejects_missing_required_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "chunks.jsonl"
            path.write_text(json.dumps({"chunk_id": "bad::00001"}) + "\n", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "line 1"):
                load_chunks_jsonl(path)

    def test_position_uses_chunk_id_delimiter(self) -> None:
        self.assertEqual(parse_chunk_position("book2024.txt::00007"), 7)
        with self.assertRaisesRegex(ValueError, "invalid chunk_id"):
            parse_chunk_position("book.txt::final")

    def test_oversized_chunk_becomes_safe_overlapping_embedding_windows(self) -> None:
        model = FakeModel()
        original_tokens = [f"word{index}" for index in range(12)]

        records = prepare_embedding_records(
            [chunk(" ".join(original_tokens))],
            model.tokenizer,
            max_tokens=10,
            window_overlap_tokens=2,
        )

        self.assertGreater(len(records), 1)
        self.assertTrue(all(len(model.tokenizer.encode(record.embedding_text)) <= 10 for record in records))
        self.assertTrue(all(record.embedding_text.startswith("Music Book — ") for record in records))
        represented = {token for record in records for token in record.embedding_text.split()}
        self.assertTrue(set(original_tokens).issubset(represented))
        self.assertTrue(all(record.document == " ".join(original_tokens) for record in records))
        self.assertTrue(all(record.parent_chunk_id == "Music Book.txt::00007" for record in records))

    def test_tiny_final_window_is_end_aligned_instead_of_dropped(self) -> None:
        model = FakeModel()
        records = prepare_embedding_records(
            [chunk(" ".join(f"word{index}" for index in range(11)))],
            model.tokenizer,
            max_tokens=10,
            window_overlap_tokens=2,
        )

        self.assertTrue(all(len(record.embedding_text.split()) >= 8 for record in records))
        self.assertIn("word10", records[-1].embedding_text)

    def test_model_limit_is_used_when_configured_limit_is_not_set(self) -> None:
        self.assertEqual(effective_max_tokens(FakeModel(), None), 10)
        self.assertEqual(effective_max_tokens(FakeModel(), 8), 8)
        with self.assertRaisesRegex(ValueError, "exceeds"):
            effective_max_tokens(FakeModel(), 11)

    def test_matching_complete_collection_is_reused_without_reembedding(self) -> None:
        model = FakeModel()
        chunks = [chunk()]
        records = prepare_embedding_records(chunks, model.tokenizer, max_tokens=10, window_overlap_tokens=2)
        metadata = collection_metadata(
            chunks,
            records,
            model_name="all-MiniLM-L6-v2",
            embedding_dimension=3,
            max_tokens=10,
            window_overlap_tokens=2,
        )
        client = FakeClient(FakeCollection(metadata, count=len(records)))

        report = build_index(
            chunks,
            model,
            client,
            collection_name="music",
            model_name="all-MiniLM-L6-v2",
            max_tokens=10,
            window_overlap_tokens=2,
            batch_size=4,
        )

        self.assertTrue(report.reused)
        self.assertEqual(model.encoded_texts, [])
        self.assertEqual(client.collection.upserts, [])  # type: ignore[union-attr]

    def test_collection_with_different_model_is_rejected(self) -> None:
        model = FakeModel()
        chunks = [chunk()]
        records = prepare_embedding_records(chunks, model.tokenizer, max_tokens=10, window_overlap_tokens=2)
        metadata = collection_metadata(
            chunks,
            records,
            model_name="different-model",
            embedding_dimension=3,
            max_tokens=10,
            window_overlap_tokens=2,
        )
        client = FakeClient(FakeCollection(metadata))

        with self.assertRaisesRegex(CollectionMismatchError, "reset"):
            build_index(
                chunks,
                model,
                client,
                collection_name="music",
                model_name="all-MiniLM-L6-v2",
                max_tokens=10,
                window_overlap_tokens=2,
                batch_size=4,
            )

        self.assertEqual(client.deleted, [])

    def test_changed_chunk_text_is_upserted_and_refreshes_state_metadata(self) -> None:
        model = FakeModel()
        old_chunks = [chunk("old text")]
        old_records = prepare_embedding_records(old_chunks, model.tokenizer, max_tokens=10, window_overlap_tokens=2)
        old_metadata = collection_metadata(
            old_chunks,
            old_records,
            model_name="all-MiniLM-L6-v2",
            embedding_dimension=3,
            max_tokens=10,
            window_overlap_tokens=2,
        )
        client = FakeClient(FakeCollection(old_metadata, count=1, ids=[old_records[0].record_id]))

        report = build_index(
            [chunk("new text")],
            model,
            client,
            collection_name="music",
            model_name="all-MiniLM-L6-v2",
            max_tokens=10,
            window_overlap_tokens=2,
            batch_size=4,
        )

        self.assertFalse(report.reused)
        self.assertTrue(client.collection.upserts)  # type: ignore[union-attr]
        self.assertEqual(client.collection.modified_metadata[-1]["chunk_count"], 1)  # type: ignore[union-attr]

    def test_removed_vector_id_requires_explicit_reset(self) -> None:
        model = FakeModel()
        chunks = [chunk("current text")]
        records = prepare_embedding_records(chunks, model.tokenizer, max_tokens=10, window_overlap_tokens=2)
        metadata = collection_metadata(
            [chunk("old text")],
            records,
            model_name="all-MiniLM-L6-v2",
            embedding_dimension=3,
            max_tokens=10,
            window_overlap_tokens=2,
        )
        client = FakeClient(FakeCollection(metadata, count=2, ids=[records[0].record_id, "removed::part01"]))

        with self.assertRaisesRegex(CollectionMismatchError, "stale vector records"):
            build_index(
                chunks,
                model,
                client,
                collection_name="music",
                model_name="all-MiniLM-L6-v2",
                max_tokens=10,
                window_overlap_tokens=2,
                batch_size=4,
            )

    def test_new_index_stores_complete_documents_and_window_metadata(self) -> None:
        model = FakeModel()
        client = FakeClient()

        report = build_index(
            [chunk("one two three four five six seven eight nine")],
            model,
            client,
            collection_name="music",
            model_name="all-MiniLM-L6-v2",
            max_tokens=10,
            window_overlap_tokens=2,
            batch_size=20,
        )

        self.assertFalse(report.reused)
        self.assertGreater(report.embedding_record_count, report.chunk_count)
        payload = client.collection.upserts[0]  # type: ignore[union-attr]
        self.assertTrue(all(document == "one two three four five six seven eight nine" for document in payload["documents"]))  # type: ignore[index]
        first_metadata = payload["metadatas"][0]  # type: ignore[index]
        self.assertEqual(first_metadata["source"], "Music Book.txt")
        self.assertEqual(first_metadata["position"], 7)
        self.assertEqual(first_metadata["chunk_id"], "Music Book.txt::00007")

    def test_reset_deletes_only_named_collection(self) -> None:
        client = FakeClient()

        reset_collection(client, "music")

        self.assertEqual(client.deleted, ["music"])


if __name__ == "__main__":
    unittest.main()
