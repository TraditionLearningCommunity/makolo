#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/e2e-env.sh"

rm -f "$DJANGO_DB_PATH"
rm -rf "$DJANGO_EMAIL_FILE_PATH"
mkdir -p "$DJANGO_EMAIL_FILE_PATH"
rm -rf staticfiles

python manage.py migrate --noinput
python manage.py prepare_e2e
python manage.py shell -c 'import importlib; from django.apps import apps; importlib.import_module("authorization.migrations.0015_dossier_scope").seed_dossier_authority(apps, None)'
python manage.py prepare_transport_e2e
python manage.py prepare_discovery_e2e
python manage.py prepare_services_e2e
python manage.py prepare_subscriptions_e2e
python manage.py prepare_m2_e2e
python manage.py prepare_m4_e2e
python manage.py collectstatic --noinput
python scripts/validate_static_manifest.py
