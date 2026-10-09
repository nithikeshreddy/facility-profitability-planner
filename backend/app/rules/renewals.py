"""Renewal review queue.

A contract enters the queue when the reasonable-cost low is above revenue (pricing/scope
problem) or the location is still loss-making after the best feasible plan. Sorted by
renewal date, then by the largest monthly gap. Each entry suggests a price, frequency
and scope review; the price is the one needed to reach the target margin.
"""

import math
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date

from app.rules.types import ContractInfo, Money, Ref, RuleResult, usd


@dataclass(frozen=True)
class RenewalInput:
    location_id: int
    location_name: str
    contract: ContractInfo
    revenue: float
    estimate_low: float | None  # None = no estimate (evidence missing)
    best_contribution: float  # after the best feasible plan (current if none beats it)
    best_plan_name: str = "Current"
    estimate_high: float | None = None
    actual_cost: Money | None = None  # this month's direct costs (revenue − current contribution)


@dataclass(frozen=True)
class Suggestion:
    key: str  # price_review | frequency_review | scope_review
    text: str


@dataclass
class RenewalItem(RuleResult):
    location_id: int = 0
    location_name: str = ""
    contract_id: int = 0
    renewal_date: date | None = None
    days_to_renewal: int = 0
    revenue: Money = Money(0.0, "actual")
    estimate_low: Money | None = None  # None = no estimate (evidence missing)
    estimate_high: Money | None = None
    actual_cost: Money | None = None
    cost_basis: Money = Money(0.0, "estimated")
    monthly_gap: Money = Money(0.0, "estimated")
    suggested_price: Money = Money(0.0, "estimated")
    projected_contribution: Money = Money(0.0, "estimated")  # at the suggested price
    target_margin: float = 0.10
    current_frequency_per_week: int = 0
    suggested_frequency_per_week: int | None = None
    triggers: list[str] = field(default_factory=list)  # pricing_scope_problem | loss_after_best_plan
    suggestions: list[Suggestion] = field(default_factory=list)


def _estimate(amount: float | None) -> Money | None:
    return None if amount is None else Money(round(amount, 2), "estimated")


def renewal_item(item: RenewalInput, as_of: date, target_margin: float, weeks_per_month: float) -> RenewalItem | None:
    c = item.contract
    triggers = []
    if item.estimate_low is not None and item.estimate_low > item.revenue:
        triggers.append("pricing_scope_problem")
    if item.best_contribution < 0:
        triggers.append("loss_after_best_plan")
    if not triggers:
        return None

    best_cost = item.revenue - item.best_contribution
    # Price must cover what we pay after the best plan, and at least the reasonable-cost low.
    cost_basis = max(best_cost, item.estimate_low or 0.0)
    price = round(cost_basis / (1 - target_margin), 2)
    gap = cost_basis - item.revenue
    days = (c.renewal_date - as_of).days

    reasons = []
    if "pricing_scope_problem" in triggers:
        reasons.append(
            f"Reasonable-cost low {usd(item.estimate_low)} is above revenue {usd(item.revenue)}: "
            "a pricing/scope problem no vendor change can fix."
        )
    if "loss_after_best_plan" in triggers:
        reasons.append(
            f"Still loss-making after the best feasible plan ({item.best_plan_name}): "
            f"{usd(item.best_contribution)} per month."
        )
    reasons.append(f"Renewal on {c.renewal_date.isoformat()} ({days} days).")

    suggestions = [
        Suggestion(
            "price_review",
            f"Price review: {usd(price)}/month reaches a {target_margin:.0%} margin on a "
            f"{usd(round(cost_basis, 2))} monthly cost (today {usd(item.revenue)}).",
        )
    ]
    visits = c.frequency_per_week * weeks_per_month
    affordable_visits = item.revenue * (1 - target_margin) / (cost_basis / visits)
    freq = math.floor(affordable_visits / weeks_per_month)
    if 1 <= freq < c.frequency_per_week:
        suggestions.append(
            Suggestion(
                "frequency_review",
                f"Frequency review: at today's price, {freq} visit(s)/week instead of {c.frequency_per_week} "
                f"would reach a {target_margin:.0%} margin.",
            )
        )
    else:
        freq = None
        suggestions.append(
            Suggestion("frequency_review", "Frequency review: reducing visits alone does not close the gap at today's price.")
        )
    suggestions.append(Suggestion("scope_review", "Scope review: confirm each item is needed — " + "; ".join(c.scope) + "."))

    return RenewalItem(
        reasons=reasons,
        evidence=[Ref("contract", c.id), Ref("location", item.location_id)],
        location_id=item.location_id,
        location_name=item.location_name,
        contract_id=c.id,
        renewal_date=c.renewal_date,
        days_to_renewal=days,
        revenue=Money(item.revenue, "actual"),
        estimate_low=_estimate(item.estimate_low),
        estimate_high=_estimate(item.estimate_high),
        actual_cost=item.actual_cost,
        cost_basis=Money(round(cost_basis, 2), "estimated"),
        monthly_gap=Money(round(gap, 2), "estimated"),
        suggested_price=Money(price, "estimated"),
        projected_contribution=Money(round(price - cost_basis, 2), "estimated"),
        target_margin=target_margin,
        current_frequency_per_week=c.frequency_per_week,
        suggested_frequency_per_week=freq,
        triggers=triggers,
        suggestions=suggestions,
    )


def renewal_queue(
    items: Iterable[RenewalInput], as_of: date, target_margin: float = 0.10, weeks_per_month: float = 4.33
) -> list[RenewalItem]:
    queue = [r for i in items if (r := renewal_item(i, as_of, target_margin, weeks_per_month)) is not None]
    return sorted(queue, key=lambda r: (r.renewal_date, -r.monthly_gap.amount))


def action_summary(item: RenewalItem) -> str:
    """One-line summary stored with a proposed renewal-review action."""
    summary = (
        f"Renewal review: propose {usd(item.suggested_price.amount)}/month ({item.target_margin:.0%} target margin) "
        f"before renewal on {item.renewal_date.isoformat()} ({item.days_to_renewal} days); today {usd(item.revenue.amount)}."
    )
    if item.suggested_frequency_per_week is not None:
        summary += (
            f" Alternative: {item.suggested_frequency_per_week} visit(s)/week instead of "
            f"{item.current_frequency_per_week} at today's price."
        )
    return summary
