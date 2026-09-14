"""Route/trip search over the stop network."""

from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal

from django.db.models import F
from django.utils import timezone

from bot.models import RouteStop, Stop, Trip
from bot.services.fares import fare_for_km

# Don't offer a bus that leaves within this window — nobody can reach it.
BOARDING_LEAD = timedelta(minutes=10)


@dataclass
class Leg:
    """A route that serves origin → destination in the correct direction."""

    route_id: int
    board: RouteStop
    alight: RouteStop

    @property
    def distance_km(self) -> Decimal:
        return self.alight.distance_from_origin - self.board.distance_from_origin


@dataclass
class TripOption:
    trip: Trip
    board_at: object
    distance_km: Decimal
    fare_per_seat: Decimal
    seats_left: int

    @property
    def route_code(self) -> str:
        return self.trip.route.code


def candidate_legs(origin_id: int, destination_id: int) -> list[Leg]:
    """Routes serving both stops, with origin *before* destination.

    The sequence comparison is what enforces direction: a route passing through
    both stops in the wrong order is not a valid journey.
    """
    board = {
        rs.route_id: rs
        for rs in RouteStop.objects.filter(
            stop_id=origin_id, route__is_active=True
        ).select_related("route")
    }
    alight = {
        rs.route_id: rs
        for rs in RouteStop.objects.filter(stop_id=destination_id, route__is_active=True)
    }
    return [
        Leg(rid, board[rid], alight[rid])
        for rid in board.keys() & alight.keys()
        if board[rid].sequence < alight[rid].sequence
    ]


def distance_between(origin_id: int, destination_id: int) -> Decimal | None:
    """Shortest distance over any route serving the pair, or None if unconnected."""
    legs = candidate_legs(origin_id, destination_id)
    if not legs:
        return None
    return min(leg.distance_km for leg in legs)


def fare_between(origin_id: int, destination_id: int) -> Decimal | None:
    km = distance_between(origin_id, destination_id)
    return None if km is None else fare_for_km(km)


def search_trips(origin_id, destination_id, service_date, seats=1, limit=5) -> list[TripOption]:
    """Bookable departures for a journey on a date, soonest first."""
    legs = candidate_legs(origin_id, destination_id)
    if not legs:
        return []

    by_route = {leg.route_id: leg for leg in legs}
    trips = (
        Trip.objects.filter(
            route_id__in=by_route,
            service_date=service_date,
            status=Trip.Status.SCHEDULED,
        )
        .annotate(available=F("total_seats") - F("seats_booked"))
        .filter(available__gte=seats)
        .select_related("route", "bus")
        .order_by("departure_datetime")
    )

    cutoff = timezone.now() + BOARDING_LEAD
    options: list[TripOption] = []
    for trip in trips:
        leg = by_route[trip.route_id]
        board_at = trip.departure_datetime + timedelta(minutes=leg.board.offset_minutes)
        if board_at < cutoff:
            continue
        km = leg.distance_km
        options.append(
            TripOption(
                trip=trip,
                board_at=board_at,
                distance_km=km,
                fare_per_seat=fare_for_km(km),
                seats_left=trip.total_seats - trip.seats_booked,
            )
        )
        if len(options) >= limit:
            break
    return options


def connected_stops(origin_id: int, limit: int = 8) -> list[Stop]:
    """Stops reachable from origin on a single route.

    Used to make "no direct bus" actionable instead of a dead end.
    """
    route_ids = RouteStop.objects.filter(
        stop_id=origin_id, route__is_active=True
    ).values_list("route_id", "sequence")

    reachable: set[int] = set()
    for route_id, sequence in route_ids:
        reachable.update(
            RouteStop.objects.filter(route_id=route_id, sequence__gt=sequence)
            .values_list("stop_id", flat=True)
        )
    reachable.discard(origin_id)
    return list(Stop.objects.filter(pk__in=reachable, is_active=True)[:limit])
