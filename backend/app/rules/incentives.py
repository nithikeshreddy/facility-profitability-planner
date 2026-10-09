"""Vendor bonus eligibility and cost.

bonus = min(bonus_rate × monthly invoice, cap), only when ALL targets are met.
Failures marked customer-caused are excluded from the calculation and listed for
exception review. A target with no evidence makes the vendor ineligible ("Evidence missing").
`apply_change` swaps one recorded service result for a what-if simulation; nothing is stored.
"""

from collections.abc import Iterable
from dataclasses import dataclass, field, replace

from app.rules.types import (
    InspectionRec,
    InvoiceLine,
    Issue,
    LocationRecords,
    Money,
    Ref,
    RuleResult,
    Targets,
    VendorInfo,
    Visit,
    month_of,
    usd,
)


@dataclass(frozen=True)
class TargetCheck:
    key: str  # completion | inspection_avg | fix_within_24h
    label: str
    target: float
    actual: float | None  # None = evidence missing
    met: bool
    detail: str
    evidence: tuple[Ref, ...]


@dataclass(frozen=True)
class ExceptionItem:
    ref: Ref
    reason: str


@dataclass
class IncentiveResult(RuleResult):
    vendor_id: int = 0
    has_program: bool = False
    eligible: bool = False
    invoice_basis: Money = Money(0.0, "actual")
    bonus: Money = Money(0.0, "estimated")
    checks: list[TargetCheck] = field(default_factory=list)
    exceptions: list[ExceptionItem] = field(default_factory=list)


def evaluate_incentive(
    vendor: VendorInfo,
    targets: Targets | None,
    invoices: Iterable[InvoiceLine],
    visits: Iterable[Visit],
    issues: Iterable[Issue],
    inspections: Iterable[InspectionRec],
    month: str,
) -> IncentiveResult:
    if not vendor.has_bonus_program:
        return IncentiveResult(
            reasons=[f"{vendor.name} has no bonus program."], vendor_id=vendor.id, has_program=False
        )

    inv = [i for i in invoices if i.month == month and i.vendor_id == vendor.id and i.line_type in ("base", "extra")]
    basis = round(sum(i.amount for i in inv), 2)
    if targets is None:
        return IncentiveResult(
            reasons=["Evidence missing: no performance targets recorded for this vendor."],
            vendor_id=vendor.id,
            has_program=True,
            invoice_basis=Money(basis, "actual"),
        )

    vis = [v for v in visits if month_of(v.date) == month and not v.return_visit]
    iss = [i for i in issues if month_of(i.date) == month]
    insp = [i for i in inspections if month_of(i.date) == month]

    exceptions: list[ExceptionItem] = []
    customer_issue_by_visit = {i.visit_id: i for i in iss if i.customer_caused and i.visit_id is not None}

    # Completion: incomplete visits explained by a customer-caused issue are excluded.
    counted, excluded = [], []
    for v in vis:
        if not v.completed and v.id in customer_issue_by_visit:
            excluded.append(v)
            exceptions.append(
                ExceptionItem(
                    Ref("service_visit", v.id),
                    f"Visit on {v.date.isoformat()} not completed — customer-caused "
                    f"({customer_issue_by_visit[v.id].description}); excluded from completion rate.",
                )
            )
        else:
            counted.append(v)
    checks: list[TargetCheck] = []
    if counted:
        done = sum(1 for v in counted if v.completed)
        pct = done / len(counted) * 100
        checks.append(
            TargetCheck(
                "completion", "Visits completed", targets.completion_min, round(pct, 2),
                pct >= targets.completion_min,
                f"{done} of {len(counted)} scheduled visits completed ({pct:.1f}%; target ≥ {targets.completion_min:g}%)"
                + (f", {len(excluded)} customer-caused excluded" if excluded else ""),
                tuple(Ref("service_visit", v.id) for v in counted),
            )
        )
    else:
        checks.append(
            TargetCheck("completion", "Visits completed", targets.completion_min, None, False,
                        "Evidence missing: no service visits recorded", ())
        )

    if insp:
        avg = sum(i.score for i in insp) / len(insp)
        checks.append(
            TargetCheck(
                "inspection_avg", "Inspection average", targets.inspection_avg_min, round(avg, 2),
                avg >= targets.inspection_avg_min,
                f"Average of {len(insp)} inspection(s) is {avg:.1f} (target ≥ {targets.inspection_avg_min:g}); "
                "scores " + ", ".join(f"{i.score:g}" for i in insp),
                tuple(Ref("inspection", i.id) for i in insp),
            )
        )
    else:
        checks.append(
            TargetCheck("inspection_avg", "Inspection average", targets.inspection_avg_min, None, False,
                        "Evidence missing: no inspections recorded", ())
        )

    vendor_issues = []
    for i in iss:
        if i.customer_caused:
            if i.visit_id not in {v.id for v in excluded}:  # already listed with its visit
                exceptions.append(
                    ExceptionItem(Ref("issue", i.id), f"Issue on {i.date.isoformat()} marked customer-caused ({i.description}); excluded.")
                )
        else:
            vendor_issues.append(i)
    if vendor_issues:
        fixed = sum(1 for i in vendor_issues if i.resolved_hours is not None and i.resolved_hours <= 24)
        pct = fixed / len(vendor_issues) * 100
        detail = f"{fixed} of {len(vendor_issues)} issues fixed within 24h ({pct:.1f}%; target ≥ {targets.fix_within_24h_min:g}%)"
    else:
        pct = 100.0
        detail = "No vendor-caused issues this month"
    checks.append(
        TargetCheck(
            "fix_within_24h", "Issues fixed within 24h", targets.fix_within_24h_min, round(pct, 2),
            pct >= targets.fix_within_24h_min, detail, tuple(Ref("issue", i.id) for i in vendor_issues),
        )
    )

    eligible = all(c.met for c in checks) and basis > 0
    raw = vendor.bonus_rate * basis
    bonus = round(min(raw, vendor.bonus_cap), 2) if eligible else 0.0

    reasons = [("Met: " if c.met else "Not met: ") + c.detail + "." for c in checks]
    if eligible:
        capped = " (cap reached)" if raw > vendor.bonus_cap else ""
        reasons.append(
            f"All targets met: bonus = min({vendor.bonus_rate:.0%} × {usd(basis)}, {usd(vendor.bonus_cap)} cap) = {usd(bonus)}{capped}."
        )
    else:
        reasons.append(f"Not eligible: {vendor.name} earns no bonus this month.")
    if exceptions:
        reasons.append(f"{len(exceptions)} item(s) excluded and listed for exception review.")

    return IncentiveResult(
        reasons=reasons,
        evidence=[r for c in checks for r in c.evidence] + [Ref("invoice", i.id) for i in inv],
        vendor_id=vendor.id,
        has_program=True,
        eligible=eligible,
        invoice_basis=Money(basis, "actual"),
        bonus=Money(bonus, "estimated"),
        checks=checks,
        exceptions=exceptions,
    )


@dataclass(frozen=True)
class ResultChange:
    """A what-if change to one service result: an inspection score, or an issue's customer-caused flag."""

    inspection_id: int | None = None
    score: float | None = None
    issue_id: int | None = None
    customer_caused: bool | None = None


def _caused_by(customer_caused: bool) -> str:
    return "customer-caused" if customer_caused else "vendor-caused"


def apply_change(records: LocationRecords, change: ResultChange) -> tuple[LocationRecords, list[str]]:
    """Records with the changed service result swapped in, plus a sentence per change. Raises ValueError
    if a changed record is not among this location's records."""
    described = []
    inspections, issues = records.inspections, records.issues
    if change.inspection_id is not None and change.score is not None:
        old = next((i for i in inspections if i.id == change.inspection_id), None)
        if old is None:
            raise ValueError(f"Inspection {change.inspection_id} is not recorded for {records.site.name}.")
        inspections = tuple(replace(i, score=change.score) if i.id == old.id else i for i in inspections)
        described.append(f"Inspection on {old.date.isoformat()}: score {old.score:g} → {change.score:g}.")
    if change.issue_id is not None and change.customer_caused is not None:
        old = next((i for i in issues if i.id == change.issue_id), None)
        if old is None:
            raise ValueError(f"Issue {change.issue_id} is not recorded for {records.site.name}.")
        issues = tuple(replace(i, customer_caused=change.customer_caused) if i.id == old.id else i for i in issues)
        described.append(
            f"Issue on {old.date.isoformat()} ({old.description}): "
            f"{_caused_by(old.customer_caused)} → {_caused_by(change.customer_caused)}."
        )
    return replace(records, inspections=inspections, issues=issues), described
