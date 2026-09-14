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

# ngrok serves the site over https on a domain we don't know ahead of time.
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])

# Public base URL (the ngrok tunnel). Used to build links sent into WhatsApp,
# and to validate Twilio request signatures.
PUBLIC_BASE_URL = env("PUBLIC_BASE_URL", default="http://127.0.0.1:8000")


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
# MySQL when DB_ENGINE=mysql, otherwise SQLite so the project runs anywhere.
# SQLite gets WAL + a busy timeout so concurrent writers wait instead of
# immediately raising "database is locked".
# --------------------------------------------------------------------------

if env("DB_ENGINE") == "mysql":
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
