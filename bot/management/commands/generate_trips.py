"""Materialize bookable Trip rows from the service pattern.

Trips are generated ahead of time rather than computed on the fly because seat
counters need a row to live on. Idempotent via the (schedule, service_date)
unique constraint.
"""

import datetime as dt
from itertools import cycle

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from bot.data.indore_network import SERVICE_PATTERN
from bot.models import Bus, Route, Schedule, Trip


class Command(BaseCommand):
    help = "Create Schedules (once) and Trips for the next N days."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=7)
        parser.add_argument(
            "--purge-past",
            action="store_true",
            help="Delete SCHEDULED trips whose date has passed and that have no bookings.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        days = options["days"]
        schedules = self._ensure_schedules()
        created = self._generate_trips(days)

        purged = 0
        if options["purge_past"]:
            purged = self._purge_past()

        self.stdout.write(
            self.style.SUCCESS(
                f"{len(schedules)} schedules; {created} new trips over {days} days; "
                f"{Trip.objects.count()} trips total"
                + (f"; {purged} past trips purged" if options["purge_past"] else "")
            )
        )

    def _ensure_schedules(self) -> list[Schedule]:
        today = timezone.localdate()
        schedules: list[Schedule] = []

        for route in Route.objects.filter(is_active=True):
            first_hour, last_hour, headway = SERVICE_PATTERN[route.kind]
            fleet = list(Bus.objects.filter(kind=route.kind, is_active=True))
            if not fleet:
                fleet = list(Bus.objects.filter(is_active=True))
            bus_cycle = cycle(fleet)

            minute = first_hour * 60
            end = last_hour * 60
            while minute <= end:
                departure = dt.time(hour=minute // 60, minute=minute % 60)
                schedule, _ = Schedule.objects.get_or_create(
                    route=route,
                    departure_time=departure,
                    valid_from=today,
                    defaults={
                        "bus": next(bus_cycle),
                        "days_of_week": "1111111",
                        "is_active": True,
                    },
                )
                schedules.append(schedule)
                minute += headway

        return schedules

    def _generate_trips(self, days: int) -> int:
        today = timezone.localdate()
        tz = timezone.get_current_timezone()
        existing = set(
            Trip.objects.filter(service_date__gte=today).values_list(
                "schedule_id", "service_date"
            )
        )

        new_trips = []
        for schedule in Schedule.objects.filter(is_active=True).select_related("route", "bus"):
            for offset in range(days):
                service_date = today + dt.timedelta(days=offset)
                if not schedule.runs_on(service_date):
                    continue
                if (schedule.pk, service_date) in existing:
                    continue

                departure = timezone.make_aware(
                    dt.datetime.combine(service_date, schedule.departure_time), tz
                )
                new_trips.append(
                    Trip(
                        schedule=schedule,
                        route=schedule.route,
                        bus=schedule.bus,
                        service_date=service_date,
                        departure_datetime=departure,
                        total_seats=schedule.bus.total_seats if schedule.bus else 32,
                        seats_booked=0,
                        status=Trip.Status.SCHEDULED,
                    )
                )

        Trip.objects.bulk_create(new_trips, batch_size=500)
        return len(new_trips)

    def _purge_past(self) -> int:
        today = timezone.localdate()
        stale = Trip.objects.filter(
            service_date__lt=today, status=Trip.Status.SCHEDULED, bookings__isnull=True
        )
        count = stale.count()
        stale.delete()
        return count
