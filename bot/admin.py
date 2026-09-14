"""Admin console — the operations surface for routes, fares, trips and tickets."""

from django.contrib import admin
from django.utils.html import format_html

from bot.models import (
    Booking,
    Bus,
    ConversationSession,
    FareSlab,
    MessageLog,
    Passenger,
    PassengerProfile,
    Payment,
    Route,
    RouteStop,
    Schedule,
    Stop,
    StopAlias,
    Trip,
)


class StopAliasInline(admin.TabularInline):
    model = StopAlias
    extra = 1
    fields = ("alias",)


@admin.register(Stop)
class StopAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "landmark", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "code", "norm_name", "aliases__alias")
    readonly_fields = ("slug", "norm_name")
    inlines = [StopAliasInline]


class RouteStopInline(admin.TabularInline):
    model = RouteStop
    extra = 0
    fields = ("sequence", "stop", "distance_from_origin", "offset_minutes")
    ordering = ("sequence",)
    autocomplete_fields = ("stop",)


@admin.register(Route)
class RouteAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "kind", "direction", "stop_count", "length_km", "is_active")
    list_filter = ("kind", "direction", "is_active")
    search_fields = ("code", "name")
    inlines = [RouteStopInline]

    @admin.display(description="Stops")
    def stop_count(self, obj):
        return obj.route_stops.count()

    @admin.display(description="Length")
    def length_km(self, obj):
        last = obj.route_stops.order_by("-sequence").first()
        return f"{last.distance_from_origin} km" if last else "—"


@admin.register(FareSlab)
class FareSlabAdmin(admin.ModelAdmin):
    list_display = ("__str__", "min_km", "max_km", "price")

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        from bot.services.fares import invalidate_cache

        invalidate_cache()


@admin.register(Bus)
class BusAdmin(admin.ModelAdmin):
    list_display = ("registration", "kind", "total_seats", "is_active")
    list_filter = ("kind", "is_active")
    search_fields = ("registration",)


@admin.register(Schedule)
class ScheduleAdmin(admin.ModelAdmin):
    list_display = ("route", "departure_time", "bus", "days_of_week", "is_active")
    list_filter = ("is_active", "route__kind", "route")
    search_fields = ("route__code",)


@admin.register(Trip)
class TripAdmin(admin.ModelAdmin):
    list_display = (
        "route", "service_date", "departure_datetime",
        "occupancy", "status", "bus",
    )
    list_filter = ("status", "service_date", "route__kind", "route")
    search_fields = ("route__code", "bus__registration")
    date_hierarchy = "service_date"
    list_select_related = ("route", "bus")

    @admin.display(description="Seats")
    def occupancy(self, obj):
        ratio = obj.seats_booked / obj.total_seats if obj.total_seats else 0
        colour = "#c0392b" if ratio >= 0.9 else "#e67e22" if ratio >= 0.6 else "#27ae60"
        return format_html(
            '<span style="color:{}">{}/{}</span>', colour, obj.seats_booked, obj.total_seats
        )


class PassengerInline(admin.TabularInline):
    model = Passenger
    extra = 0


class PaymentInline(admin.StackedInline):
    model = Payment
    extra = 0


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = (
        "pnr", "whatsapp_number", "journey", "seat_count",
        "total_fare", "status", "channel", "created_at",
    )
    list_filter = ("status", "channel", "created_at")
    search_fields = ("pnr", "whatsapp_number", "origin__name", "destination__name")
    date_hierarchy = "created_at"
    list_select_related = ("origin", "destination", "trip", "trip__route")
    inlines = [PassengerInline, PaymentInline]
    # Everything priced is frozen at purchase: editing it here would rewrite
    # what a passenger actually paid.
    readonly_fields = (
        "pnr", "distance_km", "fare_per_seat", "total_fare",
        "origin_sequence", "destination_sequence", "created_at", "confirmed_at",
    )
    actions = ["cancel_selected"]

    @admin.display(description="Journey")
    def journey(self, obj):
        return f"{obj.origin.name} → {obj.destination.name}"

    @admin.action(description="Cancel selected bookings (releases seats)")
    def cancel_selected(self, request, queryset):
        from bot.services.booking import BookingError, cancel_booking

        cancelled = 0
        for booking in queryset:
            try:
                cancel_booking(booking)
                cancelled += 1
            except BookingError:
                pass
        self.message_user(request, f"{cancelled} booking(s) cancelled.")


@admin.register(PassengerProfile)
class PassengerProfileAdmin(admin.ModelAdmin):
    list_display = ("whatsapp_number", "display_name", "user", "booking_count", "created_at")
    search_fields = ("whatsapp_number", "display_name", "user__username")

    @admin.display(description="Bookings")
    def booking_count(self, obj):
        return obj.bookings.count()


@admin.register(ConversationSession)
class ConversationSessionAdmin(admin.ModelAdmin):
    list_display = ("whatsapp_number", "state", "retry_count", "last_message_at", "expires_at")
    list_filter = ("state",)
    search_fields = ("whatsapp_number",)
    readonly_fields = ("context", "history", "last_message_at")


@admin.register(MessageLog)
class MessageLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "whatsapp_number", "direction", "preview", "state_before", "state_after")
    list_filter = ("direction", "created_at")
    search_fields = ("whatsapp_number", "body", "twilio_sid")
    readonly_fields = [f.name for f in MessageLog._meta.fields]

    @admin.display(description="Message")
    def preview(self, obj):
        return (obj.body or "")[:60]


admin.site.site_header = "Indore iBus Administration"
admin.site.site_title = "Indore iBus"
admin.site.index_title = "Operations"
