"""Read-only source and schema preflight tests (no database credentials needed)."""
import importlib.util
from pathlib import Path
import sqlite3
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'migrate_sqlite_to_postgres.py'
spec = importlib.util.spec_from_file_location('makolo_transfer', SCRIPT)
transfer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(transfer)


class TransferSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / 'test.sqlite3'
        with sqlite3.connect(self.db) as connection:
            connection.executescript('''
                PRAGMA foreign_keys = ON;
                CREATE TABLE django_migrations (id integer primary key, app text, name text);
                CREATE TABLE parent (id integer primary key, info text);
                CREATE TABLE child (id integer primary key, parent_id integer not null,
                                    foreign key (parent_id) references parent(id));
                INSERT INTO django_migrations VALUES(1,'sample','0001_initial');
                INSERT INTO parent VALUES(10,'une donneee');
                INSERT INTO child VALUES(12,10);
            ''')

    def test_inventory_read_only(self):
        with transfer.open_source(self.db) as source:
            inventory = transfer.source_inventory(source)
            self.assertEqual(inventory['parent']['count'], 1)
            self.assertEqual(inventory['child']['columns'], ['id', 'parent_id'])
            with self.assertRaises(sqlite3.OperationalError):
                source.execute('INSERT INTO parent VALUES (11, "unsafe")')
        with sqlite3.connect(self.db) as connection:
            self.assertEqual(connection.execute('select count(*) from parent').fetchone()[0],1)

    def test_source_missing_column_is_blocked(self):
        inventory = {'parent': {'count':1, 'columns':['id','info']}}
        target = {'parent': {'id': {'nullable':False,'default':True,'identity':False,'generated':False}}}
        self.assertIn('colonne source non représentée: parent.info',transfer.validate_schema(inventory,target))

    def test_new_required_target_column_is_blocked(self):
        inventory={'parent': {'count':1,'columns':['id']}}
        target={'parent': {'id':{'nullable':False,'default':True,'identity':False,'generated':False},
                           'name':{'nullable':False,'default':False,'identity':False,'generated':False}}}
        self.assertTrue(any('parent.name' in x for x in transfer.validate_schema(inventory,target)))

    def test_missing_table_is_blocked(self):
        inventory={'parent': {'count':1,'columns':['id']}}
        self.assertTrue(transfer.validate_schema(inventory,{}))

    def test_identifier_escaping(self):
        self.assertEqual(transfer.quote_ident('a"b'), '"a""b"')

    def test_source_fk_violation_detected(self):
        with sqlite3.connect(self.db) as connection:
            connection.execute('PRAGMA foreign_keys=OFF')
            connection.execute('INSERT INTO child VALUES (999,998)')
        with transfer.open_source(self.db) as source:
            with self.assertRaises(transfer.MigrationBlocked):
                transfer.source_inventory(source)


if __name__ == '__main__':
    unittest.main()
