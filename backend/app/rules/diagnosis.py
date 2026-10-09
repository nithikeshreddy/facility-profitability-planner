"""Root-cause flags: delivery problem vs pricing/scope problem, plus missing evidence."""

from collections import Counter
from dataclasses import dataclass, field

from app.rules.finance import CostRangeResult
from app.rules.types import LocationRecords, Ref, RuleResult, month_of, usd

CATEGORY_LABELS = {"access": "access", "quality": "quality", "scope": "scope", "missed": "missed-visit"}


@dataclass(frozen=True)
class Flag:
    key: str  # delivery_problem | pricing_scope_problem
    label: str
    action: str
    reasons: tuple[str, ...]
    evidence: tuple[Ref, ...]


@dataclass(frozen=True)
class MissingEvidence:
    key: str
    message: str


@dataclass
class DiagnosisResult(RuleResult):
    actual_cleaning_cost: float = 0.0
    flags: list[Flag] = field(default_factory=list)
    missing_evidence: list[MissingEvidence] = field(default_factory=list)

    @property
    def flag_keys(self) -> list[str]:
        return [f.key for f in self.flags]


def missing_evidence(records: LocationRecords, month: str) -> list[MissingEvidence]:
    out = []
    if not any(i.month == month for i in records.invoices):
        out.append(MissingEvidence("invoices", f"Evidence missing: no vendor invoices recorded for {month}."))
    if not any(month_of(v.date) == month for v in records.visits):
        out.append(MissingEvidence("visits", f"Evidence missing: no service visits recorded for {month}."))
    if not any(month_of(i.date) == month for i in records.inspections):
        out.append(
            MissingEvidence("inspections", f"Evidence missing: no inspections recorded for {month}; quality cannot be judged.")
        )
    if not records.tasks:
        out.append(MissingEvidence("site_tasks", "Evidence missing: no site profile tasks; reasonable cost cannot be estimated."))
    return out


def diagnose(records: LocationRecords, cost_range: CostRangeResult, month: str) -> DiagnosisResult:
    revenue = records.site.revenue_monthly
    invoices = [i for i in records.invoices if i.month == month]
    actual = round(sum(i.amount for i in invoices), 2)
    issues = [i for i in records.issues if month_of(i.date) == month]
    flags: list[Flag] = []

    if cost_range.available and actual > cost_range.high.amount:
        reasons = [
            f"Actual cleaning cost {usd(actual)} is above the reasonable-cost high of {usd(cost_range.high.amount)} "
            "— a delivery problem: fix how the work is delivered."
        ]
        evidence = [Ref("invoice", i.id) for i in invoices]
        rv = [i for i in invoices if i.line_type == "return_visit"]
        if rv:
            reasons.append(
                f"{len(rv)} company-paid return visit(s) cost {usd(sum(i.amount for i in rv))} this month."
            )
            evidence += [Ref("service_visit", v.id) for v in records.visits if v.return_visit and month_of(v.date) == month]
        if issues:
            counts = Counter(i.category for i in issues)
            reasons.append(
                "Issues recorded: "
                + ", ".join(f"{n} {CATEGORY_LABELS.get(c, c)}" for c, n in sorted(counts.items()))
                + "."
            )
            evidence += [Ref("issue", i.id) for i in issues]
        flags.append(Flag("delivery_problem", "Delivery problem", "Fix how work is delivered", tuple(reasons), tuple(evidence)))

    if cost_range.available and cost_range.low.amount > revenue:
        reasons = (
            f"The reasonable-cost low of {usd(cost_range.low.amount)} is above revenue of {usd(revenue)} "
            "— a pricing/scope problem: no vendor change can fix it; send to renewal review.",
        )
        evidence = tuple(cost_range.evidence) + ((Ref("contract", records.contract.id),) if records.contract else ())
        flags.append(Flag("pricing_scope_problem", "Pricing/scope problem", "Send to renewal review", reasons, evidence))

    gaps = missing_evidence(records, month)
    reasons = [r for f in flags for r in f.reasons] + [g.message for g in gaps]
    if not flags and not gaps:
        reasons.append("No delivery or pricing/scope problem found from the recorded evidence.")
    return DiagnosisResult(
        reasons=reasons,
        evidence=[r for f in flags for r in f.evidence],
        actual_cleaning_cost=actual,
        flags=flags,
        missing_evidence=gaps,
    )
