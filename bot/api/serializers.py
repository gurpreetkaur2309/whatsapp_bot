from rest_framework import serializers

from bot.models import Booking, Passenger, Route, RouteStop, Stop, Trip


class StopSerializer(serializers.ModelSerializer):
    class Meta:
        model = Stop
        fields = ("id", "name", "code", "slug", "latitude", "longitude", "landmark")


class RouteStopSerializer(serializers.ModelSerializer):
    stop = StopSerializer(read_only=True)

    class Meta:
        model = RouteStop
        fields = ("sequence", "stop", "distance_from_origin", "offset_minutes")


class RouteSerializer(serializers.ModelSerializer):
    route_stops = RouteStopSerializer(many=True, read_only=True)

    class Meta:
        model = Route
        fields = ("id", "code", "name", "kind", "direction", "is_active", "route_stops")


class RouteSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Route
        fields = ("id", "code", "name", "kind", "direction")


class TripOptionSerializer(serializers.Serializer):
    """A bookable departure. Built from services.network.TripOption, not a model."""

    trip_id = serializers.IntegerField(source="trip.id")
    route = RouteSummarySerializer(source="trip.route")
    service_date = serializers.DateField(source="trip.service_date")
    departure = serializers.DateTimeField(source="trip.departure_datetime")
    board_at = serializers.DateTimeField()
    distance_km = serializers.DecimalField(max_digits=5, decimal_places=2)
    fare_per_seat = serializers.DecimalField(max_digits=6, decimal_places=2)
    seats_left = serializers.IntegerField()


class PassengerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Passenger
        fields = ("name", "age", "gender")


class BookingSerializer(serializers.ModelSerializer):
    origin = StopSerializer(read_only=True)
    destination = StopSerializer(read_only=True)
    route = RouteSummarySerializer(source="trip.route", read_only=True)
    passengers = PassengerSerializer(many=True, read_only=True)

    class Meta:
        model = Booking
        fields = (
            "pnr", "status", "channel", "whatsapp_number",
            "origin", "destination", "route", "board_at",
            "distance_km", "fare_per_seat", "seat_count", "total_fare",
            "passengers", "created_at",
        )
        read_only_fields = fields


class BookingCreateSerializer(serializers.Serializer):
    trip_id = serializers.IntegerField()
    origin_id = serializers.IntegerField()
    destination_id = serializers.IntegerField()
    seats = serializers.IntegerField(min_value=1, max_value=6, default=1)
    whatsapp_number = serializers.CharField(max_length=20)
    passenger_name = serializers.CharField(max_length=80, required=False, allow_blank=True)
