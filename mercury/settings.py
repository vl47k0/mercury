"""Django settings for mercury — the per-user email store."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")


def _env_bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def _env_list(name: str, default: str) -> list[str]:
    return [item for item in os.getenv(name, default).split(",") if item]


# --- Core ---------------------------------------------------------------
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "insecure-dev-key-change-me")
DEBUG = _env_bool("DJANGO_DEBUG", True)
# Internal ClusterIP service behind the authd edge.
ALLOWED_HOSTS = _env_list("DJANGO_ALLOWED_HOSTS", "*")

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django.contrib.staticfiles",
    "django.contrib.postgres",
    "rest_framework",
    "corsheaders",
    "mail",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "mercury.middleware.RequestIDMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
]

ROOT_URLCONF = "mercury.urls"
WSGI_APPLICATION = "mercury.wsgi.application"
ASGI_APPLICATION = "mercury.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {"context_processors": []},
    },
]

# --- Database (PostgreSQL, on host "blue") ------------------------------
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("POSTGRES_DB", "mercury"),
        "USER": os.getenv("POSTGRES_USER", "mercury"),
        "PASSWORD": os.getenv("POSTGRES_PASSWORD", "mercury"),
        "HOST": os.getenv("POSTGRES_HOST", "192.168.1.183"),
        "PORT": os.getenv("POSTGRES_PORT", "5432"),
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# --- DRF ----------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
        "rest_framework.parsers.MultiPartParser",
    ],
    # Trust the authd edge (X-JWT-Sub); no local token decoding.
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "mercury.authentication.EdgeJWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.LimitOffsetPagination",
    "PAGE_SIZE": 50,
}

# --- Outbound SMTP (compose/send) ---------------------------------------
# When SMTP_HOST is set, sent messages are relayed; either way a copy is
# stored in the owner's "sent" mailbox (delivery status in metadata).
SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_TLS = _env_bool("SMTP_TLS", True)
SMTP_SSL = _env_bool("SMTP_SSL", False)
SMTP_DEFAULT_FROM = os.getenv("SMTP_DEFAULT_FROM", "")

# Fernet key for encrypting stored mail-account passwords (falls back to a key
# derived from DJANGO_SECRET_KEY when unset).
MAIL_ENCRYPTION_KEY = os.getenv("MAIL_ENCRYPTION_KEY", "")

# orion RAG connector — push stored mail into the assistant corpus.
ORION_INGEST_URL = os.getenv("ORION_INGEST_URL", "")
ORION_SERVICE_KEY = os.getenv("ORION_SERVICE_KEY", "")

# contacts connector — derive an address book from correspondents.
CONTACTS_INGEST_URL = os.getenv("CONTACTS_INGEST_URL", "")
CONTACTS_SERVICE_KEY = os.getenv("CONTACTS_SERVICE_KEY", "")

# --- CORS ---------------------------------------------------------------
CORS_ALLOWED_ORIGINS = _env_list(
    "CORS_ALLOWED_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173",
)

# Raw .eml uploads can be a few MB; allow a generous body.
DATA_UPLOAD_MAX_MEMORY_SIZE = int(os.getenv("MAX_UPLOAD_BYTES", str(64 * 1024**2)))

# Structured JSON logging to stdout, tagged with the per-request id.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {"request_id": {"()": "mercury.logging_json.RequestIDFilter"}},
    "formatters": {"json": {"()": "mercury.logging_json.JsonFormatter"}},
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout",
            "formatter": "json",
            "filters": ["request_id"],
        },
    },
    "root": {"handlers": ["console"], "level": "INFO"},
}
