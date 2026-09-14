"""Booking lifecycle. The single place seats are allocated or released.

Called identically by the WhatsApp bot, the website and the REST API, so fare
and seat logic exists exactly once.
"""

import logging
from datetime import timedelta

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone

from bot.models import (
    Booking,
    ConversationSession,
    Passenger,
    PassengerProfile,
    Payment,
    Trip,
)
from bot.services.fares import fare_for_km
from bot.services.network import candidate_legs
from bot.services.pnr import generate_pnr

log = logging.getLogger("bot")


class BookingError(Exception):
    """Base for booking failures that should be shown to the user."""


class SeatsUnavailable(BookingError):
    pass


class NoRouteBetweenStops(BookingError):
    pass


class TripNotBookable(BookingError):
    pass


def get_or_create_profile(whatsapp_number: str, display_name: str = "") -> PassengerProfile:
    profile, created = PassengerProfile.objects.get_or_create(
        whatsapp_number=whatsapp_number,
        defaults={"display_name": display_name},
    )
    if display_name and not profile.display_name:
        profile.display_name = display_name
        profile.save(update_fields=["display_name"])
    return profile


def _reserve_seats(trip_id: int, seats: int) -> bool:
    """Atomically claim ``seats`` on a trip. Returns False if there aren't enough.

    A conditional UPDATE, not select_for_update(), because:

      * On MySQL/InnoDB the default isolation is REPEATABLE READ, where a plain
        SELECT returns a snapshot that may already be stale — so the intuitive
        read-check-write is genuinely broken there even inside a transaction.
        UPDATE performs a *locking* read and always sees the latest commit.
      * On SQLite select_for_update() is silently a no-op (the backend reports
        has_select_for_update = False). Code built around it would look correct
        in dev and only oversell under MySQL load.

    One statement, correct on both.
    """
    updated = (
        Trip.objects.filter(
            pk=trip_id,
            status=Trip.Status.SCHEDULED,
            seats_booked__lte=F("total_seats") - seats,
        ).update(seats_booked=F("seats_booked") + seats)
    )
    return bool(updated)


def _release_seats(trip_id: int, seats: int) -> None:
    Trip.objects.filter(pk=trip_id).update(
        seats_booked=F("seats_booked") - seats
    )


@transaction.atomic
def create_booking(
    *,
    profile: PassengerProfile,
    trip_id: int,
    origin_id: int,
    destination_id: int,
    seats: int = 1,
    passenger_names: list[str] | None = None,
    channel: str = Booking.Channel.WHATSAPP,
    user=None,
    status: str = Booking.Status.CONFIRMED,
    payment_method: str = Payment.Method.CASH,
) -> Booking:
    """Reserve seats and issue a ticket.

    Every price-bearing value is frozen onto the booking here; nothing is
    recomputed later.
    """
    if seats < 1:
        raise BookingError("Seat count must be at least 1.")

    trip = (
        Trip.objects.select_related("route")
        .filter(pk=trip_id, status=Trip.Status.SCHEDULED)
        .first()
    )
    if trip is None:
        raise TripNotBookable("That bus is no longer available.")

    # The journey must lie along this trip's route, in the travel direction.
    leg = next(
        (l for l in candidate_legs(origin_id, destination_id) if l.route_id == trip.route_id),
        None,
    )
    if leg is None:
        raise NoRouteBetweenStops("That bus does not run between those stops.")

    if not _reserve_seats(trip.pk, seats):
        raise SeatsUnavailable("Not enough seats left on that bus.")

    km = leg.distance_km
    fare = fare_for_km(km)
    board_at = trip.departure_datetime + timedelta(minutes=leg.board.offset_minutes)
    now = timezone.now()

    for attempt in range(3):
        try:
            booking = Booking.objects.create(
                pnr=generate_pnr(),
                profile=profile,
                user=user or profile.user,
                whatsapp_number=profile.whatsapp_number,
                trip=trip,
                origin_id=origin_id,
                destination_id=destination_id,
                origin_sequence=leg.board.sequence,
                destination_sequence=leg.alight.sequence,
                board_at=board_at,
                distance_km=km,
                fare_per_seat=fare,
                seat_count=seats,
                total_fare=fare * seats,
                status=status,
                channel=channel,
                confirmed_at=now if status == Booking.Status.CONFIRMED else None,
            )
            break
        except IntegrityError:
            # PNR collision. The unique index is the real guarantee; retry.
            if attempt == 2:
                _release_seats(trip.pk, seats)
                raise
            log.warning("PNR collision, retrying (attempt %s)", attempt + 1)

    names = passenger_names or []
    Passenger.objects.bulk_create(
        [
            Passenger(booking=booking, name=names[i] if i < len(names) else f"Passenger {i + 1}")
            for i in range(seats)
        ]
    )

    Payment.objects.create(
        booking=booking,
        method=payment_method,
        status=Payment.Status.PENDING,
        amount=booking.total_fare,
    )

    log.info("Booking %s created: %s seats on trip %s", booking.pnr, seats, trip.pk)
    return booking


@transaction.atomic
def cancel_booking(booking: Booking) -> Booking:
    """Cancel a booking and return its seats to the trip."""
    # Re-read under the transaction so a double CANCEL can't release twice.
    fresh = Booking.objects.select_for_update().get(pk=booking.pk)
    if not fresh.is_active:
        raise BookingError(f"Booking {fresh.pnr} is already {fresh.get_status_display().lower()}.")

    _release_seats(fresh.trip_id, fresh.seat_count)
    fresh.status = Booking.Status.CANCELLED
    fresh.cancelled_at = timezone.now()
    fresh.save(update_fields=["status", "cancelled_at"])

    Payment.objects.filter(booking=fresh, status=Payment.Status.PAID).update(
        status=Payment.Status.REFUNDED
    )
    log.info("Booking %s cancelled", fresh.pnr)
    return fresh


def lookup_by_pnr(pnr: str, whatsapp_number: str | None = None) -> Booking | None:
    """Fetch a ticket. Scoped by number unless the caller is already authorized."""
    qs = Booking.objects.select_related(
        "trip", "trip__route", "origin", "destination", "profile"
    ).filter(pnr=(pnr or "").strip().upper())
    if whatsapp_number:
        qs = qs.filter(whatsapp_number=whatsapp_number)
    return qs.first()


def recent_bookings(whatsapp_number: str, limit: int = 5) -> list[Booking]:
    return list(
        Booking.objects.select_related("trip", "trip__route", "origin", "destination")
        .filter(whatsapp_number=whatsapp_number)
        .order_by("-created_at")[:limit]
    )


def expire_stale_pending(minutes: int | None = None) -> int:
    """Release seats held by PENDING bookings that were never confirmed."""
    minutes = minutes if minutes is not None else settings.SEAT_HOLD_MINUTES
    cutoff = timezone.now() - timedelta(minutes=minutes)
    stale = Booking.objects.filter(status=Booking.Status.PENDING, created_at__lt=cutoff)

    count = 0
    for booking in stale:
        with transaction.atomic():
            _release_seats(booking.trip_id, booking.seat_count)
            booking.status = Booking.Status.EXPIRED
            booking.save(update_fields=["status"])
            count += 1
    if count:
        log.info("Expired %s stale pending bookings", count)
    return count


def expire_stale_sessions(minutes: int | None = None) -> int:
    """Reset chat sessions abandoned mid-flow so held seats don't leak."""
    minutes = minutes if minutes is not None else settings.SESSION_IDLE_MINUTES
    cutoff = timezone.now() - timedelta(minutes=minutes)
    stale = ConversationSession.objects.filter(last_message_at__lt=cutoff).exclude(state="IDLE")
    count = stale.count()
    stale.update(state="IDLE", context={}, history=[], retry_count=0)
    return count
