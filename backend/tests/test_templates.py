"""Templates: every bundle for every type of thing must apply cleanly."""
from datetime import date

import pytest

from app.schemas import AssetKind
from app.templates_data import TEMPLATES

KINDS = list(AssetKind.__args__)


def test_every_kind_has_an_entry():
    assert set(KINDS) == set(TEMPLATES)


@pytest.mark.parametrize("kind", [k for k in KINDS if TEMPLATES[k]])
def test_all_templates_apply(api, kind):
    a = api.asset(f"My {kind}", kind)
    listed = api.get(f"/api/templates?kind={kind}")
    assert len(listed) == len(TEMPLATES[kind])
    total = 0
    for tpl in listed:
        res = api.post(f"/api/assets/{a['id']}/apply-template?key={tpl['key']}", {})
        assert res["tasks_created"] > 0
        total += res["tasks_created"]
    tasks = api.get(f"/api/assets/{a['id']}")["tasks"]
    assert len(tasks) == total
    assert all(t["next_due"] for t in tasks)


def test_template_tasks_are_well_formed():
    units = {"days", "weeks", "months", "years"}
    for kind, bundles in TEMPLATES.items():
        for b in bundles:
            assert b["name"]["en"] and b["name"]["no"]
            for task in b["tasks"]:
                en, no, value, unit, comp, *season = task
                assert en and no and value > 0 and unit in units, (kind, task)
                assert comp is None or comp in b["components"], (kind, task)
                if season:
                    month, day = map(int, season[0].split("-"))
                    date(2026, month, day)  # a real date


def test_applying_twice_does_not_duplicate(api):
    a = api.asset("Bike", "bicycle")
    first = api.post(f"/api/assets/{a['id']}/apply-template?key=bike_basic", {})
    second = api.post(f"/api/assets/{a['id']}/apply-template?key=bike_basic", {})
    assert first["tasks_created"] == 5 and second["tasks_created"] == 0


def test_seasonal_task_gets_its_own_date(api):
    a = api.asset("Bike", "bicycle")
    api.post(f"/api/assets/{a['id']}/apply-template?key=bike_winter&start=2026-06-01", {})
    by_title = {t["title"]: t for t in api.get(f"/api/assets/{a['id']}")["tasks"]}
    assert by_title["Fit studded tyres"]["next_due"] == "2026-11-01"
    assert by_title["Take off studded tyres"]["next_due"] == "2027-04-15"
    assert by_title["Rinse off road salt"]["next_due"] == "2026-06-01"


def test_templates_in_norwegian(api, client):
    me = api.get("/api/me")
    api.patch("/api/me", {"lang": "no"})
    a = api.asset("Sparkesykkel", "scooter")
    api.post(f"/api/assets/{a['id']}/apply-template?key=scooter_basic", {})
    titles = {t["title"] for t in api.get(f"/api/assets/{a['id']}")["tasks"]}
    assert "Sjekk dekktrykk" in titles
    assert me["lang"] == "en"


def test_unknown_template(api):
    a = api.asset()
    api.post(f"/api/assets/{a['id']}/apply-template?key=nope", {}, expect=404)
