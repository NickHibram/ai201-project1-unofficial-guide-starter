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
class Document:
    """A cleaned source document with enough metadata for later pipeline stages."""

    source: str
    text: str
    original_char_count: int
    cleaned_char_count: int


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
