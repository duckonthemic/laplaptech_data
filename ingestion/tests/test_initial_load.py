"""Offline regression tests: no ClickHouse connections are made."""

import io
import unittest
from contextlib import redirect_stdout, redirect_stderr
from unittest.mock import MagicMock, patch

from ingestion.src.initial_load_events import boundary, batch_last, parse_args, require_target, main
from ingestion.src.load_common import compare_rows
from ingestion.src.temporal import DATETIME64_COLUMNS_BY_TABLE, restore_datetime64_values


class InitialLoadTests(unittest.TestCase):
    def test_resume_requires_original_watermark(self):
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            parse_args(['--resume'])
        self.assertEqual(parse_args(['--resume', '--high-watermark', '42']).high_watermark, 42)

    def test_new_target_must_be_empty(self):
        with self.assertRaisesRegex(ValueError, 'empty target'):
            require_target((100, 100, 1, 103), False, 200)
        self.assertIsNone(require_target((0, 0, None, None), False, 200))

    def test_resume_rejects_duplicates_and_out_of_range(self):
        for values in ((3, 2, 1, 5), (3, 3, 1, 201)):
            with self.assertRaises(ValueError):
                require_target(values, True, 200)

    def test_gaps_do_not_change_next_boundary(self):
        self.assertEqual(batch_last([1, 4, 103], None, 200), 103)
        clause, params = boundary(103, 200)
        self.assertIn('id > {last:Int64}', clause)
        self.assertEqual(params, {'last': 103, 'high': 200})

    def test_first_batch_includes_zero_and_negative_ids(self):
        self.assertNotIn('id >', boundary(None, 20)[0])
        self.assertEqual(batch_last([-2, 0, 5], None, 20), 5)

    def test_bad_batches_are_rejected(self):
        for ids in ([1, 1], [3, 2], [None], [101], [0]):
            with self.assertRaises(ValueError):
                batch_last(ids, 0, 100)

    def test_timestamp_mismatch_fails_equal_count_reconciliation(self):
        with redirect_stdout(io.StringIO()), self.assertRaises(ValueError):
            compare_rows(['id', 'elton_created_at'], [(1, 1785788617672)], [(1, 1785763417672)])

    def test_all_tables_restore_temporal_fields_and_nulls(self):
        for table, fields in DATETIME64_COLUMNS_BY_TABLE.items():
            converted = restore_datetime64_values(table, fields, [[1785788617672] * len(fields), [None] * len(fields)])
            self.assertTrue(all(value.utcoffset().total_seconds() == 0 for value in converted[0]))
            self.assertTrue(all(value.microsecond == 672000 for value in converted[0]))
            self.assertEqual(converted[1], (None,) * len(fields))

    def test_dry_run_never_inserts_or_truncates(self):
        source, local = MagicMock(), MagicMock()
        source.command.side_effect = [103, 0]
        with patch('ingestion.src.initial_load_events.clients') as factory, \
             patch('ingestion.src.initial_load_events.columns_for', return_value=['id']), \
             patch('ingestion.src.initial_load_events.stats', side_effect=[(0, 0, None, None), (3, 3, 1, 103)]), \
             redirect_stdout(io.StringIO()):
            factory.return_value.__enter__.return_value = (source, local)
            main([])
        local.insert.assert_not_called()
        local.command.assert_not_called()

    def test_confirmed_event_load_uses_keysets_and_local_insert_only(self):
        source, local = MagicMock(), MagicMock()
        source.command.side_effect = [103, 0]
        source.query.return_value.result_rows = [(1,), (4,), (103,)]
        local.query.return_value.result_rows = [(1,), (4,), (103,)]
        with patch('ingestion.src.initial_load_events.clients') as factory, \
             patch('ingestion.src.initial_load_events.columns_for', return_value=['id']), \
             patch('ingestion.src.initial_load_events.stats', side_effect=[(0, 0, None, None), (3, 3, 1, 103), (3, 3, 1, 103), (3, 3, 1, 103)]), \
             redirect_stdout(io.StringIO()):
            factory.return_value.__enter__.return_value = (source, local)
            main(['--confirm'])
        source.insert.assert_not_called()
        local.command.assert_not_called()
        self.assertEqual(local.insert.call_args.args[0], 'laplap_raw.user_event_tracking')

    def test_master_plan_is_read_only(self):
        from ingestion.src.ingest_master_tables import main as master_main
        source, local = MagicMock(), MagicMock()
        with patch('ingestion.src.ingest_master_tables.clients') as factory, \
             patch('ingestion.src.ingest_master_tables.columns_for', return_value=['id']), \
             patch('ingestion.src.ingest_master_tables.stats', return_value=(2, 2, 1, 4)), \
             redirect_stdout(io.StringIO()):
            factory.return_value.__enter__.return_value = (source, local)
            master_main([])
        local.command.assert_not_called()
        local.insert.assert_not_called()
        source.command.assert_not_called()

    def test_master_snapshot_writes_only_matching_local_table(self):
        from ingestion.src.ingest_master_tables import main as master_main
        source, local = MagicMock(), MagicMock()
        source.query.return_value.result_rows = [(1,), (4,)]
        local.query.return_value.result_rows = [(1,), (4,)]
        with patch('ingestion.src.ingest_master_tables.clients') as factory, \
             patch('ingestion.src.ingest_master_tables.MASTER_TABLES', ('brand',)), \
             patch('ingestion.src.ingest_master_tables.columns_for', return_value=['id']), \
             patch('ingestion.src.ingest_master_tables.stats', return_value=(2, 2, 1, 4)), \
             redirect_stdout(io.StringIO()):
            factory.return_value.__enter__.return_value = (source, local)
            master_main(['--confirm'])
        source.command.assert_not_called()
        source.insert.assert_not_called()
        local.command.assert_called_once_with('TRUNCATE TABLE laplap_raw.brand')
        self.assertEqual(local.insert.call_args.args[0], 'laplap_raw.brand')


if __name__ == '__main__':
    unittest.main()
