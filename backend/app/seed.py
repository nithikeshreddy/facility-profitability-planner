"""Deterministic synthetic demonstration data.

    python -m app.seed      # drop, recreate and seed the database at DATABASE_URL

4 vendors, 12 detailed locations (including the five demo cases in docs/SPEC.md
section 6) and lightweight sites across real U.S. metros, 2,000 locations in total.
Every demo outcome is computed by app.rules from these records; nothing here is a result.
"""

import random
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

from app import models as m
from app.db import Base, SessionLocal, engine

SEED = 42
AS_OF = date(2026, 10, 1)
MONTH = "2026-09"
MONTH_DAYS = [date(2026, 9, d) for d in range(1, 31)]
TOTAL_LOCATIONS = 2000
LIGHTWEIGHT_LOSS_SHARE = 0.12

ASSUMPTIONS = [
    # key, label, value, text_value, unit
    ("margin_low", "Reasonable-cost vendor margin, low end", 0.15, None, "ratio"),
    ("margin_high", "Reasonable-cost vendor margin, high end", 0.25, None, "ratio"),
    ("weeks_per_month", "Weeks per month", 4.33, None, "weeks"),
    ("target_margin", "Renewal target margin", 0.10, None, "ratio"),
    ("amortization_months", "Transition cost amortization", 12, None, "months"),
    ("road_factor", "Road distance ÷ straight-line distance", 1.3, None, "ratio"),
    ("travel_speed_mph", "Average night-time travel speed", 25, None, "mph"),
    ("as_of", "Demonstration as-of date", None, AS_OF.isoformat(), "date"),
    ("evaluation_month", "Month evaluated", None, MONTH, "month"),
]

VENDORS = [
    # name, home lat, home lng, crews, shift minutes, bonus rate, bonus cap
    ("Metro Clean Co", 32.7767, -96.7970, 4, 480, None, None),
    ("Budget Shine", 33.7490, -84.3880, 3, 420, None, None),
    ("BrightPath Facility Services", 33.4484, -112.0740, 6, 480, None, None),
    ("Summit Janitorial", 39.7392, -104.9903, 3, 480, 0.05, 75.0),
]
SUMMIT_TARGETS = (98.0, 90.0, 90.0)  # completion %, inspection average, fixed within 24h %

SCOPE_BY_TYPE = {
    "office": ["Empty trash and recycling", "Vacuum carpeted areas", "Clean and restock restrooms", "Dust desks and surfaces", "Mop hard floors"],
    "retail": ["Sweep and mop sales floor", "Clean and restock restrooms", "Clean entrance glass", "Empty trash", "Clean stockroom and break room"],
    "medical": ["Disinfect exam rooms", "Clean and restock restrooms", "Mop hard floors", "Empty trash and sharps-free waste", "Disinfect waiting area"],
    "fitness": ["Disinfect equipment", "Clean locker rooms and showers", "Mop and vacuum floors", "Empty trash", "Clean mirrors and glass"],
    "bank": ["Clean lobby and teller line", "Clean and restock restrooms", "Vacuum offices", "Empty trash", "Clean entrance glass"],
}
# Share of crew minutes per task, used to split each site's profile into tasks.
TASK_SPLIT = [0.35, 0.25, 0.2, 0.2]
TASK_NAMES = ["Floors (vacuum and mop)", "Restrooms", "Trash and recycling", "Dusting and surfaces"]


@dataclass
class DetailedSpec:
    code: str
    name: str
    city: str
    state: str
    lat: float
    lng: float
    account: str
    vendor: str
    revenue: float
    base_invoice: float
    building_type: str
    sq_ft: int
    restrooms: int
    floors: int
    window: tuple[str, str]
    frequency: int
    wage: float
    task_minutes: int  # Σ crew minutes per visit, split into tasks
    travel_minutes: float
    supplies: float
    crew_size: int
    contract_start: date
    renewal: date
    inspections: list[float] = field(default_factory=list)
    extra_lines: list[tuple[float, str]] = field(default_factory=list)
    cost_items: list[tuple[str, float, str]] = field(default_factory=list)  # type, amount, description
    issues: list[tuple[int, str, str, bool, float | None]] = field(default_factory=list)  # day, category, text, customer_caused, hours


DETAILED = [
    # Case 1 — suitable bundle: three Dallas sites within ~2 miles, two current vendors.
    DetailedSpec("DAL-01", "Dallas Uptown Office Suites", "Dallas", "TX", 32.8125, -96.8010, "Fabrikam Offices",
                 "BrightPath Facility Services", 1100, 1250, "office", 9000, 3, 1, ("21:00", "00:00"), 5, 18.0, 95, 35, 2.5, 2,
                 date(2024, 1, 1), date(2027, 1, 31), inspections=[88, 90]),
    DetailedSpec("DAL-02", "Dallas Arts District Office", "Dallas", "TX", 32.7905, -96.8040, "Fabrikam Offices",
                 "BrightPath Facility Services", 1100, 1250, "office", 8800, 3, 1, ("21:00", "00:00"), 5, 18.0, 95, 35, 2.5, 2,
                 date(2024, 1, 1), date(2027, 1, 31), inspections=[89, 91]),
    DetailedSpec("DAL-03", "Dallas Lower Greenville Office", "Dallas", "TX", 32.8020, -96.7700, "Fabrikam Offices",
                 "Budget Shine", 1100, 1250, "office", 9100, 3, 1, ("21:00", "00:00"), 5, 18.0, 95, 35, 2.5, 2,
                 date(2024, 3, 1), date(2027, 2, 28), inspections=[87, 90]),
    # Case 2 — operational fix: locked stockroom causes company-paid return visits.
    DetailedSpec("PHX-01", "Phoenix Camelback Retail", "Phoenix", "AZ", 33.5092, -112.0290, "Northwind Retail",
                 "BrightPath Facility Services", 1500, 1380, "retail", 14000, 2, 1, ("22:00", "02:00"), 5, 19.0, 143, 15, 3.0, 2,
                 date(2023, 6, 1), date(2027, 5, 31), inspections=[86, 88, 90]),
    # Case 3 — underpriced agreement: reasonable cost is above revenue.
    DetailedSpec("COL-01", "Columbus Short North Clinic", "Columbus", "OH", 39.9840, -83.0040, "Contoso Health",
                 "Metro Clean Co", 900, 1240, "medical", 7000, 4, 1, ("19:00", "23:00"), 5, 20.0, 115, 20, 2.0, 2,
                 date(2023, 11, 15), AS_OF + timedelta(days=45), inspections=[91, 93]),
    # Case 4 — infeasible cheap offer: 180-minute window.
    DetailedSpec("ATL-01", "Atlanta Midtown Bank Branch", "Atlanta", "GA", 33.7838, -84.3830, "Lakeshore Banking",
                 "BrightPath Facility Services", 1350, 1300, "bank", 6500, 2, 1, ("22:00", "01:00"), 3, 17.0, 225, 15, 3.0, 2,
                 date(2024, 5, 1), date(2027, 4, 30), inspections=[92, 94]),
    # Case 5 — performance bonus: Summit meets all targets this month.
    DetailedSpec("DEN-01", "Denver LoDo Fitness Center", "Denver", "CO", 39.7530, -105.0000, "Tailspin Fitness",
                 "Summit Janitorial", 1600, 1350, "fitness", 12000, 4, 1, ("23:00", "04:00"), 5, 20.0, 135, 15, 3.0, 2,
                 date(2024, 2, 1), date(2027, 1, 31), inspections=[91, 92, 90],
                 issues=[(9, "quality", "Locker room mirrors streaked", False, 6.0),
                         (22, "quality", "Trash not emptied in yoga studio", False, 18.0)]),
    # Other detailed locations: healthy, mildly loss-making, and one with missing evidence.
    DetailedSpec("HOU-01", "Houston Galleria Retail", "Houston", "TX", 29.7390, -95.4630, "Northwind Retail",
                 "Metro Clean Co", 2400, 1900, "retail", 22000, 4, 1, ("22:00", "04:00"), 5, 18.0, 233, 15, 4.0, 3,
                 date(2023, 9, 1), date(2027, 8, 31), inspections=[93, 95, 92],
                 cost_items=[("other_direct", 80, "Floor mat rental")]),
    DetailedSpec("CHI-01", "Chicago Loop Office Tower Floors", "Chicago", "IL", 41.8810, -87.6290, "Fabrikam Offices",
                 "BrightPath Facility Services", 3200, 2600, "office", 30000, 8, 3, ("19:00", "01:00"), 5, 24.0, 230, 20, 4.0, 4,
                 date(2023, 4, 1), date(2027, 3, 31), inspections=[94, 92, 95],
                 extra_lines=[(120, "Carpet spot extraction (requested)")],
                 cost_items=[("other_direct", 150, "After-hours building access fee")]),
    DetailedSpec("SEA-01", "Seattle South Lake Union Office", "Seattle", "WA", 47.6230, -122.3370, "Fabrikam Offices",
                 "BrightPath Facility Services", 1400, 1380, "office", 6000, 2, 1, ("20:00", "00:00"), 5, 26.0, 85, 20, 3.0, 2,
                 date(2023, 12, 1), date(2026, 12, 1), inspections=[84, 86, 85],
                 cost_items=[("other_direct", 60, "Supply top-up purchased by site manager")],
                 issues=[(8, "quality", "Conference rooms not vacuumed", False, 30.0),
                         (17, "quality", "Kitchen counters left dirty", False, 20.0),
                         (25, "scope", "Crew skipped interior glass (in scope)", False, 48.0)]),
    DetailedSpec("BNA-01", "Nashville Gulch Fitness Studio", "Nashville", "TN", 36.1510, -86.7840, "Tailspin Fitness",
                 "Budget Shine", 950, 960, "fitness", 4500, 2, 1, ("22:00", "02:00"), 3, 17.0, 186, 15, 3.0, 2,
                 date(2024, 11, 1), date(2026, 11, 1), inspections=[88, 89],
                 cost_items=[("credit", 25, "Credit for missed mirror cleaning")],
                 issues=[(15, "quality", "Mirrors left streaked; customer credited", False, 10.0)]),
    # Missing evidence: no inspections recorded.
    DetailedSpec("MSP-01", "Minneapolis North Loop Office", "Minneapolis", "MN", 44.9890, -93.2770, "Fabrikam Offices",
                 "Summit Janitorial", 1700, 1450, "office", 11000, 4, 2, ("19:00", "23:00"), 5, 22.0, 134, 15, 3.0, 2,
                 date(2024, 4, 1), date(2027, 3, 31), inspections=[]),
]

# Phoenix: four nights the stockroom was locked; each needed a company-paid return visit.
PHOENIX_ACCESS_DAYS = [3, 10, 17, 24]
PHOENIX_RETURN_VISIT_PRICE = 95.0
# Denver: one visit the customer cancelled (building closed); marked customer-caused.
DENVER_CUSTOMER_MISSED_DAY = 15

OFFERS = [
    # vendor, location codes (route order), monthly price, crew size, crew-minutes per site, transition, description
    ("Metro Clean Co", ["DAL-01", "DAL-02", "DAL-03"], 3150, 2, 100, 300,
     "One crew, one route for all three Dallas sites."),
    ("Budget Shine", ["ATL-01"], 1050, 1, 225, 150, "Single cleaner, lower price."),
]

FIXES = [
    ("PHX-01", "Install stockroom lockbox", "Lockbox with a code for the crew so the stockroom is always reachable.",
     "access", 150.0, 0.90),
]

# Real U.S. metro centers for lightweight sites.
METROS = [
    ("New York", "NY", 40.7128, -74.0060), ("Los Angeles", "CA", 34.0522, -118.2437), ("Chicago", "IL", 41.8781, -87.6298),
    ("Houston", "TX", 29.7604, -95.3698), ("Phoenix", "AZ", 33.4484, -112.0740), ("Philadelphia", "PA", 39.9526, -75.1652),
    ("San Antonio", "TX", 29.4241, -98.4936), ("San Diego", "CA", 32.7157, -117.1611), ("Dallas", "TX", 32.7767, -96.7970),
    ("Austin", "TX", 30.2672, -97.7431), ("Jacksonville", "FL", 30.3322, -81.6557), ("Columbus", "OH", 39.9612, -82.9988),
    ("Charlotte", "NC", 35.2271, -80.8431), ("Indianapolis", "IN", 39.7684, -86.1581), ("San Francisco", "CA", 37.7749, -122.4194),
    ("Seattle", "WA", 47.6062, -122.3321), ("Denver", "CO", 39.7392, -104.9903), ("Washington", "DC", 38.9072, -77.0369),
    ("Boston", "MA", 42.3601, -71.0589), ("Nashville", "TN", 36.1627, -86.7816), ("Detroit", "MI", 42.3314, -83.0458),
    ("Portland", "OR", 45.5152, -122.6784), ("Las Vegas", "NV", 36.1699, -115.1398), ("Atlanta", "GA", 33.7490, -84.3880),
    ("Miami", "FL", 25.7617, -80.1918), ("Minneapolis", "MN", 44.9778, -93.2650), ("Tampa", "FL", 27.9506, -82.4572),
    ("Orlando", "FL", 28.5383, -81.3792), ("St. Louis", "MO", 38.6270, -90.1994), ("Pittsburgh", "PA", 40.4406, -79.9959),
    ("Sacramento", "CA", 38.5816, -121.4944), ("Kansas City", "MO", 39.0997, -94.5786), ("Cleveland", "OH", 41.4993, -81.6944),
    ("Raleigh", "NC", 35.7796, -78.6382), ("Salt Lake City", "UT", 40.7608, -111.8910), ("Milwaukee", "WI", 43.0389, -87.9065),
    ("Baltimore", "MD", 39.2904, -76.6122), ("New Orleans", "LA", 29.9511, -90.0715), ("Oklahoma City", "OK", 35.4676, -97.5164),
    ("Albuquerque", "NM", 35.0844, -106.6504),
]
ACCOUNTS = ["Northwind Retail", "Contoso Health", "Fabrikam Offices", "Tailspin Fitness", "Lakeshore Banking"]
ACCOUNT_TYPE = {"Northwind Retail": "retail", "Contoso Health": "medical", "Fabrikam Offices": "office",
                "Tailspin Fitness": "fitness", "Lakeshore Banking": "bank"}


def _service_days(frequency: int) -> list[date]:
    weekdays = {5: (0, 1, 2, 3, 4), 3: (0, 2, 4), 7: tuple(range(7)), 2: (1, 3)}[frequency]
    return [d for d in MONTH_DAYS if d.weekday() in weekdays]


def _at(d: date, hhmm: str, plus_minutes: float = 0) -> datetime:
    h, mm = map(int, hhmm.split(":"))
    return datetime(d.year, d.month, d.day, h, mm) + timedelta(minutes=plus_minutes)


def _split_tasks(total: int) -> list[tuple[str, int]]:
    parts = [round(total * s) for s in TASK_SPLIT[:-1]]
    parts.append(total - sum(parts))
    return list(zip(TASK_NAMES, parts))


def _seed_detailed(db: Session, rng: random.Random, vendors: dict[str, m.Vendor]) -> dict[str, m.Location]:
    locations: dict[str, m.Location] = {}
    for spec in DETAILED:
        vendor = vendors[spec.vendor]
        loc = m.Location(
            code=spec.code, name=spec.name, city=spec.city, state=spec.state, lat=spec.lat, lng=spec.lng,
            detailed=True, customer_account=spec.account, revenue_monthly=spec.revenue,
            sq_ft=spec.sq_ft, restrooms=spec.restrooms, floors=spec.floors, building_type=spec.building_type,
            service_window_start=spec.window[0], service_window_end=spec.window[1],
            frequency_per_week=spec.frequency, current_vendor_id=vendor.id, local_loaded_wage=spec.wage,
            travel_minutes_per_visit=spec.travel_minutes, supplies_per_visit=spec.supplies,
            current_crew_size=spec.crew_size,
        )
        db.add(loc)
        db.flush()
        locations[spec.code] = loc

        for task, minutes in _split_tasks(spec.task_minutes):
            db.add(m.SiteTask(location_id=loc.id, task=task, minutes=minutes))
        db.add(m.Contract(
            location_id=loc.id, price_monthly=spec.revenue, scope=SCOPE_BY_TYPE[spec.building_type],
            frequency_per_week=spec.frequency, start_date=spec.contract_start, renewal_date=spec.renewal,
        ))
        db.add(m.Invoice(location_id=loc.id, vendor_id=vendor.id, month=MONTH, amount=spec.base_invoice,
                         line_type="base", description=f"Contract cleaning, {MONTH}"))
        for amount, text in spec.extra_lines:
            db.add(m.Invoice(location_id=loc.id, vendor_id=vendor.id, month=MONTH, amount=amount,
                             line_type="extra", description=text))
        for ctype, amount, text in spec.cost_items:
            db.add(m.CostItem(location_id=loc.id, month=MONTH, type=ctype, amount=amount, description=text))

        on_site = spec.task_minutes / spec.crew_size
        visits: dict[date, m.ServiceVisit] = {}
        for d in _service_days(spec.frequency):
            start = rng.randint(0, 15)
            v = m.ServiceVisit(
                location_id=loc.id, vendor_id=vendor.id, date=d, completed=True, return_visit=False,
                checkin=_at(d, spec.window[0], start), checkout=_at(d, spec.window[0], start + on_site + rng.randint(-8, 8)),
            )
            db.add(v)
            visits[d] = v
        db.flush()

        for day, category, text, customer_caused, hours in spec.issues:
            d = date(2026, 9, day)
            db.add(m.IssueRecord(location_id=loc.id, visit_id=visits[d].id if d in visits else None, date=d,
                                 category=category, description=text, customer_caused=customer_caused,
                                 resolved_hours=hours))
        for i, score in enumerate(spec.inspections):
            db.add(m.Inspection(location_id=loc.id, date=date(2026, 9, 8 + 9 * i), score=score))

        if spec.code == "PHX-01":
            _seed_phoenix_access(db, loc, vendor, visits, spec)
        if spec.code == "DEN-01":
            _seed_denver_customer_miss(db, loc, visits)
    return locations


def _seed_phoenix_access(db: Session, loc: m.Location, vendor: m.Vendor, visits: dict, spec: DetailedSpec) -> None:
    for day in PHOENIX_ACCESS_DAYS:
        d = date(2026, 9, day)
        visits[d].completed = False
        db.add(m.IssueRecord(
            location_id=loc.id, visit_id=visits[d].id, date=d, category="access", customer_caused=True,
            description="Stockroom locked; crew could not reach supplies or the floor machine", resolved_hours=20.0,
        ))
        rv_day = d + timedelta(days=1)
        rv = m.ServiceVisit(location_id=loc.id, vendor_id=vendor.id, date=rv_day, completed=True, return_visit=True,
                            checkin=_at(rv_day, "06:00"), checkout=_at(rv_day, "07:10"))
        db.add(rv)
        db.flush()
        db.add(m.Invoice(location_id=loc.id, vendor_id=vendor.id, month=MONTH, amount=PHOENIX_RETURN_VISIT_PRICE,
                         line_type="return_visit", service_visit_id=rv.id,
                         description=f"Return visit {rv_day.isoformat()} after locked stockroom on {d.isoformat()}"))


def _seed_denver_customer_miss(db: Session, loc: m.Location, visits: dict) -> None:
    d = date(2026, 9, DENVER_CUSTOMER_MISSED_DAY)
    visits[d].completed = False
    visits[d].checkout = visits[d].checkin
    db.add(m.IssueRecord(
        location_id=loc.id, visit_id=visits[d].id, date=d, category="missed", customer_caused=True,
        description="Building closed for a member event; crew turned away at the door", resolved_hours=12.0,
    ))


def _seed_lightweight(db: Session, rng: random.Random, count: int) -> None:
    rows = []
    for n in range(1, count + 1):
        city, state, lat, lng = rng.choice(METROS)
        account = rng.choice(ACCOUNTS)
        revenue = round(rng.uniform(600, 4000), -1)
        if rng.random() < LIGHTWEIGHT_LOSS_SHARE:
            cost = round(revenue * rng.uniform(1.02, 1.25), 2)
        else:
            cost = round(revenue * rng.uniform(0.70, 0.95), 2)
        rows.append(dict(
            code=f"LW-{n:04d}", name=f"{city} {ACCOUNT_TYPE[account]} site {n:04d}", city=city, state=state,
            lat=round(lat + rng.gauss(0, 0.12), 5), lng=round(lng + rng.gauss(0, 0.15), 5), detailed=False,
            customer_account=account, revenue_monthly=revenue, actual_cost_monthly=cost,
            building_type=ACCOUNT_TYPE[account],
        ))
    db.execute(m.Location.__table__.insert(), rows)


def seed(db: Session) -> dict[str, int]:
    rng = random.Random(SEED)
    for key, label, value, text_value, unit in ASSUMPTIONS:
        db.add(m.Assumption(key=key, label=label, value=value, text_value=text_value, unit=unit))

    vendors: dict[str, m.Vendor] = {}
    for name, lat, lng, crews, shift, rate, cap in VENDORS:
        vendors[name] = m.Vendor(name=name, home_lat=lat, home_lng=lng, crews_available=crews,
                                 shift_minutes=shift, bonus_rate=rate, bonus_cap=cap)
        db.add(vendors[name])
    db.flush()
    completion, inspection, fix24 = SUMMIT_TARGETS
    db.add(m.PerformanceTarget(vendor_id=vendors["Summit Janitorial"].id, completion_min=completion,
                               inspection_avg_min=inspection, fix_within_24h_min=fix24))

    locations = _seed_detailed(db, rng, vendors)
    for vendor, codes, price, crew, minutes, transition, text in OFFERS:
        db.add(m.VendorOffer(vendor_id=vendors[vendor].id, location_ids=[locations[c].id for c in codes],
                             monthly_price=price, crew_size=crew, minutes_per_site=minutes,
                             transition_cost_one_time=transition, description=text))
    for code, name, text, category, cost, reduction in FIXES:
        db.add(m.OperationalFix(location_id=locations[code].id, name=name, description=text,
                                issue_category=category, one_time_cost=cost, return_visit_reduction=reduction))

    _seed_lightweight(db, rng, TOTAL_LOCATIONS - len(DETAILED))
    db.commit()
    return {
        "vendors": len(VENDORS),
        "detailed_locations": len(DETAILED),
        "locations": TOTAL_LOCATIONS,
    }


def reset_and_seed(bind=None) -> dict[str, int]:
    """Drop and recreate every table, then load the demonstration data."""
    bind = bind or engine
    Base.metadata.drop_all(bind=bind)
    Base.metadata.create_all(bind=bind)
    with SessionLocal(bind=bind) as db:
        return seed(db)


if __name__ == "__main__":
    summary = reset_and_seed()
    print("Seeded demonstration data:", ", ".join(f"{k}={v}" for k, v in summary.items()))
