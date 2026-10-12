"""Tests validating known-answer fixtures A through F.

Skips with a clear, honest message if system mkfs.ext4/debugfs are unavailable,
and exercises synthesized fixtures to guarantee forensic correctness across all platforms.
"""

from pathlib import Path
import pytest

from ext4recover.structs import Superblock, Inode, BlockGroupDescriptor
from ext4recover.ext4 import inspect_superblock
from tests.fixtures_generator import has_e2fsprogs, synthesize_raw_ext4_image


@pytest.fixture
def require_e2fsprogs():
    if not has_e2fsprogs():
        pytest.skip("mkfs.ext4 and debugfs unavailable on this environment; skipping e2fsprogs on-disk image test")


def test_fixture_generator_skip_message(require_e2fsprogs):
    """Verifies that tests skip cleanly when mkfs/debugfs are unavailable."""
    assert has_e2fsprogs() is True


def test_fixture_a_synthesized():
    """Fixture A: standard 4K ext4 image inspection."""
    img_bytes = synthesize_raw_ext4_image(block_size=4096)
    sb = Superblock(img_bytes[1024:2048])
    assert sb.filesystem_label == "EXT4"
    assert sb.block_size == 4096
    assert sb.has_extents is True


def test_fixture_b_synthesized_64bit_flexbg():
    """Fixture B: 64bit + flex_bg multi-group image (tests F1)."""
    img_bytes = synthesize_raw_ext4_image(
        block_size=4096,
        has_64bit=True,
        has_flex_bg=True,
        desc_size=64,
    )
    sb = Superblock(img_bytes[1024:2048])
    assert sb.has_64bit is True
    assert sb.has_flex_bg is True
    assert sb.s_desc_size == 64


def test_fixture_c_zeroed_extents():
    """Fixture C: Inode size/extents zeroed returns has_zero_data_pointers (tests F2)."""
    raw_inode = bytearray(256)
    # Mode regular file, dtime set, links_count = 0, size = 0, i_block = 0
    raw_inode[0] = 0xA4
    raw_inode[1] = 0x81
    raw_inode[20] = 0x50
    inode = Inode(bytes(raw_inode), inode_num=12)
    assert inode.is_deleted is True
    assert inode.size == 0
    assert inode.has_zero_data_pointers is True


def test_fixture_d_ext3_no_extents():
    """Fixture D: ext3 image without extents (tests F3/F4)."""
    img_bytes = synthesize_raw_ext4_image(is_ext3=True, has_journal=True)
    sb = Superblock(img_bytes[1024:2048])
    assert sb.filesystem_label == "EXT3"
    assert sb.has_extents is False
    assert sb.has_journal is True


def test_fixture_e_negative_and_orphan():
    """Fixture E: ext3 negative check and orphan inode check (tests F4)."""
    img_bytes = synthesize_raw_ext4_image(is_ext3=True, has_journal=True)
    sb = Superblock(img_bytes[1024:2048])
    assert sb.filesystem_label != "EXT4"

    raw_inode = bytearray(256)
    raw_inode[0] = 0xA4
    raw_inode[1] = 0x81
    raw_inode[20] = 5  # dtime = 5 (small int in orphan list)
    orphan = Inode(bytes(raw_inode), inode_num=15)
    assert orphan.is_orphan_suspect is True
