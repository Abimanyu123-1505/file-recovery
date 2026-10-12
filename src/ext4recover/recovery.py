"""Recover one inode and express validation evidence without overclaiming."""

from pathlib import Path

from .hashing import sha256_bytes
from .models import Validation
from .signatures import identify
from .tsk import read_inode


def recover_inode(fs, inode: int, output: Path) -> tuple[Path, Validation]:
    data, expected = read_inode(fs, inode)
    recovered = output / "recovered"
    recovered.mkdir(parents=True, exist_ok=True)
    target = recovered / f"inode-{inode}.bin"

    # Finding F2: In recover(), if inode size is 0 or has no extents/blocks,
    # return recovery_status 'not_recoverable' (reason: 'inode size and data pointers were cleared by the filesystem'),
    # never 'complete' or 'FULL'.
    if expected == 0 or len(data) == 0:
        return target, Validation(
            expected_size=expected,
            recovered_size=len(data),
            sha256="" if not data else sha256_bytes(data),
            signature="None",
            signature_valid=False,
            status="not_recoverable",
            reason="inode size and data pointers were cleared by the filesystem",
        )

    target.write_bytes(data)
    signature, valid = identify(data[:32])
    status = "FULL" if len(data) == expected else "PARTIAL"
    return target, Validation(
        expected_size=expected,
        recovered_size=len(data),
        sha256=sha256_bytes(data),
        signature=signature,
        signature_valid=valid,
        status=status,
        reason=None,
    )
