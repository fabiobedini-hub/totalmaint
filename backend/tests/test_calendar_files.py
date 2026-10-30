"""Calendar, iCal feed and attachments."""
from datetime import date, timedelta

TODAY = date.today()


def test_calendar_projects_repeats(api):
    a = api.asset()
    t = api.task(a["id"], "Filters", interval_value=1, interval_unit="months", next_due=TODAY.isoformat())
    events = api.get(f"/api/calendar?start={TODAY}&end={TODAY + timedelta(days=95)}")
    mine = [e for e in events if e["id"] == t["id"] and e["type"] == "task"]
    assert len(mine) in (3, 4)
    assert mine[0]["projected"] is False and all(e["projected"] for e in mine[1:])


def test_calendar_range_limit(api):
    api.get(f"/api/calendar?start={TODAY}&end={TODAY + timedelta(days=401)}", expect=400)


def test_calendar_shows_done_and_warranty(api):
    a = api.asset()
    t = api.task(a["id"], "Service", next_due=TODAY.isoformat())
    api.post(f"/api/tasks/{t['id']}/complete", {"done_on": TODAY.isoformat()})
    api.post(f"/api/assets/{a['id']}/warranties", {"title": "Pump", "end_date": (TODAY + timedelta(days=5)).isoformat()})
    types = {e["type"] for e in api.get(f"/api/calendar?start={TODAY}&end={TODAY + timedelta(days=10)}")}
    assert {"done", "warranty"} <= types


def test_ical_feed(api, client):
    a = api.asset()
    api.task(a["id"], "Clean gutters", next_due=(TODAY + timedelta(days=3)).isoformat())
    url = api.get("/api/me")["ical_url"]
    token_path = url[url.index("/ical/"):]
    r = client.get(token_path)
    assert r.status_code == 200 and "BEGIN:VCALENDAR" in r.text and "Clean gutters" in r.text
    assert client.get("/ical/wrong-token.ics").status_code == 404


def test_attachment_upload_download_delete(api):
    a = api.asset()
    files = {"file": ("receipt.pdf", b"%PDF-1.4 test", "application/pdf")}
    att = api.post("/api/attachments", data={"entity_type": "asset", "entity_id": str(a["id"])}, files=files)
    assert att["filename"] == "receipt.pdf"
    listed = api.get(f"/api/attachments?entity_type=asset&entity_id={a['id']}")
    assert [f["id"] for f in listed] == [att["id"]]
    r = api.get(f"/api/attachments/{att['id']}/file")
    assert r.content == b"%PDF-1.4 test"
    api.delete(f"/api/attachments/{att['id']}")
    assert api.get(f"/api/attachments?entity_type=asset&entity_id={a['id']}") == []


def test_attachment_needs_existing_target(api):
    files = {"file": ("x.txt", b"x", "text/plain")}
    api.post("/api/attachments", data={"entity_type": "asset", "entity_id": "999"}, files=files, expect=404)
    api.post("/api/attachments", data={"entity_type": "spaceship", "entity_id": "1"}, files=files, expect=400)
