"""The five demo cases (docs/SPEC.md section 6), reproduced from seeded records."""

from dataclasses import replace

import pytest
from sqlalchemy import select

from app import loaders, models, services
from app.rules import bundles, plans
from app.rules.types import Money, Ref


def _option(comparison, plan_type):
    return next(p for p in comparison.options if p.plan_type == plan_type)


# ---------------------------------------------------------------- 1. Dallas bundle


DALLAS = ["DAL-01", "DAL-02", "DAL-03"]


@pytest.mark.parametrize("code", DALLAS)
def test_dallas_bundle_is_feasible_and_turns_each_site_positive(seeded, ctx, records, code):
    r = records(code)
    comparison = services.compare_plans(seeded, ctx, r)

    assert comparison.current.projected_contribution.amount == pytest.approx(-150)
    bundle = _option(comparison, "vendor_bundle")
    assert bundle.name == "Metro Clean Co bundle"
    assert bundle.feasible
    assert bundle.vendor_change
    assert bundle.projected_contribution.amount == pytest.approx(42, abs=1)
    assert bundle.recommended
    assert comparison.best is bundle
    assert all(c.fits for c in bundle.feasibility.site_checks)



@pytest.mark.parametrize("code", DALLAS)
def test_dallas_bundle_reports_each_site_in_route_order(seeded, ctx, records, code):
    r = records(code)
    bundle = _option(services.compare_plans(seeded, ctx, r), "vendor_bundle")

    assert [s.location_id for s in bundle.sites] == [c.location_id for c in bundle.feasibility.site_checks]
    assert {s.location_name for s in bundle.sites} == {records(c).site.name for c in DALLAS}
    assert [s.location_id for s in bundle.sites if s.is_this_location] == [r.site.id]
    for s in bundle.sites:
        assert s.fits and s.required_minutes <= s.window_minutes
        assert s.current_contribution.amount == pytest.approx(-150)
        assert s.projected_contribution.amount == pytest.approx(42, abs=1)
        assert s.projected_contribution.kind == "quoted"
    mine = next(s for s in bundle.sites if s.is_this_location)
    assert mine.projected_contribution == bundle.projected_contribution
    assert bundle.transition_one_time.amount == pytest.approx(300)  # whole offer, before the split

def test_dallas_sites_have_two_current_vendors_and_are_bundle_candidates(seeded, records):
    sites = [records(c).site for c in DALLAS]
    assert len({s.current_vendor_id for s in sites}) == 2

    candidates = bundles.find_bundle_candidates(loaders.detailed_sites(seeded))
    dallas = [c for c in candidates if set(c.location_ids) == {s.id for s in sites}]
    assert len(dallas) == 1
    assert dallas[0].max_distance_miles <= 5
    assert "different vendors" in " ".join(dallas[0].reasons)


def test_dallas_bundle_vendor_has_no_bonus_program(ctx):
    metro = next(v for v in ctx.vendors.values() if v.name == "Metro Clean Co")
    assert not metro.has_bonus_program


# ---------------------------------------------------------------- 2. Phoenix operational fix


def test_phoenix_current_contribution_counts_return_visits_once(ctx, records):
    contribution, _ = services.contribution(ctx, records("PHX-01"))
    lines = {l.key: l.money.amount for l in contribution.lines}
    assert lines["vendor_invoices"] == pytest.approx(1380)
    assert lines["return_visits"] == pytest.approx(380)
    assert contribution.total.amount == pytest.approx(-260)


def test_phoenix_lockbox_fix_projects_plus_70_without_vendor_change(seeded, ctx, records):
    r = records("PHX-01")
    comparison = services.compare_plans(seeded, ctx, r)
    fix = _option(comparison, "operational_fix")

    assert fix.projected_contribution.amount == pytest.approx(70, abs=1)
    assert not fix.vendor_change
    assert fix.vendor_id == r.site.current_vendor_id
    assert fix.feasible and fix.recommended

    access = [i for i in r.issues if i.category == "access"]
    assert len(access) == 4
    assert {Ref("issue", i.id) for i in access} <= set(fix.evidence)
    evidence_text = " ".join(fix.reasons)
    assert "4 access issue(s)" in evidence_text
    for i in access:
        assert i.date.isoformat() in evidence_text


def test_phoenix_diagnosis_is_a_delivery_problem_with_access_evidence(ctx, records):
    analysis = services.analyze(ctx, records("PHX-01"))
    assert analysis.diagnosis.flag_keys == ["delivery_problem"]
    flag = analysis.diagnosis.flags[0]
    assert sum(1 for ref in flag.evidence if ref.type == "issue") == 4


# ---------------------------------------------------------------- 3. Columbus underpriced


def test_columbus_estimate_above_revenue_is_pricing_scope_problem(ctx, records):
    analysis = services.analyze(ctx, records("COL-01"))
    low, high = analysis.cost_range.low.amount, analysis.cost_range.high.amount

    assert low == pytest.approx(1150, abs=40)
    assert high == pytest.approx(1300, abs=40)
    assert analysis.cost_range.low.kind == "estimated"
    assert low > analysis.records.site.revenue_monthly == 900
    assert analysis.diagnosis.flag_keys == ["pricing_scope_problem"]
    assert {a.key for a in analysis.cost_range.assumptions} >= {
        "local_loaded_wage", "margin_low", "margin_high", "supplies_per_visit", "travel_minutes_per_visit",
    }


def test_columbus_is_in_renewal_review_with_suggested_price(seeded, ctx, records):
    r = records("COL-01")
    queue = services.renewal_queue(seeded, ctx)
    item = next(i for i in queue if i.location_id == r.site.id)

    assert "pricing_scope_problem" in item.triggers
    assert item.days_to_renewal == pytest.approx(45, abs=3)
    assert item.suggested_price.amount > 900
    assert item.suggested_price.kind == "estimated"
    # Price reaches the 10% target margin on what Columbus costs today.
    assert (item.suggested_price.amount - 1240) / item.suggested_price.amount == pytest.approx(0.10, abs=0.001)
    assert {s.key for s in item.suggestions} == {"price_review", "frequency_review", "scope_review"}


# ---------------------------------------------------------------- 4. Atlanta infeasible offer


def test_atlanta_cheap_offer_is_rejected_with_window_reason(seeded, ctx, records):
    comparison = services.compare_plans(seeded, ctx, records("ATL-01"))
    offer = _option(comparison, "vendor_offer")

    assert offer.name == "Budget Shine offer"
    assert not offer.feasible
    assert not offer.recommended
    assert offer.reasons[0] == "This offer is cheaper, but its crew requires 225 minutes within a 180-minute service window."
    # It would look better on price alone, which is why the reason matters.
    assert offer.projected_contribution.amount > comparison.current.projected_contribution.amount
    assert comparison.best is None


# ---------------------------------------------------------------- 5. Denver performance bonus


def test_denver_bonus_and_contribution(ctx, records):
    contribution, inc = services.contribution(ctx, records("DEN-01"))
    assert inc.eligible
    assert inc.bonus.amount == pytest.approx(67.50)
    assert contribution.total.amount == pytest.approx(182.50)
    # The customer-caused missed visit is excluded and listed for exception review.
    assert len(inc.exceptions) == 1
    assert inc.exceptions[0].ref.type == "service_visit"


def test_denver_one_low_inspection_makes_vendor_ineligible(mutable_db):
    loc = loaders.location_by_code(mutable_db, "DEN-01")
    inspection = mutable_db.scalars(
        select(models.Inspection).where(models.Inspection.location_id == loc.id, models.Inspection.score == 92)
    ).one()
    inspection.score = 85  # average (91 + 85 + 90) / 3 = 88.7 < 90
    mutable_db.commit()

    ctx = services.load_context(mutable_db)
    contribution, inc = services.contribution(ctx, loaders.load_records(mutable_db, loc.id))
    assert not inc.eligible
    assert inc.bonus.amount == 0
    assert contribution.total.amount == pytest.approx(250)
    assert not next(c for c in inc.checks if c.key == "inspection_avg").met


def test_denver_unmarking_customer_caused_failure_makes_vendor_ineligible(ctx, records):
    r = records("DEN-01")
    unmarked = replace(r, issues=tuple(replace(i, customer_caused=False) for i in r.issues))
    contribution, inc = services.contribution(ctx, unmarked)

    assert not inc.eligible
    assert not next(c for c in inc.checks if c.key == "completion").met  # 21 of 22 = 95.5% < 98%
    assert inc.exceptions == []
    assert contribution.total.amount == pytest.approx(250)


# ---------------------------------------------------------------- missing evidence


def test_location_without_inspections_reports_missing_evidence(seeded, ctx, records):
    detailed = loaders.detailed_sites(seeded)
    no_inspections = [s for s in detailed if not records(s.code).inspections]
    assert no_inspections, "seed must include a detailed location with no inspections"

    for site in no_inspections:
        analysis = services.analyze(ctx, records(site.code))
        missing = {g.key: g.message for g in analysis.diagnosis.missing_evidence}
        assert "inspections" in missing
        assert missing["inspections"].startswith("Evidence missing")
        if analysis.incentive.has_program:
            assert not analysis.incentive.eligible


# ---------------------------------------------------------------- transition costs


def test_transition_costs_are_included_in_plan_projections(seeded, ctx, records):
    dallas = _option(services.compare_plans(seeded, ctx, records("DAL-01")), "vendor_bundle")
    transition = next(l for l in dallas.lines if l.key == "transition").money.amount
    assert transition == pytest.approx(300 / 12 / 3, abs=0.01)
    assert dallas.projected_contribution.amount == pytest.approx(1100 - 3150 / 3 - transition, abs=0.01)

    phoenix = _option(services.compare_plans(seeded, ctx, records("PHX-01")), "operational_fix")
    assert next(l for l in phoenix.lines if l.key == "transition").money.amount == pytest.approx(150 / 12)


def test_projection_drops_when_transition_cost_rises(seeded, ctx, records):
    r = records("PHX-01")
    current, _ = services.contribution(ctx, r)
    vendor = ctx.vendors[r.site.current_vendor_id]
    fix = loaders.load_fixes_for(seeded, r.site.id)[0]

    base = plans.operational_fix_plan(r, fix, current, vendor, ctx.settings, ctx.month)
    pricier = plans.operational_fix_plan(r, replace(fix, one_time_cost=fix.one_time_cost + 1200), current, vendor, ctx.settings, ctx.month)
    assert base.projected_contribution.amount - pricier.projected_contribution.amount == pytest.approx(100)



def test_plan_card_totals_add_up_to_the_projection(seeded, ctx):
    """revenue − monthly cost − bonus − amortized transition = projected contribution, for every plan."""
    for site in loaders.detailed_sites(seeded):
        comparison = services.compare_plans(seeded, ctx, loaders.load_records(seeded, site.id))
        for p in [comparison.current, *comparison.options]:
            assert p.revenue.amount - p.monthly_cost.amount - p.bonus.amount - p.transition_monthly.amount == (
                pytest.approx(p.projected_contribution.amount, abs=0.01)
            ), (site.code, p.name)
            if p.plan_type != "vendor_bundle":
                assert p.sites == []
        assert comparison.current.transition_one_time.amount == 0


# ---------------------------------------------------------------- bonus in plan projections


def test_plan_projections_assume_the_full_bonus_cap_for_a_bonus_vendor(seeded, ctx, records):
    """Compare plans charges the full cap (not the earned bonus) when the vendor has a bonus program."""
    r = records("PHX-01")
    current, _ = services.contribution(ctx, r)
    [fix] = loaders.load_fixes_for(seeded, r.site.id)
    summit = next(v for v in ctx.vendors.values() if v.name == "Summit Janitorial")
    own = ctx.vendors[r.site.current_vendor_id]

    with_bonus = plans.operational_fix_plan(r, fix, current, summit, ctx.settings, ctx.month)
    without = plans.operational_fix_plan(r, fix, current, own, ctx.settings, ctx.month)
    assert with_bonus.bonus == Money(75, "estimated") and without.bonus.amount == 0
    assert without.projected_contribution.amount - with_bonus.projected_contribution.amount == pytest.approx(75)
