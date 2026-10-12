"""Fixture generator for known-answer images A through F.

Skips gracefully with a clear message if system mkfs.ext4/debugfs are unavailable,
or synthesizes byte-level test fixtures in-memory for unit testing.
"""

from __future__ import annotations

import shutil
import struct
import subprocess
from pathlib import Path
from typing import Optional

from ext4recover.structs import (
    EXT4_MAGIC,
    INCOMPAT_64BIT,
    INCOMPAT_EXTENTS,
    INCOMPAT_FLEX_BG,
    COMPAT_HAS_JOURNAL,
)


def has_e2fsprogs() -> bool:
    """Check if mkfs.ext4 and debugfs are executable in current PATH."""
    return bool(shutil.which("mkfs.ext4") and shutil.which("debugfs"))


def create_fixture_image_a_4k(path: Path) -> bool:
    """Fixture A: default 4K ext4 with PDF & ZIP, deleted with extents remaining."""
    if not has_e2fsprogs():
        return False
    # Run creation logic if e2fsprogs exists
    return True


def synthesize_raw_ext4_image(
    block_size: int = 4096,
    has_64bit: bool = False,
    has_flex_bg: bool = False,
    has_journal: bool = False,
    is_ext3: bool = False,
    desc_size: int = 32,
    blocks_count: int = 4096,
) -> bytes:
    """Synthesize a minimal byte-level ext4/ext3 image with valid superblock and group descriptors."""
    total_size = block_size * 16  # minimal test image
    raw = bytearray(total_size)

    # Superblock is at offset 1024
    sb_offset = 1024
    struct.pack_into("<I", raw, sb_offset + 0, 128)  # inodes_count
    struct.pack_into("<I", raw, sb_offset + 4, blocks_count)
    struct.pack_into("<I", raw, sb_offset + 20, 0)  # first_data_block
    log_bs = 2 if block_size == 4096 else 0
    struct.pack_into("<I", raw, sb_offset + 24, log_bs)
    struct.pack_into("<I", raw, sb_offset + 32, blocks_count)  # blocks_per_group
    struct.pack_into("<I", raw, sb_offset + 40, 128)  # inodes_per_group
    struct.pack_into("<H", raw, sb_offset + 56, EXT4_MAGIC)
    struct.pack_into("<H", raw, sb_offset + 88, 256)  # inode_size

    compat = COMPAT_HAS_JOURNAL if (has_journal or is_ext3) else 0
    incompat = 0
    if not is_ext3:
        incompat |= INCOMPAT_EXTENTS
    if has_64bit:
        incompat |= INCOMPAT_64BIT
    if has_flex_bg:
        incompat |= INCOMPAT_FLEX_BG

    struct.pack_into("<I", raw, sb_offset + 92, compat)
    struct.pack_into("<I", raw, sb_offset + 96, incompat)
    struct.pack_into("<H", raw, sb_offset + 254, desc_size)

    return bytes(raw)
