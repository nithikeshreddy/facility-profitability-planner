"""Compose the pure rules for one location (or the renewal queue) from stored records."""

from dataclasses import dataclass, replace
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import loaders
from app import models as m
from app.rules import bundles, diagnosis, evidence, feasibility, finance, incentives, plans, renewals
from app.rules.types import (
    AssumptionUsed,
    LocationRecords,
    Money,
    Overrides,
    Settings,
    Site,
    Targets,
    VendorInfo,
    combine_kinds,
    month_of,
)


class NotFound(LookupError):
    pass


class NotFeasible(ValueError):
    pass


class InvalidOverrides(ValueError):
    pass


class NotInQueue(ValueError):
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
        plan = plans.offer_plan(records, evaluation, offer_vendor, current_contrib)
        if evaluation.is_bundle:
            plan.sites = _bundle_sites(db, ctx, records, plan, evaluation, stops, offer_vendor)
        options.append(plan)
    return plans.recommend(current, options)


def _bundle_sites(
    db: Session, ctx: Context, records: LocationRecords, plan: plans.PlanResult,
    evaluation: bundles.OfferEvaluation, stops: list[Site], vendor: VendorInfo,
) -> list[plans.BundleSiteResult]:
    """Each bundled site's own share of the offer, so the bundle can be judged site by site."""
    by_site = {records.site.id: plan}
    for stop in stops:
        if stop.id not in by_site:
            stop_records = loaders.load_records(db, stop.id)
            by_site[stop.id] = plans.offer_plan(stop_records, evaluation, vendor, contribution(ctx, stop_records)[0])
    return plans.bundle_site_results(evaluation, stops, by_site, records.site.id)


def _renewal_input(db: Session, ctx: Context, records: LocationRecords) -> renewals.RenewalInput | None:
    if records.contract is None:
        return None
    site = records.site
    cost_range = finance.reasonable_cost_range(site, records.tasks, ctx.settings)
    current, _ = contribution(ctx, records)
    comparison = compare_plans(db, ctx, records)
    return renewals.RenewalInput(
        location_id=site.id,
        location_name=site.name,
        contract=records.contract,
        revenue=site.revenue_monthly,
        estimate_low=cost_range.low.amount if cost_range.available else None,
        estimate_high=cost_range.high.amount if cost_range.available else None,
        actual_cost=finance.direct_costs(current.revenue, current.total),
        best_contribution=plans.best_feasible_contribution(comparison),
        best_plan_name=comparison.best.name if comparison.best else "Current",
    )


def _renewal_item(db: Session, ctx: Context, records: LocationRecords) -> renewals.RenewalItem | None:
    item = _renewal_input(db, ctx, records)
    if item is None:
        return None
    return renewals.renewal_item(item, ctx.as_of, ctx.settings.target_margin, ctx.settings.weeks_per_month)


def renewal_queue(db: Session, ctx: Context) -> list[renewals.RenewalItem]:
    inputs = []
    for loc_id in db.scalars(select(m.Location.id).where(m.Location.detailed).order_by(m.Location.id)):
        if (item := _renewal_input(db, ctx, loaders.load_records(db, loc_id))) is not None:
            inputs.append(item)
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
    if ctx.settings.margin_low > ctx.settings.margin_high:
        # Checked against the values in effect, so overriding one end alone cannot invert the band.
        raise InvalidOverrides(
            f"Vendor margin low end ({ctx.settings.margin_low:.0%}) must not exceed the high end "
            f"({ctx.settings.margin_high:.0%})."
        )
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


def renewal_view(db: Session) -> dict:
    ctx = load_context(db)
    return {"as_of": ctx.as_of, "target_margin": ctx.settings.target_margin, "items": renewal_queue(db, ctx)}


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
    if plan_type == "renewal_review":
        if offer_id is not None or fix_id is not None or overrides is not None:
            raise InvalidOverrides("A renewal review takes no offer, fix or assumption overrides.")
        return save_renewal_action(db, location_id, note)
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


def save_renewal_action(db: Session, location_id: int, note: str | None = None) -> dict:
    """Store a renewal review as a proposed action; the suggested price is re-computed on the server."""
    loc = detailed_location(db, location_id)
    item = _renewal_item(db, load_context(db), loaders.load_records(db, location_id))
    if item is None:
        raise NotInQueue(
            f"{loc.name} is not in the renewal queue: its reasonable-cost low is not above revenue and it is "
            "not loss-making after the best feasible plan."
        )
    action = m.ProposedAction(
        location_id=location_id, plan_type="renewal_review", summary=renewals.action_summary(item),
        projected_contribution=item.projected_contribution.amount, projected_kind=item.projected_contribution.kind,
        status="proposed", note=note,
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


# ---------------------------------------------------------------- vendor incentives


def _vendor_location(ctx: Context, records: LocationRecords) -> dict:
    """One location's incentive result, its contribution before and after the bonus, and the service
    results this month (what a what-if simulation can change)."""
    site = records.site
    contrib, inc = contribution(ctx, records)
    before = finance.contribution(site.revenue_monthly, records.invoices, records.costs, ctx.month)
    return {
        **{k: getattr(site, k) for k in ("code", "name", "city", "state")},
        "location_id": site.id,
        "incentive": inc,
        "contribution_before_bonus": before.total,
        "contribution": contrib.total,
        "inspections": [i for i in records.inspections if month_of(i.date) == ctx.month],
        "issues": [i for i in records.issues if month_of(i.date) == ctx.month],
    }


def _money_total(amounts: list[Money], empty_kind: str = "estimated") -> Money:
    if not amounts:
        return Money(0.0, empty_kind)
    return Money(round(sum(a.amount for a in amounts), 2), combine_kinds(*(a.kind for a in amounts)))


def vendor_incentives(db: Session) -> dict:
    """Per vendor: bonus program, targets, and each detailed location it serves with targets vs results."""
    ctx = load_context(db)
    served: dict[int, list[int]] = {}
    for loc in db.scalars(select(m.Location).where(m.Location.detailed).order_by(m.Location.id)):
        served.setdefault(loc.current_vendor_id, []).append(loc.id)

    vendors = []
    for vendor in sorted(ctx.vendors.values(), key=lambda v: v.id):
        locations = [_vendor_location(ctx, loaders.load_records(db, lid)) for lid in served.get(vendor.id, [])]
        vendors.append({
            "vendor_id": vendor.id,
            "vendor_name": vendor.name,
            "has_program": vendor.has_bonus_program,
            "bonus_rate": vendor.bonus_rate,
            "bonus_cap": Money(vendor.bonus_cap, "quoted") if vendor.bonus_cap is not None else None,
            "targets": ctx.targets.get(vendor.id),
            "locations": locations,
            "total_bonus": _money_total([l["incentive"].bonus for l in locations]),
            "total_contribution": _money_total([l["contribution"] for l in locations], "actual"),
            "exceptions": [
                {"location_id": l["location_id"], "location_name": l["name"], "ref": e.ref, "reason": e.reason}
                for l in locations for e in l["incentive"].exceptions
            ],
        })
    return {"month": ctx.month, "vendors": vendors}


def simulate_incentive(db: Session, vendor_id: int, change: incentives.ResultChange) -> dict:
    """Recalculate eligibility and contribution with one service result changed. Read-only: the change
    is applied to the loaded records in memory and never written to the database."""
    ctx = load_context(db)
    vendor = ctx.vendors.get(vendor_id)
    if vendor is None:
        raise NotFound(f"Vendor {vendor_id} not found.")
    if change.inspection_id is not None:
        label, model, record_id = "Inspection", m.Inspection, change.inspection_id
    else:
        label, model, record_id = "Issue", m.IssueRecord, change.issue_id
    location_id = loaders.location_id_of(db, model, record_id)
    if location_id is None:
        raise NotFound(f"{label} {record_id} not found.")
    loc = db.get(m.Location, location_id)
    if loc.current_vendor_id != vendor_id:
        raise NotFound(f"{label} {record_id} is at {loc.name}, which {vendor.name} does not serve.")

    records = loaders.load_records(db, location_id)
    changed, described = incentives.apply_change(records, change)
    recorded, simulated = _vendor_location(ctx, records), _vendor_location(ctx, changed)
    before, after = recorded["contribution"], simulated["contribution"]
    return {
        "vendor_id": vendor.id,
        "vendor_name": vendor.name,
        "location_id": loc.id,
        "location_name": loc.name,
        "changes": described,
        "recorded": recorded,
        "simulated": simulated,
        "eligibility_changed": recorded["incentive"].eligible != simulated["incentive"].eligible,
        "contribution_change": Money(round(after.amount - before.amount, 2), combine_kinds(after.kind, before.kind)),
    }
