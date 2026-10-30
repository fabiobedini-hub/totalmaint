"""Tasks: status, completing, history, costs and the overview."""
from datetime import date, timedelta

TODAY = date.today()


def iso(d):
    return d.isoformat()


def test_status_from_date(api):
    a = api.asset()
    late = api.task(a["id"], "Late", next_due=iso(TODAY - timedelta(days=3)))
    soon = api.task(a["id"], "Soon", next_due=iso(TODAY + timedelta(days=3)), remind_days_before=7)
    later = api.task(a["id"], "Later", next_due=iso(TODAY + timedelta(days=30)), remind_days_before=7)
    assert (late["status"], soon["status"], later["status"]) == ("overdue", "due_soon", "ok")

    d = api.get("/api/dashboard")
    assert [t["title"] for t in d["overdue"]] == ["Late"]
    assert [t["title"] for t in d["due_soon"]] == ["Soon"]
    assert [t["title"] for t in d["upcoming"]] == ["Later"]


def test_complete_recurring_task(api):
    a = api.asset()
    t = api.task(a["id"], "Clean gutters", interval_value=6, interval_unit="months", next_due=iso(TODAY - timedelta(days=10)))
    done_on = TODAY - timedelta(days=2)
    res = api.post(f"/api/tasks/{t['id']}/complete", {"done_on": iso(done_on), "cost": 450, "notes": "Ladder"})
    assert res["active"] is True
    assert res["next_due"] == iso(api_add_months(done_on, 6))
    assert res["status"] == "ok"
    assert len(res["completions"]) == 1 and res["completions"][0]["cost"] == 450
    assert res["total_cost"] == 450 and res["last_done"] == iso(done_on)

    d = api.get("/api/dashboard")
    assert d["overdue"] == [] and d["done_this_year"] >= 1
    if done_on.year == TODAY.year:
        assert d["cost_this_year"] == 450


def api_add_months(d, n):
    from app.recurrence import add_interval
    return add_interval(d, n, "months")


def test_one_off_task_closes_when_done(api):
    a = api.asset()
    t = api.task(a["id"], "Fix the door", interval_value=0, interval_unit="none", next_due=iso(TODAY))
    res = api.post(f"/api/tasks/{t['id']}/complete", {})
    assert res["active"] is False and res["next_due"] is None and res["status"] == "inactive"
    assert api.get("/api/dashboard")["overdue"] == []


def test_new_recurring_task_without_date_starts_today(api):
    a = api.asset()
    t = api.task(a["id"], "No date", interval_value=1, interval_unit="months")
    assert t["next_due"] == iso(TODAY)


def test_edit_task_and_created_by(api):
    a = api.asset()
    t = api.task(a["id"], "Old title")
    assert t["created_by_name"] == "Fabio"
    body = {"title": "New title", "interval_value": 2, "interval_unit": "years", "next_due": iso(TODAY + timedelta(days=100))}
    u = api.put(f"/api/tasks/{t['id']}", body)
    assert u["title"] == "New title" and u["interval_value"] == 2 and u["created_by_name"] == "Fabio"


def test_component_must_belong_to_same_thing(api):
    house, car = api.asset("House"), api.asset("Car", "car")
    tyres = api.post(f"/api/assets/{car['id']}/components", {"name": "Tyres"})
    api.post(f"/api/assets/{house['id']}/tasks", {"title": "X", "component_id": tyres["id"]}, expect=400)


def test_delete_completion_removes_cost(api):
    a = api.asset()
    t = api.task(a["id"], "Service", next_due=iso(TODAY))
    res = api.post(f"/api/tasks/{t['id']}/complete", {"cost": 1000})
    api.delete(f"/api/completions/{res['completions'][0]['id']}")
    assert api.get(f"/api/tasks/{t['id']}")["total_cost"] == 0


def test_only_my_tasks(api, client):
    other = api.post("/api/users", {"name": "Kid", "email": "kid@test.no", "password": "secret123"})
    a = api.asset()
    api.task(a["id"], "Mine", next_due=iso(TODAY - timedelta(days=1)), assigned_to_id=api.get("/api/me")["id"])
    api.task(a["id"], "Anyone", next_due=iso(TODAY - timedelta(days=1)))
    api.task(a["id"], "Theirs", next_due=iso(TODAY - timedelta(days=1)), assigned_to_id=other["id"])
    titles = sorted(t["title"] for t in api.get("/api/dashboard?mine=true")["overdue"])
    assert titles == ["Anyone", "Mine"]
    assert len(api.get("/api/dashboard")["overdue"]) == 3


def test_asset_filter_on_overview(api):
    house, car = api.asset("House"), api.asset("Car", "car")
    api.task(house["id"], "H", next_due=iso(TODAY - timedelta(days=1)))
    api.task(car["id"], "C", next_due=iso(TODAY - timedelta(days=1)))
    d = api.get(f"/api/dashboard?asset_id={car['id']}")
    assert [t["title"] for t in d["overdue"]] == ["C"]


def test_counter_task(api):
    boat = api.asset("Boat", "boat", counter_unit="hours", counter_value=90)
    t = api.task(boat["id"], "Engine service", interval_value=0, interval_unit="none",
                 counter_interval=100, counter_next_due=100)
    assert t["status"] == "due_soon"  # 90 of 100 h: last 10 %
    api.post(f"/api/assets/{boat['id']}/counter", {"value": 104})
    assert api.get(f"/api/tasks/{t['id']}")["status"] == "overdue"
    res = api.post(f"/api/tasks/{t['id']}/complete", {"counter_value": 105})
    assert res["active"] is True  # counter tasks keep going
    assert res["counter_next_due"] == 205 and res["status"] == "ok"


def test_counter_reading_refused_without_counter(api):
    a = api.asset()
    api.post(f"/api/assets/{a['id']}/counter", {"value": 10}, expect=400)


def test_vendor_workflow(api):
    v = api.post("/api/vendors", {"company": "Rørlegger AS"})
    a = api.asset()
    t = api.task(a["id"], "Service", vendor_id=v["id"], next_due=iso(TODAY + timedelta(days=40)))
    api.patch(f"/api/tasks/{t['id']}/vendor-status", {"status": "requested"})
    booked = TODAY + timedelta(days=20)
    r = api.patch(f"/api/tasks/{t['id']}/vendor-status", {"status": "confirmed", "on": iso(booked)})
    assert r["vendor_status"] == "confirmed" and r["vendor_booked_for"] == iso(booked)
    res = api.post(f"/api/tasks/{t['id']}/complete", {"vendor_id": v["id"], "cost": 2000})
    assert res["vendor_status"] is None  # starts over for next time
    h = api.get(f"/api/vendors/{v['id']}/history")
    assert len(h["jobs"]) == 1 and h["total_spent"] == 2000


def test_confirm_needs_vendor_and_date(api):
    a = api.asset()
    t = api.task(a["id"], "No vendor")
    api.patch(f"/api/tasks/{t['id']}/vendor-status", {"status": "requested"}, expect=400)
    v = api.post("/api/vendors", {"company": "X"})
    t2 = api.task(a["id"], "With vendor", vendor_id=v["id"])
    api.patch(f"/api/tasks/{t2['id']}/vendor-status", {"status": "confirmed"}, expect=400)


def test_delete_thing_removes_its_tasks(api):
    a = api.asset()
    t = api.task(a["id"])
    api.delete(f"/api/assets/{a['id']}")
    api.get(f"/api/tasks/{t['id']}", expect=404)
