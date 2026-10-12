"""Streaming cryptographic hashes for evidence and derived files.

Supports chunked processing, progress reporting, and cooperative cancellation (Finding I1).
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Callable, Optional


def sha256_file(
    path: str | Path,
    chunk_size: int = 1024 * 1024,
    progress_callback: Optional[Callable[[int, int], None]] = None,
    check_cancelled: Optional[Callable[[], bool]] = None,
) -> str:
    """Compute SHA-256 hash in bounded chunks with cancellation and progress reporting."""
    digest = hashlib.sha256()
    p = Path(path)
    total = p.stat().st_size if p.exists() else 0
    hashed = 0

    with p.open("rb") as stream:
        while True:
            if check_cancelled and check_cancelled():
                raise RuntimeError("Operation cancelled by user.")

            block = stream.read(chunk_size)
            if not block:
                break

            digest.update(block)
            hashed += len(block)
            if progress_callback:
                progress_callback(hashed, total)

    return digest.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
