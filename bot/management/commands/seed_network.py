"""Seed the Indore stop/route/fare network. Idempotent — safe to re-run."""

from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from bot.data.indore_network import BUSES, FARE_SLABS, ROUTES, STOPS
from bot.models import Bus, FareSlab, Route, RouteStop, Stop, StopAlias
from bot.services.fares import invalidate_cache


class Command(BaseCommand):
    help = "Seed Indore stops, routes, fare slabs and buses."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete existing network rows first (fails if trips reference them).",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if options["reset"]:
            RouteStop.objects.all().delete()
            Route.objects.all().delete()
            StopAlias.objects.all().delete()
            Stop.objects.all().delete()
            self.stdout.write(self.style.WARNING("Existing network deleted."))

        self._seed_fares()
        stops = self._seed_stops()
        self._seed_routes(stops)
        self._seed_buses()
        invalidate_cache()

        self.stdout.write(
            self.style.SUCCESS(
                f"Network ready: {Stop.objects.count()} stops, "
                f"{Route.objects.count()} route directions, "
                f"{RouteStop.objects.count()} route-stops, "
                f"{Bus.objects.count()} buses, "
                f"{FareSlab.objects.count()} fare slabs."
            )
        )

    def _seed_fares(self):
        for min_km, max_km, price in FARE_SLABS:
            FareSlab.objects.update_or_create(
                min_km=Decimal(str(min_km)),
                defaults={
                    "max_km": None if max_km is None else Decimal(str(max_km)),
                    "price": Decimal(str(price)),
                },
            )

    def _seed_stops(self) -> dict[str, Stop]:
        stops: dict[str, Stop] = {}
        for name, (code, lat, lon, aliases) in STOPS.items():
            stop, _ = Stop.objects.update_or_create(
                name=name,
                defaults={
                    "code": code,
                    "latitude": Decimal(str(lat)),
                    "longitude": Decimal(str(lon)),
                    "is_active": True,
                },
            )
            stops[name] = stop
            for alias in aliases:
                # get_or_create on the alias text; norm_alias is unique and is
                # filled in by StopAlias.save().
                if not StopAlias.objects.filter(stop=stop, alias=alias).exists():
                    obj = StopAlias(stop=stop, alias=alias)
                    # Skip an alias that normalizes onto one already claimed by
                    # another stop rather than blowing up the whole seed.
                    from bot.utils.text import normalize

                    if StopAlias.objects.filter(norm_alias=normalize(alias)).exists():
                        continue
                    obj.save()
        return stops

    def _seed_routes(self, stops: dict[str, Stop]):
        for code, (name, kind, sequence) in ROUTES.items():
            total_km = Decimal(str(sequence[-1][1]))
            total_min = sequence[-1][2]

            # Forward direction, as authored.
            self._build_direction(
                code=f"{code}-UP",
                name=f"{sequence[0][0]} → {sequence[-1][0]}",
                kind=kind,
                direction=Route.Direction.UP,
                entries=[
                    (stop_name, Decimal(str(km)), offset)
                    for stop_name, km, offset in sequence
                ],
                stops=stops,
            )

            # Return direction, derived: distances and time offsets mirror.
            reversed_entries = [
                (stop_name, total_km - Decimal(str(km)), total_min - offset)
                for stop_name, km, offset in reversed(sequence)
            ]
            self._build_direction(
                code=f"{code}-DN",
                name=f"{sequence[-1][0]} → {sequence[0][0]}",
                kind=kind,
                direction=Route.Direction.DOWN,
                entries=reversed_entries,
                stops=stops,
            )

    def _build_direction(self, *, code, name, kind, direction, entries, stops):
        route, _ = Route.objects.update_or_create(
            code=code,
            defaults={
                "name": name,
                "kind": kind,
                "direction": direction,
                "is_active": True,
            },
        )
        # Rebuild the sequence wholesale; partial updates would risk violating
        # the (route, sequence) unique constraint mid-flight.
        RouteStop.objects.filter(route=route).delete()
        RouteStop.objects.bulk_create(
            [
                RouteStop(
                    route=route,
                    stop=stops[stop_name],
                    sequence=index,
                    distance_from_origin=km,
                    offset_minutes=max(offset, 0),
                )
                for index, (stop_name, km, offset) in enumerate(entries, start=1)
            ]
        )

    def _seed_buses(self):
        for registration, kind, seats in BUSES:
            Bus.objects.update_or_create(
                registration=registration,
                defaults={"kind": kind, "total_seats": seats, "is_active": True},
            )
