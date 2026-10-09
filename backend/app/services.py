"""Compose the pure rules for one location (or the renewal queue) from stored records."""

from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import loaders
from app import models as m
from app.rules import bundles, diagnosis, finance, incentives, plans, renewals
from app.rules.types import LocationRecords, Settings, Targets, VendorInfo


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


def compare_plans(db: Session, ctx: Context, records: LocationRecords) -> plans.PlanComparison:
    current_contrib, _ = contribution(ctx, records)
    current = plans.current_plan(records, current_contrib)
    vendor = ctx.vendors[records.site.current_vendor_id]

    options = [
        plans.operational_fix_plan(records, fix, current_contrib, vendor, ctx.settings, ctx.month)
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

