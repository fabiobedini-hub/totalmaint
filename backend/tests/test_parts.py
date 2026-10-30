"""Spare parts, shopping list, purchases and the shared vendor list."""
from datetime import date


def make_part(api, asset_id, **kw):
    body = {"name": "Anodes", "unit_price": 150, "qty_in_stock": 0, "min_qty": 0, "on_shopping_list": True, "qty_to_buy": 2, **kw}
    return api.post(f"/api/assets/{asset_id}/parts", body)


def test_buy_part_updates_stock_list_and_costs(api):
    boat = api.asset("Boat", "boat")
    p = make_part(api, boat["id"])
    assert [x["name"] for x in api.get("/api/shopping-list")] == ["Anodes"]
    res = api.post(f"/api/parts/{p['id']}/bought", {"qty": 2, "unit_price": 160})
    assert res["qty_in_stock"] == 2 and res["on_shopping_list"] is False and res["unit_price"] == 160
    assert api.get("/api/shopping-list") == []
    assert api.get("/api/dashboard")["cost_this_year"] == 320
    # undo the purchase
    api.delete(f"/api/purchases/{res['last_purchase_id']}")
    assert api.get(f"/api/assets/{boat['id']}")["parts"][0]["qty_in_stock"] == 0
    assert api.get("/api/dashboard")["cost_this_year"] == 0


def test_below_minimum_goes_on_shopping_list(api):
    a = api.asset()
    make_part(api, a["id"], name="Filter", on_shopping_list=False, qty_in_stock=1, min_qty=2)
    items = api.get("/api/shopping-list")
    assert items[0]["name"] == "Filter" and items[0]["below_min"] is True


def test_part_supplier_is_a_vendor(api):
    v = api.post("/api/vendors", {"company": "Biltema"})
    a = api.asset()
    p = make_part(api, a["id"], vendor_id=v["id"], supplier="ignored")
    assert p["vendor_id"] == v["id"] and p["supplier"] == "Biltema"
    # renaming the vendor shows up on the part
    api.put(f"/api/vendors/{v['id']}", {"company": "Biltema Sandefjord"})
    assert api.get(f"/api/assets/{a['id']}")["parts"][0]["supplier"] == "Biltema Sandefjord"
    # deleting the vendor keeps the name as plain text
    api.delete(f"/api/vendors/{v['id']}")
    part = api.get(f"/api/assets/{a['id']}")["parts"][0]
    assert part["vendor_id"] is None and part["supplier"] == "Biltema Sandefjord"



def test_unknown_vendor_refused_directly(api):
    a = api.asset()
    api.post(f"/api/assets/{a['id']}/parts", {"name": "X", "vendor_id": 999}, expect=400)


def test_old_free_text_suppliers_are_linked(api):
    """The one-time upgrade: typed supplier names become vendors (reusing ones with the same name)."""
    from app import models as m
    from app.db import SessionLocal, link_part_suppliers
    api.post("/api/vendors", {"company": "Biltema"})
    a = api.asset()
    with SessionLocal() as db:
        for name, supplier in [("Anodes", "biltema "), ("Oil", "Jula"), ("Rope", None)]:
            db.add(m.SparePart(asset_id=a["id"], name=name, supplier=supplier))
        db.commit()
    assert link_part_suppliers() == 2
    vendors = sorted(v["company"] for v in api.get("/api/vendors"))
    assert vendors == ["Biltema", "Jula"]
    parts = {p["name"]: p for p in api.get(f"/api/assets/{a['id']}")["parts"]}
    assert parts["Anodes"]["supplier"] == "Biltema" and parts["Oil"]["supplier"] == "Jula"
    assert parts["Rope"]["vendor_id"] is None


def test_warranty_shows_on_overview(api):
    a = api.asset()
    end = date.fromordinal(date.today().toordinal() + 30)
    api.post(f"/api/assets/{a['id']}/warranties", {"title": "Heat pump", "end_date": end.isoformat()})
    assert [w["title"] for w in api.get("/api/dashboard")["warranties_expiring"]] == ["Heat pump"]
