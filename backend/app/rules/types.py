"""Plain data passed into and out of the business rules. No ORM objects here."""

from dataclasses import dataclass, field
from datetime import date
from typing import Literal

Kind = Literal["estimated", "quoted", "actual"]

# Least certain kind wins when amounts of different kinds are combined.
_KIND_ORDER: dict[str, int] = {"actual": 0, "quoted": 1, "estimated": 2}


def combine_kinds(*kinds: Kind) -> Kind:
    return max(kinds, key=lambda k: _KIND_ORDER[k]) if kinds else "actual"


@dataclass(frozen=True)
class Ref:
    """Pointer to an evidence record, e.g. Ref("issue", 12)."""

    type: str
    id: int


@dataclass(frozen=True)
class Money:
    amount: float
    kind: Kind


@dataclass(frozen=True)
class AssumptionUsed:
    key: str
    label: str
    value: float
    unit: str
    source: str  # e.g. "location record", "global assumption", "site profile"


# ---------------------------------------------------------------- inputs


@dataclass(frozen=True)
class Settings:
    margin_low: float = 0.15
    margin_high: float = 0.25
    weeks_per_month: float = 4.33
    target_margin: float = 0.10
    amortization_months: float = 12
    road_factor: float = 1.3
    travel_speed_mph: float = 25.0


@dataclass(frozen=True)
class Overrides:
    """Manager-edited assumptions for a plan comparison; None keeps the stored value."""

    local_loaded_wage: float | None = None
    margin_low: float | None = None
    margin_high: float | None = None
    return_visit_reduction: float | None = None  # 0..1
    amortization_months: float | None = None


@dataclass(frozen=True)
class VendorInfo:
    id: int
    name: str
    crews_available: int
    shift_minutes: int
    bonus_rate: float | None = None
    bonus_cap: float | None = None

    @property
    def has_bonus_program(self) -> bool:
        return bool(self.bonus_rate) and self.bonus_cap is not None


@dataclass(frozen=True)
class Targets:
    completion_min: float  # percent
    inspection_avg_min: float  # score
    fix_within_24h_min: float  # percent


@dataclass(frozen=True)
class Site:
    id: int
    code: str
    name: str
    city: str
    state: str
    lat: float
    lng: float
    revenue_monthly: float
    window_start: str | None = None
    window_end: str | None = None
    frequency_per_week: int | None = None
    local_loaded_wage: float | None = None
    travel_minutes_per_visit: float | None = None
    supplies_per_visit: float | None = None
    building_type: str | None = None
    current_vendor_id: int | None = None
    current_crew_size: int | None = None


@dataclass(frozen=True)
class ContractInfo:
    id: int
    location_id: int
    price_monthly: float
    scope: tuple[str, ...]
    frequency_per_week: int
    start_date: date
    renewal_date: date


@dataclass(frozen=True)
class InvoiceLine:
    id: int
    vendor_id: int
    month: str
    amount: float
    line_type: str  # base | return_visit | extra
    kind: Kind = "actual"
    description: str | None = None


@dataclass(frozen=True)
class CostLine:
    id: int
    month: str
    type: str  # credit | other_direct | bonus
    amount: float
    kind: Kind = "actual"
    description: str | None = None


@dataclass(frozen=True)
class Visit:
    id: int
    date: date
    completed: bool
    return_visit: bool


@dataclass(frozen=True)
class Issue:
    id: int
    date: date
    category: str
    description: str
    customer_caused: bool
    resolved_hours: float | None
    visit_id: int | None = None


@dataclass(frozen=True)
class InspectionRec:
    id: int
    date: date
    score: float


@dataclass(frozen=True)
class Task:
    id: int
    task: str
    minutes: float


@dataclass(frozen=True)
class Offer:
    id: int
    vendor_id: int
    location_ids: tuple[int, ...]  # route order
    monthly_price: float
    crew_size: int
    minutes_per_site: float
    transition_cost_one_time: float
    description: str | None = None


@dataclass(frozen=True)
class Fix:
    id: int
    location_id: int
    name: str
    description: str
    issue_category: str
    one_time_cost: float
    return_visit_reduction: float


@dataclass(frozen=True)
class LocationRecords:
    """Everything recorded for one detailed location."""

    site: Site
    contract: ContractInfo | None = None
    invoices: tuple[InvoiceLine, ...] = ()
    costs: tuple[CostLine, ...] = ()
    visits: tuple[Visit, ...] = ()
    issues: tuple[Issue, ...] = ()
    inspections: tuple[InspectionRec, ...] = ()
    tasks: tuple[Task, ...] = ()


# ---------------------------------------------------------------- outputs


@dataclass(frozen=True)
class Line:
    """One labeled amount in a waterfall or projection breakdown."""

    key: str
    label: str
    money: Money
    evidence: tuple[Ref, ...] = ()


@dataclass
class RuleResult:
    reasons: list[str] = field(default_factory=list)
    evidence: list[Ref] = field(default_factory=list)


def month_of(d: date) -> str:
    return f"{d.year:04d}-{d.month:02d}"


def usd(amount: float) -> str:
    """Format for reason sentences: $1,234 or $67.50."""
    sign = "−" if amount < 0 else ""
    a = abs(amount)
    if abs(a - round(a)) < 0.005:
        return f"{sign}${a:,.0f}"
    return f"{sign}${a:,.2f}"
