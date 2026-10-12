"""Partition table discovery: detects MBR partitions and filesystem offsets."""

from __future__ import annotations

import struct
from pathlib import Path
from typing import BinaryIO, List

EXT4_MAGIC = 0xEF53


def find_filesystem_offsets(image_path: str | Path) -> List[int]:
    """Scan evidence for all valid EXT2/EXT3/EXT4 filesystem offsets.
    
    Checks offset 0 first, then scans MBR partition tables if present.
    """
    path = Path(image_path)
    if not path.is_file():
        return [0]

    offsets: list[int] = []

    try:
        with path.open("rb") as f:
            # 1. Check offset 0
            f.seek(1024 + 56)
            magic = f.read(2)
            if len(magic) == 2 and struct.unpack("<H", magic)[0] == EXT4_MAGIC:
                offsets.append(0)

            # 2. Check MBR partition table
            f.seek(0)
            sector0 = f.read(512)
            if len(sector0) == 512 and sector0[510:512] == b"\x55\xaa":
                for i in range(4):
                    entry_off = 446 + i * 16
                    entry = sector0[entry_off : entry_off + 16]
                    part_type = entry[4]
                    start_lba = struct.unpack_from("<I", entry, 8)[0]
                    num_sectors = struct.unpack_from("<I", entry, 12)[0]

                    if start_lba > 0 and num_sectors > 0 and part_type in (0x83, 0x82, 0x05, 0x0F):
                        fs_off = start_lba * 512
                        f.seek(fs_off + 1024 + 56)
                        m = f.read(2)
                        if len(m) == 2 and struct.unpack("<H", m)[0] == EXT4_MAGIC:
                            if fs_off not in offsets:
                                offsets.append(fs_off)
    except Exception:
        pass

    return offsets if offsets else [0]
