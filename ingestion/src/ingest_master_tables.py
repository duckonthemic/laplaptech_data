"""Explicit full snapshots of the five small master tables."""

import argparse

from .load_common import (MASTER_TABLES, clients, columns_for, compare_rows,
                          insert_rows, projection, run_safely, stats)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--confirm', action='store_true', help='replace LOCAL master snapshots')
    args = parser.parse_args(argv)
    with clients() as (source, local):
        print('TABLE SOURCE LOCAL UNIQUE_SOURCE UNIQUE_LOCAL RESULT')
        for table in MASTER_TABLES:
            columns = columns_for(source, local, table)
            before = stats(local, 'laplap_raw', table)
            if not args.confirm:
                upstream = stats(source, 'laplaptech', table)
                print(table, upstream[0], before[0], upstream[1], before[1],
                      'PLAN: replace corresponding LOCAL laplap_raw snapshot')
                continue
            rows = source.query(f'SELECT {projection(table, columns)} '
                                f'FROM laplaptech.{table} ORDER BY id').result_rows
            ids = [row[columns.index('id')] for row in rows]
            if None in ids or len(set(ids)) != len(ids):
                raise ValueError(f'{table}: null/duplicate source IDs; local untouched.')
            print(f'Replacing LOCAL laplap_raw.{table}: {before[0]} -> {len(rows)} rows')
            # Only the local client can execute writes. Snapshot is fetched first.
            local.command(f'TRUNCATE TABLE laplap_raw.{table}')
            batch_id = insert_rows(local, table, columns, rows)
            after = stats(local, 'laplap_raw', table)
            passed = (len(rows), len(set(ids))) == after[:2]
            print(table, len(rows), after[0], len(set(ids)), after[1], 'PASS' if passed else 'FAIL')
            if not passed:
                raise ValueError(f'{table}: snapshot count validation failed.')
            actual = local.query(f'SELECT {projection(table, columns)} '
                                 f'FROM laplap_raw.{table} ORDER BY id').result_rows
            compare_rows(columns, rows, actual)
            print(f'{table} batch: {batch_id}')


if __name__ == '__main__':
    run_safely(main)
