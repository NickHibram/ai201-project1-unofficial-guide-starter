"""Load and clean Project Gutenberg plaintext documents for the RAG pipeline."""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


START_MARKER = re.compile(
    r"^\*\*\* START OF THE PROJECT GUTENBERG EBOOK .+? \*\*\*\s*$",
    re.IGNORECASE | re.MULTILINE,
)
END_MARKER = re.compile(
    r"^\*\*\* END OF THE PROJECT GUTENBERG EBOOK .+? \*\*\*\s*$",
    re.IGNORECASE | re.MULTILINE,
)
KNOWN_HTML_ARTIFACTS = re.compile(r"</?pre\b[^>]*>|</?sc\s*>", re.IGNORECASE)
IN_BOOK_GUTENBERG_FOOTER = re.compile(
    r"^\s*End of Project Gutenberg(?:['’]s)?\b.*$", re.IGNORECASE | re.MULTILINE
)
LEADING_PRODUCTION_CREDIT = re.compile(
    r"\A(?:[ \t]*\n)*Produced by\b(?:[^\n]*\n)+?(?:[ \t]*\n)+",
    re.IGNORECASE,
)
LEADING_E_TEXT_CREDIT = re.compile(
    r"\A(?:[ \t]*\n)*E-text prepared by\b(?:[^\n]*\n)+?(?:[ \t]*\n)+",
    re.IGNORECASE,
)
LEADING_DOWNLOAD_NOTICE = re.compile(
    r"\A\s*Note: Project Gutenberg also has an HTML version.*?(?=^\s*(?:Transcriber|\[Illustration))",
    re.IGNORECASE | re.MULTILINE | re.DOTALL,
)
LEADING_TRANSCRIBER_NOTICE = re.compile(
    r"\A(?:[ \t]*\n)*Transcriber(?:['’]s)?\s+note[s]?:.*?(?=(?:\n[ \t]*){3,}[A-Z])",
    re.IGNORECASE | re.DOTALL,
)


@dataclass(frozen=True)
class TextAnchor:
    """A stripped whole-line anchor and its one-based occurrence."""

    text: str
    occurrence: int = 1


CONTENT_BOUNDARIES: dict[str, tuple[TextAnchor, TextAnchor | None]] = {
    "A Complete History of Music.txt": (
        TextAnchor("INTRODUCTION."),
        TextAnchor("INDEX."),
    ),
    "Chats to 'Cello Students.txt": (
        TextAnchor("PREFACE."),
        TextAnchor("THE END."),
    ),
    "First Steps to Bell Ringing.txt": (
        TextAnchor("INTRODUCTION."),
        TextAnchor("BOOKS PUBLISHED ON"),
    ),
    "HANDBOOK OF VIOLIN PLAYING.txt": (
        TextAnchor("PART I.", occurrence=2),
        TextAnchor("GUIDE THROUGH VIOLIN LITERATURE.", occurrence=2),
    ),
    "Italian Harpsichord-Building in the 16th and 17th Centuries.txt": (
        TextAnchor("Italian Harpsichord-Building in the 16th and 17th Centuries"),
        TextAnchor("FOOTNOTES:"),
    ),
    "Musical Instruments, Historic, Rare and Unique.txt": (
        TextAnchor("INTRODUCTION."),
        TextAnchor("INDEX"),
    ),
    "Piano Playing, with Piano Questions Answered.txt": (
        TextAnchor("A FOREWORD"),
        TextAnchor("ALPHABETICAL INDEX OF"),
    ),
    "Practical Organ Building.txt": (
        TextAnchor("CHAPTER I.", occurrence=2),
        TextAnchor("INDEX."),
    ),
    "Principles of Orchestration, with Musical Examples Drawn from His Own Works .txt": (
        TextAnchor("Editor's Preface."),
        None,
    ),
    "The coach-horn.txt": (
        TextAnchor("Some time ago I rather thoughtlessly remarked to a subaltern in the"),
        TextAnchor("“THE QUEEN AND THE ROAD!”"),
    ),
    "The Highland bagpipe.txt": (
        TextAnchor("CHAPTER I."),
        TextAnchor("Index."),
    ),
}

INTERNAL_REMOVAL_REGIONS: dict[str, tuple[tuple[TextAnchor, TextAnchor], ...]] = {
    "Piano Playing, with Piano Questions Answered.txt": (
        (TextAnchor("_Piano Questions Answered_"), TextAnchor("A FOREWORD", occurrence=2)),
    ),
}


@dataclass(frozen=True)
class Document:
    """A cleaned source document with enough metadata for later pipeline stages."""

    source: str
    text: str
    original_char_count: int
    cleaned_char_count: int


def _find_anchor_line(lines: list[str], anchor: TextAnchor, source: str) -> int:
    """Return the index of a required anchor in ``lines``."""
    matches = [index for index, line in enumerate(lines) if line.strip() == anchor.text]
    if len(matches) < anchor.occurrence:
        raise ValueError(
            f"{source}: anchor {anchor.text!r} occurrence {anchor.occurrence} not found"
        )
    return matches[anchor.occurrence - 1]


def strip_reference_apparatus(text: str, source: str) -> str:
    """Keep the reviewed content region for a configured source document."""
    boundary = CONTENT_BOUNDARIES.get(source)
    if boundary is None:
        return text

    lines = text.splitlines(keepends=True)
    start_anchor, end_anchor = boundary
    start_index = _find_anchor_line(lines, start_anchor, source)
    end_index = len(lines) if end_anchor is None else _find_anchor_line(lines, end_anchor, source)
    if end_index <= start_index:
        raise ValueError(f"{source}: end anchor must follow start anchor")
    retained = lines[start_index:end_index]

    for removal_start, removal_end in INTERNAL_REMOVAL_REGIONS.get(source, ()):
        removal_start_index = _find_anchor_line(retained, removal_start, source)
        removal_end_index = _find_anchor_line(retained, removal_end, source)
        if removal_end_index <= removal_start_index:
            raise ValueError(f"{source}: removal end anchor must follow its start anchor")
        del retained[removal_start_index:removal_end_index]

    return "".join(retained)


def clean_gutenberg_text(raw_text: str, source: str) -> str:
    """Return the original book text between one Gutenberg marker pair."""
    normalized_newlines = raw_text.replace("\r\n", "\n").replace("\r", "\n")
    start_markers = list(START_MARKER.finditer(normalized_newlines))
    end_markers = list(END_MARKER.finditer(normalized_newlines))

    if not start_markers:
        raise ValueError(f"{source}: missing Gutenberg start marker")
    if len(start_markers) != 1:
        raise ValueError(f"{source}: expected one Gutenberg start marker")
    if not end_markers:
        raise ValueError(f"{source}: missing Gutenberg end marker")
    if len(end_markers) != 1:
        raise ValueError(f"{source}: expected one Gutenberg end marker")

    start_marker = start_markers[0]
    end_marker = end_markers[0]
    if end_marker.start() <= start_marker.end():
        raise ValueError(f"{source}: Gutenberg end marker precedes start marker")

    cleaned_text = KNOWN_HTML_ARTIFACTS.sub(
        "", normalized_newlines[start_marker.end() : end_marker.start()]
    )
    footer = IN_BOOK_GUTENBERG_FOOTER.search(cleaned_text)
    if footer:
        cleaned_text = cleaned_text[: footer.start()]
    cleaned_text = LEADING_PRODUCTION_CREDIT.sub("", cleaned_text)
    cleaned_text = LEADING_E_TEXT_CREDIT.sub("", cleaned_text)
    cleaned_text = LEADING_DOWNLOAD_NOTICE.sub("", cleaned_text)
    cleaned_text = LEADING_TRANSCRIBER_NOTICE.sub("", cleaned_text)
    cleaned_text = strip_reference_apparatus(cleaned_text, source)
    cleaned_text = cleaned_text.strip()
    if not cleaned_text:
        raise ValueError(f"{source}: no text remains after cleaning")
    return cleaned_text


def load_documents(documents_dir: str | Path) -> list[Document]:
    """Read and clean direct UTF-8 ``.txt`` children in deterministic order."""
    directory = Path(documents_dir)
    documents = []
    for path in sorted(directory.glob("*.txt"), key=lambda item: item.name.casefold()):
        raw_text = path.read_text(encoding="utf-8")
        cleaned_text = clean_gutenberg_text(raw_text, path.name)
        documents.append(
            Document(
                source=path.name,
                text=cleaned_text,
                original_char_count=len(raw_text),
                cleaned_char_count=len(cleaned_text),
            )
        )
    return documents


def write_cleaned_documents(documents: Iterable[Document], output_dir: str | Path) -> None:
    """Write reviewable UTF-8 copies of cleaned documents using their source filenames."""
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    for document in documents:
        (destination / document.source).write_text(f"{document.text}\n", encoding="utf-8")


def format_ingestion_report(documents: Iterable[Document]) -> str:
    """Return a concise audit summary for an ingestion run."""
    records = list(documents)
    original_total = sum(document.original_char_count for document in records)
    cleaned_total = sum(document.cleaned_char_count for document in records)
    lines = [
        f"Loaded {len(records)} documents.",
        f"Characters: {original_total:,} original -> {cleaned_total:,} cleaned.",
        "",
    ]
    lines.extend(
        f"- {document.source}: {document.original_char_count:,} -> {document.cleaned_char_count:,}"
        for document in records
    )
    return "\n".join(lines)


def main() -> None:
    """Clean source files into a review directory and print an audit report."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("documents_dir", type=Path, nargs="?", default=Path("documents"))
    parser.add_argument("output_dir", type=Path, nargs="?", default=Path("cleaned_documents"))
    args = parser.parse_args()

    documents = load_documents(args.documents_dir)
    write_cleaned_documents(documents, args.output_dir)
    print(format_ingestion_report(documents))


if __name__ == "__main__":
    main()
