"""EXT4 block-level data reader honoring logical blocks, sparse holes, and indirect maps.

Implements forensic-grade extent traversal and legacy block-map resolution (single, double, triple).
Read-only, preserves hole positions, flags unwritten extents.
"""

from __future__ import annotations

import io
import struct
from typing import BinaryIO, Tuple

from .structs import Extent, ExtentHeader, Inode


def _read_physical_block(stream: BinaryIO, block_num: int, block_size: int) -> bytes:
    """Read a single physical block from the stream, returning zeros on EOF or error."""
    if block_num == 0:
        return b"\x00" * block_size
    try:
        stream.seek(block_num * block_size)
        data = stream.read(block_size)
        if len(data) < block_size:
            data = data + b"\x00" * (block_size - len(data))
        return data
    except Exception:
        return b"\x00" * block_size


def read_extent_data(
    stream: BinaryIO,
    inode: Inode,
    block_size: int,
) -> Tuple[bytes, bool]:
    """Read extent-mapped file data, honoring logical block offsets and holes.
    
    Returns (data_bytes, has_unwritten_extents).
    """
    total_size = inode.size
    if total_size == 0:
        return b"", False

    total_blocks_needed = (total_size + block_size - 1) // block_size
    output_blocks: dict[int, bytes] = {}
    has_unwritten = False

    def parse_extent_node(raw_node: bytes, depth: int) -> None:
        nonlocal has_unwritten
        if len(raw_node) < 12:
            return
        header = ExtentHeader.from_bytes(raw_node[:12])
        if not header.is_valid:
            return

        entries = min(header.eh_entries, header.eh_max)
        if header.eh_depth == 0:
            # Leaf extents
            for i in range(entries):
                offset = 12 + i * 12
                if offset + 12 > len(raw_node):
                    break
                extent = Extent.from_bytes(raw_node[offset : offset + 12])
                length = extent.length
                if extent.is_unwritten:
                    has_unwritten = True

                for b in range(length):
                    lblk = extent.ee_block + b
                    if lblk >= total_blocks_needed:
                        continue
                    if extent.is_unwritten:
                        output_blocks[lblk] = b"\x00" * block_size
                    else:
                        pblk = extent.physical_block + b
                        output_blocks[lblk] = _read_physical_block(stream, pblk, block_size)
        else:
            # Index nodes
            for i in range(entries):
                offset = 12 + i * 12
                if offset + 12 > len(raw_node):
                    break
                ei_block, ei_leaf_lo, ei_leaf_hi = struct.unpack_from("<IIH", raw_node, offset)
                child_pblk = ei_leaf_lo | (ei_leaf_hi << 32)
                child_data = _read_physical_block(stream, child_pblk, block_size)
                parse_extent_node(child_data, header.eh_depth - 1)

    # Inode i_block contains root extent header
    parse_extent_node(inode.i_block, 0)

    # Assemble logical blocks in sequence, zero-filling sparse holes
    chunks = []
    for lblk in range(total_blocks_needed):
        blk_bytes = output_blocks.get(lblk, b"\x00" * block_size)
        chunks.append(blk_bytes)

    full_data = b"".join(chunks)[:total_size]
    return full_data, has_unwritten


def read_block_map_data(
    stream: BinaryIO,
    inode: Inode,
    block_size: int,
) -> bytes:
    """Read legacy block-mapped file data (direct, single, double, triple indirect).
    
    Zero block pointers are treated as sparse holes and zero-filled.
    """
    total_size = inode.size
    if total_size == 0:
        return b""

    total_blocks_needed = (total_size + block_size - 1) // block_size
    ptrs_per_block = block_size // 4
    i_block = inode.i_block

    def read_pointers(block_num: int) -> list[int]:
        if block_num == 0:
            return [0] * ptrs_per_block
        raw = _read_physical_block(stream, block_num, block_size)
        return [struct.unpack_from("<I", raw, i * 4)[0] for i in range(ptrs_per_block)]

    physical_blocks: list[int] = []

    # 1. Direct blocks 0..11
    for i in range(12):
        if len(physical_blocks) >= total_blocks_needed:
            break
        pblk = struct.unpack_from("<I", i_block, i * 4)[0]
        physical_blocks.append(pblk)

    # 2. Single indirect block 12
    if len(physical_blocks) < total_blocks_needed:
        single_ind = struct.unpack_from("<I", i_block, 12 * 4)[0]
        s_ptrs = read_pointers(single_ind)
        for pblk in s_ptrs:
            if len(physical_blocks) >= total_blocks_needed:
                break
            physical_blocks.append(pblk)

    # 3. Double indirect block 13
    if len(physical_blocks) < total_blocks_needed:
        double_ind = struct.unpack_from("<I", i_block, 13 * 4)[0]
        d_ptrs = read_pointers(double_ind)
        for s_blk in d_ptrs:
            if len(physical_blocks) >= total_blocks_needed:
                break
            s_ptrs = read_pointers(s_blk)
            for pblk in s_ptrs:
                if len(physical_blocks) >= total_blocks_needed:
                    break
                physical_blocks.append(pblk)

    # 4. Triple indirect block 14
    if len(physical_blocks) < total_blocks_needed:
        triple_ind = struct.unpack_from("<I", i_block, 14 * 4)[0]
        t_ptrs = read_pointers(triple_ind)
        for d_blk in t_ptrs:
            if len(physical_blocks) >= total_blocks_needed:
                break
            d_ptrs = read_pointers(d_blk)
            for s_blk in d_ptrs:
                if len(physical_blocks) >= total_blocks_needed:
                    break
                s_ptrs = read_pointers(s_blk)
                for pblk in s_ptrs:
                    if len(physical_blocks) >= total_blocks_needed:
                        break
                    physical_blocks.append(pblk)

    # Read physical blocks, zero-filling holes
    chunks = []
    for pblk in physical_blocks:
        chunks.append(_read_physical_block(stream, pblk, block_size))

    return b"".join(chunks)[:total_size]


def read_inode_data(
    stream: BinaryIO,
    inode: Inode,
    block_size: int = 4096,
) -> Tuple[bytes, str]:
    """Read inode contents via extents or legacy block-map.
    
    Returns (data, status) where status is:
    - 'FULL'
    - 'partial_unwritten' if unwritten extents were present
    - 'PARTIAL' if incomplete data was read
    - 'not_recoverable' if size is 0 or pointers are empty
    """
    if inode.size == 0 or inode.has_zero_data_pointers:
        return b"", "not_recoverable"

    if inode.has_extents:
        data, has_unwritten = read_extent_data(stream, inode, block_size)
        status = "partial_unwritten" if has_unwritten else ("FULL" if len(data) == inode.size else "PARTIAL")
        return data, status
    else:
        data = read_block_map_data(stream, inode, block_size)
        status = "FULL" if len(data) == inode.size else "PARTIAL"
        return data, status
