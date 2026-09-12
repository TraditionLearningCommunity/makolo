#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/e2e-env.sh"

rm -f "$DJANGO_DB_PATH"
rm -rf "$DJANGO_EMAIL_FILE_PATH"
mkdir -p "$DJANGO_EMAIL_FILE_PATH"
rm -rf staticfiles

python manage.py migrate --noinput
python manage.py prepare_e2e
python manage.py shell -c 'from accounts.models import User; from authorization.constants import SystemRoleCode; from authorization.services import grant_activity_role; from events.models import Event; scanner = User.objects.get(email="scanner@e2e.makolo.test"); event = Event.objects.select_related("activity", "organizer").get(slug="festival-makolo-e2e"); grant_activity_role(profile=scanner, activity=event.activity, role_code=SystemRoleCode.ACTIVITY_SCANNER, granted_by=event.organizer, source="e2e-fixture")'
python manage.py shell -c 'import importlib; from django.apps import apps; importlib.import_module("authorization.migrations.0015_dossier_scope").seed_dossier_authority(apps, None)'
python manage.py prepare_transport_e2e
python manage.py prepare_discovery_e2e
python manage.py prepare_services_e2e
python manage.py prepare_subscriptions_e2e
python manage.py prepare_m2_e2e
python manage.py prepare_m4_e2e
python manage.py prepare_m8c_e2e
python manage.py collectstatic --noinput
python scripts/validate_static_manifest.py