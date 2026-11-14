"""Adversarial SQLite identifier tests for the staged PostgreSQL transfer."""

import sqlite3
import unittest

from scripts.migrate_sqlite_to_postgres import quote_ident, source_inventory


class SqliteIdentifierQuotingTests(unittest.TestCase):
    def test_quotes_delimiters_without_allowing_sql_to_escape(self):
        self.assertEqual(
            quote_ident('x"; DROP TABLE sentinel; --'),
            '"x""; DROP TABLE sentinel; --"',
        )

    def test_rejects_invalid_identifier_values(self):
        for value in (None, "", 123, "bad\x00name"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    quote_ident(value)

    def test_inventory_handles_sql_words_and_quotes_in_real_table_names(self):
        connection = sqlite3.connect(":memory:")
        self.addCleanup(connection.close)
        connection.row_factory = sqlite3.Row
        connection.execute(
            "CREATE TABLE django_migrations (id INTEGER PRIMARY KEY, app TEXT, name TEXT)"
        )
        connection.execute("CREATE TABLE sentinel (id INTEGER)")
        # A malicious-looking name is data inside one quoted identifier.
        connection.execute(
            'CREATE TABLE "x""; DROP TABLE sentinel; --" ("c""; DELETE FROM sentinel; --" TEXT)'
        )
        connection.execute(
            'INSERT INTO "x""; DROP TABLE sentinel; --" VALUES (?)', ("present",)
        )

        inventory = source_inventory(connection)
        self.assertIn('x"; DROP TABLE sentinel; --', inventory)
        self.assertEqual(inventory['x"; DROP TABLE sentinel; --']["count"], 1)
        self.assertEqual(
            inventory['x"; DROP TABLE sentinel; --']["columns"],
            ['c"; DELETE FROM sentinel; --'],
        )
        self.assertEqual(inventory["sentinel"]["count"], 0)


if __name__ == "__main__":
    unittest.main()
