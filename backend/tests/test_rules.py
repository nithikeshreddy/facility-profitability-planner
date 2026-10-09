"""Unit tests for the pure rules with hand-built inputs (no database)."""

from datetime import date

import pytest

from app.rules import feasibility, finance, incentives, renewals
from app.rules.types import (
    ContractInfo,
    CostLine,
    InspectionRec,
    InvoiceLine,
    Issue,
    Money,
    Settings,
    Site,
    Targets,
    Task,
    VendorInfo,
    Visit,
)

MONTH = "2026-09"
SETTINGS = Settings()


def _site(id=1, lat=32.80, lng=-96.80, window=("22:00", "01:00"), **kw):
    return Site(id=id, code=f"S{id}", name=f"Site {id}", city="Dallas", state="TX", lat=lat, lng=lng,
                revenue_monthly=1000, window_start=window[0], window_end=window[1], **kw)


@pytest.mark.parametrize("start,end,expected", [("22:00", "01:00", 180), ("19:00", "23:00", 240), ("23:30", "23:30", 1440)])
def test_window_minutes_handles_midnight(start, end, expected):
    assert feasibility.window_minutes(start, end) == expected


def test_route_travel_counts_from_previous_stop_only():
    vendor = VendorInfo(1, "V", crews_available=1, shift_minutes=480)
    a, b = _site(1), _site(2, lat=32.83)  # about 2 miles apart
    result = feasibility.check_route([a, b], crew_size=2, minutes_per_site=100, vendor=vendor, settings=SETTINGS)
    assert result.site_checks[0].travel_minutes == 0
    assert 5 < result.site_checks[1].travel_minutes < 8
    assert result.feasible


def test_crew_capacity_failure_has_reason():
    vendor = VendorInfo(1, "Tiny Crew", crews_available=1, shift_minutes=120)
    result = feasibility.check_route([_site(1), _site(2, lat=32.81)], crew_size=1, minutes_per_site=100,
                                     vendor=vendor, settings=SETTINGS)
    assert all(c.fits for c in result.site_checks)
    assert not result.capacity_ok and not result.feasible
    assert result.reasons[-1].startswith("Over capacity:")


def test_contribution_ignores_stored_bonus_and_counts_return_visits_once():
    invoices = [InvoiceLine(1, 1, MONTH, 1000, "base"), InvoiceLine(2, 1, MONTH, 95, "return_visit"),
                InvoiceLine(3, 1, "2026-08", 999, "base")]
    costs = [CostLine(1, MONTH, "bonus", 50), CostLine(2, MONTH, "credit", 20), CostLine(3, MONTH, "other_direct", 10)]
    result = finance.contribution(1200, invoices, costs, MONTH, bonus=Money(30, "estimated"))
    assert result.total.amount == pytest.approx(1200 - 1000 - 95 - 20 - 10 - 30)
    assert result.total.kind == "estimated"
    assert any("ignored" in r for r in result.reasons)


def test_reasonable_cost_range_formula_and_missing_inputs():
    site = _site(frequency_per_week=5, local_loaded_wage=20.0, travel_minutes_per_visit=30, supplies_per_visit=2)
    result = finance.reasonable_cost_range(site, [Task(1, "Floors", 60), Task(2, "Restrooms", 30)], SETTINGS)
    visits = 5 * 4.33
    base = 90 / 60 * visits * 20 + 30 / 60 * visits * 20 + 2 * visits
    assert result.low.amount == pytest.approx(base * 1.15, abs=0.01)
    assert result.high.amount == pytest.approx(base * 1.25, abs=0.01)

    missing = finance.reasonable_cost_range(site, [], SETTINGS)
    assert not missing.available and missing.reasons[0].startswith("Evidence missing")


VENDOR = VendorInfo(9, "Bonus Co", 2, 480, bonus_rate=0.05, bonus_cap=75)
TARGETS = Targets(98, 90, 90)


def _visits(n, failed=()):
    return [Visit(i, date(2026, 9, i), completed=i not in failed, return_visit=False) for i in range(1, n + 1)]


def test_bonus_is_capped():
    inc = incentives.evaluate_incentive(VENDOR, TARGETS, [InvoiceLine(1, 9, MONTH, 2000, "base")], _visits(20), [],
                                        [InspectionRec(1, date(2026, 9, 5), 95)], MONTH)
    assert inc.eligible and inc.bonus.amount == 75


def test_customer_caused_failure_is_excluded_and_listed():
    visits = _visits(20, failed={3})
    issue = Issue(1, date(2026, 9, 3), "missed", "Site closed", customer_caused=True, resolved_hours=None, visit_id=3)
    args = (VENDOR, TARGETS, [InvoiceLine(1, 9, MONTH, 1000, "base")], visits)
    inspections = [InspectionRec(1, date(2026, 9, 5), 95)]

    inc = incentives.evaluate_incentive(*args, [issue], inspections, MONTH)
    assert inc.eligible and inc.bonus.amount == 50
    assert [e.ref.id for e in inc.exceptions] == [3]

    vendor_caused = Issue(1, date(2026, 9, 3), "missed", "Crew no-show", customer_caused=False, resolved_hours=30, visit_id=3)
    inc = incentives.evaluate_incentive(*args, [vendor_caused], inspections, MONTH)
    assert not inc.eligible and inc.bonus.amount == 0


def test_no_inspections_means_ineligible_evidence_missing():
    inc = incentives.evaluate_incentive(VENDOR, TARGETS, [InvoiceLine(1, 9, MONTH, 1000, "base")], _visits(20), [], [], MONTH)
    check = next(c for c in inc.checks if c.key == "inspection_avg")
    assert not inc.eligible and check.actual is None and "Evidence missing" in check.detail


def _contract(id, renewal):
    return ContractInfo(id, id, 1000, ("Floors",), 5, date(2024, 1, 1), renewal)


def test_renewal_queue_sorted_by_date_then_gap_and_skips_healthy():
    inputs = [
        renewals.RenewalInput(1, "Later", _contract(1, date(2026, 12, 1)), 1000, 900, -50),
        renewals.RenewalInput(2, "Small gap", _contract(2, date(2026, 11, 1)), 1000, 900, -20),
        renewals.RenewalInput(3, "Big gap", _contract(3, date(2026, 11, 1)), 1000, 1100, -200),
        renewals.RenewalInput(4, "Healthy", _contract(4, date(2026, 10, 15)), 1000, 800, 120),
    ]
    queue = renewals.renewal_queue(inputs, as_of=date(2026, 10, 1))
    assert [i.location_name for i in queue] == ["Big gap", "Small gap", "Later"]
    assert queue[0].suggested_price.amount == pytest.approx(1200 / 0.9, abs=0.01)
