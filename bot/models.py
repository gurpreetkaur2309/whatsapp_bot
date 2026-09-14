"""Domain models for the Indore city bus ticket booking system.

Layers, in dependency order:
  network   Stop, StopAlias, Route, RouteStop, FareSlab
  ops       Bus, Schedule, Trip
  booking   PassengerProfile, Booking, Passenger, Payment
  chat      ConversationSession, MessageLog
"""

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q
from django.utils import timezone
from django.utils.text import slugify

from bot.utils.text import normalize


# ---------------------------------------------------------------------------
# Network
# ---------------------------------------------------------------------------


class Stop(models.Model):
    """A physical boarding point."""

    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True, blank=True)
    code = models.CharField(max_length=8, unique=True, help_text="Short code, e.g. VJN")
    # Persisted rather than computed at query time so exact-match lookup is an
    # indexed equality instead of LOWER() on the column, which MySQL cannot index.
    norm_name = models.CharField(max_length=100, db_index=True, blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    landmark = models.CharField(max_length=150, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)[:100]
        self.norm_name = normalize(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class StopAlias(models.Model):
    """An alternative name people use for a stop ("56 Dukan", "Palasia Square")."""

    stop = models.ForeignKey(Stop, related_name="aliases", on_delete=models.CASCADE)
    alias = models.CharField(max_length=100)
    norm_alias = models.CharField(max_length=100, db_index=True, blank=True)

    class Meta:
        verbose_name_plural = "stop aliases"
        constraints = [
            models.UniqueConstraint(fields=["norm_alias"], name="uniq_norm_alias"),
        ]

    def save(self, *args, **kwargs):
        self.norm_alias = normalize(self.alias)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.alias} → {self.stop.name}"


class Route(models.Model):
    """One direction of one bus corridor.

    Each direction is a separate row. Modelling a single route traversed both
    ways would force every query and every fare calculation to carry a direction
    flag and flip its sequence comparison; duplicating ~20 rows is cheaper than
    that branching.
    """

    class Kind(models.TextChoices):
        BRTS = "BRTS", "BRTS iBus"
        CITY = "CITY", "City Bus"

    class Direction(models.TextChoices):
        UP = "UP", "Up"
        DOWN = "DOWN", "Down"

    code = models.CharField(max_length=16, unique=True)
    name = models.CharField(max_length=120)
    kind = models.CharField(max_length=8, choices=Kind.choices, default=Kind.CITY)
    direction = models.CharField(max_length=4, choices=Direction.choices, default=Direction.UP)
    stops = models.ManyToManyField(Stop, through="RouteStop", related_name="routes")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["code"]

    def __str__(self):
        return f"{self.code} · {self.name}"


class RouteStop(models.Model):
    """A stop's position along a route.

    ``distance_from_origin`` is *cumulative* km from the route's first stop, so
    the distance between any two stops is one subtraction of two already-fetched
    rows. Per-segment distances would need a SUM() over a range for every fare
    quote, on every trip in a departure list.
    """

    route = models.ForeignKey(Route, related_name="route_stops", on_delete=models.CASCADE)
    stop = models.ForeignKey(Stop, related_name="route_stops", on_delete=models.PROTECT)
    sequence = models.PositiveSmallIntegerField()
    distance_from_origin = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    offset_minutes = models.PositiveSmallIntegerField(
        default=0, help_text="Minutes after trip departure that the bus reaches this stop"
    )

    class Meta:
        ordering = ["route", "sequence"]
        constraints = [
            models.UniqueConstraint(fields=["route", "sequence"], name="uniq_route_seq"),
            models.UniqueConstraint(fields=["route", "stop"], name="uniq_route_stop"),
        ]
        indexes = [models.Index(fields=["stop", "route"], name="ix_routestop_stop_route")]

    def __str__(self):
        return f"{self.route.code} #{self.sequence} {self.stop.name}"


class FareSlab(models.Model):
    """Distance-banded fare. Kept as data so fares can be changed without a deploy."""

    min_km = models.DecimalField(max_digits=5, decimal_places=2, help_text="Inclusive")
    max_km = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        help_text="Exclusive. Leave empty for the open-ended top slab.",
    )
    price = models.DecimalField(max_digits=6, decimal_places=2)

    class Meta:
        ordering = ["min_km"]

    def clean(self):
        if self.max_km is not None and self.max_km <= self.min_km:
            raise ValidationError("max_km must be greater than min_km.")

    def __str__(self):
        upper = f"{self.max_km} km" if self.max_km is not None else "and above"
        return f"{self.min_km}–{upper}: ₹{self.price}"


# ---------------------------------------------------------------------------
# Operations
# ---------------------------------------------------------------------------


class Bus(models.Model):
    registration = models.CharField(max_length=16, unique=True)
    kind = models.CharField(max_length=8, choices=Route.Kind.choices, default=Route.Kind.CITY)
    total_seats = models.PositiveSmallIntegerField(default=32)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name_plural = "buses"
        ordering = ["registration"]

    def __str__(self):
        return self.registration


class Schedule(models.Model):
    """A repeating departure pattern. Not itself bookable — Trips are."""

    route = models.ForeignKey(Route, related_name="schedules", on_delete=models.CASCADE)
    bus = models.ForeignKey(Bus, null=True, blank=True, on_delete=models.SET_NULL)
    departure_time = models.TimeField()
    days_of_week = models.CharField(
        max_length=7, default="1111111", help_text="Mon..Sun, 1 = runs. e.g. 1111100"
    )
    valid_from = models.DateField(default=timezone.localdate)
    valid_to = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["route", "departure_time"]
        constraints = [
            models.UniqueConstraint(
                fields=["route", "departure_time", "valid_from"], name="uniq_schedule"
            ),
        ]

    def runs_on(self, date) -> bool:
        if not self.is_active:
            return False
        if date < self.valid_from:
            return False
        if self.valid_to and date > self.valid_to:
            return False
        return self.days_of_week[date.weekday()] == "1"

    def __str__(self):
        return f"{self.route.code} @ {self.departure_time:%H:%M}"


class Trip(models.Model):
    """One concrete running of a route on one date. This is what gets booked."""

    class Status(models.TextChoices):
        SCHEDULED = "SCHEDULED", "Scheduled"
        DEPARTED = "DEPARTED", "Departed"
        COMPLETED = "COMPLETED", "Completed"
        CANCELLED = "CANCELLED", "Cancelled"

    schedule = models.ForeignKey(Schedule, null=True, blank=True, on_delete=models.SET_NULL)
    route = models.ForeignKey(Route, related_name="trips", on_delete=models.PROTECT)
    bus = models.ForeignKey(Bus, null=True, blank=True, on_delete=models.SET_NULL)
    service_date = models.DateField()
    # Denormalized from service_date + departure_time so trip search is an
    # indexed range scan rather than a computed expression.
    departure_datetime = models.DateTimeField()
    # Copied from the bus, not read through it: swapping tomorrow's bus must not
    # retroactively change yesterday's capacity.
    total_seats = models.PositiveSmallIntegerField(default=32)
    seats_booked = models.PositiveSmallIntegerField(default=0)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.SCHEDULED)

    class Meta:
        ordering = ["departure_datetime"]
        constraints = [
            models.UniqueConstraint(
                fields=["schedule", "service_date"], name="uniq_trip_per_day"
            ),
            # Backstop: if any code path ever bypasses the booking service, the
            # database refuses the write rather than overselling.
            models.CheckConstraint(
                condition=Q(seats_booked__lte=F("total_seats")), name="ck_no_oversell"
            ),
        ]
        indexes = [
            models.Index(fields=["route", "departure_datetime", "status"], name="ix_trip_lookup"),
            models.Index(fields=["service_date"], name="ix_trip_date"),
        ]

    @property
    def seats_left(self) -> int:
        return max(self.total_seats - self.seats_booked, 0)

    def __str__(self):
        return f"{self.route.code} {self.service_date} {self.departure_datetime:%H:%M}"


# ---------------------------------------------------------------------------
# Booking
# ---------------------------------------------------------------------------


class PassengerProfile(models.Model):
    """The WhatsApp identity.

    This — not ``auth.User`` — is the passenger. A WhatsApp booker has no
    password and no username; minting auth rows for them would fill the auth
    table with credential-less accounts. ``user`` is an optional link, set only
    when someone verifies their number against a website account.
    """

    whatsapp_number = models.CharField(max_length=20, unique=True, help_text="E.164")
    display_name = models.CharField(max_length=80, blank=True)
    user = models.OneToOneField(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name="passenger_profile"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.display_name or self.whatsapp_number


class Booking(models.Model):
    """An issued ticket.

    Every price-bearing field is *frozen* at booking time. The previous
    implementation recomputed the total in save() from the live route price,
    which meant re-saving a row silently repriced a ticket someone had paid for.
    """

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        CONFIRMED = "CONFIRMED", "Confirmed"
        CANCELLED = "CANCELLED", "Cancelled"
        EXPIRED = "EXPIRED", "Expired"

    class Channel(models.TextChoices):
        WHATSAPP = "WHATSAPP", "WhatsApp"
        WEB = "WEB", "Web"
        API = "API", "API"

    pnr = models.CharField(max_length=10, unique=True, editable=False)
    profile = models.ForeignKey(
        PassengerProfile, related_name="bookings", on_delete=models.PROTECT
    )
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    whatsapp_number = models.CharField(max_length=20, db_index=True)

    trip = models.ForeignKey(Trip, related_name="bookings", on_delete=models.PROTECT)
    origin = models.ForeignKey(Stop, related_name="+", on_delete=models.PROTECT)
    destination = models.ForeignKey(Stop, related_name="+", on_delete=models.PROTECT)
    origin_sequence = models.PositiveSmallIntegerField(default=0)
    destination_sequence = models.PositiveSmallIntegerField(default=0)
    board_at = models.DateTimeField(null=True, blank=True)

    distance_km = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    fare_per_seat = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    seat_count = models.PositiveSmallIntegerField(default=1)
    total_fare = models.DecimalField(max_digits=8, decimal_places=2, default=0)

    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    channel = models.CharField(
        max_length=10, choices=Channel.choices, default=Channel.WHATSAPP
    )
    created_at = models.DateTimeField(auto_now_add=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["whatsapp_number", "-created_at"], name="ix_bk_wa_recent"),
            models.Index(fields=["trip", "status"], name="ix_bk_trip_status"),
        ]

    @property
    def is_active(self) -> bool:
        return self.status in (self.Status.PENDING, self.Status.CONFIRMED)

    def __str__(self):
        return f"{self.pnr} · {self.origin} → {self.destination}"


class Passenger(models.Model):
    booking = models.ForeignKey(Booking, related_name="passengers", on_delete=models.CASCADE)
    name = models.CharField(max_length=80)
    age = models.PositiveSmallIntegerField(null=True, blank=True)
    gender = models.CharField(
        max_length=1, blank=True,
        choices=[("M", "Male"), ("F", "Female"), ("O", "Other")],
    )

    def __str__(self):
        return self.name


class Payment(models.Model):
    class Method(models.TextChoices):
        CASH = "CASH", "Pay on bus"
        UPI = "UPI", "UPI"
        MOCK = "MOCK", "Mock"

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        PAID = "PAID", "Paid"
        FAILED = "FAILED", "Failed"
        REFUNDED = "REFUNDED", "Refunded"

    booking = models.OneToOneField(Booking, related_name="payment", on_delete=models.CASCADE)
    method = models.CharField(max_length=8, choices=Method.choices, default=Method.MOCK)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    amount = models.DecimalField(max_digits=8, decimal_places=2)
    reference = models.CharField(max_length=64, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.booking.pnr} · {self.get_method_display()} · {self.status}"


# ---------------------------------------------------------------------------
# Chat
# ---------------------------------------------------------------------------


class ConversationSession(models.Model):
    """Server-side state for one WhatsApp number.

    One row per number, mutated in place. A "new row per session with an active
    flag" design would need a partial unique index, which MySQL silently ignores
    (it accepts the syntax but drops the condition), making the constraint global.
    MessageLog provides the audit trail instead.
    """

    whatsapp_number = models.CharField(max_length=20, unique=True)
    profile = models.ForeignKey(
        PassengerProfile, null=True, blank=True, on_delete=models.SET_NULL
    )
    state = models.CharField(max_length=32, default="IDLE", db_index=True)
    # JSON rather than a dozen nullable columns: the per-state payload changes
    # every time a step is added, and each change would otherwise be a migration.
    context = models.JSONField(default=dict, blank=True)
    history = models.JSONField(default=list, blank=True)
    retry_count = models.PositiveSmallIntegerField(default=0)
    last_message_at = models.DateTimeField(auto_now=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    def is_expired(self) -> bool:
        return bool(self.expires_at and timezone.now() > self.expires_at)

    def __str__(self):
        return f"{self.whatsapp_number} [{self.state}]"


class MessageLog(models.Model):
    """Audit trail, and the Twilio retry dedupe key."""

    class Direction(models.TextChoices):
        IN = "IN", "Inbound"
        OUT = "OUT", "Outbound"

    whatsapp_number = models.CharField(max_length=20, db_index=True)
    direction = models.CharField(max_length=3, choices=Direction.choices)
    body = models.TextField(blank=True)
    twilio_sid = models.CharField(max_length=48, blank=True, db_index=True)
    state_before = models.CharField(max_length=32, blank=True)
    state_after = models.CharField(max_length=32, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.direction} {self.whatsapp_number}: {self.body[:40]}"
