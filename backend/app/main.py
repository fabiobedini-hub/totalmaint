"""TotalMaint – home / car / boat maintenance manager.

Run locally:   python -m uvicorn app.main:app --reload   (from the backend folder)
Then open:     http://localhost:8000
API docs:      http://localhost:8000/docs
"""
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import api, ical, reminders
from .config import APP_VERSION, DATABASE_URL, FRONTEND_DIR
from .db import Base, SessionLocal, add_missing_columns, engine, link_part_suppliers
from .permissions import migrate_to_groups

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("totalmaint")


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Creates missing tables. When the model starts changing after real data exists,
    # switch to Alembic migrations (see README).
    Base.metadata.create_all(engine)
    added = add_missing_columns()
    for col in added:
        log.info("Database: added column %s", col)
    # once, when parts get a vendor link: turn the old free-text suppliers into vendors
    linked = link_part_suppliers() if "spare_parts.vendor_id" in added else 0
    if linked:
        log.info("Database: linked %s spare parts to the vendor list", linked)
    # once, when groups arrive: existing users and things become one family group
    with SessionLocal() as db:
        msg = migrate_to_groups(db)
    if msg:
        log.info("Database: groups – %s", msg)
    log.info("Database: %s", DATABASE_URL.split("@")[-1])
    task = asyncio.create_task(reminders.scheduler_loop())
    yield
    task.cancel()


app = FastAPI(title="TotalMaint", version=APP_VERSION, lifespan=lifespan)
app.include_router(api.router)
app.include_router(reminders.router)
app.include_router(ical.router)


@app.middleware("http")
async def no_stale_frontend(request, call_next):
    """App files must never come from the browser cache, or an update stays invisible."""
    response = await call_next(request)
    if not request.url.path.startswith("/api"):
        response.headers["Cache-Control"] = "no-cache"
    return response


@app.get("/health")
def health():
    return {"ok": True}


# ---- frontend (PWA) served from the same server ----
@app.get("/sw.js", include_in_schema=False)
def service_worker():
    # Must be served from the root so it controls the whole app
    return FileResponse(FRONTEND_DIR / "sw.js", media_type="application/javascript",
                        headers={"Cache-Control": "no-cache"})


app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
