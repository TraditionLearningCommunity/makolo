#!/usr/bin/env python3
"""Strict, staged Makolo SQLite -> Django-managed PostgreSQL data transfer.

Requires a *separately verified staging branch* whose schema was created by
``python manage.py migrate``. This never changes the source SQLite file.

No PostgreSQL writes occur unless BOTH --execute and --staging-confirmation
are given. Destination django_migrations history is retained, not overwritten.
"""

import argparse
from collections import defaultdict
from pathlib import Path
import sqlite3
import sys

ROOT = Path(__file__).resolve().parent.parent

EXCLUDED = frozenset({"django_migrations"})
POST_MIGRATE_SEED_TABLES = frozenset({"auth_permission", "django_content_type"})
CONFIRMATION = "I_VERIFIED_THIS_IS_A_DISPOSABLE_STAGING_DATABASE"


class MigrationBlocked(RuntimeError):
    """Safety precondition was not met; no data must be imported."""


def quote_ident(name):
    """Quote only a valid SQLite identifier, escaping embedded quote bytes."""
    if not isinstance(name, str) or not name or "\x00" in name:
        raise ValueError("Identifiant SQLite invalide.")
    return '"' + name.replace('"', '""') + '"'


def open_source(path):
    path = Path(path).resolve(strict=True)
    uri = path.as_uri() + "?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def source_inventory(source, *, verify_integrity=True):
    if verify_integrity:
        integrity = source.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise MigrationBlocked("SQLite integrity_check n'est pas OK")
        violation = source.execute("PRAGMA foreign_key_check").fetchone()
        if violation is not None:
            raise MigrationBlocked("SQLite comporte des violations de clés étrangères")

    tables = [row[0] for row in source.execute(
        "SELECT name FROM sqlite_master "
        "WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    )]
    inventory = {}
    for name in tables:
        columns = [row[1] for row in source.execute(
            "PRAGMA table_info(" + quote_ident(name) + ")"
        )]
        # SQLite has no identifier bind parameters; quote_ident doubles quotes.
        count = source.execute(  # nosec B608: tested quoted SQLite identifier
            "SELECT COUNT(*) FROM " + quote_ident(name)
        ).fetchone()[0]
        inventory[name] = {"columns": columns, "count": count}
    if "django_migrations" not in inventory:
        raise MigrationBlocked("django_migrations absent de SQLite")
    return inventory


def applied_migrations(source):
    return {(row[0], row[1]) for row in source.execute(
        "SELECT app, name FROM django_migrations"
    )}


def read_pg_table_metadata(cursor):
    cursor.execute("""
        SELECT table_name, column_name, is_nullable, column_default,
               is_generated, is_identity
        FROM information_schema.columns
        WHERE table_schema = 'public'
        ORDER BY table_name, ordinal_position
    """)
    result = defaultdict(dict)
    for name, col, nullable, default, generated, identity in cursor.fetchall():
        result[name][col] = {
            "nullable": nullable == "YES",
            "default": default is not None,
            "generated": generated != "NEVER",
            "identity": identity == "YES",
        }
    return dict(result)


def validate_schema(source_inventory_map, target_columns):
    errors = []
    for table, information in source_inventory_map.items():
        if table in EXCLUDED:
            continue
        if table not in target_columns:
            errors.append(f"table source absente du schéma PostgreSQL: {table}")
            continue
        columns = information["columns"]
        pg_columns = target_columns[table]
        for col in columns:
            if col not in pg_columns:
                errors.append(f"colonne source non représentée: {table}.{col}")
            elif pg_columns[col]["generated"]:
                errors.append(f"colonne générée non importable: {table}.{col}")
        for col, metadata in pg_columns.items():
            if (col not in columns and not metadata["nullable"]
                    and not metadata["default"] and not metadata["identity"]
                    and not metadata["generated"]):
                errors.append(f"colonne PostgreSQL obligatoire sans valeur: {table}.{col}")
    return errors


def nonempty_target_tables(cursor, tables):
    from psycopg import sql

    nonempty = []
    for table in sorted(tables):
        if table == "django_migrations":
            continue
        cursor.execute(sql.SQL("SELECT EXISTS (SELECT 1 FROM {} LIMIT 1)").format(
            sql.Identifier("public", table)
        ))
        if cursor.fetchone()[0]:
            nonempty.append(table)
    return nonempty


def validate_foreign_keys(cursor, table_names):
    """Reject non-deferrable cross-table FKs before bulk loading."""
    cursor.execute("""
        SELECT conrelid::regclass::text, conname
        FROM pg_constraint
        WHERE contype='f' AND NOT condeferrable
          AND connamespace='public'::regnamespace
    """)
    violations = [(table, name) for table, name in cursor.fetchall()
                  if table.removeprefix("public.").strip('"') in table_names]
    if violations:
        raise MigrationBlocked(
            "FK PostgreSQL non différables : import automatisé bloqué ("
            + str(len(violations)) + " contraintes)"
        )


def check_target(cursor, source, inventory):
    target = read_pg_table_metadata(cursor)
    errors = validate_schema(inventory, target)
    if errors:
        preview = "; ".join(errors[:12])
        raise MigrationBlocked(
            f"Schéma incompatible ({len(errors)} erreurs): {preview}"
        )
    cursor.execute("SELECT app, name FROM django_migrations")
    target_migrations = set(cursor.fetchall())
    missing = applied_migrations(source) - target_migrations
    if missing:
        raise MigrationBlocked(
            "Migrations source absentes sur la cible (exemples): "
            + ", ".join(f"{a}.{n}" for a, n in sorted(missing)[:10])
        )
    populated = nonempty_target_tables(cursor, target)
    unexpected = set(populated) - POST_MIGRATE_SEED_TABLES
    if unexpected:
        raise MigrationBlocked(
            "La cible possède déjà des données hors seeds Django : "
            + ", ".join(sorted(unexpected)[:20])
        )
    validate_foreign_keys(cursor, inventory)
    return populated


def reset_serial_sequences(cursor, inventory):
    """Position sequences after restoring existing integer primary keys."""
    from psycopg import sql

    for table, data in inventory.items():
        if table in EXCLUDED:
            continue
        cursor.execute("""
            SELECT a.attname
            FROM pg_class t
            JOIN pg_namespace ns ON t.relnamespace=ns.oid
            JOIN pg_index i ON i.indrelid=t.oid AND i.indisprimary
            JOIN pg_attribute a ON a.attrelid=t.oid
                                AND a.attnum=ANY(i.indkey)
            WHERE ns.nspname='public' AND t.relname=%s
        """, (table,))
        for (column,) in cursor.fetchall():
            cursor.execute("SELECT pg_get_serial_sequence(%s, %s)",
                           (f'public.{quote_ident(table)}', column))
            sequence = cursor.fetchone()[0]
            if not sequence:
                continue
            cursor.execute(sql.SQL("SELECT MAX({}) FROM {}").format(
                sql.Identifier(column), sql.Identifier("public", table)))
            max_id = cursor.fetchone()[0]
            if max_id is not None and (not isinstance(max_id, int) or max_id < 1):
                raise MigrationBlocked(f"Séquence atypique: {table}.{column}")
            cursor.execute("SELECT setval(%s::regclass, %s, %s)",
                           (sequence, max_id if max_id is not None else 1,
                            max_id is not None))


def copy_data(source, cursor, inventory, *, batch_size=500):
    from psycopg import sql

    # The two tables below are generated by Django post_migrate, and may be
    # replaced ONLY on a staging database verified empty otherwise.
    for table in ("auth_permission", "django_content_type"):
        if table in inventory:
            cursor.execute(sql.SQL("DELETE FROM {}").format(
                sql.Identifier("public", table)))

    cursor.execute("SET CONSTRAINTS ALL DEFERRED")
    for table, data in inventory.items():
        if table in EXCLUDED:
            continue
        columns = data["columns"]
        statement = sql.SQL("COPY {} ({}) FROM STDIN").format(
            sql.Identifier("public", table),
            sql.SQL(", ").join(sql.Identifier(c) for c in columns),
        )
        # Identifiers come from SQLite schema inventory and are quoted above.
        source_cursor = source.execute(  # nosec B608: tested quoted SQLite identifiers
            "SELECT " + ", ".join(quote_ident(c) for c in columns)
            + " FROM " + quote_ident(table)
        )
        copied = 0
        with cursor.copy(statement) as copy:
            while True:
                rows = source_cursor.fetchmany(batch_size)
                if not rows:
                    break
                for row in rows:
                    copy.write_row(tuple(row))
                    copied += 1
        if copied != data["count"]:
            raise MigrationBlocked(f"La source a changé durant la copie: {table}")
        cursor.execute(sql.SQL("SELECT COUNT(*) FROM {}").format(
            sql.Identifier("public", table)))
        if cursor.fetchone()[0] != copied:
            raise MigrationBlocked(f"Comptage différent après copie: {table}")
    reset_serial_sequences(cursor, inventory)
    # Fail inside the transaction, not after commit.
    cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--source-only", action="store_true",
                        help="vérifier SQLite sans connexion PostgreSQL")
    parser.add_argument("--execute", action="store_true",
                        help="effectuer l'import; par défaut lecture seule")
    parser.add_argument("--staging-confirmation", default="",
                        help="confirmation explicite de la cible jetable")
    args = parser.parse_args(argv)
    if args.source_only and args.execute:
        parser.error("--source-only et --execute sont exclusifs")
    with open_source(args.source) as source:
        inventory = source_inventory(source)
        print("SQLite: tables=%d, lignes=%d, migrations=%d, integrity=ok, FK=ok" % (
            len(inventory), sum(x["count"] for x in inventory.values()),
            inventory["django_migrations"]["count"],
        ))
        if args.source_only:
            return 0
        sys.path.insert(0, str(ROOT))
        import os
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
        import django
        django.setup()
        from django.db import connection, transaction
        if connection.vendor != "postgresql":
            raise MigrationBlocked("Cible Django non PostgreSQL")
        if args.execute:
            if args.staging_confirmation != CONFIRMATION:
                raise MigrationBlocked("Confirmation de cible staging manquante")
            if os.getenv("DJANGO_ENV", "development") == "production":
                raise MigrationBlocked("Refus d'import avec DJANGO_ENV=production")
        connection.ensure_connection()
        with connection.connection.cursor() as cursor:
            seeded = check_target(cursor, source, inventory)
        print("Cible: migrations compatibles, tables et FK vérifiées.")
        print("Tables seeds Django existantes: " + ", ".join(seeded))
        if not args.execute:
            print("PRECHECK OK. Aucune donnée copiée (ajouter --execute sur staging).")
            return 0
        with transaction.atomic():
            with connection.connection.cursor() as cursor:
                # Repeat checks under the same connection; no other writer is
                # permitted during the staging import.
                check_target(cursor, source, inventory)
                copy_data(source, cursor, inventory)
        print("STAGING IMPORT OK. Vérifier les scénarios Django avant cutover.")
        return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (MigrationBlocked, sqlite3.DatabaseError) as exc:
        print("IMPORT BLOQUÉ : " + str(exc), file=sys.stderr)
        raise SystemExit(2)