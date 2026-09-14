"""Website views.

Thin by design: every one of these calls the same services the bot and the API
use, so fare and seat logic exists in exactly one place.
"""

import datetime as dt
import io

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone

from bot.forms import CheckoutForm, PNRLookupForm, RegisterForm, SearchForm
from bot.models import Booking, Route, Stop
from bot.services import booking as booking_service
from bot.services import network
from bot.services.fares import fare_for_km


def home(request):
    return render(
        request,
        "bot/home.html",
        {
            "stop_count": Stop.objects.filter(is_active=True).count(),
            "route_count": Route.objects.filter(is_active=True).count(),
            "today": timezone.localdate(),
        },
    )


def search(request):
    """Pick two stops and a date; list bookable departures."""
    stops = Stop.objects.filter(is_active=True).order_by("name")
    context = {"stops": stops, "today": timezone.localdate()}

    origin_id = request.GET.get("origin")
    destination_id = request.GET.get("destination")
    if not (origin_id and destination_id):
        return render(request, "bot/search.html", context)

    form = SearchForm(
        {
            "origin": origin_id,
            "destination": destination_id,
            "service_date": request.GET.get("date") or timezone.localdate().isoformat(),
            "seats": request.GET.get("seats") or 1,
        }
    )
    if not form.is_valid():
        for error in form.errors.values():
            messages.error(request, error[0])
        return render(request, "bot/search.html", context)

    data = form.cleaned_data
    origin = Stop.objects.filter(pk=data["origin"]).first()
    destination = Stop.objects.filter(pk=data["destination"]).first()
    if not (origin and destination):
        messages.error(request, "Unknown stop selected.")
        return render(request, "bot/search.html", context)

    options = network.search_trips(
        origin.id, destination.id, data["service_date"], seats=data["seats"], limit=20
    )
    km = network.distance_between(origin.id, destination.id)

    context.update(
        {
            "searched": True,
            "origin": origin,
            "destination": destination,
            "service_date": data["service_date"],
            "seats": data["seats"],
            "options": options,
            "distance_km": km,
            "fare": fare_for_km(km) if km is not None else None,
            "no_route": km is None,
            "suggestions": network.connected_stops(origin.id) if km is None else [],
        }
    )
    return render(request, "bot/search.html", context)


def checkout(request):
    """Confirm a chosen departure and issue the ticket."""
    if request.method != "POST":
        return redirect("search")

    form = CheckoutForm(request.POST)
    if not form.is_valid():
        # Re-render the confirmation rather than bouncing the user to the start.
        trip_id = request.POST.get("trip_id")
        origin = Stop.objects.filter(pk=request.POST.get("origin")).first()
        destination = Stop.objects.filter(pk=request.POST.get("destination")).first()
        for error in form.errors.values():
            messages.error(request, error[0])
        return render(
            request,
            "bot/checkout.html",
            {
                "form": form,
                "origin": origin,
                "destination": destination,
                "trip_id": trip_id,
                "seats": request.POST.get("seats", 1),
            },
        )

    data = form.cleaned_data

    # A GET of the form (step 1) posts without confirm=1; only the second post
    # actually books, so a refresh cannot double-book.
    if request.POST.get("confirm") != "1":
        option = _find_option(data)
        return render(
            request,
            "bot/checkout.html",
            {
                "form": form,
                "option": option,
                "origin": Stop.objects.filter(pk=data["origin"]).first(),
                "destination": Stop.objects.filter(pk=data["destination"]).first(),
                "trip_id": data["trip_id"],
                "seats": data["seats"],
                "confirming": True,
            },
        )

    profile = booking_service.get_or_create_profile(
        data["whatsapp_number"], data["passenger_name"]
    )
    if request.user.is_authenticated and profile.user is None:
        profile.user = request.user
        profile.save(update_fields=["user"])

    try:
        booking = booking_service.create_booking(
            profile=profile,
            trip_id=data["trip_id"],
            origin_id=data["origin"],
            destination_id=data["destination"],
            seats=data["seats"],
            passenger_names=[data["passenger_name"]] * data["seats"],
            channel=Booking.Channel.WEB,
            user=request.user if request.user.is_authenticated else None,
        )
    except booking_service.SeatsUnavailable:
        messages.error(request, "Those seats were just taken. Please pick another bus.")
        return redirect("search")
    except booking_service.BookingError as exc:
        messages.error(request, str(exc))
        return redirect("search")

    return redirect("ticket", pnr=booking.pnr)


def _find_option(data):
    """Re-fetch the chosen departure so the confirm page shows a live fare."""
    options = network.search_trips(
        data["origin"],
        data["destination"],
        timezone.localdate(),
        seats=data["seats"],
        limit=50,
    )
    match = next((o for o in options if o.trip.id == data["trip_id"]), None)
    if match:
        return match
    # The trip may be on a future date; search that date instead.
    from bot.models import Trip

    trip = Trip.objects.filter(pk=data["trip_id"]).first()
    if not trip:
        return None
    options = network.search_trips(
        data["origin"], data["destination"], trip.service_date, seats=data["seats"], limit=50
    )
    return next((o for o in options if o.trip.id == data["trip_id"]), None)


def ticket(request, pnr):
    booking = booking_service.lookup_by_pnr(pnr)
    if booking is None:
        raise Http404("No ticket with that PNR.")
    return render(request, "bot/ticket.html", {"booking": booking})


def ticket_qr(request, pnr):
    """PNG QR of the ticket URL, embedded in the printable ticket."""
    booking = booking_service.lookup_by_pnr(pnr)
    if booking is None:
        raise Http404("No ticket with that PNR.")

    import qrcode

    image = qrcode.make(request.build_absolute_uri(f"/ticket/{booking.pnr}/"))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return HttpResponse(buffer.getvalue(), content_type="image/png")


def pnr_lookup(request):
    form = PNRLookupForm(request.GET or None)
    booking = None
    if form.is_valid():
        booking = booking_service.lookup_by_pnr(form.cleaned_data["pnr"])
        if booking is None:
            messages.error(request, "No ticket found with that PNR.")
    return render(request, "bot/pnr.html", {"form": form, "booking": booking})


@login_required
def my_tickets(request):
    profile = getattr(request.user, "passenger_profile", None)
    if profile:
        # Query through the profile so chat bookings appear too.
        bookings = (
            Booking.objects.select_related("origin", "destination", "trip__route")
            .filter(profile=profile)
            .order_by("-created_at")
        )
    else:
        bookings = (
            Booking.objects.select_related("origin", "destination", "trip__route")
            .filter(user=request.user)
            .order_by("-created_at")
        )
    return render(request, "bot/my_tickets.html", {"bookings": bookings})


@login_required
def cancel_ticket(request, pnr):
    if request.method != "POST":
        return redirect("my_tickets")

    booking = booking_service.lookup_by_pnr(pnr)
    profile = getattr(request.user, "passenger_profile", None)
    owns = booking and (
        booking.user_id == request.user.id or (profile and booking.profile_id == profile.id)
    )
    if not owns:
        messages.error(request, "That ticket isn't yours to cancel.")
        return redirect("my_tickets")

    try:
        booking_service.cancel_booking(booking)
        messages.success(request, f"Ticket {booking.pnr} cancelled.")
    except booking_service.BookingError as exc:
        messages.error(request, str(exc))
    return redirect("my_tickets")


def routes(request):
    all_routes = (
        Route.objects.filter(is_active=True)
        .prefetch_related("route_stops__stop")
        .order_by("code")
    )
    return render(request, "bot/routes.html", {"routes": all_routes})


def register(request):
    if request.user.is_authenticated:
        return redirect("home")

    form = RegisterForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        number = form.cleaned_data.get("whatsapp_number")
        if number:
            profile = booking_service.get_or_create_profile(
                number, user.get_full_name() or user.username
            )
            # Linking here makes any earlier chat bookings from this number
            # show up in My Tickets immediately.
            if profile.user is None:
                profile.user = user
                profile.save(update_fields=["user"])
        login(request, user)
        messages.success(request, "Welcome aboard!")
        return redirect("home")

    return render(request, "bot/register.html", {"form": form})
