"""SQLite identity migration and a real delayed-request/account-reuse regression."""
import test_system  # Must establish the isolated application database first.

import asyncio
import unittest
from unittest.mock import patch

from sqlalchemy import Column, ForeignKey, Integer, MetaData, Table, create_engine
from app.models import Base
from app.services import sqlite_identity
from app.services.auth_sessions import resolve_user


class SQLiteIdentityUpgradeTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite:///:memory:')
        self.addCleanup(self.engine.dispose)
        self.metadata = MetaData()
        Table('users', self.metadata, Column('id', Integer, primary_key=True), sqlite_autoincrement=True)
        Table('interview_sessions', self.metadata, Column('id', Integer, primary_key=True),
              Column('user_id', ForeignKey('users.id')), sqlite_autoincrement=True)
        Table('interview_questions', self.metadata, Column('id', Integer, primary_key=True),
              Column('session_id', ForeignKey('interview_sessions.id')), sqlite_autoincrement=True)

    def legacy_database(self, connection):
        connection.exec_driver_sql('PRAGMA foreign_keys=ON')
        connection.exec_driver_sql('''CREATE TABLE users (
            id INTEGER NOT NULL, name TEXT, email TEXT UNIQUE, payload BLOB,
            note TEXT DEFAULT 'text, PRIMARY KEY (id), remains unchanged',
            PRIMARY KEY (id))''')
        connection.exec_driver_sql('''CREATE TABLE interview_sessions (
            id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            private_note TEXT)''')
        connection.exec_driver_sql('''CREATE TABLE interview_questions (
            id INTEGER NOT NULL, session_id INTEGER REFERENCES interview_sessions(id) ON DELETE CASCADE,
            parent_id INTEGER REFERENCES interview_questions(id), question TEXT,
            CONSTRAINT question_identity PRIMARY KEY (id))''')
        connection.exec_driver_sql('CREATE TABLE audit_log (user_id INTEGER, note TEXT)')
        connection.exec_driver_sql("CREATE INDEX custom_user_name ON users(name COLLATE NOCASE) WHERE name <> ''")
        connection.exec_driver_sql('''CREATE TRIGGER user_name_audit AFTER UPDATE OF name ON users
            BEGIN INSERT INTO audit_log(user_id,note) VALUES(new.id,new.name); END''')
        connection.exec_driver_sql('CREATE VIEW retained_user_view AS SELECT name,payload FROM users')
        connection.exec_driver_sql('INSERT INTO users(id,name,email,payload) VALUES(?,?,?,?)',
                                   (7, 'Synthetic Candidate', 'synthetic@example.test', b'\x00\xffprivate-fixture'))
        connection.exec_driver_sql('INSERT INTO interview_sessions(id,user_id,private_note) VALUES(12,7,?)', ('PRIVATE-FIXTURE',))
        connection.exec_driver_sql('INSERT INTO interview_questions(id,session_id,parent_id,question) VALUES(30,12,NULL,?)', ('First?',))
        connection.exec_driver_sql('INSERT INTO interview_questions(id,session_id,parent_id,question) VALUES(31,12,30,?)', ('Follow-up?',))
        connection.commit()

    def test_existing_schema_upgrade_preserves_rows_foreign_keys_extras_and_objects(self):
        with self.engine.connect() as connection:
            self.legacy_database(connection)
            originals = {name: connection.exec_driver_sql('SELECT * FROM ' + name + ' ORDER BY id').all()
                         for name in ('users', 'interview_sessions', 'interview_questions')}
            connection.commit()
            sqlite_identity.initialize_sqlite(connection, self.metadata)
            for name, rows in originals.items():
                self.assertEqual(connection.exec_driver_sql('SELECT * FROM ' + name + ' ORDER BY id').all(), rows)
                sql = connection.exec_driver_sql('SELECT sql FROM sqlite_master WHERE name=?', (name,)).scalar()
                self.assertIn('AUTOINCREMENT', sql)
            self.assertEqual(connection.exec_driver_sql('PRAGMA foreign_keys').scalar(), 1)
            self.assertEqual(connection.exec_driver_sql('PRAGMA foreign_key_check').all(), [])
            self.assertIsNotNone(connection.exec_driver_sql("SELECT sql FROM sqlite_master WHERE name='custom_user_name'").scalar())
            self.assertEqual(connection.exec_driver_sql('SELECT COUNT(*) FROM audit_log').scalar(), 0)
            self.assertEqual(connection.exec_driver_sql('SELECT name FROM retained_user_view').scalar(), 'Synthetic Candidate')
            connection.exec_driver_sql("UPDATE users SET name='Updated Synthetic' WHERE id=7")
            self.assertEqual(connection.exec_driver_sql('SELECT note FROM audit_log').scalar(), 'Updated Synthetic')
            connection.exec_driver_sql('DELETE FROM users WHERE id=7')
            self.assertEqual(connection.exec_driver_sql('SELECT COUNT(*) FROM interview_questions').scalar(), 0)
            new_user = connection.exec_driver_sql("INSERT INTO users(name,email) VALUES('New','new@example.test')").lastrowid
            self.assertGreater(new_user, 7)
            new_session = connection.exec_driver_sql('INSERT INTO interview_sessions(user_id) VALUES(?)', (new_user,)).lastrowid
            self.assertGreater(new_session, 12)
            question = connection.exec_driver_sql('INSERT INTO interview_questions(session_id) VALUES(?)', (new_session,)).lastrowid
            self.assertGreater(question, 31)
            connection.commit()
            # Running startup again must not reset a sequence after an empty table.
            connection.exec_driver_sql('DELETE FROM users')
            connection.commit()
            sqlite_identity.initialize_sqlite(connection, self.metadata)
            self.assertGreater(connection.exec_driver_sql("INSERT INTO users(name,email) VALUES('Again','again@example.test')").lastrowid, new_user)

    def test_failed_upgrade_rolls_back_all_tables_and_restores_foreign_key_enforcement(self):
        with self.engine.connect() as connection:
            self.legacy_database(connection)
            original = sqlite_identity._upgrade_table
            changed = []

            def fail_after_first(db, table, statement):
                if changed:
                    raise RuntimeError('Synthetic migration interruption')
                original(db, table, statement)
                changed.append(table)

            with patch.object(sqlite_identity, '_upgrade_table', side_effect=fail_after_first):
                with self.assertRaises(RuntimeError):
                    sqlite_identity.initialize_sqlite(connection, self.metadata)
            self.assertEqual(changed, ['users'])
            self.assertNotIn('AUTOINCREMENT', connection.exec_driver_sql("SELECT sql FROM sqlite_master WHERE name='users'").scalar())
            self.assertEqual(connection.exec_driver_sql('SELECT id FROM users').scalar(), 7)
            self.assertEqual(connection.exec_driver_sql('SELECT COUNT(*) FROM interview_questions').scalar(), 2)
            self.assertEqual(connection.exec_driver_sql('PRAGMA foreign_keys').scalar(), 1)
            self.assertEqual(connection.exec_driver_sql("SELECT COUNT(*) FROM sqlite_master WHERE name LIKE '__preptiva_identity_%'").scalar(), 0)
            self.assertEqual(connection.exec_driver_sql('SELECT name FROM retained_user_view').scalar(), 'Synthetic Candidate')
            connection.commit()
            sqlite_identity.initialize_sqlite(connection, self.metadata)
            self.assertIn('AUTOINCREMENT', connection.exec_driver_sql("SELECT sql FROM sqlite_master WHERE name='users'").scalar())

    def test_inconsistent_foreign_keys_fail_closed_without_repairing_or_erasing_data(self):
        with self.engine.connect() as connection:
            self.legacy_database(connection)
            connection.exec_driver_sql('PRAGMA foreign_keys=OFF')
            connection.exec_driver_sql('INSERT INTO interview_sessions(id,user_id) VALUES(99,999)')
            connection.commit()
            connection.exec_driver_sql('PRAGMA foreign_keys=ON')
            connection.commit()
            with self.assertRaises(sqlite_identity.SQLiteIdentityMigrationError):
                sqlite_identity.initialize_sqlite(connection, self.metadata)
            self.assertNotIn('AUTOINCREMENT', connection.exec_driver_sql("SELECT sql FROM sqlite_master WHERE name='users'").scalar())
            self.assertEqual(connection.exec_driver_sql('SELECT user_id FROM interview_sessions WHERE id=99').scalar(), 999)
            self.assertEqual(connection.exec_driver_sql('PRAGMA foreign_keys').scalar(), 1)

    def test_every_application_generated_integer_identity_uses_a_monotonic_allocator(self):
        identities = {'users', 'interview_sessions', 'interview_questions', 'interview_answers',
                      'interview_events', 'graph_turn_inputs', 'storage_cleanup'}
        configured = {table.name for table in Base.metadata.tables.values()
                      if table.dialect_options['sqlite']['autoincrement']}
        self.assertEqual(configured, identities)
        # Minimal legacy instances cover empty/highest-row deletion independently
        # for every identity-bearing table without inserting unrelated app data.
        metadata = MetaData()
        with self.engine.connect() as connection:
            for name in identities:
                Table(name, metadata, Column('id', Integer, primary_key=True), sqlite_autoincrement=True)
                connection.exec_driver_sql('CREATE TABLE ' + name + ' (id INTEGER PRIMARY KEY)')
                connection.exec_driver_sql('INSERT INTO ' + name + '(id) VALUES(19)')
            connection.commit()
            sqlite_identity.initialize_sqlite(connection, metadata)
            for name in identities:
                connection.exec_driver_sql('DELETE FROM ' + name)
                self.assertEqual(connection.exec_driver_sql('INSERT INTO ' + name + ' DEFAULT VALUES').lastrowid, 20)
                connection.exec_driver_sql('DELETE FROM ' + name)
                self.assertEqual(connection.exec_driver_sql('INSERT INTO ' + name + ' DEFAULT VALUES').lastrowid, 21)

    def test_unsupported_custom_primary_key_fails_closed_and_preserves_original_schema(self):
        metadata = MetaData()
        Table('users', metadata, Column('id', Integer, primary_key=True), sqlite_autoincrement=True)
        with self.engine.connect() as connection:
            connection.exec_driver_sql('PRAGMA foreign_keys=ON')
            connection.exec_driver_sql('CREATE TABLE users(id INTEGER PRIMARY KEY DESC, private_note TEXT)')
            connection.exec_driver_sql("INSERT INTO users(id,private_note) VALUES(7,'PRIVATE-FIXTURE')")
            connection.commit()
            with self.assertRaises(sqlite_identity.SQLiteIdentityMigrationError):
                sqlite_identity.initialize_sqlite(connection, metadata)
            self.assertEqual(connection.exec_driver_sql('SELECT id,private_note FROM users').one(), (7, 'PRIVATE-FIXTURE'))
            self.assertIn('PRIMARY KEY DESC', connection.exec_driver_sql("SELECT sql FROM sqlite_master WHERE name='users'").scalar())
            self.assertEqual(connection.exec_driver_sql('PRAGMA foreign_keys').scalar(), 1)


class DelayedRequestIdentityTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = test_system.SystemTests.asyncSetUp
    asyncTearDown = test_system.SystemTests.asyncTearDown
    register = test_system.SystemTests.register
    form = test_system.SystemTests.form
    create = test_system.SystemTests.create

    async def test_old_authenticated_get_cannot_read_a_new_account_after_delete_and_registration(self):
        original_id = (await self.client.get('/api/me')).json()['id']
        captured = asyncio.Event()
        release = asyncio.Event()

        async def pause_authenticated_get(request, db, touch=True):
            user = await resolve_user(request, db, touch=touch)
            if request.method == 'GET' and request.url.path == '/api/sessions' and not captured.is_set():
                self.assertEqual(user.id, original_id)
                captured.set()
                await asyncio.wait_for(release.wait(), 10)
            return user

        with patch('app.deps.resolve_user', side_effect=pause_authenticated_get):
            pending = asyncio.create_task(self.client.get('/api/sessions'))
            try:
                await asyncio.wait_for(captured.wait(), 5)
                deleted = await self.client.request('DELETE', '/api/profile',
                    json={'password': 'test12345', 'confirmation': 'HAPUS AKUN'})
                self.assertEqual(deleted.status_code, 200, deleted.text)
                self.assertEqual((await self.register(self.other, 'new-account@example.com')).status_code, 200)
                replacement_id = (await self.other.get('/api/me')).json()['id']
                self.assertGreater(replacement_id, original_id)
                old_client, self.client = self.client, self.other
                try:
                    created = await self.create(candidate_name='Private New Candidate')
                finally:
                    self.client = old_client
                self.assertEqual(created.status_code, 200, created.text)
                private_id = created.json()['session_id']
                release.set()
                response = await pending
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual(response.json()['items'], [])
                self.assertNotIn(private_id, response.text)
                self.assertNotIn('Private New Candidate', response.text)
            finally:
                release.set()
                if not pending.done():
                    pending.cancel()
                await asyncio.gather(pending, return_exceptions=True)


if __name__ == '__main__':
    unittest.main()
