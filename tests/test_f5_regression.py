"""Regression tests for Finding F5.

F5: (a) full_path(): if the chain does not terminate at root inode 2, return '/…/name'
or '(parent unknown)/name', never '/name'.
(b) Build name_map with source priority: active_dirent > deleted-dirent > slack_heuristic;
prefer entries whose parent directory is still allocated.
(c) heuristic(): skip offsets that coincide with an active entry, validate inode <= inodes_count,
file_type byte in 0..7, name_len > 0 and printable UTF-8; never relabel active entries.
(d) Store the source and a confidence label (Confirmed / Probable / Uncertain) on every name,
and make the report wording follow it.
"""

import pytest
from ext4recover.naming import (
    full_path,
    validate_slack_dirent,
    build_name_map,
    NameRecord,
)


def test_f5_full_path_unknown_parent():
    """(a) If chain does not terminate at root inode 2, return '/…/name' or '(parent unknown)/name', never '/name'."""
    # Chain terminates at root inode 2
    assert full_path("test.txt", [15, 2], root_inode=2) == "/test.txt"
    assert full_path("test.txt", [15, 10, 2], dir_names={10: "docs"}, root_inode=2) == "/docs/test.txt"

    # Chain DOES NOT terminate at root inode 2 (e.g. parent is unknown or deleted directory)
    orphaned_path = full_path("secret.pdf", [55, 99], root_inode=2)
    assert orphaned_path != "/secret.pdf"
    assert orphaned_path.startswith("/…/") or orphaned_path.startswith("(parent unknown)/")
    assert "secret.pdf" in orphaned_path

    # Empty parent chain
    unknown_path = full_path("orphan.bin", [], root_inode=2)
    assert unknown_path != "/orphan.bin"
    assert unknown_path.startswith("/…/") or unknown_path.startswith("(parent unknown)/")


def test_f5_name_map_source_priority():
    """(b) Source priority: active_dirent > deleted-dirent > slack_heuristic."""
    entries = [
        NameRecord(inode=100, name="slack_name.txt", source="slack_heuristic", parent_allocated=False),
        NameRecord(inode=100, name="deleted_name.txt", source="deleted_dirent", parent_allocated=True),
        NameRecord(inode=100, name="active_name.txt", source="active_dirent", parent_allocated=True),
    ]

    name_map = build_name_map(entries)
    winner = name_map[100]
    # active_dirent beats deleted_dirent beats slack_heuristic
    assert winner.name == "active_name.txt"
    assert winner.confidence == "Confirmed"

    # deleted_dirent beats slack_heuristic
    entries_no_active = [
        NameRecord(inode=101, name="slack_name.txt", source="slack_heuristic", parent_allocated=False),
        NameRecord(inode=101, name="deleted_name.txt", source="deleted_dirent", parent_allocated=True),
    ]
    name_map2 = build_name_map(entries_no_active)
    winner2 = name_map2[101]
    assert winner2.name == "deleted_name.txt"
    assert winner2.confidence == "Probable"


def test_f5_slack_heuristic_validation():
    """(c) Validate slack entries: skip active offsets, check inode <= max, file_type in 0..7, printable UTF-8."""
    # Active span at offsets 0..24
    active_spans = [(0, 24)]

    # 1. Offset coinciding with active span must be rejected
    res1 = validate_slack_dirent(
        b"\x05\x00\x00\x00\x0c\x00\x04\x01file",
        offset=10,
        max_inodes=1000,
        active_spans=active_spans,
    )
    assert res1 is None

    # 2. Inode > max_inodes must be rejected
    buf_overflow = bytearray(16)
    buf_overflow[0:4] = (5000).to_bytes(4, "little")  # inode 5000 > max 1000
    buf_overflow[4:6] = (12).to_bytes(2, "little")   # rec_len
    buf_overflow[6] = 4                              # name_len
    buf_overflow[7] = 1                              # file_type = regular
    buf_overflow[8:12] = b"test"
    res2 = validate_slack_dirent(bytes(buf_overflow), offset=30, max_inodes=1000, active_spans=active_spans)
    assert res2 is None

    # 3. Invalid file_type (> 7) must be rejected
    buf_bad_type = bytearray(16)
    buf_bad_type[0:4] = (50).to_bytes(4, "little")
    buf_bad_type[4:6] = (12).to_bytes(2, "little")
    buf_bad_type[6] = 4
    buf_bad_type[7] = 9  # invalid type > 7
    buf_bad_type[8:12] = b"test"
    res3 = validate_slack_dirent(bytes(buf_bad_type), offset=30, max_inodes=1000, active_spans=active_spans)
    assert res3 is None

    # 4. Non-printable UTF-8 name must be rejected
    buf_nonprint = bytearray(16)
    buf_nonprint[0:4] = (50).to_bytes(4, "little")
    buf_nonprint[4:6] = (12).to_bytes(2, "little")
    buf_nonprint[6] = 4
    buf_nonprint[7] = 1
    buf_nonprint[8:12] = b"\x01\x02\x03\x04"  # control chars
    res4 = validate_slack_dirent(bytes(buf_nonprint), offset=30, max_inodes=1000, active_spans=active_spans)
    assert res4 is None

    # 5. Valid slack entry accepted
    buf_valid = bytearray(16)
    buf_valid[0:4] = (50).to_bytes(4, "little")
    buf_valid[4:6] = (12).to_bytes(2, "little")
    buf_valid[6] = 4
    buf_valid[7] = 1
    buf_valid[8:12] = b"good"
    res5 = validate_slack_dirent(bytes(buf_valid), offset=30, max_inodes=1000, active_spans=active_spans)
    assert res5 is not None
    assert res5["name"] == "good"
    assert res5["inode"] == 50
