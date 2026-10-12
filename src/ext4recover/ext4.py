"""EXT4 superblock and on-disk inspection functions."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .structs import (
    EXT4_MAGIC,
    BlockGroupDescriptor,
    Extent,
    ExtentHeader,
    Inode,
    Superblock,
    Ext4StructError,
)

class Ext4Error(ValueError):
    """The supplied image does not expose a valid EXT4 superblock."""


def inspect_superblock(image: str | Path, offset: int = 0) -> dict[str, Any]:
    with Path(image).open("rb") as stream:
        stream.seek(offset + 1024)
        raw = stream.read(1024)
    if len(raw) != 1024:
        raise Ext4Error("Image is too small for an EXT4 superblock.")
    
    try:
        sb = Superblock(raw)
    except Ext4StructError as exc:
        raise Ext4Error(str(exc)) from exc

    if not sb.is_valid_magic:
        raise Ext4Error(f"EXT4 magic not found at offset {offset + 1080} (found 0x{sb.magic:04X}).")

    return {
        "filesystem": sb.filesystem_label,
        "block_size": sb.block_size,
        "inode_size": sb.inode_size,
        "inodes": sb.s_inodes_count,
        "blocks": sb.blocks_count,
        "journal_inode": sb.s_journal_inum,
        "first_data_block": sb.s_first_data_block,
        "blocks_per_group": sb.s_blocks_per_group,
        "inodes_per_group": sb.s_inodes_per_group,
        "group_count": sb.group_count,
        "has_64bit": sb.has_64bit,
        "has_extents": sb.has_extents,
        "has_flex_bg": sb.has_flex_bg,
        "has_journal": sb.has_journal,
        "unsupported_incompat_features": sb.unsupported_incompat_features,
    }
