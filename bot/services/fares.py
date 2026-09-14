"""Distance-slab fare calculation.

Slabs live in the database (``FareSlab``) but are cached in module state: a
departure list quotes a fare per trip, and a query per quote would be wasteful
for a table of five rows. The cache is invalidated by a post_save signal in
``bot.apps``.
"""

from decimal import ROUND_HALF_UP, Decimal

from bot.models import FareSlab

_slab_cache: list[tuple[Decimal, Decimal | None, Decimal]] | None = None


def invalidate_cache() -> None:
    global _slab_cache
    _slab_cache = None


def _slabs() -> list[tuple[Decimal, Decimal | None, Decimal]]:
    global _slab_cache
    if _slab_cache is None:
        _slab_cache = [
            (s.min_km, s.max_km, s.price)
            for s in FareSlab.objects.order_by("min_km")
        ]
    return _slab_cache


def fare_for_km(km) -> Decimal:
    """Return the fare for a distance.

    Slabs are [min_km, max_km): a boundary distance falls in the *upper* slab,
    so exactly 3.00 km costs the 3–6 km fare, not the 0–3 km fare.
    """
    km = Decimal(str(km)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if km < 0:
        km = -km

    slabs = _slabs()
    if not slabs:
        raise RuntimeError("No fare slabs configured. Run: manage.py seed_fares")

    for min_km, max_km, price in slabs:
        if km >= min_km and (max_km is None or km < max_km):
            return price

    # Distance beyond every slab: charge the top slab.
    return slabs[-1][2]


def total_fare(km, seats: int) -> tuple[Decimal, Decimal]:
    """Return ``(fare_per_seat, total)``."""
    per_seat = fare_for_km(km)
    return per_seat, per_seat * seats
