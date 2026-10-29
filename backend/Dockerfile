# The backend image: gunicorn for the API, and the Celery worker and Beat
# (docker-compose.prod.yml picks the command). Built on the VM by deploy/deploy.sh.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DJANGO_SETTINGS_MODULE=config.settings.production

WORKDIR /app

COPY requirements/ requirements/
RUN pip install -r requirements/production.txt

COPY . .

# collectstatic only reads settings, so placeholder secrets are enough at build time.
RUN DJANGO_SECRET_KEY=build DATABASE_URL=sqlite:////tmp/build.db BARCODE_SIGNING_KEY=build \
    python manage.py collectstatic --noinput

RUN useradd --system --uid 1000 app
USER app

EXPOSE 8000
CMD ["gunicorn", "config.wsgi", "--bind", "0.0.0.0:8000", "--workers", "3", "--access-logfile", "-"]
