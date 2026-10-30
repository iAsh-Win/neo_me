import os
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("NEO_DATA_DIR", BASE_DIR / "data"))
UPLOAD_DIR = DATA_DIR / "uploads"
DATA_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

DATABASE_URL = os.environ.get("NEO_DATABASE_URL", f"sqlite:///{DATA_DIR / 'neo.db'}")

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False, "timeout": 30})


@event.listens_for(engine, "connect")
def _sqlite_pragmas(conn, _):
    cur = conn.cursor()
    cur.execute("PRAGMA foreign_keys=ON")
    cur.execute("PRAGMA journal_mode=WAL")
    cur.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def backup_legacy_database() -> str | None:
    """Earlier builds used a different table layout. If such a file is found, keep it as a backup
    and let the app start fresh (the first version only held demo data)."""
    from datetime import datetime

    from sqlalchemy import inspect
    if not DATABASE_URL.startswith("sqlite"):
        return None
    insp = inspect(engine)
    if not insp.has_table("users"):
        return None
    if insp.has_table("step_runs"):
        return None
    engine.dispose()
    src = DATA_DIR / "neo.db"
    dst = DATA_DIR / f"neo.old-{datetime.now():%Y%m%d-%H%M%S}.db"
    for suffix in ("", "-wal", "-shm"):
        f = Path(str(src) + suffix)
        if f.exists():
            f.replace(Path(str(dst) + suffix))
    return str(dst)


def ensure_columns() -> None:
    """Add columns introduced after a database was first created (SQLite keeps old data as it is)."""
    from sqlalchemy import inspect, text
    insp = inspect(engine)
    with engine.begin() as conn:
        for table in Base.metadata.sorted_tables:
            if not insp.has_table(table.name):
                continue
            have = {c["name"] for c in insp.get_columns(table.name)}
            for col in table.columns:
                if col.name in have:
                    continue
                kind = col.type.compile(engine.dialect)
                default = ""
                if isinstance(col.default, type(None)) is False and getattr(col.default, "is_scalar", False):
                    v = col.default.arg
                    default = f" DEFAULT {int(v) if isinstance(v, bool) else repr(v)}" if isinstance(v, (bool, int, float, str)) else ""
                conn.execute(text(f'ALTER TABLE {table.name} ADD COLUMN {col.name} {kind}{default}'))
