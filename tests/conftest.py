import os
import sys
import tempfile
from pathlib import Path
import pytest

_repo_root = Path(__file__).resolve().parent.parent
_backend_dir = _repo_root / "backend"
_src_dir = _repo_root / "src"

for p in (_repo_root, _backend_dir, _src_dir):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

_TEMP_ROOT = Path(tempfile.mkdtemp(prefix="ext4_workbench_root_test_"))
_APP_DATA = _TEMP_ROOT / "data"
_RECOVERY = _TEMP_ROOT / "recovered"
_REPORT = _TEMP_ROOT / "reports"
_LEDGER = _TEMP_ROOT / "ledger.jsonl"
_DB = _TEMP_ROOT / "test.db"

_APP_DATA.mkdir(parents=True, exist_ok=True)
_RECOVERY.mkdir(parents=True, exist_ok=True)
_REPORT.mkdir(parents=True, exist_ok=True)

os.environ.setdefault("APP_DATA_DIR", str(_APP_DATA))
os.environ.setdefault("RECOVERY_DIR", str(_RECOVERY))
os.environ.setdefault("REPORT_DIR", str(_REPORT))
os.environ.setdefault("INTEGRITY_LEDGER", str(_LEDGER))
os.environ.setdefault("DB_PATH", str(_DB))


@pytest.fixture(autouse=True)
def isolate_test_environment(tmp_path, monkeypatch):
    """Ensure each test runs with its own isolated directory structure and fresh DB."""
    test_data = tmp_path / "data"
    test_recovery = tmp_path / "recovered"
    test_reports = tmp_path / "reports"
    test_ledger = tmp_path / "ledger.jsonl"
    test_db = tmp_path / "test.db"

    test_data.mkdir(parents=True, exist_ok=True)
    test_recovery.mkdir(parents=True, exist_ok=True)
    test_reports.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("APP_DATA_DIR", str(test_data))
    monkeypatch.setenv("RECOVERY_DIR", str(test_recovery))
    monkeypatch.setenv("REPORT_DIR", str(test_reports))
    monkeypatch.setenv("INTEGRITY_LEDGER", str(test_ledger))
    monkeypatch.setenv("DB_PATH", str(test_db))

    try:
        import app.database as db_mod
        db_mod.DB_PATH = test_db
        import sqlalchemy
        db_mod.engine = sqlalchemy.create_engine(
            f"sqlite:///{test_db}",
            connect_args={"check_same_thread": False},
        )
        import sqlalchemy.orm as orm
        db_mod.SessionLocal = orm.sessionmaker(
            autocommit=False, autoflush=False, bind=db_mod.engine
        )
        db_mod.Base.metadata.create_all(bind=db_mod.engine)
    except Exception:
        pass

    yield
