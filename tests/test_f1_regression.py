"""Regression test for Finding F1.

F1: Read bg_inode_table_hi at offset 0x28 (not 48), only when the 64BIT incompat flag
is set and desc_size >= 64. Apply blocks_count_hi only when 64BIT is set.
"""

import struct
from ext4recover.structs import (
    BlockGroupDescriptor,
    Superblock,
    INCOMPAT_64BIT,
)


def test_f1_bg_inode_table_hi_offset_0x28_not_48():
    buf = bytearray(64)
    # Lower 32 bits of inode table
    struct.pack_into("<I", buf, 8, 0x1000)

    # Offset 0x28 (40 decimal): bg_inode_table_hi
    struct.pack_into("<I", buf, 0x28, 0x0005)

    # Offset 48 (0x30): dummy value that would corrupt inode_table if offset 48 were mistakenly read
    struct.pack_into("<I", buf, 48, 0x9999)

    # With 64bit and desc_size >= 64:
    desc = BlockGroupDescriptor(bytes(buf), has_64bit=True, desc_size=64)
    assert desc.bg_inode_table_hi == 0x0005
    expected_full = (0x0005 << 32) | 0x1000
    assert desc.inode_table == expected_full
    assert desc.inode_table != (0x9999 << 32) | 0x1000


def test_f1_bg_inode_table_hi_ignored_without_64bit():
    buf = bytearray(64)
    struct.pack_into("<I", buf, 8, 0x1000)
    struct.pack_into("<I", buf, 0x28, 0x0005)

    # has_64bit is False: high bits must be ignored
    desc = BlockGroupDescriptor(bytes(buf), has_64bit=False, desc_size=64)
    assert desc.bg_inode_table_hi == 0
    assert desc.inode_table == 0x1000


def test_f1_blocks_count_hi_only_when_64bit():
    sb_bytes = bytearray(1024)
    struct.pack_into("<I", sb_bytes, 4, 1000)       # s_blocks_count_lo
    struct.pack_into("<I", sb_bytes, 336, 10)       # s_blocks_count_hi
    struct.pack_into("<H", sb_bytes, 56, 0xEF53)    # magic

    # Without 64bit flag:
    sb_no_64 = Superblock(bytes(sb_bytes))
    assert sb_no_64.blocks_count == 1000

    # With 64bit flag:
    struct.pack_into("<I", sb_bytes, 96, INCOMPAT_64BIT)
    sb_64 = Superblock(bytes(sb_bytes))
    assert sb_64.blocks_count == (10 << 32) | 1000
