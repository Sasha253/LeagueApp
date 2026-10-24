"""Settings shared by every environment.

All secrets and environment-specific values come from environment variables. For local
development they can live in a git-ignored .env file at the repo root; real environment
variables always take precedence over it.
"""

import json
from datetime import timedelta
from pathlib import Path

import environ

BACKEND_DIR = Path(__file__).resolve().parents[2]
REPO_DIR = BACKEND_DIR.parent

env = environ.Env()
_env_file = REPO_DIR / ".env"
if _env_file.is_file():
    environ.Env.read_env(_env_file, overwrite=False)

SECRET_KEY = env("DJANGO_SECRET_KEY")
DEBUG = env.bool("DJANGO_DEBUG", default=False)
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=[])

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "corsheaders",
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",
    "drf_spectacular",
    "core",
    "clubs",
    "accounts",
    "teams",
    "fixtures",
    "ledger",
    "notifications",
    "payments",
    "barcodes",
    "bookings",
    "finance",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

DATABASES = {"default": env.db("DATABASE_URL")}
AUTH_USER_MODEL = "accounts.User"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# Times are stored in UTC and shown in South African time, 24-hour.
LANGUAGE_CODE = "en-za"
TIME_ZONE = "Africa/Johannesburg"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BACKEND_DIR / "staticfiles"

# The app authenticates with tokens, not session cookies (CLAUDE.md). The Django admin
# still uses its own session login.
REST_FRAMEWORK = {
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "auth": env("AUTH_THROTTLE_RATE", default="20/min"),
        # Gate scans per signed-in Admin or Referee: a busy gate, not guessing codes.
        "barcode_scan": env("BARCODE_SCAN_THROTTLE_RATE", default="60/min"),
    },
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
}

# A short-lived access token, and a refresh token that keeps the phone signed in. Each
# refresh hands out a new refresh token and blacklists the old one; logout blacklists it.
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=60),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
}

SPECTACULAR_SETTINGS = {
    "TITLE": "League App API",
    "DESCRIPTION": "Social football league management: fixtures, confirmations, payments, "
    "bookings and finances. See docs/PRD.md.",
    "VERSION": "0.1.0",
    "SERVE_INCLUDE_SCHEMA": False,
    # Separate request schemas, so read-only fields (ids, issued tokens) aren't asked for.
    "COMPONENT_SPLIT_REQUEST": True,
    "ENUM_NAME_OVERRIDES": {
        "HealthStateEnum": "core.views.HEALTH_STATES",
        "WeekdayEnum": "clubs.models.WEEKDAYS",
        "TeamStatusEnum": "teams.models.TEAM_STATUSES",
        "JoinRequestStatusEnum": "teams.models.JOIN_REQUEST_STATUSES",
        "FixtureStatusEnum": "fixtures.models.FIXTURE_STATUSES",
        "ImportActionEnum": "clubs.imports.Action",
        "FixtureImportActionEnum": "fixtures.imports.Action",
        "LedgerKindEnum": "ledger.models.LEDGER_KINDS",
        "LedgerMethodEnum": "ledger.models.LEDGER_METHODS",
        "LedgerSubjectEnum": "ledger.models.LEDGER_SUBJECTS",
        "LedgerCategoryEnum": "ledger.models.LEDGER_CATEGORIES",
        "NotificationKindEnum": "notifications.models.NOTIFICATION_KINDS",
        "NotificationAnswerEnum": "notifications.models.NOTIFICATION_ANSWERS",
        "NotificationActionEnum": "notifications.models.NOTIFICATION_ACTIONS",
        "DevicePlatformEnum": "notifications.models.DEVICE_PLATFORMS",
        "ConfirmationAnswerEnum": "fixtures.models.CONFIRMATION_ANSWERS",
        "ReadinessOutcomeEnum": "fixtures.models.READINESS_OUTCOMES",
        "ReadinessReasonEnum": "fixtures.models.READINESS_REASONS",
        "ReadinessDecisionEnum": "fixtures.readiness.Decision",
        "ReplacementStatusEnum": "fixtures.models.REPLACEMENT_STATUSES",
        "ReplacementSlotEnum": "fixtures.models.REPLACEMENT_SLOTS",
        "CauseEnum": "fixtures.models.TRANSITION_CAUSES",
        "FallbackCauseEnum": "fixtures.models.FALLBACK_CAUSES",
        "FallbackOutcomeEnum": "fixtures.models.FALLBACK_OUTCOMES",
        "CaptainRequestKindEnum": "fixtures.models.CAPTAIN_REQUEST_KINDS",
        "CaptainRequestStatusEnum": "fixtures.models.CAPTAIN_REQUEST_STATUSES",
        "PlayerRequestKindEnum": "fixtures.models.PLAYER_REQUEST_KINDS",
        "PlayerRequestStatusEnum": "fixtures.models.PLAYER_REQUEST_STATUSES",
        "FriendlyPayerEnum": "fixtures.models.FRIENDLY_PAYERS",
        "PaymentProviderEnum": "clubs.models.PaymentProvider",
        "PaymentStatusEnum": "payments.models.PAYMENT_STATUSES",
        "PaymentCreditEnum": "payments.models.PAYMENT_CREDIT_SOURCES",
        "BarcodeModeEnum": "barcodes.models.BARCODE_MODES",
        "BarcodeStateEnum": "barcodes.services.State.choices",
        "BarcodeScanMethodEnum": "barcodes.models.SCAN_METHODS",
        "BarcodeScanStateEnum": "barcodes.services.State.scan_choices",
        "BookingStatusEnum": "bookings.models.BOOKING_STATUSES",
    },
}

# The installed app (Capacitor) always calls the API from these origins, in every
# environment: capacitor://localhost on iOS, https://localhost on Android. The app uses
# token auth, so CORS never needs credentials (cookies).
CAPACITOR_ORIGINS = ["capacitor://localhost", "https://localhost"]
CORS_ALLOWED_ORIGINS = [*env.list("CORS_ALLOWED_ORIGINS", default=[]), *CAPACITOR_ORIGINS]

# Push notifications (notifications/push.py). Locally pushes are only logged; production
# sends through Firebase Cloud Messaging with a service account from the environment:
# a file path (FIREBASE_CREDENTIALS_FILE) or the JSON itself (FIREBASE_CREDENTIALS_JSON).
PUSH_SENDER = env("PUSH_SENDER", default="notifications.push.LogSender")
FIREBASE_CREDENTIALS_FILE = env("FIREBASE_CREDENTIALS_FILE", default="")
FIREBASE_CREDENTIALS_JSON = env("FIREBASE_CREDENTIALS_JSON", default="")

# Timed jobs (config/celery.py): Celery with Redis as the broker, a worker and one Beat.
# Beat starts the checkpoint pass every CHECKPOINT_INTERVAL_SECONDS; a pass that isn't
# started within that time expires, because the next one does the same work. Jobs are
# safe to run twice, so a task is acknowledged only once it has run, and is run again if
# its worker dies. Results aren't kept.
CELERY_BROKER_URL = env(
    "CELERY_BROKER_URL", default=f"redis://127.0.0.1:{env.int('REDIS_PORT', default=6380)}/0"
)
CELERY_TASK_IGNORE_RESULT = True
CELERY_TASK_ACKS_LATE = True
CELERY_TASK_REJECT_ON_WORKER_LOST = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_TIMEZONE = TIME_ZONE
CELERY_ENABLE_UTC = True
CHECKPOINT_INTERVAL_SECONDS = env.int("CHECKPOINT_INTERVAL_SECONDS", default=60)
CELERY_BEAT_SCHEDULE = {
    "timed-checkpoints": {
        "task": "fixtures.run_checkpoints",
        "schedule": float(CHECKPOINT_INTERVAL_SECONDS),
        "options": {"expires": CHECKPOINT_INTERVAL_SECONDS},
    },
    # Booking payments at the club's cutoff (FR-34) and no-shows after a booking ends.
    "booking-payments": {
        "task": "bookings.run_payments",
        "schedule": float(CHECKPOINT_INTERVAL_SECONDS),
        "options": {"expires": CHECKPOINT_INTERVAL_SECONDS},
    },
}

# Card payments (payments/). Card details go only to the gateway's hosted page, never to
# this app. PayFast credentials come from the environment: one default merchant account,
# and optionally an account per Club in PAYFAST_CLUB_ACCOUNTS, a JSON object keyed by Club
# id: {"12": {"merchant_id": "...", "merchant_key": "...", "passphrase": "..."}}.
# PAYFAST_SANDBOX picks PayFast's sandbox hosts; production must set it to false.
PAYFAST_SANDBOX = env.bool("PAYFAST_SANDBOX", default=True)
PAYFAST_MERCHANT_ID = env("PAYFAST_MERCHANT_ID", default="")
PAYFAST_MERCHANT_KEY = env("PAYFAST_MERCHANT_KEY", default="")
PAYFAST_PASSPHRASE = env("PAYFAST_PASSPHRASE", default="")
PAYFAST_CLUB_ACCOUNTS = json.loads(env("PAYFAST_CLUB_ACCOUNTS", default="") or "{}")
# Where PayFast posts its ITN (this API's payments/payfast/notify/ on a public HTTPS host),
# and where the payer's browser goes after paying or cancelling.
PAYFAST_NOTIFY_URL = env("PAYFAST_NOTIFY_URL", default="")
PAYMENT_RETURN_URL = env("PAYMENT_RETURN_URL", default="")
PAYMENT_CANCEL_URL = env("PAYMENT_CANCEL_URL", default="")
# ITNs are accepted only from PayFast's networks (PayFast's published list; check it
# before going live). Behind a reverse proxy, PAYFAST_TRUSTED_PROXIES is how many proxies
# add themselves to X-Forwarded-For; 0 reads the connecting address.
PAYFAST_ITN_NETWORKS = env.list(
    "PAYFAST_ITN_NETWORKS",
    default=[
        "197.97.145.144/28",
        "41.74.179.192/27",
        "102.216.36.0/28",
        "102.216.36.128/28",
        "144.126.193.139/32",
    ],
)
PAYFAST_TRUSTED_PROXIES = env.int("PAYFAST_TRUSTED_PROXIES", default=0)

# Payment Barcodes (barcodes/). Each code is signed with this key (HMAC-SHA256), so a code
# can't be made or moved to another Team without it. Set a long random value of its own in
# production; empty falls back to a key derived from DJANGO_SECRET_KEY. Changing it makes
# every Barcode issued so far fail its check (Admins reissue them).
BARCODE_SIGNING_KEY = env("BARCODE_SIGNING_KEY", default="")

# The privacy policy (core/legal.py, /privacy/ and /api/v1/legal/privacy/). Who runs the
# app and where to write about personal information: the store listings link to the page,
# so production sets both. No club's name: the operator runs the app for every club.
PRIVACY_OPERATOR_NAME = env("PRIVACY_OPERATOR_NAME", default="")
PRIVACY_CONTACT_EMAIL = env("PRIVACY_CONTACT_EMAIL", default="")
