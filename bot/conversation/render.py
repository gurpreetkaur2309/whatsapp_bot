"""Message templates and WhatsApp-safe formatting."""

from django.utils import timezone

# Twilio's ceiling is 1600 characters, counted in UTF-16 units — an emoji costs
# two. Split well below it so the emoji in these templates can't push a message
# over mid-send.
SPLIT_LIMIT = 1500
MAX_PARTS = 3

PAGE_SIZE = 10


def paginate(items: list, page: int = 1, per_page: int = PAGE_SIZE) -> tuple[list, bool, int]:
    """Return ``(page_items, has_more, total_pages)`` (1-indexed pages)."""
    total_pages = max(1, (len(items) + per_page - 1) // per_page)
    page = max(1, min(page, total_pages))
    start = (page - 1) * per_page
    chunk = items[start : start + per_page]
    return chunk, page < total_pages, total_pages


def split_message(body: str, limit: int = SPLIT_LIMIT) -> list[str]:
    """Split on line, then word boundaries. A safety net, not the primary control.

    Lists are paginated at the domain level so this rarely fires; when it does
    on more than MAX_PARTS, that is a template bug and the tail is dropped
    rather than spamming the user.
    """
    if len(body) <= limit:
        return [body]

    parts, current = [], ""
    for line in body.split("\n"):
        while len(line) > limit:
            cut = line.rfind(" ", 0, limit)
            cut = cut if cut > 0 else limit
            if current:
                parts.append(current.rstrip())
                current = ""
            parts.append(line[:cut])
            line = line[cut:].lstrip()
        if len(current) + len(line) + 1 > limit:
            parts.append(current.rstrip())
            current = line + "\n"
        else:
            current += line + "\n"
    if current.strip():
        parts.append(current.rstrip())

    return parts[:MAX_PARTS]


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------


def greeting(name: str = "") -> str:
    who = f" {name}" if name else ""
    return f"🚌 *Namaste{who}!* Welcome to *Indore iBus* — city bus tickets on WhatsApp."


def main_menu() -> str:
    return (
        "What would you like to do?\n\n"
        "1️⃣  Book a ticket\n"
        "2️⃣  My tickets\n"
        "3️⃣  Cancel a ticket\n"
        "4️⃣  Check a fare\n"
        "5️⃣  Browse stops\n\n"
        "_Reply with a number. Send MENU anytime to return here._"
    )


def ask_origin() -> str:
    return (
        "📍 *Where are you boarding?*\n\n"
        "Type the stop name (e.g. _Palasia_, _Vijay Nagar_)\n"
        "or reply LIST to browse all stops."
    )


def ask_destination(origin_name: str) -> str:
    return f"🎯 Boarding at *{origin_name}*.\n\n*Where are you going?*"


def stop_picker(prompt: str, stops: list, has_more: bool = False) -> str:
    lines = [prompt, ""]
    lines += [f"{i}. {stop.name}" for i, stop in enumerate(stops, start=1)]
    lines.append("")
    lines.append("_Reply with a number" + (", or MORE for more stops._" if has_more else "._"))
    return "\n".join(lines)


def ask_date() -> str:
    return (
        "📅 *When are you travelling?*\n\n"
        "1️⃣  Today\n"
        "2️⃣  Tomorrow\n\n"
        "_Or type a date as DD-MM._"
    )


def trip_list(origin: str, destination: str, options: list) -> str:
    lines = [f"🚌 *{origin} → {destination}*", ""]
    for i, opt in enumerate(options, start=1):
        local = timezone.localtime(opt.board_at)
        lines.append(
            f"{i}. *{local:%I:%M %p}* · {opt.trip.route.code}\n"
            f"    ₹{opt.fare_per_seat:.0f} · {opt.distance_km} km · {opt.seats_left} seats left"
        )
    lines.append("")
    lines.append("_Reply with a number to choose a bus._")
    return "\n".join(lines)


def no_trips(origin: str, destination: str) -> str:
    return (
        f"😕 No more buses from *{origin}* to *{destination}* on that date.\n\n"
        "Try another date, or send MENU to start over."
    )


def no_route(origin: str, destination: str, suggestions: list) -> str:
    text = f"😕 There's no direct bus from *{origin}* to *{destination}*."
    if suggestions:
        listed = ", ".join(s.name for s in suggestions[:6])
        text += f"\n\nFrom *{origin}* you can reach: {listed}."
    return text + "\n\nSend MENU to start over."


def ask_seats(max_seats: int = 6) -> str:
    return f"👥 *How many tickets?* (1–{max_seats})"


def ask_name() -> str:
    return "🙋 *Passenger name?*"


def confirm_summary(*, origin, destination, board_at, route_code, seats, fare, total, name) -> str:
    local = timezone.localtime(board_at)
    return (
        "🧾 *Please confirm*\n\n"
        f"From: *{origin}*\n"
        f"To: *{destination}*\n"
        f"Date: {local:%a %d %b %Y}\n"
        f"Departs: *{local:%I:%M %p}* ({route_code})\n"
        f"Passenger: {name}\n"
        f"Tickets: {seats} × ₹{fare:.0f}\n"
        f"*Total: ₹{total:.0f}*\n\n"
        "Reply *YES* to confirm, or *NO* to cancel."
    )


def ticket(booking) -> str:
    local = timezone.localtime(booking.board_at) if booking.board_at else None
    when = f"{local:%a %d %b · %I:%M %p}" if local else booking.trip.service_date
    return (
        "✅ *Ticket confirmed!*\n\n"
        f"🎟️ *PNR: {booking.pnr}*\n"
        f"From: {booking.origin.name}\n"
        f"To: {booking.destination.name}\n"
        f"Departs: {when}\n"
        f"Bus: {booking.trip.route.code}"
        + (f" · {booking.trip.bus.registration}" if booking.trip.bus else "")
        + f"\nTickets: {booking.seat_count}\n"
        f"*Paid: ₹{booking.total_fare:.0f}*\n\n"
        "_Show this PNR to the conductor. Safe journey!_ 🚌"
    )


def ticket_summary(booking) -> str:
    local = timezone.localtime(booking.board_at) if booking.board_at else None
    when = f"{local:%d %b · %I:%M %p}" if local else str(booking.trip.service_date)
    status = {
        "CONFIRMED": "✅",
        "CANCELLED": "❌",
        "PENDING": "⏳",
        "EXPIRED": "⌛",
    }.get(booking.status, "")
    return (
        f"{status} *{booking.pnr}* · {booking.origin.name} → {booking.destination.name}\n"
        f"    {when} · {booking.seat_count} ticket(s) · ₹{booking.total_fare:.0f}"
    )


def my_tickets(bookings: list) -> str:
    if not bookings:
        return "🎟️ You have no tickets yet.\n\nSend MENU and choose 1 to book one."
    lines = ["🎟️ *Your recent tickets*", ""]
    lines += [ticket_summary(b) for b in bookings]
    lines.append("")
    lines.append("_Send a PNR to see full details._")
    return "\n".join(lines)


def fare_quote(origin: str, destination: str, km, fare) -> str:
    return (
        f"💰 *{origin} → {destination}*\n\n"
        f"Distance: {km} km\n"
        f"Fare: *₹{fare:.0f}* per ticket\n\n"
        "_Send MENU to book._"
    )


def ask_pnr(action: str = "view") -> str:
    verb = "cancel" if action == "cancel" else "view"
    return f"🎟️ Send the *PNR* of the ticket you'd like to {verb} (e.g. IB7K4Q2M)."


def confirm_cancel(booking) -> str:
    return (
        "⚠️ *Cancel this ticket?*\n\n"
        + ticket_summary(booking)
        + "\n\nReply *CONFIRM* to cancel it, or NO to keep it."
    )


def cancelled(booking) -> str:
    return (
        f"❌ Ticket *{booking.pnr}* has been cancelled.\n"
        f"₹{booking.total_fare:.0f} will be refunded to the original payment method.\n\n"
        "_Send MENU for more options._"
    )


def help_text(state_hint: str = "") -> str:
    base = (
        "ℹ️ *Indore iBus help*\n\n"
        "MENU — main menu\n"
        "BACK — previous step\n"
        "CANCEL — abandon this booking\n"
        "HELP — this message"
    )
    return f"{base}\n\n{state_hint}" if state_hint else base


def invalid(hint: str = "") -> str:
    return "🤔 I didn't catch that." + (f"\n\n{hint}" if hint else "")


def session_expired() -> str:
    return "⌛ Your previous booking session expired, so I've started fresh."
