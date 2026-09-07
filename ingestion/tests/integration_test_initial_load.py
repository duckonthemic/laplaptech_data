"""Opt-in real ClickHouse integration test, confined to two loopback test databases."""

import argparse
from collections import Counter
from contextlib import contextmanager
import os
from pathlib import Path
import re
from unittest.mock import patch

import clickhouse_connect
from dotenv import load_dotenv

from ingestion.src import initial_load_events as loader
from ingestion.src.load_common import compare_rows, projection, stats

SOURCE = 'laplap_test_source'
TARGET = 'laplap_test_target'
TABLE = 'user_event_tracking'
IDS = [i for i in range(1, 35) if i not in (4, 9, 11, 16, 21, 26, 31)]
BASE_MS = 1785788617672


def check(condition, message):
    if not condition:
        raise AssertionError(message)


class InterruptedLoad(Exception):
    """Deliberate interruption before the second batch is written."""


class TestClient:
    """Translate production namespaces at the client boundary, using real SQL.

    No database results or pagination functions are mocked. Unknown namespaces
    and write methods on the simulated source are rejected.
    """

    def __init__(self, real, role, after_watermark=None, interrupt=False):
        self.real = real
        self.role = role
        self.after_watermark = after_watermark
        self.interrupt = interrupt
        self.batches = []
        self.high = None

    def translate(self, sql):
        check(sql.lstrip().upper().startswith('SELECT '), 'Only SELECT allowed through query adapter')
        sql = sql.replace('laplaptech.', SOURCE + '.').replace('laplap_raw.', TARGET + '.')
        check(not re.search(r'\blaplap_(raw|staging|intermediate|marts)\b|\blaplaptech\b', sql),
              'Production database reference rejected')
        return sql

    def query(self, sql, parameters=None):
        params = dict(parameters or {})
        if 'db' in params:
            check(params['db'] in ('laplaptech', 'laplap_raw'), 'Unexpected schema lookup')
            params['db'] = SOURCE if params['db'] == 'laplaptech' else TARGET
        return self.real.query(self.translate(sql), parameters=params)

    def command(self, sql):
        result = self.real.command(self.translate(sql))
        if sql == 'SELECT max(id) FROM laplaptech.user_event_tracking':
            self.high = result
            if self.after_watermark:
                self.after_watermark(result)
                self.after_watermark = None
        return result

    def insert(self, table, rows, column_names):
        check(self.role == 'target' and table == 'laplap_raw.user_event_tracking', 'Unsafe insert destination')
        if self.interrupt and self.batches:
            raise InterruptedLoad()
        self.real.insert(f'{TARGET}.{TABLE}', rows, column_names=column_names)
        self.batches.append([row[column_names.index('id')] for row in rows])


def create_fixture(client):
    ddl_path = Path(__file__).resolve().parents[2] / 'sql/ddl/002_create_raw_tables.sql'
    ddl = ddl_path.read_text(encoding='utf-8')
    match = re.search(r'CREATE TABLE IF NOT EXISTS laplap_raw\.user_event_tracking\s*\((.*?)\)\s*ENGINE', ddl, re.S)
    check(match is not None, 'Cannot extract event schema from checked-in Bronze DDL')
    declarations = match.group(1).strip()
    source_declarations = declarations.split('_ingested_at', 1)[0].rstrip().rstrip(',')
    for database in (SOURCE, TARGET):
        client.command(f'DROP DATABASE IF EXISTS {database} SYNC')
        client.command(f'CREATE DATABASE {database}')
    client.command(f'CREATE TABLE {SOURCE}.{TABLE} ({source_declarations}) '
                   'ENGINE = ReplacingMergeTree ORDER BY id SETTINGS allow_nullable_key = 1')
    client.command(f'CREATE TABLE {TARGET}.{TABLE} ({declarations}) '
                   'ENGINE = ReplacingMergeTree(_ingested_at) ORDER BY id SETTINGS allow_nullable_key = 1')
    # SQL builds the timestamp oracle independently of Python datetime conversion.
    client.command(f"INSERT INTO {SOURCE}.{TABLE} SELECT id, "
                   "['pageview','search_for_device','select_device_for_comparison'][1 + modulo(id,3)], "
                   "NULL, if(id=1, NULL, '{\"device_id\":22}'), '{\"os_name\":\"test\"}', "
                   "1700000000000 + id, 1700000000010 + id, concat('test-session-',toString(id)), "
                   "concat('test-user-',toString(id)), 'test-1', "
                   "if(id=2, NULL, fromUnixTimestamp64Milli({base:Int64} + id)) "
                   "FROM (SELECT arrayJoin({ids:Array(Int64)}) AS id)",
                   parameters={'ids': IDS, 'base': BASE_MS})
    return [line.strip().split()[0] for line in source_declarations.splitlines()]


def verify(client, columns, batches, high):
    expected = stats(client, SOURCE, TABLE, 'WHERE id <= {high:Int64}', {'high': high})
    actual = stats(client, TARGET, TABLE)
    check(expected == actual == (len(IDS), len(IDS), IDS[0], IDS[-1]), 'Counts or ranges differ')
    check(Counter(i for batch in batches for i in batch) == Counter(IDS), 'IDs inserted more than once or missing')
    canonical = projection(TABLE, columns)
    left = client.query(f'SELECT {canonical} FROM {SOURCE}.{TABLE} WHERE id <= {{high:Int64}} ORDER BY id',
                        parameters={'high': high}).result_rows
    right = client.query(f'SELECT {canonical} FROM {TARGET}.{TABLE} ORDER BY id').result_rows
    compare_rows(columns, left, right)
    temporal_index = columns.index('elton_created_at')
    check(all(row[temporal_index] == (None if row[0] == 2 else BASE_MS + row[0]) for row in right),
          'Timestamp differs from independent SQL epoch oracle')
    metadata = client.query(f"SELECT uniqExact(_ingestion_batch_id), countIf(_source_system != 'laplaptech'), "
                            f"countIf(_ingested_at <= toDateTime64(0,3)) FROM {TARGET}.{TABLE}").result_rows[0]
    check(tuple(metadata) == (len(batches), 0, 0), 'Invalid ingestion metadata')


def run_loader(source, target, args):
    @contextmanager
    def test_clients():
        yield source, target

    # Replace only connection acquisition. Exercise actual production load logic.
    with patch.object(loader, 'clients', test_clients):
        loader.main(args)


def exercise(client):
    columns = create_fixture(client)
    source, target = TestClient(client, 'source'), TestClient(client, 'target')
    run_loader(source, target, ['--batch-size', '10', '--confirm'])
    check([len(b) for b in target.batches] == [10, 10, 7], 'Expected three batches')
    verify(client, columns, target.batches, source.high)

    client.command(f'TRUNCATE TABLE {TARGET}.{TABLE}')

    def arrive_after_capture(high):
        check(high == IDS[-1], 'Unexpected original watermark')
        names = ', '.join(columns)
        values = ', '.join('id + 1000' if name == 'id' else name for name in columns)
        client.command(f'INSERT INTO {SOURCE}.{TABLE} ({names}) SELECT {values} '
                       f'FROM {SOURCE}.{TABLE} WHERE id = 1')

    source = TestClient(client, 'source', after_watermark=arrive_after_capture)
    partial = TestClient(client, 'target', interrupt=True)
    try:
        run_loader(source, partial, ['--batch-size', '10', '--confirm'])
    except InterruptedLoad:
        pass
    else:
        raise AssertionError('Expected simulated interruption')
    check(len(partial.batches) == 1 and len(partial.batches[0]) == 10, 'Incorrect partial load')
    check(client.command(f'SELECT max(id) FROM {SOURCE}.{TABLE}') > source.high, 'New event missing')
    resumed = TestClient(client, 'target')
    resumed_source = TestClient(client, 'source')
    run_loader(resumed_source, resumed, ['--resume', '--high-watermark', str(source.high),
                                        '--batch-size', '10', '--confirm'])
    check(resumed_source.high is None, 'Resume captured a new watermark')
    check([len(b) for b in resumed.batches] == [10, 7], 'Resume repeated or skipped batches')
    verify(client, columns, partial.batches + resumed.batches, source.high)
    check(client.command(f'SELECT count() FROM {TARGET}.{TABLE} WHERE id > {source.high}') == 0,
          'Loaded above original watermark')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--confirm', action='store_true', help='recreate and clean up dedicated test databases')
    args = parser.parse_args(argv)
    if not args.confirm:
        print(f'PLAN: recreate {SOURCE} and {TARGET} on loopback ClickHouse; seed 27 rows; test and clean up.')
        print('No connection or setup performed. Run with --confirm to execute.')
        return
    load_dotenv(Path(__file__).resolve().parents[2] / '.env', override=False)
    host = os.getenv('LOCAL_CH_HOST', 'localhost')
    check(host in ('localhost', '127.0.0.1', '::1'), 'Only loopback LOCAL_CH_HOST is accepted')
    client = None
    # Neither production factory is allowed, even if the loader changes later.
    with patch('ingestion.src.load_common.get_source_client', side_effect=AssertionError('Remote factory forbidden')), \
         patch('ingestion.src.load_common.get_local_client', side_effect=AssertionError('Production factory forbidden')):
        try:
            client = clickhouse_connect.get_client(host='127.0.0.1',
                port=int(os.getenv('LOCAL_CH_HTTP_PORT', '8123')),
                username=os.getenv('LOCAL_CH_USERNAME', 'default'),
                password=os.getenv('LOCAL_CH_PASSWORD', ''), database='default')
            exercise(client)
        finally:
            if client is not None:
                try:
                    for database in (SOURCE, TARGET):
                        client.command(f'DROP DATABASE IF EXISTS {database} SYNC')
                finally:
                    client.close()
    for label in ('Normal initial load', 'ID gap handling', 'High watermark boundary',
                  'Resume', 'Temporal fidelity', 'Full reconciliation'):
        print(f'{label}: PASS')


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(f'Local integration test: FAIL ({type(error).__name__})')
        raise SystemExit(1) from None
