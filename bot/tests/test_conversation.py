"""The conversation FSM, driven directly — no Twilio, no HTTP, no mocks."""

import datetime as dt
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from bot.conversation.machine import dispatch, get_session
from bot.conversation.render import SPLIT_LIMIT, paginate, split_message
from bot.conversation.states import ALLOWED_TRANSITIONS, State
from bot.models import Booking, Stop
from bot.services.booking import get_or_create_profile
from bot.tests.factories import make_fare_slabs, make_line, make_trip

NUMBER = "+919000000010"


class ConversationTestCase(TestCase):
    def setUp(self):
        make_fare_slabs()
        self.up, self.down, self.stops = make_line(
            names=("Palasia", "Vijay Nagar", "Niranjanpur", "Rajwada"),
            spacing=Decimal("4.00"),
        )
        self.trip = make_trip(self.up, seats=10, hours_ahead=4)
        self.session = get_session(NUMBER)
        self.session.profile = get_or_create_profile(NUMBER)
        self.session.save()

    def say(self, text):
        self.session.refresh_from_db()
        return dispatch(self.session, text)

    def run_script(self, *messages):
        return [self.say(m) for m in messages]


class BookingFlowTests(ConversationTestCase):
    def test_full_booking_issues_a_ticket(self):
        self.run_script("hi", "1", "palasia", "vijay nagar", "1", "1", "2", "Asha")
        reply = self.say("yes")

        booking = Booking.objects.get()
        self.assertEqual(booking.status, Booking.Status.CONFIRMED)
        self.assertEqual(booking.seat_count, 2)
        self.assertEqual(booking.origin.name, "Palasia")
        self.assertEqual(booking.destination.name, "Vijay Nagar")
        self.assertEqual(booking.total_fare, 20)          # 4 km → ₹10 × 2
        self.assertEqual(booking.channel, Booking.Channel.WHATSAPP)
        self.assertIn(booking.pnr, reply.text)
        self.assertEqual(reply.state, State.MAIN_MENU)

        self.trip.refresh_from_db()
        self.assertEqual(self.trip.seats_booked, 2)

    def test_abbreviated_stop_name_resolves(self):
        self.run_script("hi", "1", "palasia")
        reply = self.say("vijay ngr")
        self.assertEqual(reply.state, State.ASK_DATE)

    def test_declining_at_confirm_books_nothing(self):
        self.run_script("hi", "1", "palasia", "vijay nagar", "1", "1", "1", "Asha")
        reply = self.say("no")
        self.assertEqual(Booking.objects.count(), 0)
        self.assertEqual(reply.state, State.MAIN_MENU)
        self.trip.refresh_from_db()
        self.assertEqual(self.trip.seats_booked, 0)

    def test_same_origin_and_destination_is_rejected(self):
        self.run_script("hi", "1", "palasia")
        reply = self.say("palasia")
        self.assertEqual(reply.state, State.ASK_DESTINATION)
        self.assertIn("same stop", reply.text.lower())

    def test_unconnected_journey_is_reported_not_crashed(self):
        Stop.objects.create(name="Island", code="ISL")
        self.run_script("hi", "1", "palasia")
        reply = self.say("island")
        self.assertIn("no direct bus", reply.text.lower())
        self.assertEqual(reply.state, State.MAIN_MENU)

    def test_seat_count_beyond_capacity_is_rejected(self):
        self.run_script("hi", "1", "palasia", "vijay nagar", "1", "1")
        reply = self.say("99")
        self.assertEqual(reply.state, State.ASK_SEATS)
        self.assertEqual(Booking.objects.count(), 0)

    def test_remembered_name_skips_the_name_question(self):
        self.run_script("hi", "1", "palasia", "vijay nagar", "1", "1", "1", "Asha", "yes")
        # Second booking: the profile now has a name.
        self.run_script("menu", "1", "palasia", "vijay nagar", "1", "1", "1")
        self.session.refresh_from_db()
        self.assertEqual(self.session.state, State.CONFIRM)


class GlobalCommandTests(ConversationTestCase):
    def test_menu_resets_from_anywhere(self):
        self.run_script("hi", "1", "palasia")
        reply = self.say("menu")
        self.assertEqual(reply.state, State.MAIN_MENU)
        self.session.refresh_from_db()
        self.assertEqual(self.session.context, {})

    def test_back_returns_to_the_previous_question(self):
        self.run_script("hi", "1", "palasia")
        reply = self.say("back")
        self.assertEqual(reply.state, State.ASK_ORIGIN)

    def test_back_also_discards_the_stale_context(self):
        self.run_script("hi", "1", "palasia")
        self.say("back")
        self.session.refresh_from_db()
        self.assertNotIn("origin_id", self.session.context)

    def test_help_does_not_change_state(self):
        self.run_script("hi", "1", "palasia")
        reply = self.say("help")
        self.assertEqual(reply.state, State.ASK_DESTINATION)

    def test_cancel_abandons_the_flow(self):
        self.run_script("hi", "1", "palasia", "vijay nagar")
        reply = self.say("cancel")
        self.assertEqual(reply.state, State.MAIN_MENU)

    def test_back_at_the_start_falls_through_to_the_menu(self):
        self.say("hi")
        reply = self.say("back")
        self.assertEqual(reply.state, State.MAIN_MENU)


class InvalidInputTests(ConversationTestCase):
    def test_substring_digit_does_not_trigger_a_menu_option(self):
        """The old bot matched `"1" in message`, so "seat 21" started a booking."""
        self.say("hi")
        reply = self.say("seat 21")
        self.assertEqual(reply.state, State.MAIN_MENU)
        self.assertIn("didn't catch that", reply.text.lower())

    def test_repeated_invalid_input_eventually_resets(self):
        self.say("hi")
        for _ in range(5):
            reply = self.say("!!!")
        self.assertEqual(reply.state, State.MAIN_MENU)
        self.session.refresh_from_db()
        self.assertEqual(self.session.retry_count, 0)

    def test_retry_counter_resets_after_success(self):
        self.run_script("hi", "???", "???")
        self.say("1")
        self.session.refresh_from_db()
        self.assertEqual(self.session.retry_count, 0)

    def test_unknown_stop_keeps_the_user_in_place(self):
        self.run_script("hi", "1")
        reply = self.say("qwertyuiop")
        self.assertEqual(reply.state, State.ASK_ORIGIN)


class TicketManagementTests(ConversationTestCase):
    def _book(self):
        self.run_script("hi", "1", "palasia", "vijay nagar", "1", "1", "1", "Asha", "yes")
        return Booking.objects.get()

    def test_my_tickets_lists_a_booking(self):
        booking = self._book()
        reply = self.run_script("menu", "2")[-1]
        self.assertIn(booking.pnr, reply.text)

    def test_my_tickets_is_empty_not_broken_for_a_new_user(self):
        """The old bot indexed bookings[1] and bookings[2] — an IndexError 500."""
        reply = self.run_script("hi", "2")[-1]
        self.assertIn("no tickets", reply.text.lower())
        self.assertEqual(reply.state, State.MAIN_MENU)

    def test_cancelling_a_ticket_releases_seats(self):
        booking = self._book()
        self.run_script("menu", "3", booking.pnr)
        reply = self.say("confirm")
        booking.refresh_from_db()
        self.assertEqual(booking.status, Booking.Status.CANCELLED)
        self.assertIn("cancelled", reply.text.lower())
        self.trip.refresh_from_db()
        self.assertEqual(self.trip.seats_booked, 0)

    def test_keeping_a_ticket_at_the_cancel_prompt(self):
        booking = self._book()
        self.run_script("menu", "3", booking.pnr)
        self.say("no")
        booking.refresh_from_db()
        self.assertEqual(booking.status, Booking.Status.CONFIRMED)

    def test_another_users_pnr_is_not_readable(self):
        booking = self._book()
        other = get_session("+919000000099")
        other.profile = get_or_create_profile("+919000000099")
        other.save()
        dispatch(other, "hi")
        reply = dispatch(other, booking.pnr)
        self.assertNotIn(booking.origin.name, reply.text)

    def test_bare_pnr_at_the_menu_shows_the_ticket(self):
        booking = self._book()
        reply = self.run_script("menu", booking.pnr)[-1]
        self.assertIn(booking.pnr, reply.text)


class FareEnquiryTests(ConversationTestCase):
    def test_fare_enquiry_quotes_without_booking(self):
        reply = self.run_script("hi", "4", "palasia", "niranjanpur")[-1]
        self.assertIn("15", reply.text)          # 8 km → ₹15
        self.assertEqual(reply.state, State.MAIN_MENU)
        self.assertEqual(Booking.objects.count(), 0)


class SessionExpiryTests(ConversationTestCase):
    def test_expired_session_restarts_cleanly(self):
        self.run_script("hi", "1", "palasia")
        self.session.refresh_from_db()
        self.session.expires_at = timezone.now() - dt.timedelta(minutes=1)
        self.session.save()

        reply = self.say("vijay nagar")
        self.assertIn("expired", reply.text.lower())
        self.assertEqual(reply.state, State.MAIN_MENU)


class BrowseStopsTests(ConversationTestCase):
    def test_list_paginates_and_selects(self):
        self.run_script("hi", "1")
        reply = self.say("LIST")
        self.assertEqual(reply.state, State.BROWSE_STOPS)
        reply = self.say("1")
        self.assertEqual(reply.state, State.ASK_DESTINATION)


class RenderTests(TestCase):
    def test_pagination_reports_more_pages(self):
        items = list(range(25))
        page, has_more, total = paginate(items, page=1, per_page=10)
        self.assertEqual(len(page), 10)
        self.assertTrue(has_more)
        self.assertEqual(total, 3)

        page, has_more, _ = paginate(items, page=3, per_page=10)
        self.assertEqual(len(page), 5)
        self.assertFalse(has_more)

    def test_out_of_range_page_is_clamped(self):
        page, _, _ = paginate(list(range(5)), page=99, per_page=10)
        self.assertEqual(len(page), 5)

    def test_short_messages_are_not_split(self):
        self.assertEqual(split_message("hello"), ["hello"])

    def test_long_messages_are_split_below_the_twilio_limit(self):
        body = "\n".join(f"line {i} " + "x" * 60 for i in range(200))
        parts = split_message(body)
        self.assertGreater(len(parts), 1)
        for part in parts:
            self.assertLessEqual(len(part), SPLIT_LIMIT)

    def test_a_single_unbroken_run_is_still_split(self):
        parts = split_message("y" * 5000)
        self.assertGreater(len(parts), 1)
        for part in parts:
            self.assertLessEqual(len(part), SPLIT_LIMIT)


class StateTableTests(TestCase):
    def test_every_transition_target_is_a_real_state(self):
        from bot.conversation.states import ALL_STATES

        for source, targets in ALLOWED_TRANSITIONS.items():
            self.assertIn(source, ALL_STATES)
            for target in targets:
                self.assertIn(target, ALL_STATES, f"{source} → {target}")

    def test_every_handler_maps_to_a_real_state(self):
        from bot.conversation.machine import _HANDLERS
        from bot.conversation.states import ALL_STATES

        for state in _HANDLERS:
            self.assertIn(state, ALL_STATES)
