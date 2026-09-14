"""The conversation engine.

``dispatch(session, text) -> Reply`` is a pure function of (database state,
session, text). It imports nothing from Twilio and knows nothing about HTTP, so
every FSM test is a direct call with no mocks and no credentials.
"""

import datetime as dt
import logging
from dataclasses import dataclass, field
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from bot.conversation import render
from bot.conversation.states import Flow, State
from bot.models import Booking, ConversationSession, Stop
from bot.services import booking as booking_service
from bot.services import matching, network
from bot.services.pnr import looks_like_pnr

log = logging.getLogger("bot")

MAX_SEATS = 6
MAX_RETRIES = 3
RESET_RETRIES = 5


@dataclass
class Reply:
    messages: list[str] = field(default_factory=list)
    state: str = State.MAIN_MENU

    @property
    def text(self) -> str:
        return "\n\n".join(self.messages)


# ---------------------------------------------------------------------------
# Session helpers
# ---------------------------------------------------------------------------


def get_session(whatsapp_number: str) -> ConversationSession:
    session, _ = ConversationSession.objects.get_or_create(
        whatsapp_number=whatsapp_number,
        defaults={"state": State.IDLE, "context": {}, "history": []},
    )
    return session


def _touch(session: ConversationSession) -> None:
    session.expires_at = timezone.now() + timedelta(minutes=settings.SESSION_IDLE_MINUTES)


def _goto(session, state: str, *, push_history: bool = True) -> None:
    if push_history and session.state != state:
        history = list(session.history or [])
        # Snapshot the state *and* the context as they were on entry to this
        # step — captured in dispatch() before the handler ran. Using the
        # current context instead would record the answer the user just gave,
        # so BACK would return to the question with it already filled in.
        history.append(
            {
                "state": session.state,
                "context": getattr(session, "_entry_context", dict(session.context or {})),
            }
        )
        session.history = history[-10:]
    session.state = state
    session.retry_count = 0


def _reset(session) -> None:
    session.state = State.MAIN_MENU
    session.context = {}
    session.history = []
    session.retry_count = 0


def _save(session) -> None:
    _touch(session)
    session.save()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def dispatch(session: ConversationSession, text: str) -> Reply:
    """Advance the conversation by one message."""
    raw = (text or "").strip()
    upper = raw.upper()
    prefix: list[str] = []

    if session.is_expired() and session.state != State.IDLE:
        _release_pending(session)
        _reset(session)
        prefix.append(render.session_expired())

    # Global commands run before any state handler.
    if upper in ("MENU", "0", "START"):
        _reset(session)
        reply = Reply(prefix + [render.main_menu()], State.MAIN_MENU)
        return _finish(session, reply)

    if upper in ("HELP", "?"):
        # Stays in the current state — a help request is not a transition.
        reply = Reply(prefix + [render.help_text()], session.state)
        return _finish(session, reply)

    if upper in ("CANCEL", "X"):
        _release_pending(session)
        _reset(session)
        reply = Reply(prefix + ["Booking cancelled.", render.main_menu()], State.MAIN_MENU)
        return _finish(session, reply)

    if upper in ("BACK", "#"):
        return _finish(session, _go_back(session, prefix))

    if session.state in (State.IDLE, "") or upper in ("HI", "HELLO", "HEY", "NAMASTE"):
        name = session.profile.display_name if session.profile else ""
        _reset(session)
        reply = Reply(prefix + [render.greeting(name), render.main_menu()], State.MAIN_MENU)
        return _finish(session, reply)

    # Snapshot before the handler mutates anything, so _goto can record what
    # this step looked like when the user arrived at it.
    session._entry_context = dict(session.context or {})

    handler = _HANDLERS.get(session.state, _handle_main_menu)
    reply = handler(session, raw)
    reply.messages = prefix + reply.messages
    return _finish(session, reply)


def _finish(session, reply: Reply) -> Reply:
    reply.state = session.state
    _save(session)
    return reply


def _go_back(session, prefix: list[str]) -> Reply:
    history = list(session.history or [])
    if not history:
        _reset(session)
        return Reply(prefix + [render.main_menu()], State.MAIN_MENU)

    previous = history.pop()
    session.history = history
    session.state = previous["state"]
    session.context = previous["context"]
    session.retry_count = 0
    return Reply(prefix + [_prompt_for(session)], session.state)


def _release_pending(session) -> None:
    """Give back seats held by an unconfirmed booking from this session."""
    pending_id = (session.context or {}).get("pending_booking_id")
    if not pending_id:
        return
    pending = Booking.objects.filter(pk=pending_id, status=Booking.Status.PENDING).first()
    if pending:
        try:
            booking_service.cancel_booking(pending)
        except booking_service.BookingError:
            pass


def _retry(session, hint: str = "") -> Reply:
    """Re-prompt after unparseable input, with an escape hatch."""
    session.retry_count += 1
    if session.retry_count >= RESET_RETRIES:
        _reset(session)
        return Reply(["Let's start over.", render.main_menu()], State.MAIN_MENU)

    messages = [render.invalid(hint)]
    if session.retry_count >= MAX_RETRIES:
        messages.append(render.help_text())
    messages.append(_prompt_for(session))
    return Reply(messages, session.state)


def _prompt_for(session) -> str:
    """Re-render the current state's question."""
    ctx = session.context or {}
    state = session.state

    if state == State.MAIN_MENU:
        return render.main_menu()
    if state == State.ASK_ORIGIN:
        return render.ask_origin()
    if state == State.ASK_DESTINATION:
        return render.ask_destination(_stop_name(ctx.get("origin_id")))
    if state in (State.PICK_ORIGIN, State.PICK_DESTINATION, State.BROWSE_STOPS):
        options = ctx.get("options") or []
        stops = _stops_from_options(options)
        prompt = "📍 Which stop did you mean?"
        return render.stop_picker(prompt, stops, bool(ctx.get("has_more")))
    if state == State.ASK_DATE:
        return render.ask_date()
    if state == State.ASK_TRIP:
        return _render_trips(session)
    if state == State.ASK_SEATS:
        return render.ask_seats(MAX_SEATS)
    if state == State.ASK_NAME:
        return render.ask_name()
    if state == State.CONFIRM:
        return _render_confirm(session)
    if state == State.ASK_PNR:
        return render.ask_pnr(ctx.get("pnr_action", "view"))
    if state == State.CONFIRM_CANCEL:
        b = Booking.objects.filter(pk=ctx.get("cancel_booking_id")).first()
        return render.confirm_cancel(b) if b else render.ask_pnr("cancel")
    return render.main_menu()


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------


def _handle_main_menu(session, text: str) -> Reply:
    choice = text.strip().lower()
    ctx = {}

    if choice in ("1", "book", "book ticket", "book a ticket"):
        session.context = {"flow": Flow.BOOK}
        _goto(session, State.ASK_ORIGIN)
        return Reply([render.ask_origin()], session.state)

    if choice in ("2", "my tickets", "tickets"):
        bookings = booking_service.recent_bookings(session.whatsapp_number)
        return Reply([render.my_tickets(bookings), render.main_menu()], State.MAIN_MENU)

    if choice in ("3", "cancel ticket", "cancel booking"):
        session.context = {"pnr_action": "cancel"}
        _goto(session, State.ASK_PNR)
        return Reply([render.ask_pnr("cancel")], session.state)

    if choice in ("4", "fare", "check fare", "check a fare"):
        session.context = {"flow": Flow.FARE}
        _goto(session, State.ASK_ORIGIN)
        return Reply([render.ask_origin()], session.state)

    if choice in ("5", "stops", "browse stops", "list"):
        session.context = {**ctx, "page": 1}
        _goto(session, State.BROWSE_STOPS)
        return Reply([_render_stop_page(session, 1)], session.state)

    # A bare PNR at the menu is a ticket lookup — a common shortcut.
    if looks_like_pnr(text):
        return _show_ticket(session, text)

    return _retry(session, "Reply with a number from 1 to 5.")


def _handle_ask_stop(session, text: str, *, is_origin: bool) -> Reply:
    if text.strip().upper() in ("LIST", "STOPS"):
        session.context = {**session.context, "page": 1, "picking": "origin" if is_origin else "destination"}
        _goto(session, State.BROWSE_STOPS)
        return Reply([_render_stop_page(session, 1)], session.state)

    result = matching.resolve(text)

    if result.resolved:
        return _accept_stop(session, result.stop, is_origin=is_origin)

    if result.candidates:
        session.context = {
            **session.context,
            "options": [{"n": i, "id": s.id, "label": s.name}
                        for i, s in enumerate(result.candidates, start=1)],
            "has_more": False,
        }
        _goto(session, State.PICK_ORIGIN if is_origin else State.PICK_DESTINATION)
        return Reply(
            [render.stop_picker("📍 Which stop did you mean?", result.candidates)],
            session.state,
        )

    return _retry(session, "I couldn't find that stop. Try a different spelling, or reply LIST.")


def _handle_ask_origin(session, text):
    return _handle_ask_stop(session, text, is_origin=True)


def _handle_ask_destination(session, text):
    return _handle_ask_stop(session, text, is_origin=False)


def _handle_pick_stop(session, text: str, *, is_origin: bool) -> Reply:
    options = (session.context or {}).get("options") or []
    index = _as_int(text)
    # Resolve against the list actually sent, never a raw DB offset.
    match = next((o for o in options if o["n"] == index), None)
    if match is None:
        return _retry(session, f"Reply with a number from 1 to {len(options)}.")

    stop = Stop.objects.filter(pk=match["id"]).first()
    if stop is None:
        return _retry(session, "That stop is no longer available.")
    return _accept_stop(session, stop, is_origin=is_origin)


def _handle_pick_origin(session, text):
    return _handle_pick_stop(session, text, is_origin=True)


def _handle_pick_destination(session, text):
    return _handle_pick_stop(session, text, is_origin=False)


def _accept_stop(session, stop: Stop, *, is_origin: bool) -> Reply:
    ctx = dict(session.context or {})
    ctx.pop("options", None)
    ctx.pop("has_more", None)

    if is_origin:
        ctx["origin_id"] = stop.id
        session.context = ctx
        _goto(session, State.ASK_DESTINATION)
        return Reply([render.ask_destination(stop.name)], session.state)

    origin_id = ctx.get("origin_id")
    if origin_id == stop.id:
        session.context = ctx
        return _retry(session, "Origin and destination can't be the same stop.")

    ctx["destination_id"] = stop.id
    session.context = ctx

    # Fare enquiry short-circuits here rather than duplicating four states.
    if ctx.get("flow") == Flow.FARE:
        km = network.distance_between(origin_id, stop.id)
        if km is None:
            suggestions = network.connected_stops(origin_id)
            _reset(session)
            return Reply(
                [render.no_route(_stop_name(origin_id), stop.name, suggestions)],
                State.MAIN_MENU,
            )
        from bot.services.fares import fare_for_km

        _reset(session)
        return Reply(
            [render.fare_quote(_stop_name(origin_id), stop.name, km, fare_for_km(km))],
            State.MAIN_MENU,
        )

    if not network.candidate_legs(origin_id, stop.id):
        suggestions = network.connected_stops(origin_id)
        _reset(session)
        return Reply(
            [render.no_route(_stop_name(origin_id), stop.name, suggestions)], State.MAIN_MENU
        )

    _goto(session, State.ASK_DATE)
    return Reply([render.ask_date()], session.state)


def _handle_ask_date(session, text: str) -> Reply:
    today = timezone.localdate()
    choice = text.strip().lower()

    if choice in ("1", "today"):
        service_date = today
    elif choice in ("2", "tomorrow"):
        service_date = today + timedelta(days=1)
    else:
        service_date = _parse_date(text, today)
        if service_date is None:
            return _retry(session, "Reply 1 for today, 2 for tomorrow, or type a date as DD-MM.")
        if service_date < today:
            return _retry(session, "That date has already passed.")

    ctx = dict(session.context)
    ctx["service_date"] = service_date.isoformat()
    session.context = ctx

    options = network.search_trips(
        ctx["origin_id"], ctx["destination_id"], service_date, seats=1
    )
    if not options:
        _reset(session)
        return Reply(
            [render.no_trips(_stop_name(ctx["origin_id"]), _stop_name(ctx["destination_id"]))],
            State.MAIN_MENU,
        )

    ctx["options"] = [
        {
            "n": i,
            "id": o.trip.id,
            "label": f"{timezone.localtime(o.board_at):%H:%M}",
            "fare": str(o.fare_per_seat),
            "km": str(o.distance_km),
            "board_at": o.board_at.isoformat(),
            "route": o.trip.route.code,
            "seats_left": o.seats_left,
        }
        for i, o in enumerate(options, start=1)
    ]
    session.context = ctx
    _goto(session, State.ASK_TRIP)
    return Reply([_render_trips(session)], session.state)


def _handle_ask_trip(session, text: str) -> Reply:
    ctx = dict(session.context)
    options = ctx.get("options") or []
    index = _as_int(text)
    match = next((o for o in options if o["n"] == index), None)
    if match is None:
        return _retry(session, f"Reply with a number from 1 to {len(options)}.")

    ctx["trip_id"] = match["id"]
    ctx["fare_per_seat"] = match["fare"]
    ctx["km"] = match["km"]
    ctx["board_at"] = match["board_at"]
    ctx["route_code"] = match["route"]
    ctx["seats_left"] = match["seats_left"]
    ctx.pop("options", None)
    session.context = ctx
    _goto(session, State.ASK_SEATS)
    return Reply([render.ask_seats(min(MAX_SEATS, match["seats_left"]))], session.state)


def _handle_ask_seats(session, text: str) -> Reply:
    ctx = dict(session.context)
    seats = _as_int(text)
    cap = min(MAX_SEATS, ctx.get("seats_left", MAX_SEATS))
    if seats is None or seats < 1 or seats > cap:
        return _retry(session, f"Reply with a number from 1 to {cap}.")

    ctx["seats"] = seats
    session.context = ctx

    name = session.profile.display_name if session.profile else ""
    if not name:
        _goto(session, State.ASK_NAME)
        return Reply([render.ask_name()], session.state)

    ctx["passenger_name"] = name
    session.context = ctx
    _goto(session, State.CONFIRM)
    return Reply([_render_confirm(session)], session.state)


def _handle_ask_name(session, text: str) -> Reply:
    name = text.strip()
    if len(name) < 2 or len(name) > 60:
        return _retry(session, "Please send a name between 2 and 60 characters.")

    ctx = dict(session.context)
    ctx["passenger_name"] = name
    session.context = ctx

    if session.profile and not session.profile.display_name:
        session.profile.display_name = name
        session.profile.save(update_fields=["display_name"])

    _goto(session, State.CONFIRM)
    return Reply([_render_confirm(session)], session.state)


def _handle_confirm(session, text: str) -> Reply:
    answer = text.strip().lower()
    if answer in ("no", "n", "2"):
        _reset(session)
        return Reply(["No problem — nothing was booked.", render.main_menu()], State.MAIN_MENU)

    if answer not in ("yes", "y", "1", "confirm", "ok"):
        return _retry(session, "Reply YES to confirm or NO to cancel.")

    ctx = dict(session.context)
    profile = session.profile or booking_service.get_or_create_profile(
        session.whatsapp_number, ctx.get("passenger_name", "")
    )
    session.profile = profile

    try:
        booking = booking_service.create_booking(
            profile=profile,
            trip_id=ctx["trip_id"],
            origin_id=ctx["origin_id"],
            destination_id=ctx["destination_id"],
            seats=ctx["seats"],
            passenger_names=[ctx.get("passenger_name", "")] * ctx["seats"],
            channel=Booking.Channel.WHATSAPP,
        )
    except booking_service.SeatsUnavailable:
        _reset(session)
        return Reply(
            ["😕 Those seats were just taken. Please try another bus.", render.main_menu()],
            State.MAIN_MENU,
        )
    except booking_service.BookingError as exc:
        _reset(session)
        return Reply([f"😕 {exc}", render.main_menu()], State.MAIN_MENU)

    _reset(session)
    return Reply([render.ticket(booking)], State.MAIN_MENU)


def _handle_ask_pnr(session, text: str) -> Reply:
    ctx = dict(session.context or {})
    action = ctx.get("pnr_action", "view")

    if text.strip().lower() in ("last", "latest"):
        recent = booking_service.recent_bookings(session.whatsapp_number, limit=1)
        booking = recent[0] if recent else None
    else:
        if not looks_like_pnr(text):
            return _retry(session, "A PNR looks like IB7K4Q2M.")
        booking = booking_service.lookup_by_pnr(text, session.whatsapp_number)

    if booking is None:
        return _retry(session, "I couldn't find a ticket with that PNR on this number.")

    if action == "cancel":
        if not booking.is_active:
            _reset(session)
            return Reply(
                [f"That ticket is already {booking.get_status_display().lower()}.",
                 render.main_menu()],
                State.MAIN_MENU,
            )
        ctx["cancel_booking_id"] = booking.id
        session.context = ctx
        _goto(session, State.CONFIRM_CANCEL)
        return Reply([render.confirm_cancel(booking)], session.state)

    _reset(session)
    return Reply([render.ticket(booking), render.main_menu()], State.MAIN_MENU)


def _handle_confirm_cancel(session, text: str) -> Reply:
    answer = text.strip().lower()
    if answer in ("no", "n"):
        _reset(session)
        return Reply(["Ticket kept.", render.main_menu()], State.MAIN_MENU)
    if answer not in ("confirm", "yes", "y", "1"):
        return _retry(session, "Reply CONFIRM to cancel the ticket, or NO to keep it.")

    booking = Booking.objects.filter(pk=(session.context or {}).get("cancel_booking_id")).first()
    if booking is None:
        _reset(session)
        return Reply(["That ticket is no longer available.", render.main_menu()], State.MAIN_MENU)

    try:
        booking = booking_service.cancel_booking(booking)
    except booking_service.BookingError as exc:
        _reset(session)
        return Reply([f"😕 {exc}", render.main_menu()], State.MAIN_MENU)

    _reset(session)
    return Reply([render.cancelled(booking)], State.MAIN_MENU)


def _handle_browse_stops(session, text: str) -> Reply:
    ctx = dict(session.context or {})
    upper = text.strip().upper()

    if upper == "MORE":
        page = int(ctx.get("page", 1)) + 1
        return Reply([_render_stop_page(session, page)], session.state)

    index = _as_int(text)
    options = ctx.get("options") or []
    match = next((o for o in options if o["n"] == index), None)
    if match:
        stop = Stop.objects.filter(pk=match["id"]).first()
        if stop:
            picking = ctx.get("picking")
            if picking in ("origin", "destination"):
                return _accept_stop(session, stop, is_origin=(picking == "origin"))
            # Browsing outside a booking flow: show what it connects to.
            onward = network.connected_stops(stop.id)
            _reset(session)
            return Reply(
                [render.no_route(stop.name, "…", onward) if onward
                 else f"*{stop.name}* has no onward services.", render.main_menu()],
                State.MAIN_MENU,
            )

    # Anything else: treat as a stop-name search.
    result = matching.resolve(text)
    if result.resolved and ctx.get("picking"):
        return _accept_stop(session, result.stop, is_origin=(ctx["picking"] == "origin"))

    return _retry(session, "Reply with a number, MORE for the next page, or MENU.")


_HANDLERS = {
    State.MAIN_MENU: _handle_main_menu,
    State.ASK_ORIGIN: _handle_ask_origin,
    State.PICK_ORIGIN: _handle_pick_origin,
    State.ASK_DESTINATION: _handle_ask_destination,
    State.PICK_DESTINATION: _handle_pick_destination,
    State.ASK_DATE: _handle_ask_date,
    State.ASK_TRIP: _handle_ask_trip,
    State.ASK_SEATS: _handle_ask_seats,
    State.ASK_NAME: _handle_ask_name,
    State.CONFIRM: _handle_confirm,
    State.ASK_PNR: _handle_ask_pnr,
    State.CONFIRM_CANCEL: _handle_confirm_cancel,
    State.BROWSE_STOPS: _handle_browse_stops,
}


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------


def _as_int(text: str) -> int | None:
    try:
        return int(text.strip())
    except (TypeError, ValueError):
        return None


def _parse_date(text: str, today) -> dt.date | None:
    raw = text.strip().replace("/", "-").replace(".", "-")
    for fmt in ("%d-%m-%Y", "%d-%m-%y", "%d-%m"):
        try:
            parsed = dt.datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
        if fmt == "%d-%m":
            parsed = parsed.replace(year=today.year)
            # "02-01" typed in December means next January.
            if parsed < today:
                parsed = parsed.replace(year=today.year + 1)
        return parsed
    return None


def _stop_name(stop_id) -> str:
    stop = Stop.objects.filter(pk=stop_id).first()
    return stop.name if stop else "—"


def _stops_from_options(options: list) -> list[Stop]:
    ids = [o["id"] for o in options]
    by_id = Stop.objects.in_bulk(ids)
    return [by_id[i] for i in ids if i in by_id]


def _render_stop_page(session, page: int) -> str:
    stops = list(Stop.objects.filter(is_active=True).order_by("name"))
    chunk, has_more, _ = render.paginate(stops, page)
    ctx = dict(session.context or {})
    ctx["page"] = page
    ctx["options"] = [{"n": i, "id": s.id, "label": s.name} for i, s in enumerate(chunk, start=1)]
    ctx["has_more"] = has_more
    session.context = ctx
    return render.stop_picker("🚏 *Indore bus stops*", chunk, has_more)


def _render_trips(session) -> str:
    ctx = session.context or {}
    options = ctx.get("options") or []
    if not options:
        return render.ask_date()

    class _Row:
        """Adapter so render.trip_list works from stored context, not live objects."""

        def __init__(self, opt):
            from types import SimpleNamespace

            self.board_at = dt.datetime.fromisoformat(opt["board_at"])
            self.fare_per_seat = float(opt["fare"])
            self.distance_km = opt["km"]
            self.seats_left = opt["seats_left"]
            self.trip = SimpleNamespace(route=SimpleNamespace(code=opt["route"]))

    return render.trip_list(
        _stop_name(ctx.get("origin_id")),
        _stop_name(ctx.get("destination_id")),
        [_Row(o) for o in options],
    )


def _render_confirm(session) -> str:
    ctx = session.context or {}
    fare = float(ctx.get("fare_per_seat", 0))
    seats = int(ctx.get("seats", 1))
    return render.confirm_summary(
        origin=_stop_name(ctx.get("origin_id")),
        destination=_stop_name(ctx.get("destination_id")),
        board_at=dt.datetime.fromisoformat(ctx["board_at"]),
        route_code=ctx.get("route_code", ""),
        seats=seats,
        fare=fare,
        total=fare * seats,
        name=ctx.get("passenger_name", "—"),
    )


def _show_ticket(session, pnr: str) -> Reply:
    booking = booking_service.lookup_by_pnr(pnr, session.whatsapp_number)
    if booking is None:
        return _retry(session, "I couldn't find a ticket with that PNR on this number.")
    return Reply([render.ticket(booking), render.main_menu()], State.MAIN_MENU)
