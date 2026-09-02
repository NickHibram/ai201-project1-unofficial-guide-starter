"""Recursive, source-attributed chunking for the music knowledge corpus."""

from __future__ import annotations

import argparse
import json
import re
import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from src.ingestion import Document, load_documents


MAX_CHUNK_CHARS = 900
CHUNK_OVERLAP_CHARS = 150
MIN_CHUNK_CHARS = 150
SEPARATORS = ("\n\n", ". ", "? ", "! ", " ", "")
ABBREVIATIONS = {
    "mr.", "mrs.", "ms.", "dr.", "st.", "op.", "no.", "nos.", "vol.",
    "fig.", "pp.", "viz.", "etc.", "&c.", "jan.", "feb.", "mar.", "apr.",
    "jun.", "jul.", "aug.", "sep.", "sept.", "oct.", "nov.", "dec.",
}
TABLE_SPACING = re.compile(r"\S {2,}\S")


@dataclass(frozen=True)
class ChunkUnit:
    text: str
    is_table: bool = False


def normalize_for_chunking(text: str) -> str:
    """Normalize prose for splitting while retaining paragraph boundaries."""
    paragraphs = re.split(r"\n[ \t]*\n+", text.strip())
    return "\n\n".join(re.sub(r"\s+", " ", paragraph).strip() for paragraph in paragraphs if paragraph.strip())


def _is_table(text: str) -> bool:
    return sum(bool(TABLE_SPACING.search(line)) for line in text.splitlines()) >= 2


def _is_noise(text: str) -> bool:
    compact = " ".join(text.split())
    lowered = compact.lower()
    if re.fullmatch(r"\[illustration(?::[^\]]*)?\]", compact, re.IGNORECASE):
        return True
    if lowered.startswith(("copyright", "all rights reserved", "printed by", "printer:")):
        return True
    if re.fullmatch(r"[ivxlcdm,; .]+", compact, re.IGNORECASE):
        return True
    return False


def _units(text: str) -> list[ChunkUnit]:
    raw_paragraphs = [part.strip("\n") for part in re.split(r"\n[ \t]*\n+", text.strip()) if part.strip()]
    units: list[ChunkUnit] = []
    for paragraph in raw_paragraphs:
        if _is_noise(paragraph):
            continue
        if _is_table(paragraph):
            if units and not units[-1].is_table and units[-1].text.rstrip().endswith((":", ":—", "—")):
                units[-1] = ChunkUnit(f"{units[-1].text}\n\n{paragraph}", is_table=True)
            else:
                units.append(ChunkUnit(paragraph, is_table=True))
        else:
            units.append(ChunkUnit(re.sub(r"\s+", " ", paragraph).strip()))
    return units


def _is_abbreviation_boundary(text: str, index: int) -> bool:
    prefix = text[: index + 1]
    match = re.search(r"([^\s]+)$", prefix)
    if not match:
        return False
    token = match.group(1).lower()
    return token in ABBREVIATIONS or bool(re.fullmatch(r"[a-zA-Z]\.", token))


def _split_once(text: str, separator: str) -> list[str]:
    if not separator:
        return [text[index : index + MAX_CHUNK_CHARS] for index in range(0, len(text), MAX_CHUNK_CHARS)]
    if separator == "\n\n":
        return [piece.strip() for piece in text.split(separator) if piece.strip()]

    pieces: list[str] = []
    start = 0
    cursor = 0
    while True:
        found = text.find(separator, cursor)
        if found < 0:
            break
        if separator == ". " and _is_abbreviation_boundary(text, found):
            cursor = found + len(separator)
            continue
        end = found + 1  # Keep terminal punctuation, but not the following space.
        pieces.append(text[start:end].strip())
        start = found + len(separator)
        cursor = start
    pieces.append(text[start:].strip())
    return [piece for piece in pieces if piece]


def _recursive_pieces(text: str, separator_index: int = 0) -> list[str]:
    if len(text) <= MAX_CHUNK_CHARS:
        return [text]
    if separator_index >= len(SEPARATORS):
        return [text[index : index + MAX_CHUNK_CHARS] for index in range(0, len(text), MAX_CHUNK_CHARS)]

    pieces = _split_once(text, SEPARATORS[separator_index])
    if len(pieces) == 1:
        return _recursive_pieces(text, separator_index + 1)

    result: list[str] = []
    for piece in pieces:
        if len(piece) > MAX_CHUNK_CHARS:
            result.extend(_recursive_pieces(piece, separator_index + 1))
        else:
            result.append(piece)
    return result


def _semantic_overlap(parts: list[str]) -> list[str]:
    overlap: list[str] = []
    length = 0
    for part in reversed(parts):
        added = len(part) + (1 if overlap else 0)
        if length + added > CHUNK_OVERLAP_CHARS:
            break
        overlap.insert(0, part)
        length += added
    return overlap


def _pack_prose(text: str) -> list[str]:
    pieces = _recursive_pieces(text)
    chunks: list[str] = []
    current: list[str] = []

    for piece in pieces:
        candidate = " ".join([*current, piece])
        if current and len(candidate) > MAX_CHUNK_CHARS:
            chunks.append(" ".join(current))
            current = _semantic_overlap(current)
            if current and len(" ".join([*current, piece])) > MAX_CHUNK_CHARS:
                current = []
        current.append(piece)

    if current:
        final = " ".join(current)
        if len(final) < MIN_CHUNK_CHARS and chunks:
            merged = f"{chunks[-1]} {final}"
            if len(merged) <= MAX_CHUNK_CHARS:
                chunks[-1] = merged
            else:
                chunks.append(final)
        else:
            chunks.append(final)

    return [chunk for chunk in chunks if len(chunk) >= MIN_CHUNK_CHARS]


def _split_table(text: str) -> list[str]:
    if len(text) <= MAX_CHUNK_CHARS:
        return [text]

    lines = text.splitlines()
    first_row = next((index for index, line in enumerate(lines) if TABLE_SPACING.search(line)), 0)
    intro = lines[:first_row]
    rows = lines[first_row:]
    header = rows[0] if rows else ""
    chunks: list[str] = []
    intro_text = "\n".join(intro).strip()
    if len(intro_text) > MAX_CHUNK_CHARS:
        intro_chunks = _pack_prose(normalize_for_chunking(intro_text))
        chunks.extend(intro_chunks[:-1])
        current = [intro_chunks[-1]]
    else:
        current = intro.copy()
    for row in rows:
        candidate = "\n".join([*current, row])
        if current and len(candidate) > MAX_CHUNK_CHARS:
            chunks.append("\n".join(current))
            current = [header] if header else []
        if len(row) > MAX_CHUNK_CHARS:
            row_parts = _recursive_pieces(row, SEPARATORS.index(" "))
            for row_part in row_parts:
                if len("\n".join([*current, row_part])) > MAX_CHUNK_CHARS and current:
                    chunks.append("\n".join(current))
                    current = [header] if header else []
                current.append(row_part)
        else:
            current.append(row)
    if current:
        chunks.append("\n".join(current))
    return chunks


def chunk_documents(documents: Iterable[Document]) -> list[dict[str, str]]:
    """Return deterministic source-attributed chunks for a sequence of documents."""
    chunks: list[dict[str, str]] = []
    for document in documents:
        source_chunks: list[str] = []
        prose_parts: list[str] = []

        def flush_prose() -> None:
            if prose_parts:
                source_chunks.extend(_pack_prose("\n\n".join(prose_parts)))
                prose_parts.clear()

        for unit in _units(document.text):
            if unit.is_table:
                flush_prose()
                source_chunks.extend(_split_table(unit.text))
            else:
                prose_parts.append(unit.text)
        flush_prose()

        for index, chunk_text in enumerate(source_chunks, start=1):
            chunks.append(
                {
                    "chunk_id": f"{document.source}::{index:05d}",
                    "source": document.source,
                    "chunk_txt": chunk_text,
                }
            )
    return chunks


def write_chunks_jsonl(chunks: Iterable[dict[str, str]], output_path: str | Path) -> None:
    """Write chunks as one UTF-8 JSON object per line."""
    path = Path(output_path)
    with path.open("w", encoding="utf-8") as handle:
        for chunk in chunks:
            handle.write(json.dumps(chunk, ensure_ascii=False) + "\n")


def main() -> None:
    """Load cleaned documents, chunk them, and write a JSONL review artifact."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("documents_dir", type=Path, nargs="?", default=Path("documents"))
    parser.add_argument("output_path", type=Path, nargs="?", default=Path("chunks.jsonl"))
    args = parser.parse_args()

    chunks = chunk_documents(load_documents(args.documents_dir))
    write_chunks_jsonl(chunks, args.output_path)
    lengths = [len(chunk["chunk_txt"]) for chunk in chunks]
    print(f"Created {len(chunks):,} chunks.")
    print(f"Characters: min={min(lengths):,}, median={statistics.median(lengths):,.0f}, max={max(lengths):,}.")


if __name__ == "__main__":
    main()
