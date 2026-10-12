"""Evidence-format detection and read-only image access.

Raw images are opened directly.  E01/EWF containers can be opened directly
when the optional ``pyewf`` binding is installed.  Other supported containers
must first be exposed as a read-only raw byte stream by their forensic reader;
this deliberately avoids silent conversion or mutation of original evidence.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


RAW_EXTENSIONS = {".img", ".dd", ".raw", ".bin"}
EWF_EXTENSIONS = {".e01", ".s01"}
STREAM_EXTENSIONS = {
    ".l01": "FTK logical image",
    ".aff": "AFF image",
    ".afd": "AFF image",
    ".afm": "AFF image",
    ".aff4": "AFF4 image",
    ".qcow2": "QCOW2 virtual disk",
    ".vmdk": "VMDK virtual disk",
    ".vhd": "VHD virtual disk",
    ".vhdx": "VHDX virtual disk",
    ".gz": "gzip-compressed raw image",
    ".xz": "xz-compressed raw image",
    ".zst": "zstd-compressed raw image",
}


class EvidenceError(ValueError):
    """Raised when an evidence source cannot safely be opened."""


@dataclass(frozen=True)
class EvidenceSource:
    original: Path
    stream: Path | None
    format: str
    direct_ewf: bool = False

    @property
    def analysis_path(self) -> Path:
        if self.stream is None:
            raise EvidenceError("This evidence format needs a read-only byte stream.")
        return self.stream


def detect_format(path: str | Path) -> str:
    """Classify from a conservative suffix; E01 segment suffixes are accepted."""
    suffix = Path(path).suffix.lower()
    if suffix in RAW_EXTENSIONS:
        return "raw"
    if suffix in EWF_EXTENSIONS or (len(suffix) == 4 and suffix.startswith(".e") and suffix[2:].isdigit()):
        return "E01/EWF"
    return STREAM_EXTENSIONS.get(suffix, "unknown")


def open_evidence(path: str | Path, stream: str | Path | None = None) -> EvidenceSource:
    """Validate an immutable evidence input and choose its analysis stream."""
    original = Path(path)
    if not original.is_file():
        raise EvidenceError(f"Evidence file not found: {original}")
    fmt = detect_format(original)
    if stream is not None:
        raw_stream = Path(stream)
        if not raw_stream.is_file():
            raise EvidenceError(f"Read-only analysis stream not found: {raw_stream}")
        return EvidenceSource(original, raw_stream, fmt)
    if fmt == "raw":
        return EvidenceSource(original, original, fmt)
    if fmt == "E01/EWF":
        return EvidenceSource(original, None, fmt, direct_ewf=True)
    if fmt != "unknown":
        raise EvidenceError(
            f"{fmt} requires --stream PATH to a read-only raw stream exposed by its forensic reader. "
            "Do not overwrite, decompress over, or mount the original evidence read-write."
        )
    raise EvidenceError(
        "Unsupported evidence format. Use raw (.img/.dd/.raw/.bin), E01/EWF, or provide a supported "
        "container (.L01, AFF4, QCOW2, VMDK, VHD/VHDX, .gz/.xz/.zst) with --stream."
    )
