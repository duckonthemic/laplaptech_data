"""Offline safety checks for the opt-in integration harness."""

from contextlib import redirect_stdout
import io
import unittest
from unittest.mock import MagicMock, patch

from ingestion.tests.integration_test_initial_load import TestClient, main


class HarnessTests(unittest.TestCase):
    def test_without_confirmation_does_not_connect(self):
        with patch('ingestion.tests.integration_test_initial_load.clickhouse_connect.get_client') as connect, \
             redirect_stdout(io.StringIO()):
            main([])
        connect.assert_not_called()

    def test_target_insert_translates_to_test_database(self):
        real = MagicMock()
        target = TestClient(real, 'target')
        target.insert('laplap_raw.user_event_tracking', [(1,)], ['id'])
        self.assertEqual(real.insert.call_args.args[0], 'laplap_test_target.user_event_tracking')
        self.assertEqual(target.batches, [[1]])

    def test_source_insert_and_production_command_rejected(self):
        real = MagicMock()
        source = TestClient(real, 'source')
        with self.assertRaises(AssertionError):
            source.insert('laplap_raw.user_event_tracking', [(1,)], ['id'])
        with self.assertRaises(AssertionError):
            source.command('TRUNCATE TABLE laplap_raw.user_event_tracking')
        real.insert.assert_not_called()
        real.command.assert_not_called()


if __name__ == '__main__':
    unittest.main()
