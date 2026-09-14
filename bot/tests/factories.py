"""Shared test fixtures: a small deterministic network."""

import datetime as dt
from decimal import Decimal

from django.utils import timezone

from bot.models import Bus, FareSlab, Route, RouteStop, Stop, Trip
from bot.services.fares import invalidate_cache


def make_fare_slabs():
    FareSlab.objects.all().delete()
    for min_km, max_km, price in [(0, 3, 5), (3, 6, 10), (6, 10, 15), (10, 15, 20), (15, None, 25)]:
        FareSlab.objects.create(
            min_km=Decimal(str(min_km)),
            max_km=None if max_km is None else Decimal(str(max_km)),
            price=Decimal(str(price)),
        )
    invalidate_cache()


def make_line(code="T-1", names=("A", "B", "C", "D"), spacing=Decimal("4.00")):
    """A straight line of stops, `spacing` km apart, with both directions."""
    stops = []
    for i, name in enumerate(names):
        stop, _ = Stop.objects.get_or_create(
            name=name, defaults={"code": f"S{i}{name[:2]}".upper()[:8]}
        )
        stops.append(stop)

    up = Route.objects.create(code=f"{code}-UP", name="up", direction=Route.Direction.UP)
    down = Route.objects.create(code=f"{code}-DN", name="down", direction=Route.Direction.DOWN)

    total = spacing * (len(stops) - 1)
    for i, stop in enumerate(stops):
        RouteStop.objects.create(
            route=up, stop=stop, sequence=i + 1,
            distance_from_origin=spacing * i, offset_minutes=i * 5,
        )
    for i, stop in enumerate(reversed(stops)):
        RouteStop.objects.create(
            route=down, stop=stop, sequence=i + 1,
            distance_from_origin=total - (spacing * (len(stops) - 1 - i)),
            offset_minutes=i * 5,
        )
    return up, down, stops


def make_trip(route, *, seats=10, hours_ahead=3, service_date=None):
    bus = Bus.objects.create(
        registration=f"MP09 TEST {Trip.objects.count() + 1:04d}", total_seats=seats
    )
    departure = timezone.now() + dt.timedelta(hours=hours_ahead)
    return Trip.objects.create(
        route=route,
        bus=bus,
        service_date=service_date or timezone.localdate(departure),
        departure_datetime=departure,
        total_seats=seats,
        seats_booked=0,
        status=Trip.Status.SCHEDULED,
    )
