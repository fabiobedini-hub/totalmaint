from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import DATABASE_URL

_is_sqlite = DATABASE_URL.startswith("sqlite")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if _is_sqlite else {},
    pool_pre_ping=True,
)

if _is_sqlite:
    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(dbapi_conn, _):
        cur = dbapi_conn.cursor()
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


# Columns added after the first release. create_all() makes new tables but never changes
# existing ones, so these are added by hand when missing. Existing rows get NULL.
NEW_COLUMNS = {
    "tasks": {
        "vendor_id": "INTEGER REFERENCES vendors(id) ON DELETE SET NULL",
        "created_by_id": "INTEGER REFERENCES users(id) ON DELETE SET NULL",
        "counter_interval": "FLOAT",
        "counter_next_due": "FLOAT",
        "counter_remind_before": "FLOAT",
        "vendor_status": "VARCHAR(12)",
        "vendor_requested_on": "DATE",
        "vendor_booked_for": "DATE",
    },
    "assets": {
        "counter_unit": "VARCHAR(10) NOT NULL DEFAULT 'none'",
        "counter_value": "FLOAT",
        "counter_on": "DATE",
    },
    "spare_parts": {
        "vendor_id": "INTEGER REFERENCES vendors(id) ON DELETE SET NULL",
    },
    "completions": {
        "counter_value": "FLOAT",
        "vendor_id": "INTEGER REFERENCES vendors(id) ON DELETE SET NULL",
    },
}


def add_missing_columns() -> list[str]:
    added = []
    insp = inspect(engine)
    with engine.begin() as conn:
        for table, cols in NEW_COLUMNS.items():
            if not insp.has_table(table):
                continue
            have = {c["name"] for c in insp.get_columns(table)}
            for name, ddl in cols.items():
                if name not in have:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))
                    added.append(f"{table}.{name}")
    return added


def link_part_suppliers() -> int:
    """Spare parts used to have a free-text supplier. Link each one to the vendor list:
    same name (ignoring case) -> that vendor, otherwise a new vendor is created. Runs once, when the vendor_id column is added."""
    from sqlalchemy import select
    from . import models as m
    n = 0
    with SessionLocal() as db:
        parts = db.scalars(select(m.SparePart).where(m.SparePart.vendor_id.is_(None), m.SparePart.supplier.is_not(None))).all()
        if not parts:
            return 0
        by_name = {v.company.strip().lower(): v for v in db.scalars(select(m.Vendor))}
        for p in parts:
            name = (p.supplier or "").strip()
            if not name:
                continue
            v = by_name.get(name.lower())
            if v is None:
                v = m.Vendor(company=name, active=True)
                db.add(v)
                db.flush()
                by_name[name.lower()] = v
            p.vendor_id = v.id
            n += 1
        db.commit()
    return n
