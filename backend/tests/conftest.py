"""Shared test setup.

Every test gets an empty database in a temporary folder, so tests never touch your real data.
Run from the backend folder:   python -m pytest
"""
import os
import sys
import tempfile
from pathlib import Path

# Must happen before the app is imported: config.py reads these when it loads.
_TMP = Path(tempfile.mkdtemp(prefix="totalmaint-tests-"))
os.environ["DATA_DIR"] = str(_TMP)
os.environ["DATABASE_URL"] = f"sqlite:///{(_TMP / 'test.db').as_posix()}"
os.environ["UPLOAD_DIR"] = str(_TMP / "uploads")
os.environ["SECRET_KEY"] = "test-secret-key-not-for-production"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import reminders  # noqa: E402
from app.db import Base, engine  # noqa: E402
from app.main import app  # noqa: E402


async def _no_scheduler():  # never send reminder e-mails from tests
    return None


reminders.scheduler_loop = _no_scheduler


@pytest.fixture
def client():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with TestClient(app) as c:
        yield c


class Api:
    """Small helper: logged-in calls that fail loudly when the server says no."""

    def __init__(self, client, token):
        self.c = client
        self.h = {"Authorization": f"Bearer {token}"}

    def _check(self, r, expect):
        assert r.status_code == expect, f"{r.request.method} {r.request.url} -> {r.status_code}: {r.text}"
        return r.json() if r.headers.get("content-type", "").startswith("application/json") else r

    def get(self, path, expect=200, **kw):
        return self._check(self.c.get(path, headers=self.h, **kw), expect)

    def post(self, path, json=None, expect=200, **kw):
        return self._check(self.c.post(path, json=json, headers=self.h, **kw), expect)

    def put(self, path, json=None, expect=200):
        return self._check(self.c.put(path, json=json, headers=self.h), expect)

    def patch(self, path, json=None, expect=200):
        return self._check(self.c.patch(path, json=json, headers=self.h), expect)

    def delete(self, path, expect=200):
        return self._check(self.c.delete(path, headers=self.h), expect)

    # shortcuts
    def asset(self, name="House", kind="home", **kw):
        return self.post("/api/assets", {"name": name, "kind": kind, **kw})

    def task(self, asset_id, title="Task", **kw):
        body = {"title": title, "interval_value": 1, "interval_unit": "years", **kw}
        return self.post(f"/api/assets/{asset_id}/tasks", body)


@pytest.fixture
def api(client):
    """Logged in as the first user (administrator)."""
    r = client.post("/api/auth/setup", json={"name": "Fabio", "email": "admin@test.no", "password": "secret123", "lang": "en"})
    assert r.status_code == 200, r.text
    return Api(client, r.json()["token"])
