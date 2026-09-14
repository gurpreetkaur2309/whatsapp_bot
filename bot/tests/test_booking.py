"""Booking lifecycle, seat accounting and concurrency."""

import threading
import time
from decimal import Decimal

from django.db import OperationalError, connections
from django.test import TestCase, TransactionTestCase

from bot.models import Booking, Payment, Trip
from bot.services import booking as bk
from bot.services.pnr import PREFIX, generate_pnr, looks_like_pnr
from bot.tests.factories import make_fare_slabs, make_line, make_trip


class BookingServiceTests(TestCase):
    def setUp(self):
        make_fare_slabs()
        self.up, self.down, self.stops = make_line(spacing=Decimal("4.00"))
        self.a, self.b, self.c, self.d = self.stops
        self.trip = make_trip(self.up, seats=10)
        self.profile = bk.get_or_create_profile("+919000000001", "Test Rider")

    def _book(self, seats=1, origin=None, destination=None):
        return bk.create_booking(
            profile=self.profile,
            trip_id=self.trip.id,
            origin_id=(origin or self.a).id,
            destination_id=(destination or self.c).id,
            seats=seats,
        )

    def test_booking_freezes_price_at_purchase_time(self):
        booking = self._book(seats=2)
        self.assertEqual(booking.distance_km, Decimal("8.00"))
        self.assertEqual(booking.fare_per_seat, 15)
        self.assertEqual(booking.total_fare, 30)

        # Repricing the network must not alter a sold ticket.
        from bot.models import FareSlab
        from bot.services.fares import invalidate_cache

        FareSlab.objects.filter(min_km=Decimal("6")).update(price=Decimal("99"))
        invalidate_cache()
        booking.refresh_from_db()
        self.assertEqual(booking.total_fare, 30)

    def test_booking_creates_passengers_and_payment(self):
        booking = self._book(seats=3)
        self.assertEqual(booking.passengers.count(), 3)
        self.assertEqual(booking.payment.amount, booking.total_fare)
        self.assertEqual(booking.payment.status, Payment.Status.PENDING)

    def test_seats_are_deducted_from_the_trip(self):
        self._book(seats=4)
        self.trip.refresh_from_db()
        self.assertEqual(self.trip.seats_booked, 4)
        self.assertEqual(self.trip.seats_left, 6)

    def test_overselling_is_refused(self):
        self._book(seats=8)
        with self.assertRaises(bk.SeatsUnavailable):
            self._book(seats=5)
        self.trip.refresh_from_db()
        self.assertEqual(self.trip.seats_booked, 8)

    def test_booking_exactly_to_capacity_is_allowed(self):
        self._book(seats=10)
        self.trip.refresh_from_db()
        self.assertEqual(self.trip.seats_booked, 10)
        with self.assertRaises(bk.SeatsUnavailable):
            self._book(seats=1)

    def test_journey_not_served_by_the_trip_is_refused(self):
        # C → A is the reverse direction; this trip runs A → D.
        with self.assertRaises(bk.NoRouteBetweenStops):
            self._book(origin=self.c, destination=self.a)

    def test_zero_seats_is_refused(self):
        with self.assertRaises(bk.BookingError):
            self._book(seats=0)

    def test_cancelling_returns_the_seats(self):
        booking = self._book(seats=3)
        bk.cancel_booking(booking)
        self.trip.refresh_from_db()
        self.assertEqual(self.trip.seats_booked, 0)
        booking.refresh_from_db()
        self.assertEqual(booking.status, Booking.Status.CANCELLED)

    def test_double_cancel_does_not_release_seats_twice(self):
        booking = self._book(seats=3)
        bk.cancel_booking(booking)
        with self.assertRaises(bk.BookingError):
            bk.cancel_booking(booking)
        self.trip.refresh_from_db()
        self.assertEqual(self.trip.seats_booked, 0)

    def test_pnr_lookup_is_scoped_to_the_owning_number(self):
        booking = self._book()
        self.assertIsNotNone(bk.lookup_by_pnr(booking.pnr, "+919000000001"))
        # Someone else guessing the PNR gets nothing.
        self.assertIsNone(bk.lookup_by_pnr(booking.pnr, "+919999999999"))

    def test_expiring_stale_pending_releases_seats(self):
        booking = bk.create_booking(
            profile=self.profile, trip_id=self.trip.id,
            origin_id=self.a.id, destination_id=self.c.id, seats=2,
            status=Booking.Status.PENDING,
        )
        Booking.objects.filter(pk=booking.pk).update(
            created_at=booking.created_at.replace(year=booking.created_at.year - 1)
        )
        released = bk.expire_stale_pending(minutes=10)
        self.assertEqual(released, 1)
        self.trip.refresh_from_db()
        self.assertEqual(self.trip.seats_booked, 0)


class PNRTests(TestCase):
    def test_pnr_shape_and_alphabet(self):
        pnr = generate_pnr()
        self.assertTrue(pnr.startswith(PREFIX))
        self.assertEqual(len(pnr), 8)
        # No glyph-ambiguous characters in the random part — these get read
        # aloud to a conductor. (The fixed "IB" prefix is exempt: it is never
        # a source of ambiguity because it is always the same two letters.)
        self.assertFalse(set("01OIL") & set(pnr[len(PREFIX):]))

    def test_pnrs_are_unique_across_many_draws(self):
        self.assertEqual(len({generate_pnr() for _ in range(200)}), 200)

    def test_looks_like_pnr_validation(self):
        self.assertTrue(looks_like_pnr("IB7K4Q2M"))
        self.assertTrue(looks_like_pnr(" ib7k4q2m "))
        self.assertFalse(looks_like_pnr("IB7K4Q2"))     # too short
        self.assertFalse(looks_like_pnr("XX7K4Q2M"))    # wrong prefix
        self.assertFalse(looks_like_pnr("IB7K4Q2O"))    # O is not in the alphabet


class SeatConcurrencyTests(TransactionTestCase):
    """The oversell guard under genuinely parallel writers.

    TransactionTestCase (not TestCase) because each thread needs its own real
    transaction rather than a shared wrapping one.
    """

    def setUp(self):
        make_fare_slabs()
        self.up, _, self.stops = make_line(spacing=Decimal("4.00"))
        self.trip = make_trip(self.up, seats=10)
        self.profile = bk.get_or_create_profile("+919000000002", "Racer")

    def test_reserve_seats_refuses_when_short(self):
        """The conditional UPDATE itself, deterministically.

        This is the guard that makes the threaded test below meaningful: it
        proves the WHERE predicate — not application-level checking — is what
        refuses the write.
        """
        self.assertTrue(bk._reserve_seats(self.trip.id, 10))
        self.trip.refresh_from_db()
        self.assertEqual(self.trip.seats_booked, 10)

        self.assertFalse(bk._reserve_seats(self.trip.id, 1))
        self.trip.refresh_from_db()
        self.assertEqual(self.trip.seats_booked, 10)

    def test_parallel_bookings_never_oversell(self):
        seats_total = self.trip.total_seats          # 10
        attempts = 30
        sold_out, locked, succeeded = [], [], []
        barrier = threading.Barrier(attempts)

        def book():
            try:
                barrier.wait(timeout=10)
                # SQLite serializes writers, so a busy-timeout loss is a
                # platform artifact, not an oversell. Retry those so the seat
                # guard — not the lock — decides the outcome.
                for attempt in range(40):
                    try:
                        bk.create_booking(
                            profile=self.profile,
                            trip_id=self.trip.id,
                            origin_id=self.stops[0].id,
                            destination_id=self.stops[2].id,
                            seats=1,
                        )
                        succeeded.append(1)
                        return
                    except bk.SeatsUnavailable:
                        sold_out.append(1)
                        return
                    except OperationalError:
                        time.sleep(min(0.02 * (attempt + 1), 0.25))
                locked.append(1)
            finally:
                connections.close_all()

        threads = [threading.Thread(target=book) for _ in range(attempts)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=60)

        self.trip.refresh_from_db()
        confirmed = Booking.objects.filter(
            trip=self.trip, status=Booking.Status.CONFIRMED
        ).count()

        # The invariant: capacity is never exceeded, and the counter agrees
        # with the bookings actually written.
        self.assertLessEqual(self.trip.seats_booked, seats_total)
        self.assertEqual(self.trip.seats_booked, len(succeeded))
        self.assertEqual(confirmed, len(succeeded))
        self.assertEqual(len(succeeded) + len(sold_out) + len(locked), attempts)

        # With 30 racers for 10 seats, every seat should sell and the excess
        # must be refused by the guard. If this is ever short, the reservation
        # is losing writes rather than serializing them.
        self.assertEqual(len(locked), 0, "writers starved on the busy timeout")
        self.assertEqual(len(succeeded), seats_total)
        self.assertEqual(len(sold_out), attempts - seats_total)
