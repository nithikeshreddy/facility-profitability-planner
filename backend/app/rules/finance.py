"""Contribution and reasonable-cost range (docs/SPEC.md section 4)."""

from collections.abc import Iterable
from dataclasses import dataclass, field

from app.rules.types import (
    AssumptionUsed,
    CostLine,
    InvoiceLine,
    Line,
    Money,
    Ref,
    RuleResult,
    Settings,
    Site,
    Task,
    combine_kinds,
    usd,
)


@dataclass
class ContributionResult(RuleResult):
    revenue: Money = Money(0.0, "actual")
    lines: list[Line] = field(default_factory=list)  # costs, as positive amounts
    total: Money = Money(0.0, "actual")


def _sum_line(key: str, label: str, items: list[InvoiceLine] | list[CostLine], ref_type: str) -> Line:
    amount = round(sum(i.amount for i in items), 2)
    kind = combine_kinds(*(i.kind for i in items)) if items else "actual"
    return Line(key, label, Money(amount, kind), tuple(Ref(ref_type, i.id) for i in items))


def contribution(
    revenue: float,
    invoices: Iterable[InvoiceLine],
    costs: Iterable[CostLine],
    month: str,
    bonus: Money | None = None,
    bonus_evidence: Iterable[Ref] = (),
) -> ContributionResult:
    """revenue − vendor invoices − other direct − return visits − credits − vendor bonus.

    Vendor invoices are `base` + `extra` lines. `return_visit` lines are the company-paid
    return visits (counted once). The bonus comes from rules.incentives; stored
    CostItem(type=bonus) rows are ignored so a bonus is never counted twice.
    """
    inv = [i for i in invoices if i.month == month]
    cst = [c for c in costs if c.month == month]

    lines = [
        _sum_line("vendor_invoices", "Vendor invoices", [i for i in inv if i.line_type in ("base", "extra")], "invoice"),
        _sum_line("other_direct", "Other direct costs", [c for c in cst if c.type == "other_direct"], "cost_item"),
        _sum_line(
            "return_visits", "Company-paid return visits", [i for i in inv if i.line_type == "return_visit"], "invoice"
        ),
        _sum_line("credits", "Customer credits", [c for c in cst if c.type == "credit"], "cost_item"),
    ]
    bonus = bonus or Money(0.0, "actual")
    lines.append(Line("vendor_bonus", "Vendor bonus", bonus, tuple(bonus_evidence)))

    rev = Money(revenue, "actual")
    total_amount = round(revenue - sum(l.money.amount for l in lines), 2)
    used = [l for l in lines if l.money.amount]
    total = Money(total_amount, combine_kinds(rev.kind, *(l.money.kind for l in used)))

    ignored = [c for c in cst if c.type == "bonus"]
    reasons = [
        f"Contribution {usd(total_amount)} = revenue {usd(revenue)}"
        + "".join(f" − {l.label.lower()} {usd(l.money.amount)}" for l in used)
        + "."
    ]
    if ignored:
        reasons.append(
            f"{len(ignored)} stored bonus cost item(s) ignored; the bonus is calculated from vendor targets."
        )
    evidence = [r for l in lines for r in l.evidence]
    return ContributionResult(reasons=reasons, evidence=evidence, revenue=rev, lines=lines, total=total)


def lightweight_contribution(revenue: float, actual_cost: float) -> Money:
    return Money(round(revenue - actual_cost, 2), "actual")


@dataclass(frozen=True)
class PortfolioTotals:
    sites: int
    loss_making: int
    revenue: Money
    direct_costs: Money  # revenue − contribution
    contribution: Money


def portfolio_totals(rows: Iterable[tuple[Money, Money]]) -> PortfolioTotals:
    """KPI totals over (revenue, contribution) pairs; the least certain kind wins."""
    rows = list(rows)
    revenue = round(sum(r.amount for r, _ in rows), 2)
    contribution = round(sum(c.amount for _, c in rows), 2)
    rev_kind = combine_kinds(*(r.kind for r, _ in rows))
    con_kind = combine_kinds(*(c.kind for _, c in rows))
    return PortfolioTotals(
        sites=len(rows),
        loss_making=sum(1 for _, c in rows if c.amount < 0),
        revenue=Money(revenue, rev_kind),
        direct_costs=Money(round(revenue - contribution, 2), combine_kinds(rev_kind, con_kind)),
        contribution=Money(contribution, con_kind),
    )


@dataclass
class CostRangeResult(RuleResult):
    available: bool = False
    crew_minutes_per_visit: float = 0.0
    visits_per_month: float = 0.0
    labor: Money = Money(0.0, "estimated")
    travel: Money = Money(0.0, "estimated")
    supplies: Money = Money(0.0, "estimated")
    base: Money = Money(0.0, "estimated")
    low: Money = Money(0.0, "estimated")
    high: Money = Money(0.0, "estimated")
    assumptions: list[AssumptionUsed] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)


def reasonable_cost_range(site: Site, tasks: Iterable[Task], settings: Settings) -> CostRangeResult:
    tasks = list(tasks)
    missing = []
    if not tasks:
        missing.append("site profile task minutes")
    if site.frequency_per_week is None:
        missing.append("service frequency")
    if site.local_loaded_wage is None:
        missing.append("local loaded wage")
    if site.travel_minutes_per_visit is None:
        missing.append("travel minutes per visit")
    if site.supplies_per_visit is None:
        missing.append("supplies per visit")
    if missing:
        return CostRangeResult(
            reasons=["Evidence missing: cannot estimate a reasonable cost without " + ", ".join(missing) + "."],
            missing=missing,
        )

    crew_minutes = sum(t.minutes for t in tasks)
    visits = site.frequency_per_week * settings.weeks_per_month
    wage = site.local_loaded_wage
    labor = crew_minutes / 60 * visits * wage
    travel = site.travel_minutes_per_visit / 60 * visits * wage
    supplies = site.supplies_per_visit * visits
    base = labor + travel + supplies
    low = base * (1 + settings.margin_low)
    high = base * (1 + settings.margin_high)

    assumptions = [
        AssumptionUsed("crew_minutes_per_visit", "Crew minutes per visit (sum of site tasks)", crew_minutes, "min", "site profile"),
        AssumptionUsed("frequency_per_week", "Visits per week", site.frequency_per_week, "visits/wk", "location record"),
        AssumptionUsed("weeks_per_month", "Weeks per month", settings.weeks_per_month, "wk", "global assumption"),
        AssumptionUsed("local_loaded_wage", "Local loaded wage", wage, "USD/hr", "location record"),
        AssumptionUsed("travel_minutes_per_visit", "Travel minutes per visit", site.travel_minutes_per_visit, "min", "location record"),
        AssumptionUsed("supplies_per_visit", "Supplies per visit", site.supplies_per_visit, "USD", "location record"),
        AssumptionUsed("margin_low", "Vendor margin, low end", settings.margin_low, "ratio", "global assumption"),
        AssumptionUsed("margin_high", "Vendor margin, high end", settings.margin_high, "ratio", "global assumption"),
    ]
    reasons = [
        f"{crew_minutes:g} crew minutes × {visits:.2f} visits/month at {usd(wage)}/hr = labor {usd(round(labor, 2))}; "
        f"travel {usd(round(travel, 2))}; supplies {usd(round(supplies, 2))}.",
        f"Reasonable cost {usd(round(low, 2))}–{usd(round(high, 2))} per month "
        f"(+{settings.margin_low:.0%} to +{settings.margin_high:.0%} vendor margin).",
    ]

    def m(x: float) -> Money:
        return Money(round(x, 2), "estimated")

    return CostRangeResult(
        reasons=reasons,
        evidence=[Ref("site_task", t.id) for t in tasks],
        available=True,
        crew_minutes_per_visit=crew_minutes,
        visits_per_month=round(visits, 4),
        labor=m(labor),
        travel=m(travel),
        supplies=m(supplies),
        base=m(base),
        low=m(low),
        high=m(high),
        assumptions=assumptions,
    )
