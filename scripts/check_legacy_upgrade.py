#!/usr/bin/env python3
"""Fail-fast preflight for a deployed Makolo database before migrations.

This script intentionally uses Django setup directly instead of ``manage.py shell``
so command output stays machine-readable even when Django shell auto-imports are
enabled. It never prints secrets or row payloads.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django  # noqa: E402


django.setup()

from django.conf import settings  # noqa: E402
from django.db import connection  # noqa: E402
from django.db.migrations.executor import MigrationExecutor  # noqa: E402


def main() -> int:
    database = settings.DATABASES["default"]
    print(f"DB_VENDOR={connection.vendor}")
    print(f"DB_NAME={database.get('NAME', '')}")

    if connection.vendor == "sqlite":
        with connection.cursor() as cursor:
            cursor.execute("PRAGMA integrity_check")
            result = cursor.fetchone()
        integrity = result[0] if result else "missing"
        print(f"SQLITE_INTEGRITY={integrity}")
        if integrity != "ok":
            return 2

    executor = MigrationExecutor(connection)
    plan = executor.migration_plan(executor.loader.graph.leaf_nodes())
    print(f"PENDING_MIGRATIONS={len(plan)}")
    for migration, backwards in plan:
        direction = "UNAPPLY" if backwards else "APPLY"
        print(f"{direction}={migration.app_label}.{migration.name}")

    # Counts only: enough to distinguish a fresh database from an existing beta
    # database without exposing user or business payloads.
    model_counts = (
        ("tickets", "TicketOrder"),
        ("tickets", "TicketOrderItem"),
        ("tickets", "Ticket"),
        ("commerce", "CommerceOrder"),
        ("commerce", "CommerceOrderItem"),
        ("payments", "Payment"),
        ("promotions", "Promotion"),
        ("operations", "OperationsIncident"),
    )
    apps = django.apps.apps
    for app_label, model_name in model_counts:
        try:
            model = apps.get_model(app_label, model_name)
            count = model.objects.count()
        except Exception as exc:  # schema can legitimately be behind runtime
            print(f"COUNT_{app_label}_{model_name}=UNAVAILABLE:{exc.__class__.__name__}")
        else:
            print(f"COUNT_{app_label}_{model_name}={count}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
