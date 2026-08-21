#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/e2e-env.sh"

rm -f "$DJANGO_DB_PATH"
rm -rf "$DJANGO_EMAIL_FILE_PATH"
mkdir -p "$DJANGO_EMAIL_FILE_PATH"
rm -rf staticfiles

python manage.py migrate --noinput
python manage.py prepare_e2e
python manage.py prepare_transport_e2e
python manage.py prepare_discovery_e2e
python manage.py collectstatic --noinput
python scripts/validate_static_manifest.py
