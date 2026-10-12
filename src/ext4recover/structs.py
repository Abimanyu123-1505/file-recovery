"""EXT4 on-disk structures parser: Superblock, Group Descriptors, Inodes, Extents, Dirents.

Pure-Python forensic implementations adhering to Linux ext4 specifications.
Read-only, cautious, and exact.
"""

from __future__ import annotations

import math
import struct
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

EXT4_MAGIC = 0xEF53

# Superblock feature flags
COMPAT_HAS_JOURNAL = 0x0004
INCOMPAT_COMPRESSION = 0x0001
INCOMPAT_FILETYPE = 0x0002
INCOMPAT_RECOVER = 0x0004
INCOMPAT_JOURNAL_DEV = 0x0008
INCOMPAT_META_BG = 0x0010
INCOMPAT_EXTENTS = 0x0040
INCOMPAT_64BIT = 0x0080
INCOMPAT_MMP = 0x0100
INCOMPAT_FLEX_BG = 0x0200
INCOMPAT_EA_INODE = 0x0400
INCOMPAT_DIRDATA = 0x1000
INCOMPAT_CSUM_SEED = 0x2000
INCOMPAT_LARGEDIR = 0x4000
INCOMPAT_INLINE_DATA = 0x8000
INCOMPAT_ENCRYPT = 0x10000
INCOMPAT_CASEFOLD = 0x20000

# Inode flags
EXT4_EXTENTS_FL = 0x00080000


class Ext4StructError(ValueError):
    """Raised when on-disk data cannot be safely or validly parsed."""


@dataclass
class Superblock:
    """EXT4 Superblock parser (1024 bytes)."""
    raw_bytes: bytes

    s_inodes_count: int = 0
    s_blocks_count_lo: int = 0
    s_r_blocks_count_lo: int = 0
    s_free_blocks_count_lo: int = 0
    s_free_inodes_count: int = 0
    s_first_data_block: int = 0
    s_log_block_size: int = 0
    s_log_cluster_size: int = 0
    s_blocks_per_group: int = 0
    s_clusters_per_group: int = 0
    s_inodes_per_group: int = 0
    s_magic: int = 0
    s_state: int = 0
    s_errors: int = 0
    s_rev_level: int = 0
    s_inode_size: int = 256
    s_block_group_nr: int = 0
    s_feature_compat: int = 0
    s_feature_incompat: int = 0
    s_feature_ro_compat: int = 0
    s_uuid: bytes = b""
    s_volume_name: str = ""
    s_desc_size: int = 32
    s_blocks_count_hi: int = 0
    s_journal_inum: int = 0

    def __post_init__(self):
        if len(self.raw_bytes) < 1024:
            raise Ext4StructError("Superblock buffer smaller than 1024 bytes.")
        b = self.raw_bytes
        self.s_inodes_count = struct.unpack_from("<I", b, 0)[0]
        self.s_blocks_count_lo = struct.unpack_from("<I", b, 4)[0]
        self.s_r_blocks_count_lo = struct.unpack_from("<I", b, 8)[0]
        self.s_free_blocks_count_lo = struct.unpack_from("<I", b, 12)[0]
        self.s_free_inodes_count = struct.unpack_from("<I", b, 16)[0]
        self.s_first_data_block = struct.unpack_from("<I", b, 20)[0]
        self.s_log_block_size = struct.unpack_from("<I", b, 24)[0]
        self.s_log_cluster_size = struct.unpack_from("<I", b, 28)[0]
        self.s_blocks_per_group = struct.unpack_from("<I", b, 32)[0]
        self.s_clusters_per_group = struct.unpack_from("<I", b, 36)[0]
        self.s_inodes_per_group = struct.unpack_from("<I", b, 40)[0]
        self.s_magic = struct.unpack_from("<H", b, 56)[0]
        self.s_state = struct.unpack_from("<H", b, 58)[0]
        self.s_errors = struct.unpack_from("<H", b, 60)[0]
        self.s_rev_level = struct.unpack_from("<I", b, 76)[0]
        self.s_inode_size = struct.unpack_from("<H", b, 88)[0]
        self.s_block_group_nr = struct.unpack_from("<H", b, 90)[0]
        self.s_feature_compat = struct.unpack_from("<I", b, 92)[0]
        self.s_feature_incompat = struct.unpack_from("<I", b, 96)[0]
        self.s_feature_ro_compat = struct.unpack_from("<I", b, 100)[0]
        self.s_uuid = b[104:120]
        self.s_volume_name = b[120:136].rstrip(b"\x00").decode("utf-8", errors="replace")
        self.s_journal_inum = struct.unpack_from("<I", b, 224)[0]

        if len(b) >= 260:
            desc_sz = struct.unpack_from("<H", b, 254)[0]
            if desc_sz >= 32:
                self.s_desc_size = desc_sz
        if len(b) >= 340:
            self.s_blocks_count_hi = struct.unpack_from("<I", b, 336)[0]

    @property
    def magic(self) -> int:
        return self.s_magic

    @property
    def is_valid_magic(self) -> bool:
        return self.s_magic == EXT4_MAGIC

    @property
    def block_size(self) -> int:
        return 1024 << self.s_log_block_size

    @property
    def inode_size(self) -> int:
        return self.s_inode_size or 256

    @property
    def has_64bit(self) -> bool:
        return bool(self.s_feature_incompat & INCOMPAT_64BIT)

    @property
    def has_extents(self) -> bool:
        return bool(self.s_feature_incompat & INCOMPAT_EXTENTS)

    @property
    def has_flex_bg(self) -> bool:
        return bool(self.s_feature_incompat & INCOMPAT_FLEX_BG)

    @property
    def has_journal(self) -> bool:
        return bool(self.s_feature_compat & COMPAT_HAS_JOURNAL)

    @property
    def blocks_count(self) -> int:
        # Finding F1: Apply blocks_count_hi only when 64BIT is set
        if self.has_64bit:
            return self.s_blocks_count_lo | (self.s_blocks_count_hi << 32)
        return self.s_blocks_count_lo

    @property
    def group_count(self) -> int:
        # Finding F4: Use s_first_data_block when computing group count
        if not self.s_blocks_per_group:
            return 1
        blocks = self.blocks_count - self.s_first_data_block
        return math.ceil(blocks / self.s_blocks_per_group)

    @property
    def filesystem_label(self) -> str:
        # Finding F4: identify filesystem as ext2/ext3/ext4 from compat/incompat flags
        if self.has_extents or self.has_64bit or self.has_flex_bg:
            return "EXT4"
        if self.has_journal:
            return "EXT3"
        return "EXT2"

    @property
    def unsupported_incompat_features(self) -> list[str]:
        # Finding F4: refuse or clearly flag unsupported incompat features
        unsupported = []
        flags = self.s_feature_incompat
        if flags & INCOMPAT_INLINE_DATA:
            unsupported.append("inline_data (files stored directly inside inodes)")
        if flags & INCOMPAT_META_BG:
            unsupported.append("meta_bg (meta block groups)")
        if flags & 0x0200 and not self.has_flex_bg:  # bigalloc flag (0x0200 when cluster size > block size)
            if self.s_log_cluster_size > self.s_log_block_size:
                unsupported.append("bigalloc (cluster allocation)")
        if flags & INCOMPAT_ENCRYPT:
            unsupported.append("encrypt (filesystem level encryption)")
        if flags & INCOMPAT_CASEFOLD:
            unsupported.append("casefold (case-insensitive directories)")
        if flags & INCOMPAT_COMPRESSION:
            unsupported.append("compression (transparent compression)")
        return unsupported


@dataclass
class BlockGroupDescriptor:
    """EXT4 block group descriptor.
    
    Finding F1: Read bg_inode_table_hi at offset 0x28 (not 48), only when the
    64BIT incompat flag is set and desc_size >= 64.
    """
    raw_bytes: bytes
    has_64bit: bool = False
    desc_size: int = 32

    bg_block_bitmap_lo: int = 0
    bg_inode_bitmap_lo: int = 0
    bg_inode_table_lo: int = 0
    bg_free_blocks_count_lo: int = 0
    bg_free_inodes_count_lo: int = 0
    bg_used_dirs_count_lo: int = 0
    bg_flags: int = 0

    bg_block_bitmap_hi: int = 0
    bg_inode_bitmap_hi: int = 0
    bg_inode_table_hi: int = 0
    bg_free_blocks_count_hi: int = 0
    bg_free_inodes_count_hi: int = 0
    bg_used_dirs_count_hi: int = 0

    def __post_init__(self):
        b = self.raw_bytes
        if len(b) < 32:
            raise Ext4StructError("Descriptor smaller than 32 bytes.")
        self.bg_block_bitmap_lo = struct.unpack_from("<I", b, 0)[0]
        self.bg_inode_bitmap_lo = struct.unpack_from("<I", b, 4)[0]
        self.bg_inode_table_lo = struct.unpack_from("<I", b, 8)[0]
        self.bg_free_blocks_count_lo = struct.unpack_from("<H", b, 12)[0]
        self.bg_free_inodes_count_lo = struct.unpack_from("<H", b, 14)[0]
        self.bg_used_dirs_count_lo = struct.unpack_from("<H", b, 16)[0]
        self.bg_flags = struct.unpack_from("<H", b, 18)[0]

        # Finding F1: Only when 64BIT incompat flag is set and desc_size >= 64
        if self.has_64bit and self.desc_size >= 64 and len(b) >= 64:
            self.bg_block_bitmap_hi = struct.unpack_from("<I", b, 0x20)[0]
            self.bg_inode_bitmap_hi = struct.unpack_from("<I", b, 0x24)[0]
            # EXACT OFFSET 0x28 (decimal 40), NOT 48 (0x30)!
            self.bg_inode_table_hi = struct.unpack_from("<I", b, 0x28)[0]
            self.bg_free_blocks_count_hi = struct.unpack_from("<H", b, 0x2C)[0]
            self.bg_free_inodes_count_hi = struct.unpack_from("<H", b, 0x2E)[0]
            self.bg_used_dirs_count_hi = struct.unpack_from("<H", b, 0x30)[0]

    @property
    def inode_table(self) -> int:
        if self.has_64bit and self.desc_size >= 64:
            return self.bg_inode_table_lo | (self.bg_inode_table_hi << 32)
        return self.bg_inode_table_lo

    @property
    def block_bitmap(self) -> int:
        if self.has_64bit and self.desc_size >= 64:
            return self.bg_block_bitmap_lo | (self.bg_block_bitmap_hi << 32)
        return self.bg_block_bitmap_lo

    @property
    def inode_bitmap(self) -> int:
        if self.has_64bit and self.desc_size >= 64:
            return self.bg_inode_bitmap_lo | (self.bg_inode_bitmap_hi << 32)
        return self.bg_inode_bitmap_lo


@dataclass
class Inode:
    """EXT4 Inode parser (128, 256, or more bytes).
    
    Finding F2, F4:
    - is_deleted: mode set and dtime set and links_count == 0
    - is_orphan_suspect: dtime < 2000-01-01 or small integer
    """
    raw_bytes: bytes
    inode_num: int = 0

    i_mode: int = 0
    i_uid: int = 0
    i_size_lo: int = 0
    i_atime: int = 0
    i_ctime: int = 0
    i_mtime: int = 0
    i_dtime: int = 0
    i_gid: int = 0
    i_links_count: int = 0
    i_blocks_lo: int = 0
    i_flags: int = 0
    i_block: bytes = b""
    i_size_high: int = 0
    i_crtime: int = 0

    def __post_init__(self):
        b = self.raw_bytes
        if len(b) < 128:
            raise Ext4StructError("Inode raw bytes shorter than 128 bytes.")
        self.i_mode = struct.unpack_from("<H", b, 0)[0]
        self.i_uid = struct.unpack_from("<H", b, 2)[0]
        self.i_size_lo = struct.unpack_from("<I", b, 4)[0]
        self.i_atime = struct.unpack_from("<I", b, 8)[0]
        self.i_ctime = struct.unpack_from("<I", b, 12)[0]
        self.i_mtime = struct.unpack_from("<I", b, 16)[0]
        self.i_dtime = struct.unpack_from("<I", b, 20)[0]
        self.i_gid = struct.unpack_from("<H", b, 24)[0]
        self.i_links_count = struct.unpack_from("<H", b, 26)[0]
        self.i_blocks_lo = struct.unpack_from("<I", b, 28)[0]
        self.i_flags = struct.unpack_from("<I", b, 32)[0]
        self.i_block = b[40:100]  # 60 bytes of block pointers / extent tree

        if len(b) >= 128:
            self.i_size_high = struct.unpack_from("<I", b, 108)[0]
        if len(b) >= 160:
            # Extra fields in inode >= 160 bytes: i_crtime at offset 144 + 4
            self.i_crtime = struct.unpack_from("<I", b, 144)[0]

    @property
    def size(self) -> int:
        if self.is_regular_file:
            return self.i_size_lo | (self.i_size_high << 32)
        return self.i_size_lo

    @property
    def has_extents(self) -> bool:
        return bool(self.i_flags & EXT4_EXTENTS_FL)

    @property
    def is_regular_file(self) -> bool:
        return (self.i_mode & 0xF000) == 0x8000

    @property
    def is_directory(self) -> bool:
        return (self.i_mode & 0xF000) == 0x4000

    @property
    def is_deleted(self) -> bool:
        # Real honest forensic rule: mode set and dtime set and links_count == 0
        return self.i_mode != 0 and self.i_dtime != 0 and self.i_links_count == 0

    @property
    def is_orphan_suspect(self) -> bool:
        # Finding F4: dtime not plausible (> 2000-01-01 / 946684800) or small integer orphan-chain value
        if self.i_dtime == 0:
            return False
        return self.i_dtime < 946684800 or self.i_dtime < 1000

    @property
    def has_zero_data_pointers(self) -> bool:
        # Finding F2: check if inode data pointers or extents were zeroed
        if self.has_extents:
            magic = struct.unpack_from("<H", self.i_block, 0)[0]
            entries = struct.unpack_from("<H", self.i_block, 2)[0]
            # Extent header magic is 0xF30A; if magic is 0 or entries is 0, extent tree is cleared
            if magic != 0xF30A or entries == 0:
                return True
        return self.i_block == b"\x00" * 60


@dataclass
class ExtentHeader:
    eh_magic: int = 0
    eh_entries: int = 0
    eh_max: int = 0
    eh_depth: int = 0
    eh_generation: int = 0

    @classmethod
    def from_bytes(cls, b: bytes) -> ExtentHeader:
        if len(b) < 12:
            raise Ext4StructError("Extent header buffer too small.")
        magic, entries, max_entries, depth, generation = struct.unpack_from("<HHHHI", b, 0)
        return cls(magic, entries, max_entries, depth, generation)

    @property
    def is_valid(self) -> bool:
        return self.eh_magic == 0xF30A


@dataclass
class Extent:
    """EXT4 leaf extent.
    
    Finding F3:
    - fix ee_len > 32768 handling (len = raw - 32768 only when raw > 32768)
    - unwritten extent flag
    """
    ee_block: int
    ee_len_raw: int
    ee_start_hi: int
    ee_start_lo: int

    @classmethod
    def from_bytes(cls, b: bytes) -> Extent:
        if len(b) < 12:
            raise Ext4StructError("Extent entry buffer too small.")
        ee_block, ee_len_raw, ee_start_hi, ee_start_lo = struct.unpack_from("<IHHI", b, 0)
        return cls(ee_block, ee_len_raw, ee_start_hi, ee_start_lo)

    @property
    def is_unwritten(self) -> bool:
        return self.ee_len_raw > 32768

    @property
    def length(self) -> int:
        # Finding F3: raw - 32768 only when raw > 32768, otherwise raw!
        if self.ee_len_raw > 32768:
            return self.ee_len_raw - 32768
        return self.ee_len_raw

    @property
    def physical_block(self) -> int:
        return self.ee_start_lo | (self.ee_start_hi << 32)
