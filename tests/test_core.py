"""Core API alignment tests: Superblock, Inode, and platform-safe path handling."""

from pathlib import Path
import pytest

from ext4recover.structs import Superblock, Inode, EXT4_MAGIC
from ext4recover.evidence import detect_format, open_evidence


def test_core_superblock_magic_property():
    """T1/T2: Superblock exposes honest .magic property."""
    raw = bytearray(1024)
    raw[56] = 0x53
    raw[57] = 0xEF
    sb = Superblock(bytes(raw))
    assert sb.magic == EXT4_MAGIC
    assert sb.is_valid_magic is True


def test_core_inode_is_deleted_property():
    """T1/T2: Inode.is_deleted = mode set and dtime set and links_count == 0."""
    raw = bytearray(128)
    # Mode 0x81A4 (regular file)
    raw[0] = 0xA4
    raw[1] = 0x81
    # Size 100
    raw[4] = 100
    # dtime = 1718000000
    dtime = 1718000000
    raw[20:24] = dtime.to_bytes(4, "little")
    # links_count = 0
    raw[26] = 0
    raw[27] = 0

    inode = Inode(bytes(raw))
    assert inode.is_deleted is True

    # If links_count is 1, not deleted
    raw[26] = 1
    inode_linked = Inode(bytes(raw))
    assert inode_linked.is_deleted is False


def test_core_platform_safe_windows_path(tmp_path):
    """T1/T2: Make Windows path test platform-safe using Path objects."""
    img_name = "test_evidence.img"
    img_path = tmp_path / img_name
    img_path.write_bytes(b"EXT4 TEST BYTES")

    evidence = open_evidence(img_path)
    # Ensure analysis_path matches the given path irrespective of Windows vs POSIX separators
    assert Path(evidence.analysis_path).resolve() == img_path.resolve()
    assert Path(evidence.analysis_path).name == img_name
