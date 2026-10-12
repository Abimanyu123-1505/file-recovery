"""EXT4 filename reconstruction and provenance tracing.

Implements cautious name mapping, strict parent-chain validation, and slack dirent heuristics.
Forensic principles:
- Never claim certainty when parent is unconfirmed.
- Strict source priority: active_dirent > deleted_dirent > slack_heuristic.
- Confidence tiers: Confirmed, Probable, Uncertain.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


@dataclass
class NameRecord:
    inode: int
    name: str
    source: str  # active_dirent, deleted_dirent, slack_heuristic
    path: Optional[str] = None
    parent_allocated: bool = True
    confidence: str = "Uncertain"  # Confirmed, Probable, Uncertain


def full_path(
    name: str,
    parent_chain: Optional[List[int]] = None,
    dir_names: Optional[Dict[int, str]] = None,
    root_inode: int = 2,
) -> str:
    """Reconstruct full directory path.
    
    Finding F5 (a): If the chain does not terminate at root inode 2,
    return '/…/name' or '(parent unknown)/name', NEVER '/name'.
    """
    if not name:
        return ""

    if not parent_chain:
        return f"/…/{name}"

    # Does the chain reach root_inode (2)?
    if parent_chain[-1] != root_inode:
        return f"/…/{name}"

    # Build forward path from root
    # parent_chain is e.g. [leaf_inode, parent_inode, ..., root_inode]
    dirs = []
    dir_map = dir_names or {}
    for p_ino in reversed(parent_chain[:-1]):
        if p_ino in dir_map:
            dirs.append(dir_map[p_ino])

    if dirs:
        return f"/{'/'.join(dirs)}/{name}"
    return f"/{name}"


def validate_slack_dirent(
    raw: bytes,
    offset: int,
    max_inodes: int,
    active_spans: Optional[List[Tuple[int, int]]] = None,
) -> Optional[dict]:
    """Validate a candidate directory entry found in directory slack space.
    
    Finding F5 (c):
    - Skip offsets that coincide with an active entry.
    - Validate 0 < inode <= inodes_count.
    - Validate file_type byte in 0..7.
    - Validate name_len > 0 and printable UTF-8.
    - Never relabel active entries.
    """
    if active_spans:
        for start, end in active_spans:
            if start <= offset < end:
                return None

    if len(raw) < 8:
        return None

    inode = struct.unpack_from("<I", raw, 0)[0]
    if inode <= 0 or inode > max_inodes:
        return None

    rec_len = struct.unpack_from("<H", raw, 4)[0]
    name_len = raw[6]
    file_type = raw[7]

    if file_type > 7:
        return None

    if name_len == 0 or name_len > 255 or 8 + name_len > len(raw):
        return None

    name_bytes = raw[8 : 8 + name_len]
    try:
        name_str = name_bytes.decode("utf-8")
    except UnicodeDecodeError:
        return None

    # Check for printable chars (no control characters except none)
    if not all(c.isprintable() for c in name_str):
        return None

    if name_str in (".", ".."):
        return None

    return {
        "inode": inode,
        "name": name_str,
        "rec_len": rec_len,
        "file_type": file_type,
    }


def build_name_map(records: List[NameRecord]) -> Dict[int, NameRecord]:
    """Build name map with strict source priority.
    
    Finding F5 (b) & (d):
    - Priority: active_dirent > deleted_dirent > slack_heuristic
    - Prefer entries whose parent directory is still allocated.
    - Confidence label:
      active_dirent -> Confirmed
      deleted_dirent with allocated parent -> Probable
      others -> Uncertain
    """
    priority = {
        "active_dirent": 30,
        "deleted_dirent": 20,
        "slack_heuristic": 10,
    }

    by_inode: dict[int, list[NameRecord]] = {}
    for r in records:
        by_inode.setdefault(r.inode, []).append(r)

    result: dict[int, NameRecord] = {}
    for inode, candidates in by_inode.items():
        def score(cand: NameRecord) -> float:
            base = priority.get(cand.source, 0)
            if cand.parent_allocated:
                base += 5
            return base

        best = max(candidates, key=score)

        if best.source == "active_dirent":
            confidence = "Confirmed"
        elif best.source == "deleted_dirent" and best.parent_allocated:
            confidence = "Probable"
        else:
            confidence = "Uncertain"

        best.confidence = confidence
        result[inode] = best

    return result
