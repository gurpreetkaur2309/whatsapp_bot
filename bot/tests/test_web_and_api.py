"""HTTP surface: website views, REST API and the Twilio webhook."""

from decimal import Decimal

from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from bot.models import Booking, MessageLog
from bot.services import booking as bk
from bot.tests.factories import make_fare_slabs, make_line, make_trip


class WebsiteTests(TestCase):
    def setUp(self):
        make_fare_slabs()
        self.up, _, self.stops = make_line(
            names=("Palasia", "Vijay Nagar", "Niranjanpur", "Rajwada"), spacing=Decimal("4.00")
        )
        self.trip = make_trip(self.up, seats=10, hours_ahead=5)
        self.client = Client()

    def test_home_renders(self):
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Indore iBus")

    def test_search_without_params_shows_the_form(self):
        response = self.client.get(reverse("search"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Select boarding stop")

    def test_search_lists_departures(self):
        response = self.client.get(
            reverse("search"),
            {
                "origin": self.stops[0].id,
                "destination": self.stops[1].id,
                "date": timezone.localdate().isoformat(),
                "seats": 1,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.trip.route.code)

    def test_search_reports_unconnected_stops_without_crashing(self):
        from bot.models import Stop

        island = Stop.objects.create(name="Island", code="ISL")
        response = self.client.get(
            reverse("search"), {"origin": self.stops[0].id, "destination": island.id}
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No direct bus")

    def test_identical_origin_and_destination_is_rejected(self):
        response = self.client.get(
            reverse("search"), {"origin": self.stops[0].id, "destination": self.stops[0].id}
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Select</button>")

    def test_checkout_books_and_redirects_to_the_ticket(self):
        response = self.client.post(
            reverse("checkout"),
            {
                "trip_id": self.trip.id,
                "origin": self.stops[0].id,
                "destination": self.stops[1].id,
                "seats": 2,
                "passenger_name": "Asha Verma",
                "whatsapp_number": "+919876500123",
                "confirm": "1",
            },
        )
        booking = Booking.objects.get()
        self.assertRedirects(response, reverse("ticket", args=[booking.pnr]))
        self.assertEqual(booking.seat_count, 2)
        self.assertEqual(booking.channel, Booking.Channel.WEB)
        self.assertEqual(booking.total_fare, 20)

    def test_ticket_page_shows_the_pnr(self):
        booking = self._make_booking()
        response = self.client.get(reverse("ticket", args=[booking.pnr]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, booking.pnr)

    def test_unknown_pnr_is_a_404_not_a_500(self):
        self.assertEqual(self.client.get(reverse("ticket", args=["IBZZZZZZ"])).status_code, 404)

    def test_ticket_qr_returns_a_png(self):
        booking = self._make_booking()
        response = self.client.get(reverse("ticket_qr", args=[booking.pnr]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "image/png")
        self.assertTrue(response.content.startswith(b"\x89PNG"))

    def test_my_tickets_requires_login(self):
        response = self.client.get(reverse("my_tickets"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response["Location"])

    def test_registration_creates_a_user_and_links_the_profile(self):
        response = self.client.post(
            reverse("register"),
            {
                "username": "newrider",
                "password1": "a-strong-passphrase-42",
                "password2": "a-strong-passphrase-42",
                "whatsapp_number": "9876500999",
            },
        )
        self.assertRedirects(response, reverse("home"))
        user = User.objects.get(username="newrider")
        self.assertEqual(user.passenger_profile.whatsapp_number, "+919876500999")

    def test_registration_rejects_a_weak_password(self):
        self.client.post(
            reverse("register"),
            {"username": "weak", "password1": "123", "password2": "123"},
        )
        self.assertFalse(User.objects.filter(username="weak").exists())

    def test_login_page_renders(self):
        self.assertEqual(self.client.get(reverse("login")).status_code, 200)

    def test_routes_page_lists_routes(self):
        response = self.client.get(reverse("routes"))
        self.assertContains(response, self.up.code)

    def test_pnr_lookup_finds_a_ticket(self):
        booking = self._make_booking()
        response = self.client.get(reverse("pnr_lookup"), {"pnr": booking.pnr})
        self.assertContains(response, booking.pnr)

    def _make_booking(self, seats=1):
        profile = bk.get_or_create_profile("+919876500123", "Asha")
        return bk.create_booking(
            profile=profile,
            trip_id=self.trip.id,
            origin_id=self.stops[0].id,
            destination_id=self.stops[1].id,
            seats=seats,
            channel=Booking.Channel.WEB,
        )


class ApiTests(TestCase):
    def setUp(self):
        make_fare_slabs()
        self.up, _, self.stops = make_line(spacing=Decimal("4.00"))
        self.trip = make_trip(self.up, seats=10, hours_ahead=5)

    def test_stop_list_and_search(self):
        response = self.client.get("/api/stops/", {"q": "a"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("results", response.json())

    def test_fare_endpoint(self):
        response = self.client.get(
            "/api/fare/", {"origin": self.stops[0].id, "destination": self.stops[2].id}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["distance_km"], "8.00")
        self.assertEqual(response.json()["fare_per_seat"], "15.00")

    def test_fare_requires_both_stops(self):
        self.assertEqual(self.client.get("/api/fare/", {"origin": 1}).status_code, 400)

    def test_fare_404s_for_unconnected_stops(self):
        from bot.models import Stop

        island = Stop.objects.create(name="Island", code="ISL")
        response = self.client.get(
            "/api/fare/", {"origin": self.stops[0].id, "destination": island.id}
        )
        self.assertEqual(response.status_code, 404)

    def test_trip_search_returns_options(self):
        response = self.client.get(
            "/api/trips/",
            {
                "origin": self.stops[0].id,
                "destination": self.stops[2].id,
                "date": timezone.localdate().isoformat(),
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(response.json()["count"], 1)

    def test_trip_search_rejects_a_bad_date(self):
        response = self.client.get(
            "/api/trips/",
            {"origin": self.stops[0].id, "destination": self.stops[2].id, "date": "not-a-date"},
        )
        self.assertEqual(response.status_code, 400)

    def test_api_booking_creates_a_ticket(self):
        response = self.client.post(
            "/api/bookings/create/",
            {
                "trip_id": self.trip.id,
                "origin_id": self.stops[0].id,
                "destination_id": self.stops[2].id,
                "seats": 2,
                "whatsapp_number": "+919000004444",
                "passenger_name": "API Rider",
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["seat_count"], 2)
        self.assertEqual(Booking.objects.count(), 1)

    def test_api_booking_conflicts_when_sold_out(self):
        from bot.models import Trip

        Trip.objects.filter(pk=self.trip.id).update(seats_booked=10)
        response = self.client.post(
            "/api/bookings/create/",
            {
                "trip_id": self.trip.id,
                "origin_id": self.stops[0].id,
                "destination_id": self.stops[2].id,
                "seats": 1,
                "whatsapp_number": "+919000004444",
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 409)

    def test_booking_lookup_is_scoped_by_number(self):
        booking = bk.create_booking(
            profile=bk.get_or_create_profile("+919000005555"),
            trip_id=self.trip.id,
            origin_id=self.stops[0].id,
            destination_id=self.stops[2].id,
            seats=1,
        )
        ok = self.client.get(f"/api/bookings/{booking.pnr}/", {"whatsapp_number": "+919000005555"})
        self.assertEqual(ok.status_code, 200)
        # An anonymous caller without the number gets nothing.
        self.assertEqual(self.client.get(f"/api/bookings/{booking.pnr}/").status_code, 404)


@override_settings(TWILIO_VALIDATE_SIGNATURE=False)
class WebhookTests(TestCase):
    URL = "/webhook/whatsapp/"

    def setUp(self):
        make_fare_slabs()
        self.up, _, self.stops = make_line(
            names=("Palasia", "Vijay Nagar", "Niranjanpur", "Rajwada"), spacing=Decimal("4.00")
        )
        self.trip = make_trip(self.up, seats=10, hours_ahead=5)

    def post(self, body, sid="SM1", number="whatsapp:+919000007777"):
        return self.client.post(
            self.URL, {"From": number, "Body": body, "MessageSid": sid, "ProfileName": "Rider"}
        )

    def test_webhook_returns_twiml(self):
        response = self.post("hi")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/xml")
        self.assertIn("<Response>", response.content.decode())
        self.assertIn("Indore iBus", response.content.decode())

    def test_get_is_not_allowed(self):
        self.assertEqual(self.client.get(self.URL).status_code, 405)

    def test_duplicate_message_sid_is_ignored(self):
        """Twilio retries on timeout; a retry must not run the turn twice."""
        self.post("hi", sid="SMDUP")
        first = MessageLog.objects.filter(direction="IN").count()
        self.post("hi", sid="SMDUP")
        self.assertEqual(MessageLog.objects.filter(direction="IN").count(), first)

    def test_messages_are_logged_both_ways(self):
        self.post("hi", sid="SMLOG")
        self.assertTrue(MessageLog.objects.filter(direction="IN", twilio_sid="SMLOG").exists())
        self.assertTrue(MessageLog.objects.filter(direction="OUT", twilio_sid="SMLOG").exists())

    def test_full_booking_over_the_webhook(self):
        script = ["hi", "1", "palasia", "vijay nagar", "1", "1", "1", "Asha", "yes"]
        for i, message in enumerate(script):
            response = self.post(message, sid=f"SM{i}")
            self.assertEqual(response.status_code, 200)

        booking = Booking.objects.get()
        self.assertEqual(booking.status, Booking.Status.CONFIRMED)
        self.assertEqual(booking.whatsapp_number, "+919000007777")
        self.assertIn(booking.pnr, response.content.decode())

    def test_empty_from_is_handled(self):
        response = self.client.post(self.URL, {"From": "", "Body": "hi", "MessageSid": "SMX"})
        self.assertEqual(response.status_code, 200)


class WebhookSignatureTests(TestCase):
    @override_settings(TWILIO_VALIDATE_SIGNATURE=True, TWILIO_AUTH_TOKEN="")
    def test_unsigned_request_is_rejected(self):
        response = self.client.post(
            "/webhook/whatsapp/", {"From": "whatsapp:+911", "Body": "hi", "MessageSid": "S1"}
        )
        self.assertEqual(response.status_code, 403)
