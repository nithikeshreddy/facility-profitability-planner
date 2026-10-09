"""Compose the pure rules for one location (or the renewal queue) from stored records."""

from dataclasses import dataclass, replace
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import loaders
from app import models as m
from app.rules import bundles, diagnosis, evidence, feasibility, finance, incentives, plans, renewals
from app.rules.types import AssumptionUsed, LocationRecords, Money, Overrides, Settings, Targets, VendorInfo


class NotFound(LookupError):
    pass


class NotFeasible(ValueError):
    pass


@dataclass
class Context:
    settings: Settings
    as_of: date
    month: str
    vendors: dict[int, VendorInfo]
    targets: dict[int, Targets]


def load_context(db: Session, settings: Settings | None = None) -> Context:
    as_of, month = loaders.load_as_of(db)
    return Context(settings or loaders.load_settings(db), as_of, month, loaders.load_vendors(db), loaders.load_targets(db))


def incentive(ctx: Context, records: LocationRecords) -> incentives.IncentiveResult:
    vendor = ctx.vendors[records.site.current_vendor_id]
    return incentives.evaluate_incentive(
        vendor, ctx.targets.get(vendor.id), records.invoices, records.visits, records.issues, records.inspections, ctx.month
    )


def contribution(ctx: Context, records: LocationRecords) -> tuple[finance.ContributionResult, incentives.IncentiveResult]:
    inc = incentive(ctx, records)
    result = finance.contribution(
        records.site.revenue_monthly, records.invoices, records.costs, ctx.month,
        bonus=inc.bonus if inc.eligible else None, bonus_evidence=inc.evidence if inc.eligible else (),
    )
    return result, inc


@dataclass
class LocationAnalysis:
    records: LocationRecords
    contribution: finance.ContributionResult
    incentive: incentives.IncentiveResult
    cost_range: finance.CostRangeResult
    diagnosis: diagnosis.DiagnosisResult


def analyze(ctx: Context, records: LocationRecords) -> LocationAnalysis:
    contrib, inc = contribution(ctx, records)
    cost_range = finance.reasonable_cost_range(records.site, records.tasks, ctx.settings)
    return LocationAnalysis(records, contrib, inc, cost_range, diagnosis.diagnose(records, cost_range, ctx.month))


def compare_plans(
    db: Session, ctx: Context, records: LocationRecords, return_visit_reduction: float | None = None
) -> plans.PlanComparison:
    current_contrib, _ = contribution(ctx, records)
    vendor = ctx.vendors[records.site.current_vendor_id]
    current = plans.current_plan(records, current_contrib, vendor)

    options = [
        plans.operational_fix_plan(records, fix, current_contrib, vendor, ctx.settings, ctx.month, return_visit_reduction)
        for fix in loaders.load_fixes_for(db, records.site.id)
    ]
    for offer in loaders.load_offers_for(db, records.site.id):
        stops = [loaders.site_from(db.get(m.Location, lid)) for lid in offer.location_ids]
        offer_vendor = ctx.vendors[offer.vendor_id]
        evaluation = bundles.evaluate_offer(offer, stops, offer_vendor, ctx.settings)
        options.append(plans.offer_plan(records, evaluation, offer_vendor, current_contrib))
    return plans.recommend(current, options)


def renewal_queue(db: Session, ctx: Context) -> list[renewals.RenewalItem]:
    inputs = []
    for loc in db.scalars(select(m.Location).where(m.Location.detailed).order_by(m.Location.id)):
        records = loaders.load_records(db, loc.id)
        if records.contract is None:
            continue
        cost_range = finance.reasonable_cost_range(records.site, records.tasks, ctx.settings)
        comparison = compare_plans(db, ctx, records)
        inputs.append(renewals.RenewalInput(
            location_id=loc.id,
            location_name=loc.name,
            contract=records.contract,
            revenue=loc.revenue_monthly,
            estimate_low=cost_range.low.amount if cost_range.available else None,
            best_contribution=plans.best_feasible_contribution(comparison),
            best_plan_name=comparison.best.name if comparison.best else "Current",
        ))
    return renewals.renewal_queue(inputs, ctx.as_of, ctx.settings.target_margin, ctx.settings.weeks_per_month)



# ---------------------------------------------------------------- API views
# Composition for the routers: load records, call the rules, assemble one response object.


def detailed_location(db: Session, location_id: int) -> m.Location:
    loc = db.get(m.Location, location_id)
    if loc is None:
        raise NotFound(f"Location {location_id} not found.")
    if not loc.detailed:
        raise NotFound(
            f"Location {location_id} ({loc.name}) has summary data only; detailed evidence is not recorded."
        )
    return loc


@dataclass
class SiteSummary:
    id: int
    code: str
    name: str
    city: str
    state: str
    lat: float
    lng: float
    detailed: bool
    revenue: Money
    direct_costs: Money
    contribution: Money


def overview(db: Session, state: str | None = None, loss_only: bool = False, detailed_only: bool = False) -> dict:
    ctx = load_context(db)
    query = select(m.Location).order_by(m.Location.id)
    if state:
        query = query.where(m.Location.state == state.upper())
    if detailed_only:
        query = query.where(m.Location.detailed)

    sites = []
    for loc in db.scalars(query):
        if loc.detailed:
            contrib = contribution(ctx, loaders.load_records(db, loc.id))[0].total
        else:
            contrib = finance.lightweight_contribution(loc.revenue_monthly, loc.actual_cost_monthly)
        if loss_only and contrib.amount >= 0:
            continue
        revenue = Money(loc.revenue_monthly, "actual")
        sites.append(SiteSummary(loc.id, loc.code, loc.name, loc.city, loc.state, loc.lat, loc.lng, loc.detailed,
                                 revenue, finance.direct_costs(revenue, contrib), contrib))

    totals = finance.portfolio_totals((s.revenue, s.contribution) for s in sites)
    return {
        "totals": {**vars(totals), "detailed_sites": sum(1 for s in sites if s.detailed)},
        "states": sorted(db.scalars(select(m.Location.state).distinct())),
        "sites": sites,
    }


def location_detail(db: Session, location_id: int) -> dict:
    loc = detailed_location(db, location_id)
    ctx = load_context(db)
    records = loaders.load_records(db, location_id)
    a = analyze(ctx, records)
    site, c = records.site, records.contract
    window = (
        feasibility.window_minutes(site.window_start, site.window_end) if site.window_start and site.window_end else None
    )
    return {
        "location": {
            **{k: getattr(loc, k) for k in ("id", "code", "name", "city", "state", "lat", "lng", "customer_account",
                                             "building_type", "sq_ft", "restrooms", "floors")},
            "current_vendor_id": loc.current_vendor_id,
            "current_vendor_name": loc.current_vendor.name if loc.current_vendor else None,
        },
        "contract": {
            "id": c.id, "price_monthly": Money(c.price_monthly, "actual"), "scope": list(c.scope),
            "frequency_per_week": c.frequency_per_week, "start_date": c.start_date, "renewal_date": c.renewal_date,
            "days_to_renewal": (c.renewal_date - ctx.as_of).days,
        } if c else None,
        "service_requirements": {
            "window_start": site.window_start, "window_end": site.window_end, "window_minutes": window,
            "frequency_per_week": site.frequency_per_week, "current_crew_size": site.current_crew_size,
            "tasks": list(records.tasks), "crew_minutes_per_visit": sum(t.minutes for t in records.tasks),
        },
        "month": ctx.month,
        "as_of": ctx.as_of,
        "contribution": a.contribution,
        "reasonable_cost": a.cost_range,
        "actual_cleaning_cost": Money(a.diagnosis.actual_cleaning_cost, "actual"),
        "diagnosis": {
            "flags": [
                {"key": f.key, "label": f.label, "action": f.action, "reasons": list(f.reasons),
                 "evidence": evidence.describe(f.evidence, records)}
                for f in a.diagnosis.flags
            ],
            "reasons": a.diagnosis.reasons,
        },
        "missing_evidence": a.diagnosis.missing_evidence,
        "incentive": a.incentive,
    }


def apply_overrides(ctx: Context, records: LocationRecords, ov: Overrides) -> tuple[Context, LocationRecords]:
    changes = {k: getattr(ov, k) for k in ("margin_low", "margin_high", "amortization_months") if getattr(ov, k) is not None}
    ctx = replace(ctx, settings=replace(ctx.settings, **changes))
    if ov.local_loaded_wage is not None:
        records = replace(records, site=replace(records.site, local_loaded_wage=ov.local_loaded_wage))
    return ctx, records


def _assumptions_used(db: Session, ctx: Context, records: LocationRecords, ov: Overrides) -> list[AssumptionUsed]:
    def src(key: str, default: str) -> str:
        return "override" if getattr(ov, key) is not None else default

    s = ctx.settings
    out = []
    if records.site.local_loaded_wage is not None:
        out.append(AssumptionUsed("local_loaded_wage", "Local loaded wage", records.site.local_loaded_wage, "USD/hr",
                                  src("local_loaded_wage", "location record")))
    out += [
        AssumptionUsed("margin_low", "Vendor margin, low end", s.margin_low, "ratio", src("margin_low", "global assumption")),
        AssumptionUsed("margin_high", "Vendor margin, high end", s.margin_high, "ratio", src("margin_high", "global assumption")),
        AssumptionUsed("amortization_months", "Transition cost amortization", s.amortization_months, "months",
                       src("amortization_months", "global assumption")),
    ]
    for fix in loaders.load_fixes_for(db, records.site.id):
        value = fix.return_visit_reduction if ov.return_visit_reduction is None else ov.return_visit_reduction
        out.append(AssumptionUsed("return_visit_reduction", f"Return visits removed by: {fix.name}", value, "ratio",
                                  src("return_visit_reduction", "operational fix record")))
    return out


def plan_workbench(db: Session, location_id: int, overrides: Overrides | None = None) -> dict:
    detailed_location(db, location_id)
    ov = overrides or Overrides()
    ctx, records = apply_overrides(load_context(db), loaders.load_records(db, location_id), ov)
    comparison = compare_plans(db, ctx, records, ov.return_visit_reduction)
    return {
        "location_id": location_id,
        "assumptions": _assumptions_used(db, ctx, records, ov),
        "reasonable_cost": finance.reasonable_cost_range(records.site, records.tasks, ctx.settings),
        "current": comparison.current,
        "options": comparison.options,
        "recommended": comparison.best,
        "recommendation_reasons": comparison.reasons,
    }


def _find_plan(workbench: dict, plan_type: str, offer_id: int | None, fix_id: int | None) -> plans.PlanResult:
    if plan_type == "current":
        return workbench["current"]
    for p in workbench["options"]:
        if p.plan_type == plan_type and offer_id in (None, p.offer_id) and fix_id in (None, p.fix_id):
            return p
    raise NotFound(f"No {plan_type.replace('_', ' ')} plan found for location {workbench['location_id']}.")


def action_view(a: m.ProposedAction) -> dict:
    return {
        **{k: getattr(a, k) for k in ("id", "location_id", "plan_type", "summary", "status", "created_at", "note",
                                       "offer_id", "fix_id", "overrides")},
        "location_name": a.location.name,
        "projected_contribution": Money(a.projected_contribution, a.projected_kind),
    }


def save_action(
    db: Session, location_id: int, plan_type: str, offer_id: int | None = None, fix_id: int | None = None,
    overrides: Overrides | None = None, note: str | None = None,
) -> dict:
    """Re-run the comparison on the server and store the chosen plan as a proposed action."""
    workbench = plan_workbench(db, location_id, overrides)
    plan = _find_plan(workbench, plan_type, offer_id, fix_id)
    if not plan.feasible:
        raise NotFeasible(plan.reasons[0])
    used = {k: v for k, v in vars(overrides).items() if v is not None} if overrides else {}
    action = m.ProposedAction(
        location_id=location_id, plan_type=plan.plan_type, summary=plans.action_summary(plan),
        projected_contribution=plan.projected_contribution.amount, projected_kind=plan.projected_contribution.kind,
        status="proposed", note=note, offer_id=plan.offer_id, fix_id=plan.fix_id, overrides=used or None,
    )
    db.add(action)
    db.commit()
    db.refresh(action)
    return action_view(action)


def list_actions(db: Session, location_id: int | None = None) -> list[dict]:
    query = select(m.ProposedAction).order_by(m.ProposedAction.created_at.desc(), m.ProposedAction.id.desc())
    if location_id is not None:
        query = query.where(m.ProposedAction.location_id == location_id)
    return [action_view(a) for a in db.scalars(query)]
