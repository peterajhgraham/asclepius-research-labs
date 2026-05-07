"""Sliding window text chunker for large documents."""

from __future__ import annotations


def chunk_text(
    text: str,
    chunk_size: int = 200,
    overlap: int = 50,
) -> list[str]:
    """Split text into overlapping word-level chunks.

    Args:
        text: Input text to chunk.
        chunk_size: Maximum number of words per chunk.
        overlap: Number of words to overlap between consecutive chunks.

    Returns:
        List of text chunks. Single-chunk texts are returned as-is.
    """
    words = text.split()
    if len(words) <= chunk_size:
        return [text]

    chunks: list[str] = []
    start = 0
    while start < len(words):
        end = min(start + chunk_size, len(words))
        chunks.append(" ".join(words[start:end]))
        if end >= len(words):
            break
        start += chunk_size - overlap
    return chunks
