"""Regression tests for Finding F8.

F8: When carving is enabled, run the carver over genuinely unallocated block ranges
(from the block bitmap), not a hardcoded 50MB window; enforce max_carved_size = 100MB;
skip ranges already covered by an inode finding; tag carved outputs with source='carved',
no filename, no path, confidence='Uncertain'.
"""

import pytest
from pathlib import Path
from ext4recover.carving import CarvedFile, carve_unallocated, MAX_CARVED_SIZE


def test_f8_carved_file_tags():
    """Tag carved outputs with source='carved', no filename, no path, confidence='Uncertain'."""
    cf = CarvedFile(
        offset=4096,
        size=1024,
        signature="PDF",
        sha256="abc",
        output_path="/tmp/carved.pdf",
    )
    data = cf.json()
    assert data["source"] == "carved"
    assert data["name"] is None
    assert data["path"] is None
    assert data["confidence"] == "Uncertain"


def test_f8_max_carved_size_enforced():
    """Enforce max_carved_size = 100MB (104857600 bytes)."""
    assert MAX_CARVED_SIZE == 100 * 1024 * 1024


def test_f8_skip_covered_ranges(tmp_path):
    """Carver must skip byte ranges already covered by an inode finding."""
    # Synthesize a minimal EXT4 image with an unallocated PDF
    # and verify that if covered_ranges overlaps the PDF, it is skipped.
    img_path = tmp_path / "test.img"
    block_size = 1024
    img_size = block_size * 20
    data = bytearray(img_size)

    # Superblock at offset 1024
    sb_off = 1024
    data[sb_off + 0x38 : sb_off + 0x3A] = b"\x53\xef"  # magic
    data[sb_off + 4 : sb_off + 8] = (20).to_bytes(4, "little")  # 20 blocks
    data[sb_off + 24 : sb_off + 28] = (0).to_bytes(4, "little")  # block size 1024
    data[sb_off + 32 : sb_off + 36] = (20).to_bytes(4, "little")  # blocks per group
    data[sb_off + 88 : sb_off + 92] = (1).to_bytes(4, "little")   # rev 1
    data[sb_off + 254 : sb_off + 256] = (32).to_bytes(2, "little") # desc size 32

    # Group descriptor at block 2 (offset 2048)
    gdt_off = 2048
    data[gdt_off : gdt_off + 4] = (3).to_bytes(4, "little")  # block bitmap at block 3
    data[gdt_off + 4 : gdt_off + 8] = (4).to_bytes(4, "little") # inode bitmap at block 4
    data[gdt_off + 8 : gdt_off + 12] = (5).to_bytes(4, "little") # inode table at block 5

    # Block bitmap at block 3 (offset 3072):
    # blocks 0..5 allocated (bits 0..5 = 1 -> 0x3F)
    # block 10 unallocated (bit 10 = 0)
    data[3072] = 0x3F  # 00111111b

    # Place a PDF in block 10 (offset 10240)
    pdf_content = b"%PDF-1.4\nTest PDF\n%%EOF"
    pdf_off = 10 * block_size
    data[pdf_off : pdf_off + len(pdf_content)] = pdf_content

    img_path.write_bytes(data)

    out_dir = tmp_path / "out"
    # When covered_ranges covers block 10, carve should skip it
    covered = [(pdf_off, pdf_off + len(pdf_content))]
    results_skipped = carve_unallocated(
        img_path, offset=0, output=out_dir, covered_ranges=covered
    )
    assert len(results_skipped) == 0

    # When covered_ranges does NOT cover block 10, carve finds it
    results_found = carve_unallocated(
        img_path, offset=0, output=out_dir, covered_ranges=[]
    )
    assert len(results_found) == 1
    assert results_found[0].signature == "PDF"
    assert results_found[0].confidence == "Uncertain"
    assert results_found[0].source == "carved"
