"""Nearby + compatible site grouping, and per-site allocation of a vendor offer."""

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, field

from app.rules.feasibility import FeasibilityResult, check_route, clock_minutes, haversine_miles, window_minutes
from app.rules.types import Money, Offer, Ref, RuleResult, Settings, Site, VendorInfo, usd


def _window_interval(site: Site) -> tuple[int, int] | None:
    if not (site.window_start and site.window_end):
        return None
    start = clock_minutes(site.window_start)
    return start, start + window_minutes(site.window_start, site.window_end)


def _windows_overlap(a: Site, b: Site) -> bool:
    wa, wb = _window_interval(a), _window_interval(b)
    if wa is None or wb is None:
        return False
    # Compare on a two-day clock so a 22:00–01:00 window can overlap a 23:00–02:00 one.
    return any(
        max(wa[0] + da, wb[0] + db) < min(wa[1] + da, wb[1] + db) for da in (0, 1440) for db in (0, 1440)
    )


@dataclass
class BundleCandidate(RuleResult):
    location_ids: list[int] = field(default_factory=list)
    max_distance_miles: float = 0.0


def find_bundle_candidates(sites: Sequence[Site], radius_miles: float = 5.0) -> list[BundleCandidate]:
    """Group sites in the same metro that are all within `radius_miles` of each other
    and whose service windows overlap. Greedy, deterministic (input order)."""
    by_metro: dict[tuple[str, str], list[Site]] = defaultdict(list)
    for s in sites:
        by_metro[(s.city, s.state)].append(s)

    out = []
    for (city, state), group in by_metro.items():
        used: set[int] = set()
        for seed in group:
            if seed.id in used:
                continue
            members = [seed]
            for other in group:
                if other.id in used or other is seed:
                    continue
                if all(
                    haversine_miles(m.lat, m.lng, other.lat, other.lng) <= radius_miles and _windows_overlap(m, other)
                    for m in members
                ):
                    members.append(other)
            if len(members) < 2:
                continue
            used.update(m.id for m in members)
            dist = max(
                haversine_miles(a.lat, a.lng, b.lat, b.lng) for i, a in enumerate(members) for b in members[i + 1 :]
            )
            vendors = {m.current_vendor_id for m in members if m.current_vendor_id is not None}
            reasons = [
                f"{len(members)} sites in {city}, {state} are within {dist:.1f} miles of each other "
                "and their service windows overlap."
            ]
            if len(vendors) > 1:
                reasons.append(
                    f"They are served today by {len(vendors)} different vendors, each driving out separately."
                )
            out.append(
                BundleCandidate(
                    reasons=reasons,
                    evidence=[Ref("location", m.id) for m in members],
                    location_ids=[m.id for m in members],
                    max_distance_miles=round(dist, 2),
                )
            )
    return out


@dataclass
class OfferEvaluation(RuleResult):
    offer_id: int = 0
    vendor_id: int = 0
    location_ids: list[int] = field(default_factory=list)
    is_bundle: bool = False
    price_per_site: Money = Money(0.0, "quoted")
    transition_per_site_monthly: Money = Money(0.0, "quoted")
    feasibility: FeasibilityResult = field(default_factory=FeasibilityResult)


def evaluate_offer(offer: Offer, stops: Sequence[Site], vendor: VendorInfo, settings: Settings) -> OfferEvaluation:
    """Split the quoted price equally across the offer's sites, amortize the one-time
    transition cost over `amortization_months` and across the sites, and check the route."""
    n = len(offer.location_ids)
    price_per_site = offer.monthly_price / n
    transition_monthly = offer.transition_cost_one_time / settings.amortization_months
    transition_per_site = transition_monthly / n
    feas = check_route(stops, offer.crew_size, offer.minutes_per_site, vendor, settings)

    reasons = [f"{vendor.name} quotes {usd(offer.monthly_price)}/month for {n} site(s): {usd(round(price_per_site, 2))} per site."]
    if offer.transition_cost_one_time:
        reasons.append(
            f"Transition cost {usd(offer.transition_cost_one_time)} one-time = {usd(round(transition_monthly, 2))}/month "
            f"over {settings.amortization_months:g} months"
            + (f", {usd(round(transition_per_site, 2))} per site." if n > 1 else ".")
        )
    return OfferEvaluation(
        reasons=reasons,
        evidence=[Ref("vendor_offer", offer.id)] + feas.evidence,
        offer_id=offer.id,
        vendor_id=vendor.id,
        location_ids=list(offer.location_ids),
        is_bundle=n > 1,
        price_per_site=Money(round(price_per_site, 2), "quoted"),
        transition_per_site_monthly=Money(round(transition_per_site, 4), "quoted"),
        feasibility=feas,
    )
