from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.ingestion import clean_gutenberg_text, load_documents, write_cleaned_documents


START = "*** START OF THE PROJECT GUTENBERG EBOOK SAMPLE BOOK ***"
END = "*** END OF THE PROJECT GUTENBERG EBOOK SAMPLE BOOK ***"


class CleanGutenbergTextTests(unittest.TestCase):
    def test_applies_configured_content_boundaries(self) -> None:
        raw = (
            f"{START}\n"
            "Title and contents.\n\n"
            "PREFACE.\n\n"
            "Useful cello instruction.\n\n"
            "THE END.\n\n"
            "THE STRAD publisher advertisement.\n"
            f"{END}"
        )

        cleaned = clean_gutenberg_text(raw, "Chats to 'Cello Students.txt")

        self.assertEqual(cleaned, "PREFACE.\n\nUseful cello instruction.")

    def test_selects_explicit_occurrences_of_repeated_anchors(self) -> None:
        raw = (
            f"{START}\n"
            "PART I.\nContents entry.\n\n"
            "PART I.\nActual violin instruction.\n\n"
            "GUIDE THROUGH VIOLIN LITERATURE.\nUseful literature guide.\n\n"
            "GUIDE THROUGH VIOLIN LITERATURE.\nRepeated contents block.\n"
            f"{END}"
        )

        cleaned = clean_gutenberg_text(raw, "HANDBOOK OF VIOLIN PLAYING.txt")

        self.assertEqual(
            cleaned,
            "PART I.\nActual violin instruction.\n\n"
            "GUIDE THROUGH VIOLIN LITERATURE.\nUseful literature guide.",
        )

    def test_removes_piano_internal_contents_without_removing_second_foreword(self) -> None:
        raw = (
            f"{START}\n"
            "A FOREWORD\nFirst book prose.\n\n"
            "_Piano Questions Answered_\nCONTENTS\nTechnique 3\n\n"
            "A FOREWORD\nSecond book prose.\n\n"
            "ALPHABETICAL INDEX OF\nQUESTIONS\nTechnique 3\n"
            f"{END}"
        )

        cleaned = clean_gutenberg_text(raw, "Piano Playing, with Piano Questions Answered.txt")

        self.assertEqual(
            cleaned,
            "A FOREWORD\nFirst book prose.\n\nA FOREWORD\nSecond book prose.",
        )

    def test_rejects_configured_source_when_an_anchor_is_missing(self) -> None:
        raw = f"{START}\nBook text without configured anchors.\n{END}"

        with self.assertRaisesRegex(ValueError, "The coach-horn.txt.*anchor"):
            clean_gutenberg_text(raw, "The coach-horn.txt")

    def test_removes_wrappers_without_reflowing_book_content(self) -> None:
        raw = (
            "Project Gutenberg licensing information\n\n"
            f"{START}\n\n"
            "First line of a hard-wrapped paragraph\n"
            "    continues with indentation.\n\n\n"
            "Column A          Column B\n"
            "first value       second value\n\n"
            f"{END}\n\n"
            "More Gutenberg licensing information"
        )

        cleaned = clean_gutenberg_text(raw, "sample.txt")

        self.assertEqual(
            cleaned,
            "First line of a hard-wrapped paragraph\n"
            "    continues with indentation.\n\n\n"
            "Column A          Column B\n"
            "first value       second value",
        )

    def test_rejects_source_without_a_complete_marker_pair(self) -> None:
        with self.assertRaisesRegex(ValueError, "broken.txt.*end marker"):
            clean_gutenberg_text(f"{START}\nBook text", "broken.txt")

    def test_removes_known_html_artifacts_without_reflowing_text(self) -> None:
        raw = (
            f"{START}\n"
            "<pre id=\"pg-footer\">\n"
            "This style is _martelé</sc>.\n"
            "  Spacing stays intact.\n"
            "</pre>\n"
            f"{END}"
        )

        cleaned = clean_gutenberg_text(raw, "markup.txt")

        self.assertEqual(cleaned, "This style is _martelé.\n  Spacing stays intact.")

    def test_removes_an_in_book_gutenberg_end_notice_and_its_trailing_text(self) -> None:
        raw = (
            f"{START}\n"
            "Actual book ending.\n\n"
            "End of Project Gutenberg's Sample Book, by Example Author\n\n"
            "Distribution notice\n"
            f"{END}"
        )

        cleaned = clean_gutenberg_text(raw, "footer.txt")

        self.assertEqual(cleaned, "Actual book ending.")

    def test_removes_a_leading_gutenberg_production_credit(self) -> None:
        raw = (
            f"{START}\n\n"
            "Produced by Example Volunteer and the Online Distributed Proofreading Team\n"
            "https://www.pgdp.net\n\n\n"
            "BOOK TITLE\n\n"
            "A later sentence says the sound is produced by a pipe.\n"
            f"{END}"
        )

        cleaned = clean_gutenberg_text(raw, "credit.txt")

        self.assertEqual(
            cleaned,
            "BOOK TITLE\n\nA later sentence says the sound is produced by a pipe.",
        )

    def test_removes_leading_download_and_transcriber_notices(self) -> None:
        raw = (
            f"{START}\n"
            "Note: Project Gutenberg also has an HTML version of this file.\n"
            "https://www.gutenberg.org/example\n\n"
            "Transcriber’s note:\n\n"
            "  Small capitals have been changed to CAPITALS.\n\n\n\n"
            "BOOK TITLE\n\n"
            "Book content.\n"
            f"{END}"
        )

        cleaned = clean_gutenberg_text(raw, "notice.txt")

        self.assertEqual(cleaned, "BOOK TITLE\n\nBook content.")

    def test_removes_a_leading_e_text_credit_before_a_download_notice(self) -> None:
        raw = (
            f"{START}\n"
            "E-text prepared by Example Volunteer and the Online Distributed Proofreading Team\n"
            "(http://www.pgdp.net)\n\n"
            "Note: Project Gutenberg also has an HTML version of this file.\n"
            "https://www.gutenberg.org/example\n\n\n"
            "[Illustration: Title page]\n\n"
            "BOOK TITLE\n"
            f"{END}"
        )

        cleaned = clean_gutenberg_text(raw, "etext.txt")

        self.assertEqual(cleaned, "[Illustration: Title page]\n\nBOOK TITLE")


class LoadingAndWritingTests(unittest.TestCase):
    def test_writes_one_cleaned_copy_per_source_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_dir = root / "documents"
            output_dir = root / "cleaned_documents"
            source_dir.mkdir()
            (source_dir / "zeta.txt").write_text(
                f"Before\n{START}\nZeta text.\n{END}\nAfter", encoding="utf-8"
            )
            (source_dir / "alpha.txt").write_text(
                f"Before\n{START}\nAlpha text.\n{END}\nAfter", encoding="utf-8"
            )

            documents = load_documents(source_dir)
            write_cleaned_documents(documents, output_dir)

            self.assertEqual([document.source for document in documents], ["alpha.txt", "zeta.txt"])
            self.assertEqual(
                sorted(path.name for path in output_dir.glob("*.txt")), ["alpha.txt", "zeta.txt"]
            )
            self.assertEqual((output_dir / "alpha.txt").read_text(encoding="utf-8"), "Alpha text.\n")
            self.assertNotIn("PROJECT GUTENBERG", (output_dir / "zeta.txt").read_text(encoding="utf-8"))

    def test_real_corpus_loads_only_reviewed_book_content(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        documents = load_documents(project_root / "documents")
        by_source = {document.source: document for document in documents}

        self.assertEqual(len(documents), 11)
        self.assertTrue(all(document.text for document in documents))
        self.assertTrue(all("*** START OF THE PROJECT GUTENBERG" not in document.text for document in documents))
        self.assertTrue(
            by_source["A Complete History of Music.txt"].text.startswith("INTRODUCTION.")
        )
        self.assertNotIn("\n                                 INDEX.\n", by_source["A Complete History of Music.txt"].text)
        self.assertTrue(by_source["Chats to 'Cello Students.txt"].text.startswith("PREFACE."))
        self.assertNotIn("THE STRAD publisher", by_source["Chats to 'Cello Students.txt"].text)
        self.assertNotIn("TENTH YEAR OF ISSUE", by_source["Chats to 'Cello Students.txt"].text)
        self.assertTrue(by_source["First Steps to Bell Ringing.txt"].text.startswith("INTRODUCTION."))
        self.assertNotIn("BOOKS PUBLISHED ON", by_source["First Steps to Bell Ringing.txt"].text)
        self.assertNotIn("OPINIONS OF THE PRESS.", by_source["First Steps to Bell Ringing.txt"].text)
        self.assertIn(
            "GUIDE THROUGH VIOLIN LITERATURE.", by_source["HANDBOOK OF VIOLIN PLAYING.txt"].text
        )
        self.assertEqual(
            by_source["HANDBOOK OF VIOLIN PLAYING.txt"].text.count(
                "GUIDE THROUGH VIOLIN LITERATURE."
            ),
            1,
        )
        self.assertNotIn(
            "ALPHABETICAL INDEX OF\nQUESTIONS",
            by_source["Piano Playing, with Piano Questions Answered.txt"].text,
        )
        self.assertNotIn(
            "_Piano Questions Answered_",
            by_source["Piano Playing, with Piano Questions Answered.txt"].text,
        )
        self.assertIn(
            "                    _Polygonal    _Harpsichord_\n"
            "                      virginal_\n"
            "  c´´´                 6-5/8          5-1/16\n"
            "  c´´ (pitch C)       12-15/16       10",
            by_source["Italian Harpsichord-Building in the 16th and 17th Centuries.txt"].text,
        )
        self.assertTrue(all("<pre" not in document.text.lower() for document in documents))
        self.assertTrue(all("</pre>" not in document.text.lower() for document in documents))
        self.assertNotIn("martelé</sc>", by_source["Chats to 'Cello Students.txt"].text)
        self.assertTrue(all("end of project gutenberg" not in document.text.lower() for document in documents))
        self.assertFalse(
            by_source["Italian Harpsichord-Building in the 16th and 17th Centuries.txt"].text.startswith(
                "Produced by"
            )
        )
        self.assertTrue(by_source["Practical Organ Building.txt"].text.startswith("CHAPTER I."))


if __name__ == "__main__":
    unittest.main()
