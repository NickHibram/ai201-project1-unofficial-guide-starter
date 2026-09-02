from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src.ingestion import Document, load_documents
from src.chunking import chunk_documents, normalize_for_chunking, write_chunks_jsonl


def document(source: str, text: str) -> Document:
    return Document(source=source, text=text, original_char_count=len(text), cleaned_char_count=len(text))


class ChunkingTests(unittest.TestCase):
    def test_normalizes_hard_wrapped_prose_without_removing_paragraph_boundaries(self) -> None:
        text = "First sentence wraps\non the next line.\n\nSecond    paragraph."

        self.assertEqual(
            normalize_for_chunking(text), "First sentence wraps on the next line.\n\nSecond paragraph."
        )

    def test_returns_exact_dictionary_shape_and_deterministic_ids(self) -> None:
        text = "A complete sentence. " * 80

        chunks = chunk_documents([document("sample.txt", text)])

        self.assertTrue(chunks)
        self.assertEqual(set(chunks[0]), {"chunk_id", "source", "chunk_txt"})
        self.assertEqual(chunks[0]["chunk_id"], "sample.txt::00001")
        self.assertTrue(all(chunk["source"] == "sample.txt" for chunk in chunks))
        self.assertTrue(all(150 <= len(chunk["chunk_txt"]) <= 900 for chunk in chunks))

    def test_preserves_bound_table_spacing_and_allows_short_table_unit(self) -> None:
        text = (
            "The measurements are listed below:\n\n"
            "  Note       Virginal    Harpsichord\n"
            "  c'''       6-5/8       5-1/16\n"
            "  c''        12-15/16    10\n"
        )

        chunks = chunk_documents([document("table.txt", text)])

        self.assertEqual(len(chunks), 1)
        self.assertIn("measurements are listed below:", chunks[0]["chunk_txt"])
        self.assertIn("  Note       Virginal    Harpsichord", chunks[0]["chunk_txt"])
        self.assertLess(len(chunks[0]["chunk_txt"]), 150)

    def test_keeps_abbreviations_with_the_following_sentence(self) -> None:
        text = ("Dr. Smith studied the organ. " * 45) + ("Op. 3 is cited here. " * 20)

        chunks = chunk_documents([document("abbreviations.txt", text)])

        self.assertTrue(all(not chunk["chunk_txt"].endswith(("Dr.", "Op.")) for chunk in chunks))

    def test_writes_jsonl_records_without_ascii_escaping(self) -> None:
        chunks = [
            {"chunk_id": "music.txt::00001", "source": "music.txt", "chunk_txt": "martelé"},
        ]
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "chunks.jsonl"
            write_chunks_jsonl(chunks, path)

            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), chunks[0])
            self.assertIn("martelé", path.read_text(encoding="utf-8"))

    def test_full_corpus_never_exceeds_the_900_character_cap(self) -> None:
        project_root = Path(__file__).resolve().parents[1]

        chunks = chunk_documents(load_documents(project_root / "documents"))

        self.assertTrue(chunks)
        self.assertLessEqual(max(len(chunk["chunk_txt"]) for chunk in chunks), 900)


if __name__ == "__main__":
    unittest.main()
