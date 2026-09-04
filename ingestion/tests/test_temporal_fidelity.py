from __future__ import annotations

import unittest
from datetime import UTC

from ingestion.src.temporal import (
    DATETIME64_COLUMNS_BY_TABLE,
    epoch_millis_to_utc_datetime,
)


class TemporalFidelityTests(unittest.TestCase):
    def test_epoch_millis_becomes_an_aware_utc_datetime(self) -> None:
        epoch_millis = 1_735_689_123_456

        value = epoch_millis_to_utc_datetime(epoch_millis)

        self.assertIsNotNone(value)
        self.assertIs(value.tzinfo, UTC)
        self.assertEqual(int(value.timestamp() * 1_000), epoch_millis)

    def test_nullable_datetime64_remains_null(self) -> None:
        self.assertIsNone(epoch_millis_to_utc_datetime(None))

    def test_every_bronze_datetime64_column_has_a_mapping(self) -> None:
        self.assertEqual(
            DATETIME64_COLUMNS_BY_TABLE,
            {
                "brand": ("created_on", "changed_on", "elton_created_at"),
                "cpu_model": ("created_on", "changed_on", "elton_created_at"),
                "gpu_model": ("created_on", "changed_on", "elton_created_at"),
                "laptop_model": ("created_on", "changed_on", "elton_created_at"),
                "laptop_benchmark_result": ("created_on", "changed_on", "elton_created_at"),
                "user_event_tracking": ("elton_created_at",),
            },
        )


if __name__ == "__main__":
    unittest.main()
