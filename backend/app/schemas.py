"""Pydantic request/response models. Responses validate straight from the rule dataclasses
(`from_attributes`), so every money value is a {amount, kind} pair."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Kind = Literal["estimated", "quoted", "actual"]
PlanType = Literal["current", "operational_fix", "vendor_offer", "vendor_bundle"]


class Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class MoneyOut(Out):
    amount: float
    kind: Kind


class RefOut(Out):
    type: str
    id: int


class LineOut(Out):
    key: str
    label: str
    money: MoneyOut
    evidence: list[RefOut]


class AssumptionOut(Out):
    key: str
    label: str
    value: float
    unit: str
    source: str


class EvidenceItemOut(Out):
    type: str
    id: int
    date: date | None
    summary: str
    money: MoneyOut | None


class ContributionOut(Out):
    revenue: MoneyOut
    lines: list[LineOut]
    total: MoneyOut
    reasons: list[str]


class CostRangeOut(Out):
    available: bool
    crew_minutes_per_visit: float
    visits_per_month: float
    labor: MoneyOut
    travel: MoneyOut
    supplies: MoneyOut
    base: MoneyOut
    low: MoneyOut
    high: MoneyOut
    assumptions: list[AssumptionOut]
    missing: list[str]
    reasons: list[str]
    evidence: list[RefOut]


# ---------------------------------------------------------------- overview


class TotalsOut(Out):
    sites: int
    detailed_sites: int
    loss_making: int
    revenue: MoneyOut
    direct_costs: MoneyOut
    contribution: MoneyOut


class SiteOut(Out):
    id: int
    code: str
    name: str
    city: str
    state: str
    lat: float
    lng: float
    detailed: bool
    contribution: MoneyOut


class OverviewOut(Out):
    totals: TotalsOut
    states: list[str]
    sites: list[SiteOut]


# ---------------------------------------------------------------- location details


class LocationOut(Out):
    id: int
    code: str
    name: str
    city: str
    state: str
    lat: float
    lng: float
    customer_account: str
    building_type: str | None
    sq_ft: int | None
    restrooms: int | None
    floors: int | None
    current_vendor_id: int | None
    current_vendor_name: str | None


class ContractOut(Out):
    id: int
    price_monthly: MoneyOut
    scope: list[str]
    frequency_per_week: int
    start_date: date
    renewal_date: date
    days_to_renewal: int


class TaskOut(Out):
    id: int
    task: str
    minutes: float


class ServiceRequirementsOut(Out):
    window_start: str | None
    window_end: str | None
    window_minutes: int | None
    frequency_per_week: int | None
    current_crew_size: int | None
    tasks: list[TaskOut]
    crew_minutes_per_visit: float


class FlagOut(Out):
    key: str
    label: str
    action: str
    reasons: list[str]
    evidence: list[EvidenceItemOut]


class DiagnosisOut(Out):
    flags: list[FlagOut]
    reasons: list[str]


class MissingEvidenceOut(Out):
    key: str
    message: str


class TargetCheckOut(Out):
    key: str
    label: str
    target: float
    actual: float | None
    met: bool
    detail: str
    evidence: list[RefOut]


class ExceptionOut(Out):
    ref: RefOut
    reason: str


class IncentiveOut(Out):
    vendor_id: int
    has_program: bool
    eligible: bool
    invoice_basis: MoneyOut
    bonus: MoneyOut
    checks: list[TargetCheckOut]
    exceptions: list[ExceptionOut]
    reasons: list[str]


class LocationDetailOut(Out):
    location: LocationOut
    contract: ContractOut | None
    service_requirements: ServiceRequirementsOut
    month: str
    as_of: date
    contribution: ContributionOut
    reasonable_cost: CostRangeOut
    actual_cleaning_cost: MoneyOut
    diagnosis: DiagnosisOut
    missing_evidence: list[MissingEvidenceOut]
    incentive: IncentiveOut


# ---------------------------------------------------------------- plans


class PlanOverridesIn(BaseModel):
    """Optional assumption overrides. Ratios are 0–1 (the UI shows them as %)."""

    model_config = ConfigDict(extra="forbid")

    local_loaded_wage: float | None = Field(None, gt=0)
    margin_low: float | None = Field(None, ge=0, le=1)
    margin_high: float | None = Field(None, ge=0, le=1)
    return_visit_reduction: float | None = Field(None, ge=0, le=1)
    amortization_months: float | None = Field(None, ge=1)

    @model_validator(mode="after")
    def _margin_band(self):
        if self.margin_low is not None and self.margin_high is not None and self.margin_low > self.margin_high:
            raise ValueError("margin_low must not exceed margin_high")
        return self


class SiteCheckOut(Out):
    location_id: int
    location_name: str
    cleaning_minutes: float
    travel_minutes: float
    required_minutes: float
    window_minutes: int | None
    fits: bool
    sentence: str


class FeasibilityOut(Out):
    feasible: bool
    capacity_ok: bool
    total_crew_minutes: float
    capacity_minutes: float
    site_checks: list[SiteCheckOut]
    reasons: list[str]


class PlanOut(Out):
    plan_type: PlanType
    name: str
    location_id: int
    vendor_id: int | None
    vendor_name: str | None
    vendor_change: bool
    feasible: bool
    recommended: bool
    revenue: MoneyOut
    lines: list[LineOut]
    projected_contribution: MoneyOut
    current_contribution: MoneyOut
    change: MoneyOut
    offer_id: int | None
    fix_id: int | None
    feasibility: FeasibilityOut | None
    reasons: list[str]
    evidence: list[RefOut]


class RecommendedOut(Out):
    plan_type: PlanType
    name: str
    offer_id: int | None
    fix_id: int | None


class PlanComparisonOut(Out):
    location_id: int
    assumptions: list[AssumptionOut]
    reasonable_cost: CostRangeOut
    current: PlanOut
    options: list[PlanOut]
    recommended: RecommendedOut | None
    recommendation_reasons: list[str]


# ---------------------------------------------------------------- proposed actions


class ActionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    location_id: int
    plan_type: PlanType
    offer_id: int | None = None
    fix_id: int | None = None
    overrides: PlanOverridesIn | None = None
    note: str | None = Field(None, max_length=2000)


class ActionOut(Out):
    id: int
    location_id: int
    location_name: str
    plan_type: str
    summary: str
    projected_contribution: MoneyOut
    status: str
    created_at: datetime
    note: str | None
    offer_id: int | None
    fix_id: int | None
    overrides: dict[str, float] | None


class ResetOut(BaseModel):
    status: str
    vendors: int
    detailed_locations: int
    locations: int
