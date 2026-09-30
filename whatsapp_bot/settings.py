"""
Django settings for the Indore City Bus ticket booking project.

Configuration is read from a .env file at the project root (see .env.example).
Nothing secret is hardcoded here.
"""

from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
    DEBUG=(bool, False),
    ALLOWED_HOSTS=(list, ["127.0.0.1", "localhost"]),
    DB_ENGINE=(str, "sqlite"),
    SEAT_HOLD_MINUTES=(int, 10),
    SESSION_IDLE_MINUTES=(int, 30),
    TWILIO_VALIDATE_SIGNATURE=(bool, True),
)
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("SECRET_KEY", default="django-insecure-dev-only-change-me")
DEBUG = env("DEBUG")
ALLOWED_HOSTS = env("ALLOWED_HOSTS")

# ngrok / Vercel serve the site over https on a domain we don't know ahead of
# time. Vercel injects VERCEL_URL (host only, no scheme) at build and runtime.
VERCEL_URL = env("VERCEL_URL", default="")
VERCEL_BRANCH_URL = env("VERCEL_BRANCH_URL", default="")

CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])

for _host in (VERCEL_URL, VERCEL_BRANCH_URL):
    if _host:
        ALLOWED_HOSTS.append(_host)
        CSRF_TRUSTED_ORIGINS.append(f"https://{_host}")

if env("ALLOW_ALL_VERCEL_SUBDOMAINS", default=False):
    # Preview deployments get a fresh hostname per commit.
    ALLOWED_HOSTS.append(".vercel.app")

# Public base URL (the ngrok tunnel, or the Vercel domain). Used to build links
# sent into WhatsApp, and to validate Twilio request signatures.
PUBLIC_BASE_URL = env(
    "PUBLIC_BASE_URL",
    default=(f"https://{VERCEL_URL}" if VERCEL_URL else "http://127.0.0.1:8000"),
)

# Behind Vercel's proxy Django sees http; without this, request.is_secure() is
# False and secure-cookie/redirect logic misbehaves.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# Production hardening. Gated on DEBUG so local http development is unaffected
# — secure cookies over plain http would simply never be sent.
if not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_SSL_REDIRECT = env("SECURE_SSL_REDIRECT", default=True)
    SECURE_CONTENT_TYPE_NOSNIFF = True
    # Start HSTS short. Raise it once you're confident the domain will stay
    # HTTPS-only — browsers honour the max-age even after you stop sending it.
    SECURE_HSTS_SECONDS = env("SECURE_HSTS_SECONDS", default=3600)
    SECURE_HSTS_INCLUDE_SUBDOMAINS = False
    SECURE_HSTS_PRELOAD = False
    X_FRAME_OPTIONS = "DENY"


# --------------------------------------------------------------------------
# Applications
# --------------------------------------------------------------------------

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "bot",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # Serverless hosts don't serve Django's static files for you; WhiteNoise
    # serves them straight from the app.
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "whatsapp_bot.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "whatsapp_bot.wsgi.application"


# --------------------------------------------------------------------------
# Database
#
# Three ways in, in priority order:
#   1. DATABASE_URL  — one env var, what every managed host hands you.
#                      e.g. mysql://user:pass@host:3306/dbname
#                           postgres://user:pass@host:5432/dbname
#   2. DB_ENGINE=mysql + DB_* parts
#   3. SQLite (default) so the project still runs anywhere with no config.
#
# SQLite gets WAL + a busy timeout so concurrent writers wait instead of
# immediately raising "database is locked".
#
# NOTE: SQLite cannot be used on a serverless host such as Vercel — the
# filesystem is read-only and each invocation gets a fresh container, so writes
# are discarded. Deployments must set DATABASE_URL.
# --------------------------------------------------------------------------

DATABASE_URL = env("DATABASE_URL", default="")

if DATABASE_URL:
    DATABASES = {"default": env.db_url("DATABASE_URL")}
    _db = DATABASES["default"]
    # Managed databases sit behind a network hop.
    _db["CONN_MAX_AGE"] = env("CONN_MAX_AGE", default=0)

    if "mysql" in _db["ENGINE"]:
        options = _db.setdefault("OPTIONS", {})

        # Providers append connection hints to the URL query string (Aiven ends
        # its URL with "?ssl-mode=REQUIRED"), and django-environ passes every
        # query parameter straight through into OPTIONS. Those become keyword
        # arguments to the driver's connect(), which rejects anything it does
        # not recognise — a hyphenated key can never be a valid kwarg, so drop
        # them and translate the ones we understand.
        ssl_hint = options.pop("ssl-mode", None) or options.pop("sslmode", None)

        options["charset"] = "utf8mb4"

        require_ssl = env(
            "DB_REQUIRE_SSL",
            default=str(ssl_hint).upper() in {"REQUIRED", "VERIFY_CA", "VERIFY_IDENTITY"},
        )
        if require_ssl:
            # PyMySQL/mysqlclient both accept an `ssl` dict.
            options["ssl"] = {"ssl_mode": "REQUIRED"}
        else:
            options.pop("ssl", None)

        # Anything left with a hyphen cannot be a driver kwarg.
        for key in [k for k in options if "-" in k]:
            options.pop(key)
elif env("DB_ENGINE") == "mysql":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.mysql",
            "NAME": env("DB_NAME", default="indore_ibus"),
            "USER": env("DB_USER", default="root"),
            "PASSWORD": env("DB_PASSWORD", default=""),
            "HOST": env("DB_HOST", default="127.0.0.1"),
            "PORT": env("DB_PORT", default="3306"),
            "OPTIONS": {
                "charset": "utf8mb4",
                "init_command": "SET sql_mode='STRICT_TRANS_TABLES'",
            },
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
            "OPTIONS": {
                "timeout": 20,
                "init_command": "PRAGMA journal_mode=WAL;",
            },
        }
    }


AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]


# --------------------------------------------------------------------------
# Internationalization
# --------------------------------------------------------------------------

LANGUAGE_CODE = "en-us"

# Indore. Departure times are meaningless in UTC.
TIME_ZONE = "Asia/Kolkata"

USE_I18N = True
USE_TZ = True


# --------------------------------------------------------------------------
# Static files
# --------------------------------------------------------------------------

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [d for d in [BASE_DIR / "static"] if d.exists()]

# WhiteNoise compresses and fingerprints static files at collectstatic time so
# they can be served directly by the app with far-future cache headers.
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"
        if not DEBUG
        else "django.contrib.staticfiles.storage.StaticFilesStorage"
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# --------------------------------------------------------------------------
# Auth redirects
# --------------------------------------------------------------------------

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "home"
LOGOUT_REDIRECT_URL = "home"


# --------------------------------------------------------------------------
# Twilio / WhatsApp
# --------------------------------------------------------------------------

TWILIO_ACCOUNT_SID = env("TWILIO_ACCOUNT_SID", default="")
TWILIO_AUTH_TOKEN = env("TWILIO_AUTH_TOKEN", default="")
TWILIO_WHATSAPP_NUMBER = env("TWILIO_WHATSAPP_NUMBER", default="whatsapp:+14155238886")

# Reject webhook calls that aren't signed by Twilio. Only turn this off for
# local curl testing.
TWILIO_VALIDATE_SIGNATURE = env("TWILIO_VALIDATE_SIGNATURE")

# How long a PENDING booking holds its seats, and how long a chat session
# survives without a message before it resets.
# Shared secret for the scheduled-maintenance endpoint (Vercel Cron).
CRON_SECRET = env("CRON_SECRET", default="")

SEAT_HOLD_MINUTES = env("SEAT_HOLD_MINUTES")
SESSION_IDLE_MINUTES = env("SESSION_IDLE_MINUTES")


# --------------------------------------------------------------------------
# REST framework
# --------------------------------------------------------------------------

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.AllowAny",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 25,
}


LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "loggers": {
        "bot": {"handlers": ["console"], "level": "INFO"},
    },
}
