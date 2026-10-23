# Load the Celery app with Django, so shared_task uses it (config/celery.py).
from .celery import app as celery_app

__all__ = ["celery_app"]
