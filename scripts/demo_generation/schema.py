"""Read-only schema readiness gate for the demo generation entrypoints.

A Django migration model is not enough: an existing SQLite demo database may
still contain the previous table layout. Stop *before* a generator writes any
domain rows, preserving the DB and the pending migration workflow.
"""
from django.db import connection
from django.db.migrations.executor import MigrationExecutor


class DemoSchemaNotReady(RuntimeError):
    """Database and current Django models/migrations are out of sync."""


def assert_demo_schema_ready():
    """Refuse pending migrations or the known Journey beneficiary drift.

    Never generate migrations or execute migrate implicitly: that requires an
    operator decision and an existing backup/rollback plan.
    """
    try:
        executor = MigrationExecutor(connection)
        pending = executor.migration_plan(executor.loader.graph.leaf_nodes())
    except Exception as exc:
        raise DemoSchemaNotReady(
            "Impossible de lire l'etat des migrations Django sur cette base. "
            "Verifier python manage.py showmigrations puis migrate --plan."
        ) from exc
    if pending:
        names = ", ".join(
            f"{migration.app_label}.{migration.name}"
            for migration, _backward in pending[:8]
        )
        suffix = " ..." if len(pending) > 8 else ""
        raise DemoSchemaNotReady(
            "Base de demonstration non migree : "
            + names + suffix
            + ". Verifier python manage.py migrate --plan, sauvegarder la "
            "SQLite de demo, puis executer python manage.py migrate. "
            "Aucune generation n'a commence."
        )

    # A hand-modified or inconsistent django_migrations table can incorrectly
    # report green even while the Journey schema itself is still obsolete.
    from journeys.models import Journey

    table = Journey._meta.db_table
    required = Journey._meta.get_field("beneficiary_space").column
    try:
        with connection.cursor() as cursor:
            columns = {
                field.name
                for field in connection.introspection.get_table_description(
                    cursor, table
                )
            }
    except Exception as exc:
        raise DemoSchemaNotReady(
            f"Impossible d'inspecter {table}. Verifier la base configuree "
            "et les migrations Django avant de generer des donnees."
        ) from exc
    if required not in columns:
        raise DemoSchemaNotReady(
            f"Schema incoherent : {table}.{required} manque, alors que "
            "Journey le declare. Ne pas contourner cette colonne. "
            "Verifier python manage.py showmigrations journeys, "
            "python manage.py migrate --plan et "
            "python manage.py makemigrations --check --dry-run. "
            "Corriger/appliquer la migration manquante apres sauvegarde "
            "de la base ; aucune generation n'a commence."
        )
