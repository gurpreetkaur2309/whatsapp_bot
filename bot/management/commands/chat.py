"""Drive the bot from the terminal — no Twilio, no ngrok, no phone.

    python manage.py chat
    python manage.py chat --number +919999900001 --script "hi|1|palasia|vijay nagar|1|1|2|Asha|yes"
"""

from django.core.management.base import BaseCommand

from bot.conversation.machine import dispatch, get_session
from bot.services.booking import get_or_create_profile


class Command(BaseCommand):
    help = "Interactive REPL against the WhatsApp conversation engine."

    def add_arguments(self, parser):
        parser.add_argument("--number", default="+919999900001")
        parser.add_argument(
            "--script",
            help="Pipe-separated messages to replay non-interactively.",
        )
        parser.add_argument(
            "--reset", action="store_true", help="Clear this number's session first."
        )

    def handle(self, *args, **options):
        number = options["number"]
        session = get_session(number)
        session.profile = session.profile or get_or_create_profile(number)

        if options["reset"]:
            session.state = "IDLE"
            session.context = {}
            session.history = []
            session.save()

        self.stdout.write(self.style.SUCCESS(f"Chatting as {number}. Ctrl-D to quit.\n"))

        if options["script"]:
            for message in options["script"].split("|"):
                self._exchange(session, message.strip())
            return

        while True:
            try:
                message = input("you › ").strip()
            except (EOFError, KeyboardInterrupt):
                self.stdout.write("\nbye")
                return
            if not message:
                continue
            self._exchange(session, message)

    def _exchange(self, session, message: str):
        self.stdout.write(self.style.HTTP_INFO(f"you › {message}"))
        reply = dispatch(session, message)
        for part in reply.messages:
            self.stdout.write(f"bot › {part}")
        self.stdout.write(self.style.WARNING(f"      [state: {reply.state}]\n"))
