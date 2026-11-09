"""Regression tests for the demo-timeline SQL boundary."""
import datetime as dt
import sqlite3
import unittest

from scripts.demo_generation.clock import FIELDS, approved_timeline_sql, update_by_id, update_occurrence


class TimelineSQLSecurityTests(unittest.TestCase):
    def test_only_canonical_sql_identifiers_and_operations(self):
        invalid = (
            ('select', 'access_access";DROP TABLE x;--', ('valid_from',)),
            ('update', 'access_access', ('valid_from";--',)),
            ('delete', 'access_access', ('valid_from',)),
            ('update', 'access_access', ()),
            ('update', 'access_access', ('valid_from', 'valid_from')),
        )
        for operation, table, columns in invalid:
            with self.subTest(operation=operation, table=table, columns=columns):
                with self.assertRaises(ValueError):
                    approved_timeline_sql(operation, table, columns)

    def test_multi_date_update_is_atomic_under_sqlite_check(self):
        with sqlite3.connect(':memory:') as db:
            db.execute(
                'CREATE TABLE access_access (id TEXT PRIMARY KEY, valid_from TEXT, '
                'valid_until TEXT, CHECK (valid_from <= valid_until))'
            )
            db.execute(
                'INSERT INTO access_access VALUES (?, ?, ?)',
                ('a', '2026-01-01 12:00:00', '2026-01-02 12:00:00'),
            )
            self.assertEqual(update_by_id(
                db, 'access_access', 'a', FIELDS['access_access'], dt.timedelta(days=3)
            ), 1)
            self.assertEqual(db.execute(
                'SELECT valid_from, valid_until FROM access_access'
            ).fetchone(), ('2026-01-04 12:00:00', '2026-01-05 12:00:00'))

    def test_legacy_partial_schema_remains_compatible(self):
        with sqlite3.connect(':memory:') as db:
            db.execute('CREATE TABLE access_accesscredential (id TEXT PRIMARY KEY, expired_at TEXT)')
            db.execute('INSERT INTO access_accesscredential VALUES (?, ?)', ('c', '2026-01-01 12:00:00'))
            self.assertEqual(update_by_id(
                db, 'access_accesscredential', 'c',
                FIELDS['access_accesscredential'], dt.timedelta(days=1)
            ), 1)
            self.assertEqual(db.execute(
                'SELECT expired_at FROM access_accesscredential WHERE id=?', ('c',)
            ).fetchone()[0], '2026-01-02 12:00:00')

    def test_occurrence_exact_and_local_dates_are_updated_together(self):
        with sqlite3.connect(':memory:') as db:
            db.execute(
                'CREATE TABLE activities_occurrence (id TEXT PRIMARY KEY, '
                'start_at TEXT, end_at TEXT, start_date TEXT, end_date TEXT, '
                'start_time TEXT, end_time TEXT, schedule_local_date TEXT, '
                'timezone TEXT, schedule_id TEXT, '
                'CHECK (start_at < end_at), CHECK (start_date <= end_date))'
            )
            db.execute(
                'INSERT INTO activities_occurrence VALUES (?,?,?,?,?,?,?,?,?,?)',
                ('o', '2026-01-01 12:00:00', '2026-01-02 12:00:00',
                 '2026-01-01', '2026-01-02', '12:00:00', '12:00:00',
                 None, 'UTC', None),
            )
            self.assertEqual(update_occurrence(db, 'o', dt.timedelta(days=4)), 1)
            self.assertEqual(db.execute(
                'SELECT start_date, end_date FROM activities_occurrence WHERE id=?', ('o',)
            ).fetchone(), ('2026-01-05', '2026-01-06'))


if __name__ == '__main__':
    unittest.main()
