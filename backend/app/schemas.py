"""Pydantic request/response models. Responses validate straight from the rule dataclasses
(`from_attributes`), so every money value is a {amount, kind} pair."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Kind = Literal["estimated", "quoted", "actual"]
PlanType = Literal["current", "operational_fix", "vendor_offer", "vendor_bundle"]
ActionType = Literal["current", "operational_fix", "vendor_offer", "vendor_bundle", "renewal_review"]


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
    revenue: MoneyOut
    direct_costs: MoneyOut
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


class BundleSiteOut(Out):
    location_id: int
    location_name: str
    lat: float
    lng: float
    is_this_location: bool
    fits: bool
    required_minutes: float
    window_minutes: int | None
    current_contribution: MoneyOut
    projected_contribution: MoneyOut
    change: MoneyOut


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
    monthly_cost: MoneyOut
    bonus: MoneyOut
    transition_monthly: MoneyOut
    transition_one_time: MoneyOut
    projected_contribution: MoneyOut
    current_contribution: MoneyOut
    change: MoneyOut
    offer_id: int | None
    fix_id: int | None
    feasibility: FeasibilityOut | None
    sites: list[BundleSiteOut]
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


# ---------------------------------------------------------------- renewal review


class SuggestionOut(Out):
    key: str
    text: str


class RenewalItemOut(Out):
    location_id: int
    location_name: str
    contract_id: int
    renewal_date: date
    days_to_renewal: int
    revenue: MoneyOut
    estimate_low: MoneyOut | None
    estimate_high: MoneyOut | None
    actual_cost: MoneyOut | None
    cost_basis: MoneyOut
    monthly_gap: MoneyOut
    suggested_price: MoneyOut
    projected_contribution: MoneyOut
    target_margin: float
    current_frequency_per_week: int
    suggested_frequency_per_week: int | None
    triggers: list[str]
    suggestions: list[SuggestionOut]
    reasons: list[str]
    evidence: list[RefOut]


class RenewalQueueOut(Out):
    as_of: date
    target_margin: float
    items: list[RenewalItemOut]


# ---------------------------------------------------------------- vendor incentives


class TargetsOut(Out):
    completion_min: float
    inspection_avg_min: float
    fix_within_24h_min: float


class InspectionOut(Out):
    id: int
    date: date
    score: float


class IssueOut(Out):
    id: int
    date: date
    category: str
    description: str
    customer_caused: bool
    resolved_hours: float | None
    visit_id: int | None


class VendorLocationOut(Out):
    location_id: int
    code: str
    name: str
    city: str
    state: str
    incentive: IncentiveOut
    contribution_before_bonus: MoneyOut
    contribution: MoneyOut  # after bonus
    inspections: list[InspectionOut]
    issues: list[IssueOut]


class VendorExceptionOut(Out):
    location_id: int
    location_name: str
    ref: RefOut
    reason: str


class VendorIncentiveOut(Out):
    vendor_id: int
    vendor_name: str
    has_program: bool
    bonus_rate: float | None
    bonus_cap: MoneyOut | None
    targets: TargetsOut | None
    locations: list[VendorLocationOut]
    total_bonus: MoneyOut
    total_contribution: MoneyOut
    exceptions: list[VendorExceptionOut]


class VendorIncentivesOut(Out):
    month: str
    vendors: list[VendorIncentiveOut]


class SimulateIn(BaseModel):
    """One changed service result: an inspection's score, or an issue's customer-caused flag."""

    model_config = ConfigDict(extra="forbid")

    inspection_id: int | None = None
    score: float | None = Field(None, ge=0, le=100)
    issue_id: int | None = None
    customer_caused: bool | None = None

    @model_validator(mode="after")
    def _exactly_one_change(self):
        inspection = (self.inspection_id is not None, self.score is not None)
        issue = (self.issue_id is not None, self.customer_caused is not None)
        if inspection[0] != inspection[1]:
            raise ValueError("inspection_id and score go together")
        if issue[0] != issue[1]:
            raise ValueError("issue_id and customer_caused go together")
        if inspection[0] == issue[0]:
            raise ValueError("change exactly one service result: an inspection score or an issue's customer_caused flag")
        return self


class SimulationOut(Out):
    vendor_id: int
    vendor_name: str
    location_id: int
    location_name: str
    changes: list[str]
    recorded: VendorLocationOut
    simulated: VendorLocationOut
    eligibility_changed: bool
    contribution_change: MoneyOut


# ---------------------------------------------------------------- proposed actions


class ActionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    location_id: int
    plan_type: ActionType
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
