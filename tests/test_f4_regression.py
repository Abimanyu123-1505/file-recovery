"""Regression tests for Finding F4.

F4: Add feature-flag checks: identify the filesystem as ext2/ext3/ext4 from compat/incompat
flags and report that exact label; refuse or clearly flag unsupported incompat features
(inline_data, bigalloc, meta_bg, encrypt, casefold, compression) with a plain-language
limitation recorded in the scan and report. Use s_first_data_block when computing the group
count. Scan ALL valid filesystem offsets (partitions) and tag every finding with its filesystem
offset. Cross-check candidates against the inode bitmap; require deletion_time to look plausible
(> 2000-01-01 and not an orphan-chain value; links_count == 0), and put suspect inodes in a
separate 'orphan/uncertain' category instead of 'deleted'.
"""

import io
import struct
from pathlib import Path
import pytest

from ext4recover.structs import (
    Superblock,
    Inode,
    EXT4_MAGIC,
    INCOMPAT_EXTENTS,
    INCOMPAT_INLINE_DATA,
    INCOMPAT_ENCRYPT,
    COMPAT_HAS_JOURNAL,
)
from ext4recover.partitions import find_filesystem_offsets


def test_f4_filesystem_identification_labels():
    raw = bytearray(1024)
    struct.pack_into("<H", raw, 56, EXT4_MAGIC)

    # EXT2: no journal, no extents
    sb_ext2 = Superblock(bytes(raw))
    assert sb_ext2.filesystem_label == "EXT2"

    # EXT3: journal present, no extents
    struct.pack_into("<I", raw, 92, COMPAT_HAS_JOURNAL)
    sb_ext3 = Superblock(bytes(raw))
    assert sb_ext3.filesystem_label == "EXT3"

    # EXT4: extents present
    struct.pack_into("<I", raw, 96, INCOMPAT_EXTENTS)
    sb_ext4 = Superblock(bytes(raw))
    assert sb_ext4.filesystem_label == "EXT4"


def test_f4_unsupported_incompat_features():
    raw = bytearray(1024)
    struct.pack_into("<H", raw, 56, EXT4_MAGIC)
    struct.pack_into("<I", raw, 96, INCOMPAT_EXTENTS | INCOMPAT_INLINE_DATA | INCOMPAT_ENCRYPT)

    sb = Superblock(bytes(raw))
    unsupported = sb.unsupported_incompat_features
    assert any("inline_data" in u for u in unsupported)
    assert any("encrypt" in u for u in unsupported)


def test_f4_group_count_uses_s_first_data_block():
    raw = bytearray(1024)
    struct.pack_into("<H", raw, 56, EXT4_MAGIC)
    struct.pack_into("<I", raw, 4, 10001)       # s_blocks_count_lo = 10001
    struct.pack_into("<I", raw, 20, 1)          # s_first_data_block = 1 (1KB block size)
    struct.pack_into("<I", raw, 32, 5000)       # s_blocks_per_group = 5000

    sb = Superblock(bytes(raw))
    # (10001 - 1) / 5000 = 10000 / 5000 = exactly 2 groups!
    # Without s_first_data_block: ceil(10001 / 5000) = 3 (wrong!)
    assert sb.group_count == 2


def test_f4_scan_mbr_partition_offsets(tmp_path):
    img = tmp_path / "partitioned.img"
    # Create image with MBR partition table
    # Sector 0 (512 bytes): MBR with partition 1 starting at sector 2048 (offset 1048576)
    mbr = bytearray(512)
    mbr[510] = 0x55
    mbr[511] = 0xAA

    # Partition 1 entry at offset 446:
    part1 = bytearray(16)
    part1[4] = 0x83  # Linux partition
    struct.pack_into("<I", part1, 8, 2048)   # start LBA: 2048
    struct.pack_into("<I", part1, 12, 10000) # num sectors
    mbr[446:462] = part1

    # Write MBR
    with img.open("wb") as f:
        f.write(mbr)
        # Write EXT4 superblock at 2048 * 512 + 1024
        f.seek(2048 * 512 + 1024 + 56)
        f.write(struct.pack("<H", EXT4_MAGIC))
        # Ensure file extends beyond
        f.seek(2048 * 512 + 4096)
        f.write(b"\x00")

    offsets = find_filesystem_offsets(img)
    assert 2048 * 512 in offsets


def test_f4_plausible_deletion_time_and_orphan_categorization():
    """Suspect inodes with dtime < 2000-01-01 or small int are categorized as orphan/uncertain."""
    # Plausible deleted inode (dtime in 2024, links_count = 0)
    raw = bytearray(128)
    struct.pack_into("<H", raw, 0, 0x81A4)
    struct.pack_into("<I", raw, 4, 100)
    struct.pack_into("<I", raw, 20, 1718000000)  # 2024
    struct.pack_into("<H", raw, 26, 0)           # links_count = 0

    valid_del = Inode(bytes(raw))
    assert valid_del.is_deleted is True
    assert valid_del.is_orphan_suspect is False

    # Orphan-chain suspect (dtime = 3)
    struct.pack_into("<I", raw, 20, 3)
    orphan = Inode(bytes(raw))
    assert orphan.is_orphan_suspect is True

    # Pre-2000 suspect (dtime = 500000)
    struct.pack_into("<I", raw, 20, 500000)
    old = Inode(bytes(raw))
    assert old.is_orphan_suspect is True
