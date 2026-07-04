#!/usr/bin/env sh
set -eu
cd /app
JL=/app/deploy/json-log.sh
$JL migrate python manage.py migrate --noinput
exec "$@"
