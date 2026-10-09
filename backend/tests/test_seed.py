from sqlalchemy import func, select

from app import models as m
from app.db import SessionLocal
from app.rules.finance import lightweight_contribution
from app.seed import reset_and_seed


def _summary(db):
    return [
        (l.code, l.lat, l.lng, l.revenue_monthly, l.actual_cost_monthly)
        for l in db.scalars(select(m.Location).order_by(m.Location.code))
    ] + [(v.date, v.checkin, v.checkout, v.completed) for v in db.scalars(select(m.ServiceVisit).order_by(m.ServiceVisit.id))]


def test_counts(seeded):
    assert seeded.scalar(select(func.count(m.Vendor.id))) == 4
    assert seeded.scalar(select(func.count(m.Location.id)).where(m.Location.detailed)) == 12
    assert 1900 <= seeded.scalar(select(func.count(m.Location.id))) <= 2100


def test_lightweight_sites_have_summary_fields_only(seeded):
    lw = seeded.scalars(select(m.Location).where(~m.Location.detailed)).all()
    assert all(l.actual_cost_monthly is not None and l.current_vendor_id is None for l in lw)
    assert seeded.scalar(
        select(func.count(m.ServiceVisit.id)).join(m.Location, m.Location.id == m.ServiceVisit.location_id).where(~m.Location.detailed)
    ) == 0
    assert len({(l.city, l.state) for l in lw}) >= 30


def test_loss_share_between_10_and_15_percent(seeded):
    lw = seeded.scalars(select(m.Location).where(~m.Location.detailed)).all()
    losses = sum(1 for l in lw if lightweight_contribution(l.revenue_monthly, l.actual_cost_monthly).amount < 0)
    assert 0.10 <= losses / len(lw) <= 0.15


def test_no_bonus_cost_items_are_seeded(seeded):
    assert seeded.scalar(select(func.count(m.CostItem.id)).where(m.CostItem.type == "bonus")) == 0


def test_money_rows_carry_a_kind(seeded):
    assert {k for (k,) in seeded.execute(select(m.Invoice.kind).distinct())} == {"actual"}
    assert {k for (k,) in seeded.execute(select(m.VendorOffer.kind).distinct())} == {"quoted"}
    assert {k for (k,) in seeded.execute(select(m.OperationalFix.kind).distinct())} == {"estimated"}


def test_seed_is_deterministic(mutable_db):
    first = _summary(mutable_db)
    reset_and_seed()
    with SessionLocal() as db:
        assert _summary(db) == first
