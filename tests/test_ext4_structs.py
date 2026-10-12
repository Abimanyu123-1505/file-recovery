"""Tests for EXT4 low-level on-disk structures (Superblock, Group Descriptors, Inode, Extents)."""

import struct
import pytest
from ext4recover.structs import (
    EXT4_MAGIC,
    BlockGroupDescriptor,
    Extent,
    ExtentHeader,
    Inode,
    Superblock,
    Ext4StructError,
    INCOMPAT_64BIT,
    INCOMPAT_EXTENTS,
    INCOMPAT_FLEX_BG,
    COMPAT_HAS_JOURNAL,
)


def make_superblock_bytes(
    magic=0xEF53,
    inodes_count=1000,
    blocks_count_lo=2000,
    blocks_count_hi=5,
    first_data_block=0,
    log_block_size=2,  # 4096
    blocks_per_group=1000,
    inode_size=256,
    feature_compat=0,
    feature_incompat=0,
    desc_size=32,
) -> bytes:
    buf = bytearray(1024)
    struct.pack_into("<I", buf, 0, inodes_count)
    struct.pack_into("<I", buf, 4, blocks_count_lo)
    struct.pack_into("<I", buf, 20, first_data_block)
    struct.pack_into("<I", buf, 24, log_block_size)
    struct.pack_into("<I", buf, 32, blocks_per_group)
    struct.pack_into("<H", buf, 56, magic)
    struct.pack_into("<H", buf, 88, inode_size)
    struct.pack_into("<I", buf, 92, feature_compat)
    struct.pack_into("<I", buf, 96, feature_incompat)
    struct.pack_into("<H", buf, 254, desc_size)
    struct.pack_into("<I", buf, 336, blocks_count_hi)
    return bytes(buf)


def test_superblock_properties():
    raw = make_superblock_bytes(
        magic=EXT4_MAGIC,
        feature_incompat=INCOMPAT_EXTENTS | INCOMPAT_FLEX_BG,
    )
    sb = Superblock(raw)
    assert sb.magic == 0xEF53
    assert sb.is_valid_magic is True
    assert sb.block_size == 4096
    assert sb.inode_size == 256
    assert sb.filesystem_label == "EXT4"
    assert sb.has_extents is True
    assert sb.has_64bit is False
    assert sb.blocks_count == 2000  # blocks_count_hi ignored because 64BIT not set


def test_superblock_64bit_blocks_count():
    raw = make_superblock_bytes(
        blocks_count_lo=0x1000,
        blocks_count_hi=0x2,
        feature_incompat=INCOMPAT_64BIT | INCOMPAT_EXTENTS,
    )
    sb = Superblock(raw)
    assert sb.has_64bit is True
    # 0x2 << 32 | 0x1000 = 8589938688
    assert sb.blocks_count == (2 << 32) | 0x1000


def test_superblock_first_data_block_group_count():
    # 1KB block size on ext4 usually has first_data_block = 1
    raw = make_superblock_bytes(
        blocks_count_lo=8001,
        first_data_block=1,
        blocks_per_group=4000,
    )
    sb = Superblock(raw)
    assert sb.group_count == 2  # ceil((8001 - 1) / 4000) = 2


def test_superblock_filesystem_identification():
    # EXT4
    sb4 = Superblock(make_superblock_bytes(feature_incompat=INCOMPAT_EXTENTS))
    assert sb4.filesystem_label == "EXT4"

    # EXT3 (has journal, no extents/64bit/flex_bg)
    sb3 = Superblock(make_superblock_bytes(feature_compat=COMPAT_HAS_JOURNAL))
    assert sb3.filesystem_label == "EXT3"

    # EXT2 (no journal, no extents)
    sb2 = Superblock(make_superblock_bytes())
    assert sb2.filesystem_label == "EXT2"


def test_group_descriptor_f1_offset_0x28():
    """Finding F1: Read bg_inode_table_hi at offset 0x28 (not 48), only when 64BIT and desc_size >= 64."""
    buf = bytearray(64)
    # 32-bit fields
    struct.pack_into("<I", buf, 0, 100)   # block_bitmap_lo
    struct.pack_into("<I", buf, 4, 101)   # inode_bitmap_lo
    struct.pack_into("<I", buf, 8, 102)   # inode_table_lo
    # 64-bit high fields
    # Offset 0x28 (40 decimal): bg_inode_table_hi
    struct.pack_into("<I", buf, 0x28, 0x000A)
    # Offset 48 (0x30): bg_used_dirs_count_hi (if someone read offset 48, they read wrong field!)
    struct.pack_into("<H", buf, 48, 0x00FF)

    # Without 64bit flag:
    desc32 = BlockGroupDescriptor(bytes(buf), has_64bit=False, desc_size=32)
    assert desc32.inode_table == 102

    # With 64bit flag and desc_size >= 64:
    desc64 = BlockGroupDescriptor(bytes(buf), has_64bit=True, desc_size=64)
    assert desc64.bg_inode_table_hi == 0x000A
    # Inode table address combined:
    assert desc64.inode_table == (0x000A << 32) | 102


def test_inode_is_deleted_honest_property():
    """T1/T2: Inode.is_deleted = mode set and dtime set and links_count == 0."""
    raw = bytearray(128)
    # Regular file: mode 0x81A4 (-rw-r--r--)
    struct.pack_into("<H", raw, 0, 0x81A4)
    # Size 500
    struct.pack_into("<I", raw, 4, 500)
    # dtime = 1718000000 (valid deletion time)
    struct.pack_into("<I", raw, 20, 1718000000)
    # links_count = 0
    struct.pack_into("<H", raw, 26, 0)

    deleted_inode = Inode(bytes(raw), inode_num=12)
    assert deleted_inode.is_deleted is True
    assert deleted_inode.is_orphan_suspect is False

    # If links_count > 0, not deleted!
    struct.pack_into("<H", raw, 26, 1)
    allocated_inode = Inode(bytes(raw), inode_num=12)
    assert allocated_inode.is_deleted is False

    # If dtime == 0, not deleted!
    struct.pack_into("<H", raw, 26, 0)
    struct.pack_into("<I", raw, 20, 0)
    live_inode = Inode(bytes(raw), inode_num=12)
    assert live_inode.is_deleted is False


def test_inode_orphan_suspect():
    """Finding F4: suspect orphan inode with small integer dtime."""
    raw = bytearray(128)
    struct.pack_into("<H", raw, 0, 0x81A4)
    # dtime = 5 (small integer in orphan chain)
    struct.pack_into("<I", raw, 20, 5)
    struct.pack_into("<H", raw, 26, 0)

    orphan_inode = Inode(bytes(raw), inode_num=14)
    assert orphan_inode.is_deleted is True
    assert orphan_inode.is_orphan_suspect is True


def test_extent_f3_len_32768_rule():
    """Finding F3: raw > 32768 means unwritten extent of length (raw - 32768)."""
    raw_entry = bytearray(12)
    # ee_block = 0, ee_len = 10 (normal initialized extent)
    struct.pack_into("<IHHI", raw_entry, 0, 0, 10, 0, 1000)
    e1 = Extent.from_bytes(bytes(raw_entry))
    assert e1.is_unwritten is False
    assert e1.length == 10

    # ee_len = 32778 (raw > 32768 -> unwritten extent of length 10)
    struct.pack_into("<IHHI", raw_entry, 0, 0, 32778, 0, 1000)
    e2 = Extent.from_bytes(bytes(raw_entry))
    assert e2.is_unwritten is True
    assert e2.length == 10
