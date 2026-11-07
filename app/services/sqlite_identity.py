"""Upgrade SQLite identities without reusing deleted primary keys.

Run at startup before serving traffic, with every old web/worker process stopped.
Rebuilds preserve existing DDL, columns, indexes, triggers, views and row IDs. A
single SQLite transaction supplies rollback protection without a second personal
data backup that could outlive account deletion. PostgreSQL uses its sequences.
"""
import re
from uuid import uuid4


class SQLiteIdentityMigrationError(RuntimeError):
    pass


_IDENTIFIER = r'(?:"(?:[^\"]|\"\")+"|`(?:[^`]|``)+`|\[[^\]]+\]|[A-Za-z_]\w*)'


def _quote(name):
    return '"' + name.replace('"', '""') + '"'


def _unquote(value):
    if value[0] in ('"', '`'):
        return value[1:-1].replace(value[0] * 2, value[0])
    if value[0] == '[':
        return value[1:-1]
    return value


def _mask_quotes(text):
    """Leave positions intact while ignoring quoted strings/identifiers."""
    output = list(text)
    quote, index = None, 0
    while index < len(text):
        char = text[index]
        if quote:
            output[index] = ' '
            if char == quote:
                if index + 1 < len(text) and text[index + 1] == quote and quote != ']':
                    output[index + 1] = ' '
                    index += 1
                else:
                    quote = None
        elif char in ('\'', '"', '`', '['):
            quote = ']' if char == '[' else char
            output[index] = ' '
        index += 1
    if quote:
        raise SQLiteIdentityMigrationError('Format skema SQLite tidak didukung; migrasi dibatalkan.')
    return ''.join(output)


def _definitions(body):
    masked = _mask_quotes(body)
    if '--' in masked or '/*' in masked:
        raise SQLiteIdentityMigrationError('Komentar skema SQLite perlu ditinjau sebelum migrasi.')
    depth, start, result = 0, 0, []
    for position, char in enumerate(masked):
        if char == '(':
            depth += 1
        elif char == ')':
            depth -= 1
        elif char == ',' and depth == 0:
            result.append(body[start:position].strip())
            start = position + 1
        if depth < 0:
            raise SQLiteIdentityMigrationError('Format skema SQLite tidak didukung; migrasi dibatalkan.')
    if depth:
        raise SQLiteIdentityMigrationError('Format skema SQLite tidak didukung; migrasi dibatalkan.')
    result.append(body[start:].strip())
    return result


def _autoincrement_sql(original, table, temporary):
    head = re.match(r'^\s*CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(' + _IDENTIFIER + r')\s*\(', original, re.I)
    end = original.rfind(')')
    if not head or _unquote(head.group(1)) != table or end < head.end():
        raise SQLiteIdentityMigrationError('Format tabel SQLite tidak didukung; migrasi dibatalkan.')
    suffix = original[end + 1:]
    if suffix.strip().rstrip(';').strip().upper() not in ('', 'STRICT'):
        raise SQLiteIdentityMigrationError('Opsi tabel SQLite tidak didukung; migrasi dibatalkan.')
    definitions = _definitions(original[head.end():end])
    column_index, constraint_index, primary = None, None, None
    for index, definition in enumerate(definitions):
        first = re.match(r'^(' + _IDENTIFIER + r')\s+INTEGER\b', definition, re.I)
        if first and _unquote(first.group(1)) == 'id':
            column_index = index
        constraint = re.fullmatch(r'(?P<named>CONSTRAINT\s+' + _IDENTIFIER + r'\s+)?PRIMARY\s+KEY\s*\(\s*(?P<column>' + _IDENTIFIER + r')\s*\)(?P<conflict>\s+ON\s+CONFLICT\s+(?:ROLLBACK|ABORT|FAIL|IGNORE|REPLACE))?', definition, re.I)
        if constraint and _unquote(constraint.group('column')) == 'id':
            constraint_index = index
            primary = (constraint.group('named') or '') + 'PRIMARY KEY' + (constraint.group('conflict') or '') + ' AUTOINCREMENT'
    if column_index is None:
        raise SQLiteIdentityMigrationError('Kolom identitas SQLite tidak didukung; migrasi dibatalkan.')
    column = definitions[column_index]
    inline = re.search(r'\bPRIMARY\s+KEY(?:\s+ASC)?(?:\s+ON\s+CONFLICT\s+(?:ROLLBACK|ABORT|FAIL|IGNORE|REPLACE))?\b', _mask_quotes(column), re.I)
    if inline:
        if constraint_index is not None or re.search(r'\bPRIMARY\s+KEY\s+DESC\b', _mask_quotes(column), re.I):
            raise SQLiteIdentityMigrationError('Primary key SQLite tidak didukung; migrasi dibatalkan.')
        definitions[column_index] = column[:inline.end()] + ' AUTOINCREMENT' + column[inline.end():]
    elif constraint_index is not None:
        definitions[column_index] = column + ' ' + primary
        del definitions[constraint_index]
    else:
        raise SQLiteIdentityMigrationError('Primary key SQLite tidak didukung; migrasi dibatalkan.')
    return 'CREATE TABLE ' + _quote(temporary) + ' (\n' + ',\n'.join(definitions) + '\n)' + suffix


def _upgrade_table(connection, table, original):
    identifier = _quote(table)
    info = connection.exec_driver_sql('PRAGMA table_xinfo(' + identifier + ')').mappings().all()
    primary = [row for row in info if row['pk']]
    if len(primary) != 1 or primary[0]['name'] != 'id' or primary[0]['type'].upper() != 'INTEGER':
        raise SQLiteIdentityMigrationError('Identitas SQLite tidak sesuai skema aplikasi; migrasi dibatalkan.')
    columns = [_quote(row['name']) for row in info if row['hidden'] == 0]
    objects = connection.exec_driver_sql(
        "SELECT sql FROM sqlite_master WHERE tbl_name=? AND type IN ('index','trigger') AND sql IS NOT NULL ORDER BY type,name", (table,)).scalars().all()
    before = connection.exec_driver_sql('SELECT COUNT(*), COALESCE(MAX(id), 0) FROM ' + identifier).one()
    high_water = max(0, before[1])
    if connection.exec_driver_sql("SELECT 1 FROM sqlite_master WHERE name='sqlite_sequence'").scalar():
        prior = connection.exec_driver_sql('SELECT seq FROM sqlite_sequence WHERE name=?', (table,)).scalar()
        high_water = max(high_water, prior or 0)
    temporary = '__preptiva_identity_' + table + '_' + uuid4().hex[:12]
    connection.exec_driver_sql(_autoincrement_sql(original, table, temporary))
    joined = ','.join(columns)
    connection.exec_driver_sql('INSERT INTO ' + _quote(temporary) + ' (' + joined + ') SELECT ' + joined + ' FROM ' + identifier)
    copied = connection.exec_driver_sql('SELECT COUNT(*) FROM ' + _quote(temporary)).scalar()
    if copied != before[0]:
        raise SQLiteIdentityMigrationError('Jumlah data migrasi SQLite tidak sesuai; migrasi dibatalkan.')
    connection.exec_driver_sql('DROP TABLE ' + identifier)
    connection.exec_driver_sql('ALTER TABLE ' + _quote(temporary) + ' RENAME TO ' + identifier)
    for statement in objects:
        connection.exec_driver_sql(statement)
    connection.exec_driver_sql('UPDATE sqlite_sequence SET seq=MAX(seq,?) WHERE name=?', (high_water, table))
    connection.exec_driver_sql('INSERT INTO sqlite_sequence(name,seq) SELECT ?,? WHERE NOT EXISTS(SELECT 1 FROM sqlite_sequence WHERE name=?)', (table, high_water, table))


def initialize_sqlite(connection, metadata):
    """Run on a dedicated SQLAlchemy connection, never inside a caller transaction."""
    if connection.in_transaction():
        raise SQLiteIdentityMigrationError('Migrasi SQLite memerlukan koneksi khusus tanpa transaksi aktif.')
    foreign_keys = connection.exec_driver_sql('PRAGMA foreign_keys').scalar()
    legacy_alter = connection.exec_driver_sql('PRAGMA legacy_alter_table').scalar()
    connection.commit()
    connection.exec_driver_sql('PRAGMA foreign_keys=OFF')
    connection.exec_driver_sql('PRAGMA legacy_alter_table=ON')
    connection.commit()
    try:
        connection.exec_driver_sql('BEGIN IMMEDIATE')
        metadata.create_all(connection)
        for table in metadata.sorted_tables:
            if not table.dialect_options['sqlite']['autoincrement']:
                continue
            original = connection.exec_driver_sql("SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table.name,)).scalar_one()
            if re.search(r'\bAUTOINCREMENT\b', _mask_quotes(original), re.I):
                continue
            _upgrade_table(connection, table.name, original)
        if connection.exec_driver_sql('PRAGMA foreign_key_check').first() is not None:
            raise SQLiteIdentityMigrationError('Relasi data SQLite tidak konsisten; migrasi dibatalkan.')
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.exec_driver_sql('PRAGMA legacy_alter_table=' + ('ON' if legacy_alter else 'OFF'))
        connection.exec_driver_sql('PRAGMA foreign_keys=' + ('ON' if foreign_keys else 'OFF'))
        connection.commit()
