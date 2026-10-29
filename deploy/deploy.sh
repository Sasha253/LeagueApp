#!/bin/sh
# Builds and starts League App on the VM. Run from the release the workflow just
# unpacked (.github/workflows/deploy.yml); .env must sit next to docker-compose.prod.yml.
set -eu
cd "$(dirname "$0")/.."

compose() { docker compose -f docker-compose.prod.yml "$@"; }

compose build
compose up -d --wait postgres redis
compose run --rm web python manage.py migrate --noinput
compose up -d --remove-orphans
docker image prune -f
