"""Plan evaluation: current vs operational fix vs vendor offers/bundles.

projected contribution = revenue − projected vendor cost − projected other costs
                         − bonus (full cap, only if that vendor has a bonus program)
                         − transition cost ÷ amortization months.
A plan is recommended only if it is feasible AND beats current contribution.
"""

from collections.abc import Iterable
from dataclasses import dataclass, field

from app.rules.bundles import OfferEvaluation
from app.rules.feasibility import FeasibilityResult
from app.rules.finance import ContributionResult
from app.rules.types import (
    Fix,
    Line,
    LocationRecords,
    Money,
    Ref,
    RuleResult,
    Settings,
    VendorInfo,
    combine_kinds,
    month_of,
    usd,
)


@dataclass
class PlanResult(RuleResult):
    plan_type: str = "current"  # current | operational_fix | vendor_offer | vendor_bundle
    name: str = ""
    location_id: int = 0
    vendor_id: int | None = None
    vendor_name: str | None = None
    vendor_change: bool = False
    feasible: bool = True
    revenue: Money = Money(0.0, "actual")
    lines: list[Line] = field(default_factory=list)  # projected costs, positive amounts
    projected_contribution: Money = Money(0.0, "actual")
    current_contribution: Money = Money(0.0, "actual")
    change: Money = Money(0.0, "actual")  # projected − current
    recommended: bool = False
    offer_id: int | None = None
    fix_id: int | None = None
    feasibility: FeasibilityResult | None = None


def _projected(revenue: Money, lines: list[Line]) -> Money:
    amount = round(revenue.amount - sum(l.money.amount for l in lines), 2)
    return Money(amount, combine_kinds(revenue.kind, *(l.money.kind for l in lines if l.money.amount)))


def _change(projected: Money, current: Money) -> Money:
    return Money(round(projected.amount - current.amount, 2), combine_kinds(projected.kind, current.kind))


def _line(current: ContributionResult, key: str) -> Line:
    return next(l for l in current.lines if l.key == key)


def _assumed_bonus(vendor: VendorInfo) -> Line:
    amount = vendor.bonus_cap if vendor.has_bonus_program else 0.0
    return Line("vendor_bonus", "Vendor bonus (full cap assumed)", Money(amount or 0.0, "estimated"))


def current_plan(records: LocationRecords, current: ContributionResult, vendor: VendorInfo | None = None) -> PlanResult:
    return PlanResult(
        reasons=["Current vendor and delivery, from this month's records."] + current.reasons,
        evidence=list(current.evidence),
        plan_type="current",
        name="Current",
        location_id=records.site.id,
        vendor_id=records.site.current_vendor_id,
        vendor_name=vendor.name if vendor else None,
        revenue=current.revenue,
        lines=list(current.lines),
        projected_contribution=current.total,
        current_contribution=current.total,
    )


def operational_fix_plan(
    records: LocationRecords,
    fix: Fix,
    current: ContributionResult,
    vendor: VendorInfo,
    settings: Settings,
    month: str,
    return_visit_reduction: float | None = None,
) -> PlanResult:
    """Same vendor; the fix removes a share of company-paid return visits."""
    reduction = fix.return_visit_reduction if return_visit_reduction is None else return_visit_reduction
    rv_now = _line(current, "return_visits")
    rv_after = round(rv_now.money.amount * (1 - reduction), 2)
    transition = fix.one_time_cost / settings.amortization_months
    lines = [
        _line(current, "vendor_invoices"),
        _line(current, "other_direct"),
        Line("return_visits", "Company-paid return visits (projected)", Money(rv_after, "estimated"), rv_now.evidence),
        _line(current, "credits"),
        _assumed_bonus(vendor),
        Line("transition", "Transition cost (amortized)", Money(round(transition, 4), "estimated"), (Ref("operational_fix", fix.id),)),
    ]
    projected = _projected(current.revenue, lines)
    issues = [i for i in records.issues if i.category == fix.issue_category and month_of(i.date) == month]
    reasons = [
        f"{fix.name} ({usd(fix.one_time_cost)} one-time, {usd(round(transition, 2))}/month over "
        f"{settings.amortization_months:g} months) is expected to remove about {reduction:.0%} of company-paid "
        f"return visits ({usd(rv_now.money.amount)} → {usd(rv_after)} per month), with no vendor change.",
        f"Evidence: {len(issues)} {fix.issue_category} issue(s) this month — "
        + "; ".join(f"{i.date.isoformat()}: {i.description}" for i in issues)
        + ".",
        f"Projected contribution {usd(projected.amount)} vs current {usd(current.total.amount)}.",
    ]
    return PlanResult(
        reasons=reasons,
        evidence=[Ref("operational_fix", fix.id)] + [Ref("issue", i.id) for i in issues] + list(rv_now.evidence),
        plan_type="operational_fix",
        name=fix.name,
        location_id=records.site.id,
        vendor_id=records.site.current_vendor_id,
        vendor_name=vendor.name,
        vendor_change=False,
        feasible=True,
        revenue=current.revenue,
        lines=lines,
        projected_contribution=projected,
        current_contribution=current.total,
        change=_change(projected, current.total),
        fix_id=fix.id,
    )


def offer_plan(
    records: LocationRecords,
    evaluation: OfferEvaluation,
    vendor: VendorInfo,
    current: ContributionResult,
) -> PlanResult:
    """One site's share of a vendor offer (single-site offer or bundle)."""
    site = records.site
    current_vendor_cost = _line(current, "vendor_invoices").money.amount
    lines = [
        Line("vendor_invoices", f"{vendor.name} quoted price (site share)", evaluation.price_per_site, (Ref("vendor_offer", evaluation.offer_id),)),
        _line(current, "other_direct"),
        _line(current, "return_visits"),
        _line(current, "credits"),
        _assumed_bonus(vendor),
        Line("transition", "Transition cost (amortized, site share)", evaluation.transition_per_site_monthly, (Ref("vendor_offer", evaluation.offer_id),)),
    ]
    projected = _projected(current.revenue, lines)
    feas = evaluation.feasibility
    cheaper = evaluation.price_per_site.amount < current_vendor_cost
    reasons = list(evaluation.reasons)

    if feas.feasible:
        reasons.append("Feasible: the route fits every service window and the vendor's crew capacity.")
    else:
        failed = [c for c in feas.site_checks if not c.fits]
        mine = next((c for c in failed if c.location_id == site.id), None) or (failed[0] if failed else None)
        if mine is not None:
            lead = "This offer is cheaper, but" if cheaper else "This offer does not fit:"
            reasons.insert(0, f"{lead} {mine.clause}.")
        if not feas.capacity_ok:
            reasons.append(feas.reasons[-1])
    if _line(current, "return_visits").money.amount:
        reasons.append("Company-paid return visits are kept: a vendor change alone does not remove their cause.")
    reasons.append(f"Projected contribution {usd(projected.amount)} vs current {usd(current.total.amount)}.")

    return PlanResult(
        reasons=reasons,
        evidence=list(evaluation.evidence),
        plan_type="vendor_bundle" if evaluation.is_bundle else "vendor_offer",
        name=f"{vendor.name} {'bundle' if evaluation.is_bundle else 'offer'}",
        location_id=site.id,
        vendor_id=vendor.id,
        vendor_name=vendor.name,
        vendor_change=vendor.id != site.current_vendor_id,
        feasible=feas.feasible,
        revenue=current.revenue,
        lines=lines,
        projected_contribution=projected,
        current_contribution=current.total,
        change=_change(projected, current.total),
        offer_id=evaluation.offer_id,
        feasibility=feas,
    )


@dataclass
class PlanComparison(RuleResult):
    current: PlanResult = field(default_factory=PlanResult)
    options: list[PlanResult] = field(default_factory=list)
    best: PlanResult | None = None  # best recommended plan, if any


def recommend(current: PlanResult, options: Iterable[PlanResult]) -> PlanComparison:
    options = list(options)
    for p in options:
        p.recommended = p.feasible and p.projected_contribution.amount > current.projected_contribution.amount
        if not p.feasible:
            p.reasons.append("Not recommended: the plan is not feasible.")
        elif not p.recommended:
            p.reasons.append("Not recommended: it does not beat current contribution.")
        else:
            p.reasons.append("Recommended: feasible and beats current contribution. A manager approves every change.")
    good = [p for p in options if p.recommended]
    best = max(good, key=lambda p: p.projected_contribution.amount) if good else None
    reasons = (
        [f"Best plan: {best.name}, projected {usd(best.projected_contribution.amount)} per month."]
        if best
        else ["No feasible plan beats current contribution."]
    )
    return PlanComparison(
        reasons=reasons, evidence=list(best.evidence) if best else [], current=current, options=options, best=best
    )


def best_feasible_contribution(comparison: PlanComparison) -> float:
    """The contribution after the best feasible plan (current if nothing beats it)."""
    return comparison.best.projected_contribution.amount if comparison.best else comparison.current.projected_contribution.amount


def action_summary(plan: PlanResult) -> str:
    """One-line summary stored with a proposed action."""
    return (
        f"{plan.name}: projected contribution {usd(plan.projected_contribution.amount)} "
        f"vs current {usd(plan.current_contribution.amount)} per month."
    )
