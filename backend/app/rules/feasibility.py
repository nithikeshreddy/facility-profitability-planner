"""Service window, travel and crew capacity checks for a vendor offer's route."""

import math
from collections.abc import Sequence
from dataclasses import dataclass, field

from app.rules.types import Ref, RuleResult, Settings, Site, VendorInfo

EARTH_RADIUS_MILES = 3958.8


def clock_minutes(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def window_minutes(start: str, end: str) -> int:
    """Length of a service window; an end at or before the start crosses midnight."""
    length = clock_minutes(end) - clock_minutes(start)
    return length if length > 0 else length + 24 * 60


def haversine_miles(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_MILES * math.asin(math.sqrt(a))


def travel_minutes(a: Site, b: Site, settings: Settings) -> float:
    miles = haversine_miles(a.lat, a.lng, b.lat, b.lng) * settings.road_factor
    return miles / settings.travel_speed_mph * 60


@dataclass(frozen=True)
class SiteCheck:
    location_id: int
    location_name: str
    cleaning_minutes: float  # on site, = crew-minutes ÷ crew size
    travel_minutes: float  # from the previous stop
    required_minutes: float
    window_minutes: int | None
    fits: bool
    clause: str  # lower-case clause usable inside a sentence

    @property
    def sentence(self) -> str:
        return self.clause[0].upper() + self.clause[1:] + "."


@dataclass
class FeasibilityResult(RuleResult):
    feasible: bool = False
    site_checks: list[SiteCheck] = field(default_factory=list)
    total_crew_minutes: float = 0.0
    capacity_minutes: float = 0.0
    capacity_ok: bool = False


def check_route(
    stops: Sequence[Site], crew_size: int, minutes_per_site: float, vendor: VendorInfo, settings: Settings
) -> FeasibilityResult:
    """Per site: cleaning minutes ÷ crew size + travel from previous stop ≤ service window.

    Travel to the first stop happens before the window opens, so it counts as 0.
    Whole route: total crew-minutes ≤ vendor crews_available × shift_minutes
    (every site in the offer is assumed to be serviced the same night — the worst case).
    """
    checks: list[SiteCheck] = []
    prev: Site | None = None
    for site in stops:
        cleaning = minutes_per_site / crew_size
        travel = travel_minutes(prev, site, settings) if prev else 0.0
        required = cleaning + travel
        if site.window_start and site.window_end:
            window = window_minutes(site.window_start, site.window_end)
            fits = required <= window
            travel_part = f" ({cleaning:.0f} cleaning + {travel:.0f} travel)" if travel >= 0.5 else ""
            clause = (
                f"its crew requires {required:.0f} minutes{travel_part} within a {window}-minute service window"
            )
            if len(stops) > 1:
                clause += f" at {site.name}"
        else:
            window, fits = None, False
            clause = f"{site.name} has no recorded service window (evidence missing)"
        checks.append(SiteCheck(site.id, site.name, cleaning, travel, required, window, fits, clause))
        prev = site

    total = sum(c.required_minutes for c in checks)
    capacity = vendor.crews_available * vendor.shift_minutes
    capacity_ok = total <= capacity

    reasons = []
    for c in checks:
        reasons.append(c.sentence if not c.fits else f"Fits: {c.clause}.")
    cap_sentence = (
        f"The route needs {total:.0f} crew-minutes per night; {vendor.name} has "
        f"{vendor.crews_available} crew(s) × {vendor.shift_minutes} minutes = {capacity} available."
    )
    reasons.append(cap_sentence if capacity_ok else "Over capacity: " + cap_sentence)

    return FeasibilityResult(
        reasons=reasons,
        evidence=[Ref("location", s.id) for s in stops],
        feasible=capacity_ok and all(c.fits for c in checks),
        site_checks=checks,
        total_crew_minutes=round(total, 2),
        capacity_minutes=capacity,
        capacity_ok=capacity_ok,
    )
