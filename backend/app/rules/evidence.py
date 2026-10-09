"""Turn evidence pointers (Ref) into readable records for the UI."""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date

from app.rules.types import LocationRecords, Money, Ref, usd

LINE_TYPE_LABELS = {"base": "Base", "extra": "Extra", "return_visit": "Return visit"}


@dataclass(frozen=True)
class EvidenceItem:
    type: str
    id: int
    date: date | None
    summary: str
    money: Money | None = None


def _describe_one(ref: Ref, r: LocationRecords) -> EvidenceItem:
    def find(rows):
        return next((x for x in rows if x.id == ref.id), None)

    if ref.type == "invoice" and (i := find(r.invoices)):
        label = LINE_TYPE_LABELS.get(i.line_type, i.line_type)
        return EvidenceItem(ref.type, ref.id, None, f"{label} invoice line, {i.month}: {i.description or i.line_type}",
                            Money(i.amount, i.kind))
    if ref.type == "cost_item" and (c := find(r.costs)):
        return EvidenceItem(ref.type, ref.id, None, f"{c.type.replace('_', ' ').capitalize()}, {c.month}: "
                            f"{c.description or c.type}", Money(c.amount, c.kind))
    if ref.type == "issue" and (i := find(r.issues)):
        resolved = f"resolved in {i.resolved_hours:g}h" if i.resolved_hours is not None else "unresolved"
        caused = "customer-caused" if i.customer_caused else "vendor-caused"
        return EvidenceItem(ref.type, ref.id, i.date, f"{i.category.capitalize()} issue: {i.description} ({caused}, {resolved})")
    if ref.type == "service_visit" and (v := find(r.visits)):
        kind = "Return visit" if v.return_visit else "Scheduled visit"
        return EvidenceItem(ref.type, ref.id, v.date, f"{kind}, {'completed' if v.completed else 'not completed'}")
    if ref.type == "inspection" and (i := find(r.inspections)):
        return EvidenceItem(ref.type, ref.id, i.date, f"Inspection score {i.score:g}")
    if ref.type == "site_task" and (t := find(r.tasks)):
        return EvidenceItem(ref.type, ref.id, None, f"Site task: {t.task}, {t.minutes:g} crew minutes per visit")
    if ref.type == "contract" and r.contract and r.contract.id == ref.id:
        c = r.contract
        return EvidenceItem(ref.type, ref.id, None, f"Contract: {usd(c.price_monthly)}/month, {c.frequency_per_week} "
                            f"visits/week, renews {c.renewal_date.isoformat()}", Money(c.price_monthly, "actual"))
    if ref.type == "location" and r.site.id == ref.id:
        return EvidenceItem(ref.type, ref.id, None, f"Location: {r.site.name}")
    return EvidenceItem(ref.type, ref.id, None, f"{ref.type.replace('_', ' ').capitalize()} #{ref.id}")


def describe(refs: Iterable[Ref], records: LocationRecords) -> list[EvidenceItem]:
    """Readable records for `refs`, in order, without duplicates."""
    seen: set[Ref] = set()
    out = []
    for ref in refs:
        if ref not in seen:
            seen.add(ref)
            out.append(_describe_one(ref, records))
    return out
