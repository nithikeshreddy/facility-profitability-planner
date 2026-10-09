"""SQLAlchemy models (docs/SPEC.md section 5).

Additions beyond the spec's minimum are marked "addition" and exist so every demo
number can be computed from stored records instead of hardcoded.
"""

from datetime import date, datetime

from sqlalchemy import JSON, CheckConstraint, Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

MONEY_KINDS = ("estimated", "quoted", "actual")


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


class Vendor(Base):
    __tablename__ = "vendors"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    home_lat: Mapped[float] = mapped_column(Float)
    home_lng: Mapped[float] = mapped_column(Float)
    crews_available: Mapped[int] = mapped_column(Integer)
    shift_minutes: Mapped[int] = mapped_column(Integer)
    # Null means the vendor has no bonus program.
    bonus_rate: Mapped[float | None] = mapped_column(Float)
    bonus_cap: Mapped[float | None] = mapped_column(Float)

    target: Mapped["PerformanceTarget | None"] = relationship(back_populates="vendor")


class Location(Base):
    __tablename__ = "locations"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True)  # addition: stable lookup key
    name: Mapped[str] = mapped_column(String(160))
    city: Mapped[str] = mapped_column(String(80))
    state: Mapped[str] = mapped_column(String(2))
    lat: Mapped[float] = mapped_column(Float)
    lng: Mapped[float] = mapped_column(Float)
    detailed: Mapped[bool] = mapped_column(default=False)
    customer_account: Mapped[str] = mapped_column(String(120))
    revenue_monthly: Mapped[float] = mapped_column(Float)
    # addition: lightweight sites only carry a summary cost; detailed sites use invoices.
    actual_cost_monthly: Mapped[float | None] = mapped_column(Float)
    sq_ft: Mapped[int | None] = mapped_column(Integer)
    restrooms: Mapped[int | None] = mapped_column(Integer)
    floors: Mapped[int | None] = mapped_column(Integer)
    building_type: Mapped[str | None] = mapped_column(String(40))
    service_window_start: Mapped[str | None] = mapped_column(String(5))  # "HH:MM"
    service_window_end: Mapped[str | None] = mapped_column(String(5))  # may cross midnight
    frequency_per_week: Mapped[int | None] = mapped_column(Integer)
    current_vendor_id: Mapped[int | None] = mapped_column(ForeignKey("vendors.id"))
    local_loaded_wage: Mapped[float | None] = mapped_column(Float)
    # additions: stored reasonable-cost assumptions and the current crew size
    travel_minutes_per_visit: Mapped[float | None] = mapped_column(Float)
    supplies_per_visit: Mapped[float | None] = mapped_column(Float)
    current_crew_size: Mapped[int | None] = mapped_column(Integer)

    current_vendor: Mapped[Vendor | None] = relationship()
    contract: Mapped["Contract | None"] = relationship(back_populates="location")


class SiteTask(Base):
    """addition: the site profile's task list; Σ minutes = crew minutes per visit."""

    __tablename__ = "site_tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    location_id: Mapped[int] = mapped_column(ForeignKey("locations.id"), index=True)
    task: Mapped[str] = mapped_column(String(120))
    minutes: Mapped[float] = mapped_column(Float)


class Contract(Base):
    __tablename__ = "contracts"

    id: Mapped[int] = mapped_column(primary_key=True)
    location_id: Mapped[int] = mapped_column(ForeignKey("locations.id"), unique=True)
    price_monthly: Mapped[float] = mapped_column(Float)
    scope: Mapped[list[str]] = mapped_column(JSON)
    frequency_per_week: Mapped[int] = mapped_column(Integer)
    start_date: Mapped[date] = mapped_column(Date)
    renewal_date: Mapped[date] = mapped_column(Date)

    location: Mapped[Location] = relationship(back_populates="contract")


class Invoice(Base):
    __tablename__ = "invoices"
    __table_args__ = (
        CheckConstraint(_in("kind", MONEY_KINDS)),
        CheckConstraint(_in("line_type", ("base", "return_visit", "extra"))),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    location_id: Mapped[int] = mapped_column(ForeignKey("locations.id"), index=True)
    vendor_id: Mapped[int] = mapped_column(ForeignKey("vendors.id"))
    month: Mapped[str] = mapped_column(String(7))  # "YYYY-MM"
    amount: Mapped[float] = mapped_column(Float)
    kind: Mapped[str] = mapped_column(String(10), default="actual")
    line_type: Mapped[str] = mapped_column(String(20))
    description: Mapped[str | None] = mapped_column(Text)  # addition
    service_visit_id: Mapped[int | None] = mapped_column(ForeignKey("service_visits.id"))  # addition


class CostItem(Base):
    __tablename__ = "cost_items"
    __table_args__ = (
        CheckConstraint(_in("kind", MONEY_KINDS)),
        CheckConstraint(_in("type", ("credit", "other_direct", "bonus"))),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    location_id: Mapped[int] = mapped_column(ForeignKey("locations.id"), index=True)
    month: Mapped[str] = mapped_column(String(7))
    type: Mapped[str] = mapped_column(String(20))
    amount: Mapped[float] = mapped_column(Float)
    kind: Mapped[str] = mapped_column(String(10), default="actual")
    description: Mapped[str | None] = mapped_column(Text)  # addition


class ServiceVisit(Base):
    __tablename__ = "service_visits"

    id: Mapped[int] = mapped_column(primary_key=True)
    location_id: Mapped[int] = mapped_column(ForeignKey("locations.id"), index=True)
    vendor_id: Mapped[int | None] = mapped_column(ForeignKey("vendors.id"))  # addition
    date: Mapped[date] = mapped_column(Date)
    checkin: Mapped[datetime | None] = mapped_column(DateTime)
    checkout: Mapped[datetime | None] = mapped_column(DateTime)
    completed: Mapped[bool] = mapped_column(default=True)
    return_visit: Mapped[bool] = mapped_column(default=False)


class IssueRecord(Base):
    __tablename__ = "issue_records"
    __table_args__ = (CheckConstraint(_in("category", ("access", "quality", "scope", "missed"))),)

    id: Mapped[int] = mapped_column(primary_key=True)
    location_id: Mapped[int] = mapped_column(ForeignKey("locations.id"), index=True)
    # addition: links a failed visit to the issue that explains it
    visit_id: Mapped[int | None] = mapped_column(ForeignKey("service_visits.id"))
    date: Mapped[date] = mapped_column(Date)
    category: Mapped[str] = mapped_column(String(20))
    description: Mapped[str] = mapped_column(Text)
    customer_caused: Mapped[bool] = mapped_column(default=False)
    resolved_hours: Mapped[float | None] = mapped_column(Float)  # null = unresolved


class Inspection(Base):
    __tablename__ = "inspections"

    id: Mapped[int] = mapped_column(primary_key=True)
    location_id: Mapped[int] = mapped_column(ForeignKey("locations.id"), index=True)
    date: Mapped[date] = mapped_column(Date)
    score: Mapped[float] = mapped_column(Float)


class VendorOffer(Base):
    __tablename__ = "vendor_offers"
    __table_args__ = (CheckConstraint(_in("kind", MONEY_KINDS)),)

    id: Mapped[int] = mapped_column(primary_key=True)
    vendor_id: Mapped[int] = mapped_column(ForeignKey("vendors.id"))
    location_ids: Mapped[list[int]] = mapped_column(JSON)  # route order
    monthly_price: Mapped[float] = mapped_column(Float)
    kind: Mapped[str] = mapped_column(String(10), default="quoted")
    crew_size: Mapped[int] = mapped_column(Integer)
    minutes_per_site: Mapped[float] = mapped_column(Float)  # crew-minutes of cleaning per site
    transition_cost_one_time: Mapped[float] = mapped_column(Float, default=0.0)
    description: Mapped[str | None] = mapped_column(Text)  # addition


class OperationalFix(Base):
    """addition: a candidate fix that changes how work is delivered, without a vendor change."""

    __tablename__ = "operational_fixes"
    __table_args__ = (CheckConstraint(_in("kind", MONEY_KINDS)),)

    id: Mapped[int] = mapped_column(primary_key=True)
    location_id: Mapped[int] = mapped_column(ForeignKey("locations.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text)
    issue_category: Mapped[str] = mapped_column(String(20))  # issues this fix addresses
    one_time_cost: Mapped[float] = mapped_column(Float)
    return_visit_reduction: Mapped[float] = mapped_column(Float)  # 0..1
    kind: Mapped[str] = mapped_column(String(10), default="estimated")


class PerformanceTarget(Base):
    __tablename__ = "performance_targets"

    id: Mapped[int] = mapped_column(primary_key=True)
    vendor_id: Mapped[int] = mapped_column(ForeignKey("vendors.id"), unique=True)
    completion_min: Mapped[float] = mapped_column(Float)  # percent
    inspection_avg_min: Mapped[float] = mapped_column(Float)  # score 0-100
    fix_within_24h_min: Mapped[float] = mapped_column(Float)  # percent

    vendor: Mapped[Vendor] = relationship(back_populates="target")


class ProposedAction(Base):
    __tablename__ = "proposed_actions"
    __table_args__ = (CheckConstraint(_in("projected_kind", MONEY_KINDS)),)

    id: Mapped[int] = mapped_column(primary_key=True)
    location_id: Mapped[int] = mapped_column(ForeignKey("locations.id"), index=True)
    plan_type: Mapped[str] = mapped_column(String(40))
    summary: Mapped[str] = mapped_column(Text)
    projected_contribution: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(20), default="proposed")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    note: Mapped[str | None] = mapped_column(Text)
    # additions: what the projection was computed from, so a saved action can be traced and re-run
    projected_kind: Mapped[str] = mapped_column(String(10), default="estimated")
    offer_id: Mapped[int | None] = mapped_column(ForeignKey("vendor_offers.id"))
    fix_id: Mapped[int | None] = mapped_column(ForeignKey("operational_fixes.id"))
    overrides: Mapped[dict | None] = mapped_column(JSON)  # assumption overrides used

    location: Mapped[Location] = relationship()


class Assumption(Base):
    """addition: global labeled assumptions (margin band, weeks per month, as-of date, ...)."""

    __tablename__ = "assumptions"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(60), unique=True)
    label: Mapped[str] = mapped_column(String(160))
    value: Mapped[float | None] = mapped_column(Float)
    text_value: Mapped[str | None] = mapped_column(String(60))
    unit: Mapped[str | None] = mapped_column(String(30))
