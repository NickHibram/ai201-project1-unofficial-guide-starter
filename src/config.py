"""Configuration for the local music-knowledge RAG pipeline."""

from __future__ import annotations

import os
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

if load_dotenv is not None:
    load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parents[1]

# Generation (Milestone 5)
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
LLM_MODEL = "openai/gpt-oss-120b"

# Embeddings
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
# None adopts the loaded model's max_seq_length. Set a lower integer to override it.
EMBEDDING_MAX_TOKENS: int | None = None
EMBEDDING_WINDOW_OVERLAP_TOKENS = 32
MIN_EMBEDDING_WINDOW_TOKENS = 32
EMBEDDING_BATCH_SIZE = 64

# Vector store
CHROMA_COLLECTION = "music_knowledge"
CHROMA_PATH = PROJECT_ROOT / "chroma_db"

# Retrieval
N_RESULTS = 5

# Chunk artifact
CHUNKS_PATH = PROJECT_ROOT / "chunks.jsonl"
