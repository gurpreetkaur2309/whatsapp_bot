"""REST API over the same domain services the bot and website use."""

import datetime as dt

from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import api_view
from rest_framework.response import Response

from bot.api.serializers import (
    BookingCreateSerializer,
    BookingSerializer,
    RouteSerializer,
    StopSerializer,
    TripOptionSerializer,
)
from bot.models import Booking, Route, Stop
from bot.services import booking as booking_service
from bot.services import network
from bot.services.fares import fare_for_km


class StopViewSet(viewsets.ReadOnlyModelViewSet):
    """GET /api/stops/?q=pal — stop autocomplete."""

    serializer_class = StopSerializer

    def get_queryset(self):
        qs = Stop.objects.filter(is_active=True).order_by("name")
        query = self.request.query_params.get("q")
        if query:
            from bot.utils.text import normalize

            needle = normalize(query)
            qs = qs.filter(norm_name__icontains=needle)
        return qs


class RouteViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = RouteSerializer
    queryset = (
        Route.objects.filter(is_active=True)
        .prefetch_related("route_stops__stop")
        .order_by("code")
    )


class BookingViewSet(viewsets.ReadOnlyModelViewSet):
    """Ticket lookup by PNR: GET /api/bookings/IB7K4Q2M/"""

    serializer_class = BookingSerializer
    lookup_field = "pnr"
    lookup_value_regex = "[A-Za-z0-9]+"

    def get_queryset(self):
        qs = Booking.objects.select_related(
            "origin", "destination", "trip__route"
        ).prefetch_related("passengers")
        number = self.request.query_params.get("whatsapp_number")
        if number:
            return qs.filter(whatsapp_number=number)
        # Without a number, a signed-in user sees only their own tickets.
        if self.request.user.is_authenticated:
            profile = getattr(self.request.user, "passenger_profile", None)
            if profile:
                return qs.filter(profile=profile)
            return qs.filter(user=self.request.user)
        return qs.none()


def _resolve_pair(request):
    """Parse and validate origin/destination query params."""
    try:
        origin_id = int(request.query_params["origin"])
        destination_id = int(request.query_params["destination"])
    except (KeyError, TypeError, ValueError):
        return None, None, Response(
            {"detail": "origin and destination stop ids are required."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if origin_id == destination_id:
        return None, None, Response(
            {"detail": "origin and destination must differ."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    return origin_id, destination_id, None


@api_view(["GET"])
def fare_quote(request):
    """GET /api/fare/?origin=1&destination=5"""
    origin_id, destination_id, error = _resolve_pair(request)
    if error:
        return error

    km = network.distance_between(origin_id, destination_id)
    if km is None:
        return Response(
            {"detail": "No direct route between those stops."},
            status=status.HTTP_404_NOT_FOUND,
        )
    return Response(
        {
            "origin": StopSerializer(Stop.objects.get(pk=origin_id)).data,
            "destination": StopSerializer(Stop.objects.get(pk=destination_id)).data,
            "distance_km": str(km),
            "fare_per_seat": str(fare_for_km(km)),
            "currency": "INR",
        }
    )


@api_view(["GET"])
def trip_search(request):
    """GET /api/trips/?origin=1&destination=5&date=2026-09-14&seats=2"""
    origin_id, destination_id, error = _resolve_pair(request)
    if error:
        return error

    raw_date = request.query_params.get("date")
    if raw_date:
        try:
            service_date = dt.date.fromisoformat(raw_date)
        except ValueError:
            return Response(
                {"detail": "date must be YYYY-MM-DD."}, status=status.HTTP_400_BAD_REQUEST
            )
    else:
        service_date = timezone.localdate()

    try:
        seats = max(1, int(request.query_params.get("seats", 1)))
    except ValueError:
        seats = 1

    options = network.search_trips(origin_id, destination_id, service_date, seats=seats, limit=10)
    return Response(
        {
            "date": service_date.isoformat(),
            "seats": seats,
            "count": len(options),
            "results": TripOptionSerializer(options, many=True).data,
        }
    )


@api_view(["POST"])
def create_booking(request):
    """POST /api/bookings/create/"""
    form = BookingCreateSerializer(data=request.data)
    form.is_valid(raise_exception=True)
    data = form.validated_data

    profile = booking_service.get_or_create_profile(
        data["whatsapp_number"], data.get("passenger_name", "")
    )
    try:
        booking = booking_service.create_booking(
            profile=profile,
            trip_id=data["trip_id"],
            origin_id=data["origin_id"],
            destination_id=data["destination_id"],
            seats=data["seats"],
            passenger_names=[data.get("passenger_name", "")] * data["seats"],
            channel=Booking.Channel.API,
            user=request.user if request.user.is_authenticated else None,
        )
    except booking_service.SeatsUnavailable as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
    except booking_service.BookingError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    return Response(BookingSerializer(booking).data, status=status.HTTP_201_CREATED)
