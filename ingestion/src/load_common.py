"""Shared schema, transport and validation for explicit initial loads."""

from contextlib import contextmanager
from uuid import uuid4

from .config import load_config
from .connections import get_local_client, get_source_client
from .temporal import datetime64_columns, epoch_millis_select_list, restore_datetime64_values

MASTER_TABLES = ('brand', 'cpu_model', 'gpu_model', 'laptop_model', 'laptop_benchmark_result')
EVENT_TABLE = 'user_event_tracking'


@contextmanager
def clients():
    config = load_config()
    if config.source.database != 'laplaptech':
        raise ValueError('SOURCE_CH_DATABASE must be laplaptech.')
    if config.local.host.lower() not in ('localhost', '127.0.0.1', '::1'):
        raise ValueError('Initial loads require a loopback LOCAL_CH_HOST.')
    source = local = None
    try:
        source = get_source_client()
        local = get_local_client()
        yield source, local
    finally:
        if local is not None:
            local.close()
        if source is not None:
            source.close()


def columns_for(source, local, table):
    if table not in (*MASTER_TABLES, EVENT_TABLE):
        raise ValueError('Unsupported source table.')
    query = ('SELECT name, type FROM system.columns '
             'WHERE database = {db:String} AND table = {table:String} ORDER BY position')
    schema = source.query(query, parameters={'db': 'laplaptech', 'table': table}).result_rows
    target = local.query(query, parameters={'db': 'laplap_raw', 'table': table}).result_rows
    target_source = [row for row in target if not row[0].startswith('_')]
    if not schema or list(map(tuple, schema)) != list(map(tuple, target_source)):
        raise ValueError(f'{table}: source/local schema mismatch.')
    temporal = {name for name, kind in schema if 'DateTime' in kind}
    if temporal != set(datetime64_columns(table)):
        raise ValueError(f'{table}: temporal mapping requires review.')
    if any(kind != 'Nullable(DateTime64(3))' for name, kind in schema if name in temporal):
        raise ValueError(f'{table}: unsupported temporal precision/type.')
    return [name for name, _ in schema]


def projection(table, columns):
    return ', '.join(epoch_millis_select_list(table, columns))


def stats(client, database, table, where='', parameters=None):
    return tuple(client.query(
        f'SELECT count(), uniqExact(id), min(id), max(id) FROM {database}.{table} {where}',
        parameters=parameters,
    ).result_rows[0])


def insert_rows(local, table, columns, rows):
    if table not in (*MASTER_TABLES, EVENT_TABLE):
        raise ValueError('Unsupported local target.')
    batch_id = str(uuid4())
    restored = restore_datetime64_values(table, columns, rows)
    if restored:
        local.insert(f'laplap_raw.{table}',
                     [row + (batch_id, 'laplaptech') for row in restored],
                     column_names=[*columns, '_ingestion_batch_id', '_source_system'])
    # _ingested_at is populated by the Bronze DEFAULT now64(3).
    return batch_id


def compare_rows(columns, source_rows, local_rows):
    index = columns.index('id')
    left = {row[index]: tuple(row) for row in source_rows}
    right = {row[index]: tuple(row) for row in local_rows}
    if (len(left) != len(source_rows) or len(right) != len(local_rows)
            or None in left or None in right or left.keys() != right.keys()):
        raise ValueError('Reconciliation failed: duplicate, null or different IDs.')
    failed = []
    for i, column in enumerate(columns):
        matches = all(left[key][i] == right[key][i] for key in left)
        print(f'{column}: {"MATCH" if matches else "FAIL"}')
        if not matches:
            failed.append(column)
    if failed:
        raise ValueError('Reconciliation failed for columns: ' + ', '.join(failed))


def run_safely(main):
    try:
        main()
    except Exception as error:
        # Driver exception text can include payloads or connection details.
        print(f'Load stopped ({type(error).__name__}). No automatic retry. Check the last safe status.')
        raise SystemExit(1) from None
