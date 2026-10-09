"""Turn ORM rows into the plain dataclasses the rules take. The only DB-aware glue."""

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models as m
from app.rules.types import (
    ContractInfo,
    CostLine,
    Fix,
    InspectionRec,
    InvoiceLine,
    Issue,
    LocationRecords,
    Offer,
    Settings,
    Site,
    Targets,
    Task,
    VendorInfo,
    Visit,
)


def load_assumptions(db: Session) -> dict[str, m.Assumption]:
    return {a.key: a for a in db.scalars(select(m.Assumption))}


def load_settings(db: Session) -> Settings:
    a = load_assumptions(db)
    defaults = Settings()
    keys = ("margin_low", "margin_high", "weeks_per_month", "target_margin", "amortization_months",
            "road_factor", "travel_speed_mph")
    return Settings(**{k: a[k].value if k in a else getattr(defaults, k) for k in keys})


def load_as_of(db: Session) -> tuple[date, str]:
    a = load_assumptions(db)
    return date.fromisoformat(a["as_of"].text_value), a["evaluation_month"].text_value


def vendor_info(v: m.Vendor) -> VendorInfo:
    return VendorInfo(v.id, v.name, v.crews_available, v.shift_minutes, v.bonus_rate, v.bonus_cap)


def load_vendors(db: Session) -> dict[int, VendorInfo]:
    return {v.id: vendor_info(v) for v in db.scalars(select(m.Vendor))}


def load_targets(db: Session) -> dict[int, Targets]:
    return {
        t.vendor_id: Targets(t.completion_min, t.inspection_avg_min, t.fix_within_24h_min)
        for t in db.scalars(select(m.PerformanceTarget))
    }


def site_from(loc: m.Location) -> Site:
    return Site(
        id=loc.id, code=loc.code, name=loc.name, city=loc.city, state=loc.state, lat=loc.lat, lng=loc.lng,
        revenue_monthly=loc.revenue_monthly, window_start=loc.service_window_start,
        window_end=loc.service_window_end, frequency_per_week=loc.frequency_per_week,
        local_loaded_wage=loc.local_loaded_wage, travel_minutes_per_visit=loc.travel_minutes_per_visit,
        supplies_per_visit=loc.supplies_per_visit, building_type=loc.building_type,
        current_vendor_id=loc.current_vendor_id, current_crew_size=loc.current_crew_size,
    )


def location_by_code(db: Session, code: str) -> m.Location:
    return db.scalars(select(m.Location).where(m.Location.code == code)).one()


def detailed_sites(db: Session) -> list[Site]:
    return [site_from(l) for l in db.scalars(select(m.Location).where(m.Location.detailed).order_by(m.Location.id))]


def _rows(db: Session, model, location_id: int):
    return db.scalars(select(model).where(model.location_id == location_id).order_by(model.id))


def load_records(db: Session, location_id: int) -> LocationRecords:
    loc = db.get(m.Location, location_id)
    c = loc.contract
    return LocationRecords(
        site=site_from(loc),
        contract=ContractInfo(c.id, c.location_id, c.price_monthly, tuple(c.scope), c.frequency_per_week,
                              c.start_date, c.renewal_date) if c else None,
        invoices=tuple(InvoiceLine(i.id, i.vendor_id, i.month, i.amount, i.line_type, i.kind, i.description)
                       for i in _rows(db, m.Invoice, location_id)),
        costs=tuple(CostLine(c.id, c.month, c.type, c.amount, c.kind, c.description)
                    for c in _rows(db, m.CostItem, location_id)),
        visits=tuple(Visit(v.id, v.date, v.completed, v.return_visit) for v in _rows(db, m.ServiceVisit, location_id)),
        issues=tuple(Issue(i.id, i.date, i.category, i.description, i.customer_caused, i.resolved_hours, i.visit_id)
                     for i in _rows(db, m.IssueRecord, location_id)),
        inspections=tuple(InspectionRec(i.id, i.date, i.score) for i in _rows(db, m.Inspection, location_id)),
        tasks=tuple(Task(t.id, t.task, t.minutes) for t in _rows(db, m.SiteTask, location_id)),
    )


def load_offers_for(db: Session, location_id: int) -> list[Offer]:
    return [
        Offer(o.id, o.vendor_id, tuple(o.location_ids), o.monthly_price, o.crew_size, o.minutes_per_site,
              o.transition_cost_one_time, o.description)
        for o in db.scalars(select(m.VendorOffer).order_by(m.VendorOffer.id))
        if location_id in o.location_ids
    ]


def load_fixes_for(db: Session, location_id: int) -> list[Fix]:
    return [
        Fix(f.id, f.location_id, f.name, f.description, f.issue_category, f.one_time_cost, f.return_visit_reduction)
        for f in _rows(db, m.OperationalFix, location_id)
    ]
