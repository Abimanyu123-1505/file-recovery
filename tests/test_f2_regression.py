"""Regression test for Finding F2.

F2: In recover(), if the inode size is 0, or the inode has no extents/blocks,
return recovery_status 'not_recoverable' (reason: 'inode size and data pointers were
cleared by the filesystem'), never 'complete'. Mark such findings recoverable=0
in the scanner and show the reason.
"""

from unittest.mock import MagicMock
from pathlib import Path
import pytest

from ext4recover.recovery import recover_inode
from ext4recover.models import Validation


def test_f2_zero_size_inode_returns_not_recoverable(tmp_path):
    mock_fs = MagicMock()
    mock_entry = MagicMock()
    mock_meta = MagicMock()
    mock_meta.size = 0
    mock_entry.info.meta = mock_meta
    mock_entry.read_random.return_value = b""
    mock_fs.open_meta.return_value = mock_entry

    target, validation = recover_inode(mock_fs, 12, tmp_path)
    assert validation.status == "not_recoverable"
    assert validation.status != "FULL"
    assert validation.status != "complete"
    assert validation.reason == "inode size and data pointers were cleared by the filesystem"


def test_f2_empty_data_blocks_returns_not_recoverable(tmp_path):
    mock_fs = MagicMock()
    mock_entry = MagicMock()
    mock_meta = MagicMock()
    mock_meta.size = 1024
    mock_entry.info.meta = mock_meta
    # FS reports expected size 1024, but data pointers are cleared / returns 0 bytes
    mock_entry.read_random.return_value = b""
    mock_fs.open_meta.return_value = mock_entry

    target, validation = recover_inode(mock_fs, 13, tmp_path)
    assert validation.status == "not_recoverable"
    assert validation.status != "FULL"
    assert validation.status != "complete"
    assert validation.reason == "inode size and data pointers were cleared by the filesystem"
