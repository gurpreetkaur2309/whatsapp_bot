"""Release seats held by bookings that were never confirmed, and reset
abandoned chat sessions. Safe to run on a cron/systemd timer.
"""

from django.core.management.base import BaseCommand

from bot.services.booking import expire_stale_pending, expire_stale_sessions


class Command(BaseCommand):
    help = "Expire stale PENDING bookings and idle chat sessions."

    def add_arguments(self, parser):
        parser.add_argument("--minutes", type=int, default=None)

    def handle(self, *args, **options):
        bookings = expire_stale_pending(options["minutes"])
        sessions = expire_stale_sessions()
        self.stdout.write(
            self.style.SUCCESS(
                f"{bookings} booking(s) expired, {sessions} session(s) reset."
            )
        )
