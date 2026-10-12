"""Small data models shared by reports and recovery."""

from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class Candidate:
    inode: int
    size: int
    allocated: bool
    file_type: str
    name: str | None = None
    path: str | None = None
    recoverable: int = 1
    not_recoverable_reason: str | None = None

    def json(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Validation:
    expected_size: int
    recovered_size: int
    sha256: str
    signature: str
    signature_valid: bool
    status: str
    reason: str | None = None

    def json(self) -> dict[str, Any]:
        return asdict(self)
