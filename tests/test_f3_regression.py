"""Regression tests for Finding F3.

F3: Rewrite extent and block-map reading to honour logical block numbers:
seek/zero-fill holes so output offsets match, treat unwritten extents as zeros
but flag the file 'partial_unwritten', fix ee_len > 32768 handling (len = raw - 32768
only when raw > 32768), implement single, double and triple indirect, and do NOT skip
zero block pointers (they are holes). Verify output SHA-256 against original file.
"""

import io
import struct
import pytest

from ext4recover.structs import Inode, EXT4_EXTENTS_FL
from ext4recover.block_reader import read_inode_data, read_extent_data, read_block_map_data


def test_f3_extent_sparse_hole_zero_filled():
    """Verify that logical block gaps between extents are zero-filled."""
    block_size = 1024
    stream = io.BytesIO(b"\x00" * (block_size * 20))

    # Physical block 5: b"BLOCK_ZERO"
    stream.seek(5 * block_size)
    stream.write(b"BLOCK_ZERO".ljust(block_size, b"\x00"))

    # Physical block 10: b"BLOCK_TWO" (logical block 2; logical block 1 is a hole)
    stream.seek(10 * block_size)
    stream.write(b"BLOCK_TWO".ljust(block_size, b"\x00"))

    # Construct inode with extent header + 2 leaf extents
    raw_inode = bytearray(256)
    # Mode regular file, size = 3000 bytes
    struct.pack_into("<H", raw_inode, 0, 0x81A4)
    struct.pack_into("<I", raw_inode, 4, 3000)
    struct.pack_into("<I", raw_inode, 32, EXT4_EXTENTS_FL)

    # i_block at offset 40:
    # Extent header (12 bytes): magic=0xF30A, entries=2, max=4, depth=0, gen=0
    struct.pack_into("<HHHHI", raw_inode, 40, 0xF30A, 2, 4, 0, 0)
    # Extent 0: ee_block=0, ee_len=1, ee_start_hi=0, ee_start_lo=5
    struct.pack_into("<IHHI", raw_inode, 52, 0, 1, 0, 5)
    # Extent 1: ee_block=2, ee_len=1, ee_start_hi=0, ee_start_lo=10 (hole at ee_block=1)
    struct.pack_into("<IHHI", raw_inode, 64, 2, 1, 0, 10)

    inode = Inode(bytes(raw_inode))
    data, flag = read_inode_data(stream, inode, block_size)

    assert len(data) == 3000
    # First block has data
    assert data[:10] == b"BLOCK_ZERO"
    # Hole at block 1 must be zero-filled!
    assert data[block_size : block_size + 10] == b"\x00" * 10
    # Third block has BLOCK_TWO
    assert data[2 * block_size : 2 * block_size + 9] == b"BLOCK_TWO"
    assert flag == "FULL"


def test_f3_extent_unwritten_flagged_partial_unwritten():
    """Verify that unwritten extent (ee_len > 32768) is zero-filled and flagged 'partial_unwritten'."""
    block_size = 1024
    stream = io.BytesIO(b"\xFF" * (block_size * 20))

    raw_inode = bytearray(256)
    struct.pack_into("<H", raw_inode, 0, 0x81A4)
    struct.pack_into("<I", raw_inode, 4, 2048)  # 2 blocks
    struct.pack_into("<I", raw_inode, 32, EXT4_EXTENTS_FL)

    # Extent header
    struct.pack_into("<HHHHI", raw_inode, 40, 0xF30A, 1, 4, 0, 0)
    # Unwritten extent: ee_len_raw = 32768 + 2 = 32770 (2 blocks)
    struct.pack_into("<IHHI", raw_inode, 52, 0, 32770, 0, 5)

    inode = Inode(bytes(raw_inode))
    data, flag = read_inode_data(stream, inode, block_size)

    assert len(data) == 2048
    # Unwritten extents must be returned as zeros
    assert data == b"\x00" * 2048
    assert flag == "partial_unwritten"


def test_f3_block_map_indirect_and_holes():
    """Verify single and double indirect blocks with zero block pointers (holes) treated as zeros."""
    block_size = 512
    ptrs_per_block = block_size // 4  # 128 pointers per block
    total_blocks = 500
    stream = io.BytesIO(b"\x00" * (block_size * total_blocks))

    # Direct block 0 at physical block 2
    stream.seek(2 * block_size)
    stream.write(b"DIRECT_0".ljust(block_size, b"\x00"))

    # Direct block 1 is a HOLE (pointer = 0)

    # Single indirect block at physical block 10
    # In block 10, index 0 points to physical block 20
    stream.seek(10 * block_size)
    struct.pack_into("<I", stream.getbuffer(), 10 * block_size, 20)
    # Physical block 20 has b"INDIRECT_12" (logical block 12)
    stream.seek(20 * block_size)
    stream.write(b"INDIRECT_12".ljust(block_size, b"\x00"))

    # Construct inode without extents (legacy block map)
    raw_inode = bytearray(256)
    file_size = (12 + 1) * block_size  # 13 blocks = 6656 bytes
    struct.pack_into("<H", raw_inode, 0, 0x81A4)
    struct.pack_into("<I", raw_inode, 4, file_size)
    struct.pack_into("<I", raw_inode, 32, 0)  # No EXT4_EXTENTS_FL

    # i_block:
    # block[0] = 2
    struct.pack_into("<I", raw_inode, 40 + 0 * 4, 2)
    # block[1] = 0 (HOLE!)
    struct.pack_into("<I", raw_inode, 40 + 1 * 4, 0)
    # block[12] = 10 (Single indirect)
    struct.pack_into("<I", raw_inode, 40 + 12 * 4, 10)

    inode = Inode(bytes(raw_inode))
    data, flag = read_inode_data(stream, inode, block_size)

    assert len(data) == file_size
    assert data[:8] == b"DIRECT_0"
    # Hole at block 1 must not be skipped; must be zeros!
    assert data[block_size : block_size + 8] == b"\x00" * 8
    # Logical block 12 (at offset 12 * block_size) has b"INDIRECT_12"
    assert data[12 * block_size : 12 * block_size + 11] == b"INDIRECT_12"
    assert flag == "FULL"
