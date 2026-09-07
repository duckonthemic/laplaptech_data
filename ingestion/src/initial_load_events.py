"""Bounded, manually confirmed event initial load with keyset resume."""

import argparse
from math import ceil

from .load_common import (EVENT_TABLE, clients, columns_for, compare_rows,
                          insert_rows, projection, run_safely, stats)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--confirm', action='store_true')
    parser.add_argument('--batch-size', type=int, default=10000)
    parser.add_argument('--resume', action='store_true')
    parser.add_argument('--high-watermark', type=int)
    args = parser.parse_args(argv)
    if args.batch_size <= 0:
        parser.error('--batch-size must be positive')
    if args.resume != (args.high_watermark is not None):
        parser.error('--resume and the original --high-watermark must be supplied together')
    if args.high_watermark is not None and not -(2**63) <= args.high_watermark < 2**63:
        parser.error('--high-watermark must fit Int64')
    return args


def require_target(local_stats, resume, high):
    count, unique, low, last = local_stats
    if count and not resume:
        raise ValueError('Initial load requires an empty target; existing Bronze data was not changed.')
    if count != unique or (count and (last is None or high is None or last > high)):
        raise ValueError('Resume target contains null/duplicate IDs or exceeds original watermark.')
    return last if count else None


def boundary(last_id, high):
    params = {'high': high}
    clause = 'WHERE id <= {high:Int64}'
    if last_id is not None:
        clause += ' AND id > {last:Int64}'
        params['last'] = last_id
    return clause, params


def batch_last(ids, last, high):
    if not ids or any(value is None for value in ids):
        raise ValueError('Batch contains no IDs or null IDs.')
    if ids != sorted(set(ids)) or ids[-1] > high or (last is not None and ids[0] <= last):
        raise ValueError('Invalid keyset batch boundary or duplicate IDs.')
    return ids[-1]


def main(argv=None):
    args = parse_args(argv)
    with clients() as (source, local):
        columns = columns_for(source, local, EVENT_TABLE)
        current = stats(local, 'laplap_raw', EVENT_TABLE)
        # max(Nullable) is NULL for an empty source. No sentinel excludes negative IDs.
        high = args.high_watermark if args.resume else source.command(
            'SELECT max(id) FROM laplaptech.user_event_tracking')
        where, params = boundary(None, high) if high is not None else ('WHERE 0', {})
        expected = stats(source, 'laplaptech', EVENT_TABLE, where, params)
        print(f'Initial high watermark: {high}\nExpected bounded source rows: {expected[0]}\n'
              f'Local rows: {current[0]}\nBatch size: {args.batch_size}\n'
              f'Estimated batch count: {ceil(max(0, expected[0] - current[0]) / args.batch_size)}')
        try:
            last = require_target(current, args.resume, high)
        except ValueError as error:
            print(str(error))
            raise
        nulls = source.command('SELECT count() FROM laplaptech.user_event_tracking WHERE id IS NULL')
        if nulls or expected[0] != expected[1]:
            raise ValueError('Source has null/duplicate IDs; keyset load cannot preserve every row.')
        if args.resume and last is not None:
            prefix = stats(source, 'laplaptech', EVENT_TABLE, 'WHERE id <= {last:Int64}', {'last': last})
            if prefix != current:
                raise ValueError('Resume prefix does not match source; inspect target before continuing.')
        if not args.confirm:
            print('PLAN: append bounded event batches to LOCAL laplap_raw.user_event_tracking; no writes.')
            return
        inserted = current[0]
        number = 0
        while high is not None and (last is None or last < high):
            clause, batch_params = boundary(last, high)
            batch_params['size'] = args.batch_size
            rows = source.query(f'SELECT {projection(EVENT_TABLE, columns)} '
                                f'FROM laplaptech.user_event_tracking {clause} '
                                'ORDER BY id LIMIT {size:UInt64}', parameters=batch_params).result_rows
            if not rows:
                break
            next_id = batch_last([row[columns.index('id')] for row in rows], last, high)
            batch_id = insert_rows(local, EVENT_TABLE, columns, rows)
            last = next_id
            inserted += len(rows)
            number += 1
            print(f'Batch {number:03d} | Fetched: {len(rows)} | Inserted: {len(rows)} | '
                  f'Last ID: {last} | Progress: {inserted / max(1, expected[0]):.1%} | Batch UUID: {batch_id}')
        final_source = stats(source, 'laplaptech', EVENT_TABLE, where, params)
        final_local = stats(local, 'laplap_raw', EVENT_TABLE)
        print(f'Bounded source (rows, unique, min, max): {final_source}')
        print(f'Local (rows, unique, min, max): {final_local}')
        if final_source != expected or final_local != final_source:
            raise ValueError('FAIL: counts/ranges differ or bounded source changed during load.')
        for direction in ('ASC', 'DESC'):
            sample = source.query(f'SELECT {projection(EVENT_TABLE, columns)} '
                                  f'FROM laplaptech.user_event_tracking {where} '
                                  f'ORDER BY id {direction} LIMIT 100', parameters=params).result_rows
            ids = [row[columns.index('id')] for row in sample]
            actual = local.query(f'SELECT {projection(EVENT_TABLE, columns)} '
                                 'FROM laplap_raw.user_event_tracking WHERE id IN {ids:Array(Int64)}',
                                 parameters={'ids': ids}).result_rows if ids else []
            print(f'Sample {direction}: {len(sample)} rows')
            compare_rows(columns, sample, actual)
        print('Initial load validation: PASS')


if __name__ == '__main__':
    run_safely(main)
