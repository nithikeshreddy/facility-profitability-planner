"""API workflows through FastAPI's TestClient: open location → evaluate plans → feasibility → save."""

import pytest
from sqlalchemy import select

from app import loaders
from app import models as m

ATLANTA_REASON = "This offer is cheaper, but its crew requires 225 minutes within a 180-minute service window."


@pytest.fixture
def location_id(seeded):
    return lambda code: loaders.location_by_code(seeded, code).id


def _option(body, plan_type):
    return next(p for p in body["options"] if p["plan_type"] == plan_type)


# ---------------------------------------------------------------- overview


def test_overview_totals_and_sites(client, seeded):
    body = client.get("/api/overview").json()
    totals, sites = body["totals"], body["sites"]

    assert totals["sites"] == len(sites) == 2000
    assert totals["detailed_sites"] == 12
    assert totals["loss_making"] == sum(1 for s in sites if s["contribution"]["amount"] < 0)
    assert totals["revenue"]["amount"] - totals["direct_costs"]["amount"] == pytest.approx(totals["contribution"]["amount"])
    assert {"id", "lat", "lng", "revenue", "direct_costs", "contribution", "detailed", "name", "city", "state"} <= set(sites[0])
    for s in sites:
        assert s["revenue"]["amount"] - s["direct_costs"]["amount"] == pytest.approx(s["contribution"]["amount"])
    lightweight = next(s for s in sites if not s["detailed"])
    assert lightweight["direct_costs"]["kind"] == "actual"
    assert sites[0]["contribution"]["kind"] in ("estimated", "quoted", "actual")
    assert "AZ" in body["states"]


def test_overview_filters(client, seeded):
    losses = client.get("/api/overview", params={"loss_only": True}).json()
    assert losses["sites"] and all(s["contribution"]["amount"] < 0 for s in losses["sites"])
    assert losses["totals"]["loss_making"] == len(losses["sites"])

    az = client.get("/api/overview", params={"state": "AZ", "detailed_only": True}).json()["sites"]
    assert [s["name"] for s in az] == ["Phoenix Camelback Retail"]


# ---------------------------------------------------------------- Phoenix workflow


def test_phoenix_location_details(client, location_id):
    body = client.get(f"/api/locations/{location_id('PHX-01')}").json()

    contribution = body["contribution"]
    lines = {l["key"]: l["money"] for l in contribution["lines"]}
    assert lines["vendor_invoices"] == {"amount": 1380, "kind": "actual"}
    assert lines["return_visits"] == {"amount": 380, "kind": "actual"}
    assert contribution["total"] == {"amount": -260, "kind": "actual"}

    assert body["contract"]["price_monthly"] == {"amount": 1500, "kind": "actual"}
    assert body["service_requirements"]["window_minutes"] == 240
    assert body["reasonable_cost"]["available"] and body["reasonable_cost"]["low"]["kind"] == "estimated"
    assert {a["key"] for a in body["reasonable_cost"]["assumptions"]} >= {"local_loaded_wage", "margin_low", "margin_high"}

    [flag] = body["diagnosis"]["flags"]
    assert flag["key"] == "delivery_problem"
    access = [e for e in flag["evidence"] if e["type"] == "issue"]
    assert len(access) == 4
    assert all(e["date"] and "Stockroom locked" in e["summary"] for e in access)


def test_phoenix_plans_recommend_lockbox(client, location_id):
    body = client.post(f"/api/locations/{location_id('PHX-01')}/plans").json()

    assert body["current"]["projected_contribution"]["amount"] == pytest.approx(-260)
    fix = _option(body, "operational_fix")
    assert fix["projected_contribution"]["amount"] == pytest.approx(70, abs=1)
    assert fix["projected_contribution"]["kind"] == "estimated"
    assert fix["change"]["amount"] == pytest.approx(fix["projected_contribution"]["amount"] + 260)
    assert not fix["vendor_change"] and fix["feasible"] and fix["recommended"]
    assert body["recommended"] == {"plan_type": "operational_fix", "name": "Install stockroom lockbox",
                                   "offer_id": None, "fix_id": fix["fix_id"]}
    assert body["recommendation_reasons"][0].startswith("Best plan: Install stockroom lockbox")



def test_phoenix_plan_card_totals(client, location_id):
    body = client.post(f"/api/locations/{location_id('PHX-01')}/plans").json()

    current = body["current"]
    assert current["monthly_cost"] == {"amount": 1760, "kind": "actual"}  # 1,380 invoice + 380 return visits
    assert current["transition_one_time"]["amount"] == 0 and current["sites"] == []

    fix = _option(body, "operational_fix")
    assert fix["monthly_cost"] == {"amount": pytest.approx(1380 + 38), "kind": "estimated"}  # 90% of visits removed
    assert fix["transition_one_time"] == {"amount": 150, "kind": "estimated"}
    assert fix["transition_monthly"]["amount"] == pytest.approx(12.5)
    assert fix["bonus"]["amount"] == 0
    assert fix["sites"] == []


def test_dallas_bundle_returns_per_site_results(client, location_id):
    dal = location_id("DAL-01")
    url = f"/api/locations/{dal}/plans"
    bundle = _option(client.post(url).json(), "vendor_bundle")

    assert bundle["transition_one_time"] == {"amount": 300, "kind": "quoted"}
    assert len(bundle["sites"]) == 3
    assert [s["location_id"] for s in bundle["sites"] if s["is_this_location"]] == [dal]
    for s in bundle["sites"]:
        assert {"lat", "lng", "location_name", "fits", "required_minutes", "window_minutes"} <= set(s)
        assert s["current_contribution"]["amount"] == pytest.approx(-150)
        assert s["projected_contribution"]["amount"] == pytest.approx(42, abs=1)

    six = _option(client.post(url, json={"amortization_months": 6}).json(), "vendor_bundle")
    assert six["transition_monthly"]["amount"] == pytest.approx(300 / 6 / 3, abs=0.01)
    for before, after in zip(bundle["sites"], six["sites"]):
        assert before["projected_contribution"]["amount"] - after["projected_contribution"]["amount"] == (
            pytest.approx(300 / 12 / 3, abs=0.01)
        )

def test_phoenix_overrides_rerun_the_calculation(client, location_id):
    url = f"/api/locations/{location_id('PHX-01')}/plans"

    half = client.post(url, json={"return_visit_reduction": 0.5}).json()
    assert _option(half, "operational_fix")["projected_contribution"]["amount"] == pytest.approx(1500 - 1380 - 190 - 12.5)
    assert next(a for a in half["assumptions"] if a["key"] == "return_visit_reduction")["source"] == "override"

    none = client.post(url, json={"return_visit_reduction": 0}).json()
    assert _option(none, "operational_fix")["projected_contribution"]["amount"] == pytest.approx(-272.5)
    assert not _option(none, "operational_fix")["recommended"]
    assert none["recommended"] is None

    six = client.post(url, json={"amortization_months": 6}).json()
    transition = next(l for l in _option(six, "operational_fix")["lines"] if l["key"] == "transition")
    assert transition["money"]["amount"] == pytest.approx(25)

    default_low = client.post(url).json()["reasonable_cost"]["low"]["amount"]
    pricier = client.post(url, json={"local_loaded_wage": 25, "margin_low": 0.2, "margin_high": 0.3}).json()
    assert pricier["reasonable_cost"]["low"]["amount"] > default_low
    assert {a["key"]: a["source"] for a in pricier["assumptions"]}["local_loaded_wage"] == "override"


def test_plan_overrides_are_validated(client, location_id):
    url = f"/api/locations/{location_id('PHX-01')}/plans"
    assert client.post(url, json={"margin_low": 0.3, "margin_high": 0.2}).status_code == 422
    assert client.post(url, json={"return_visit_reduction": 1.5}).status_code == 422
    assert client.post(url, json={"amortization_months": 0}).status_code == 422


def test_one_margin_override_is_checked_against_the_recorded_other_end(client, location_id):
    phx = location_id("PHX-01")
    response = client.post(f"/api/locations/{phx}/plans", json={"margin_low": 0.4})  # recorded high end is lower
    assert response.status_code == 422
    assert "must not exceed the high end" in response.json()["detail"]

    action = client.post("/api/actions", json={"location_id": phx, "plan_type": "operational_fix",
                                               "overrides": {"margin_high": 0.05}})
    assert action.status_code == 422


def test_phoenix_save_proposed_action(client, mutable_db):
    phx = loaders.location_by_code(mutable_db, "PHX-01").id
    plans = client.post(f"/api/locations/{phx}/plans").json()
    fix = _option(plans, "operational_fix")

    response = client.post("/api/actions", json={
        "location_id": phx, "plan_type": "operational_fix", "fix_id": fix["fix_id"], "note": "Ask site manager for a code.",
    })
    assert response.status_code == 201
    action = response.json()
    assert action["status"] == "proposed"
    assert action["location_name"] == "Phoenix Camelback Retail"
    assert action["projected_contribution"] == fix["projected_contribution"]  # computed on the server
    assert action["summary"].startswith("Install stockroom lockbox: projected contribution")

    listed = client.get("/api/actions").json()
    assert [a["id"] for a in listed] == [action["id"]]
    assert client.get("/api/actions", params={"location_id": phx + 1}).json() == []


def test_saved_action_uses_its_overrides(client, mutable_db):
    phx = loaders.location_by_code(mutable_db, "PHX-01").id
    action = client.post("/api/actions", json={
        "location_id": phx, "plan_type": "operational_fix", "overrides": {"return_visit_reduction": 0.5},
    }).json()
    assert action["projected_contribution"]["amount"] == pytest.approx(-82.5)
    assert action["overrides"] == {"return_visit_reduction": 0.5}



def test_actions_are_listed_per_location_and_cleared_by_reset(client, mutable_db):
    phx = loaders.location_by_code(mutable_db, "PHX-01").id
    dal = loaders.location_by_code(mutable_db, "DAL-01").id
    client.post("/api/actions", json={"location_id": phx, "plan_type": "operational_fix", "note": "Lockbox first."})
    saved = client.post("/api/actions", json={"location_id": dal, "plan_type": "vendor_bundle"}).json()

    listed = client.get("/api/actions", params={"location_id": dal}).json()
    assert [a["id"] for a in listed] == [saved["id"]]
    assert listed[0]["note"] is None and listed[0]["projected_contribution"]["kind"] == "quoted"
    assert [a["note"] for a in client.get("/api/actions", params={"location_id": phx}).json()] == ["Lockbox first."]

    client.post("/api/demo/reset")
    assert client.get("/api/actions", params={"location_id": dal}).json() == []
    assert client.get("/api/actions", params={"location_id": phx}).json() == []

# ---------------------------------------------------------------- Atlanta workflow


def test_atlanta_cheap_offer_rejected_with_reason(client, location_id):
    body = client.post(f"/api/locations/{location_id('ATL-01')}/plans").json()
    offer = _option(body, "vendor_offer")

    assert offer["name"] == "Budget Shine offer"
    assert offer["vendor_name"] == "Budget Shine" and offer["vendor_change"]
    assert offer["projected_contribution"]["amount"] > body["current"]["projected_contribution"]["amount"]
    assert not offer["feasible"] and not offer["recommended"]
    assert offer["reasons"][0] == ATLANTA_REASON
    [check] = offer["feasibility"]["site_checks"]
    assert check["required_minutes"] == 225 and check["window_minutes"] == 180 and not check["fits"]
    assert body["recommended"] is None
    assert body["recommendation_reasons"] == ["No feasible plan beats current contribution."]


def test_atlanta_infeasible_offer_cannot_be_saved(client, mutable_db):
    atl = loaders.location_by_code(mutable_db, "ATL-01").id
    response = client.post("/api/actions", json={"location_id": atl, "plan_type": "vendor_offer"})
    assert response.status_code == 422
    assert response.json()["detail"] == ATLANTA_REASON
    assert client.get("/api/actions").json() == []


# ---------------------------------------------------------------- errors


def test_unknown_and_lightweight_locations_are_404(client, seeded):
    lightweight = seeded.scalar(select(m.Location.id).where(~m.Location.detailed).limit(1))
    for path in ("/api/locations/999999", f"/api/locations/{lightweight}"):
        assert client.get(path).status_code == 404
    response = client.post(f"/api/locations/{lightweight}/plans")
    assert response.status_code == 404
    assert "summary data only" in response.json()["detail"]


def test_saving_a_plan_that_does_not_exist_is_404(client, location_id):
    response = client.post("/api/actions", json={"location_id": location_id("COL-01"), "plan_type": "vendor_bundle"})
    assert response.status_code == 404


# ---------------------------------------------------------------- reset


def test_reset_restores_demonstration_data(client, mutable_db):
    phx = loaders.location_by_code(mutable_db, "PHX-01").id
    assert client.post("/api/actions", json={"location_id": phx, "plan_type": "operational_fix"}).status_code == 201
    assert len(client.get("/api/actions").json()) == 1

    response = client.post("/api/demo/reset")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "vendors": 4, "detailed_locations": 12, "locations": 2000}

    assert client.get("/api/actions").json() == []
    assert client.get(f"/api/locations/{phx}").json()["contribution"]["total"]["amount"] == pytest.approx(-260)
