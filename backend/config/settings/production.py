"""Production settings: HTTPS only, secure cookies, no debug."""

from .base import *

DEBUG = False

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = env.bool("DJANGO_SECURE_SSL_REDIRECT", default=True)
SECURE_HSTS_SECONDS = env.int("DJANGO_SECURE_HSTS_SECONDS", default=60 * 60 * 24 * 30)
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
CSRF_TRUSTED_ORIGINS = env.list("DJANGO_CSRF_TRUSTED_ORIGINS", default=[])

# WhiteNoise serves the collected static files from the web process, right after
# SecurityMiddleware. Development uses runserver's own static file handling.
MIDDLEWARE = [MIDDLEWARE[0], "whitenoise.middleware.WhiteNoiseMiddleware", *MIDDLEWARE[1:]]

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

PUSH_SENDER = env("PUSH_SENDER", default="notifications.push.FirebaseSender")

# Live PayFast unless the environment says otherwise.
PAYFAST_SANDBOX = env.bool("PAYFAST_SANDBOX", default=False)

# Payment Barcodes are signed with a key of their own in production (barcodes/).
BARCODE_SIGNING_KEY = env("BARCODE_SIGNING_KEY")
