from __future__ import annotations

import unittest

from src.retrieval import QueryTooLongError, format_result, retrieve
from tests.test_embeddings import FakeModel


class FakeQueryCollection:
    def __init__(self) -> None:
        self.metadata = {
            "embedding_model": "all-MiniLM-L6-v2",
            "embedding_dimension": 3,
            "max_tokens": 10,
        }
        self.requested: list[int] = []

    def count(self) -> int:
        return 4

    def query(self, *, n_results: int, **_: object) -> dict[str, object]:
        self.requested.append(n_results)
        return {
            "ids": [["a::part01", "a::part02", "b::part01", "c::part01"][:n_results]],
            "documents": [["A full chunk", "A full chunk", "B full chunk", "C full chunk"][:n_results]],
            "metadatas": [[
                {"chunk_id": "a", "source": "a.txt", "position": 1, "part": 1, "parts": 2},
                {"chunk_id": "a", "source": "a.txt", "position": 1, "part": 2, "parts": 2},
                {"chunk_id": "b", "source": "b.txt", "position": 2, "part": 1, "parts": 1},
                {"chunk_id": "c", "source": "c.txt", "position": 3, "part": 1, "parts": 1},
            ][:n_results]],
            "distances": [[0.1, 0.2, 0.3, 0.4][:n_results]],
        }


class RetrievalTests(unittest.TestCase):
    def test_formatted_result_includes_chunk_id_and_distance(self) -> None:
        formatted = format_result(
            1,
            {
                "chunk_id": "organ.txt::00066",
                "source": "organ.txt",
                "position": 66,
                "chunk_txt": "Wind enters the sound-board.",
                "distance": 0.316,
            },
        )

        self.assertIn("1. organ.txt", formatted)
        self.assertIn("chunk_id organ.txt::00066", formatted)
        self.assertIn("distance 0.3160", formatted)

    def test_retrieval_deduplicates_windows_by_original_chunk(self) -> None:
        results = retrieve(
            "organ sound",
            FakeModel(),
            FakeQueryCollection(),
            top_k=3,
            expected_model_name="all-MiniLM-L6-v2",
            max_tokens=10,
        )

        self.assertEqual([result["chunk_id"] for result in results], ["a", "b", "c"])
        self.assertEqual(results[0], {
            "chunk_id": "a",
            "source": "a.txt",
            "position": 1,
            "chunk_txt": "A full chunk",
            "distance": 0.1,
        })

    def test_query_over_model_limit_is_rejected(self) -> None:
        with self.assertRaisesRegex(QueryTooLongError, "10-token"):
            retrieve(
                "one two three four five six seven eight nine",
                FakeModel(),
                FakeQueryCollection(),
                top_k=3,
                expected_model_name="all-MiniLM-L6-v2",
                max_tokens=10,
            )


if __name__ == "__main__":
    unittest.main()
