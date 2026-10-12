import struct
from io import BytesIO
from pathlib import Path

import pytest

from ext4recover.ext4 import Ext4Error, inspect_superblock
from ext4recover.signatures import identify


def image(magic=0xEF53):
    raw = bytearray(2048)
    struct.pack_into("<H", raw, 1024 + 56, magic)
    struct.pack_into("<I", raw, 1024 + 24, 2)
    struct.pack_into("<H", raw, 1024 + 88, 256)
    struct.pack_into("<I", raw, 1024 + 96, 0x0040)  # INCOMPAT_EXTENTS (EXT4)
    return bytes(raw)


def inspect(raw, monkeypatch):
    monkeypatch.setattr(Path, "open", lambda *_: BytesIO(raw))
    return inspect_superblock("evidence.img")


def test_reads_ext4_superblock(monkeypatch):
    report = inspect(image(), monkeypatch)
    assert report["filesystem"] == "EXT4"
    assert report["block_size"] == 4096
    assert report["inode_size"] == 256


def test_rejects_invalid_magic(monkeypatch):
    with pytest.raises(Ext4Error):
        inspect(image(0), monkeypatch)


@pytest.mark.parametrize(("raw", "name"), [(b"%PDF-1.7", "PDF"), (b"other", "Unknown")])
def test_identifies_signatures(raw, name):
    assert identify(raw)[0] == name
