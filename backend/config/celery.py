"""The Celery app: timed jobs, run by a worker and scheduled by Celery Beat.

Both run as their own processes, never inside the web app (make worker, make beat):

    celery -A config worker   # runs the jobs
    celery -A config beat     # sends them on schedule (run one Beat only)

Settings come from Django's, under the CELERY_ prefix; the schedule is CELERY_BEAT_SCHEDULE
in config/settings/base.py. Every job is safe to run twice or late (fixtures/checkpoints.py).
"""

import os

from celery import Celery

# As wsgi.py: a deployment that forgets DJANGO_SETTINGS_MODULE runs with DEBUG off.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.production")

app = Celery("leagueapp")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
