"""Vercel serverless entrypoint.

Vercel looks for a WSGI/ASGI callable named `app` (or `handler`) in this file
and routes every request here via vercel.json.
"""

import os
import sys
from pathlib import Path

# The project root is one level up from api/.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "whatsapp_bot.settings")

from whatsapp_bot.wsgi import application  # noqa: E402

app = application
