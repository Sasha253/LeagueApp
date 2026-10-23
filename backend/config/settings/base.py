"""Settings shared by every environment.

All secrets and environment-specific values come from environment variables. For local
development they can live in a git-ignored .env file at the repo root; real environment
variables always take precedence over it.
"""

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
    "DEFAULT_THROTTLE_RATES": {"auth": env("AUTH_THROTTLE_RATE", default="20/min")},
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
}
