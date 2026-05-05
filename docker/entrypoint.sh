#!/bin/sh
# Entrypoint del contenedor web. Corre migraciones Alembic y arranca gunicorn.
set -e

echo "==> flask db upgrade"
flask db upgrade

echo "==> arrancando gunicorn en :5000"
exec gunicorn --bind 0.0.0.0:5000 --workers 2 --access-logfile - wsgi:app
