"""Timezone-safe conversion helpers for Bronze DateTime64(3) source fields."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Iterable, Sequence


DATETIME64_COLUMNS_BY_TABLE = {
    "brand": ("created_on", "changed_on", "elton_created_at"),
    "cpu_model": ("created_on", "changed_on", "elton_created_at"),
    "gpu_model": ("created_on", "changed_on", "elton_created_at"),
    "laptop_model": ("created_on", "changed_on", "elton_created_at"),
    "laptop_benchmark_result": ("created_on", "changed_on", "elton_created_at"),
    "user_event_tracking": ("elton_created_at",),
}


def epoch_millis_to_utc_datetime(epoch_millis: int | None) -> datetime | None:
    """Convert a ClickHouse epoch-millisecond value into an aware UTC datetime."""
    if epoch_millis is None:
        return None

    seconds, millis = divmod(int(epoch_millis), 1_000)
    return datetime.fromtimestamp(seconds, tz=UTC).replace(microsecond=millis * 1_000)


def datetime64_columns(table_name: str) -> tuple[str, ...]:
    """Return source DateTime64(3) columns that need canonical transport."""
    try:
        return DATETIME64_COLUMNS_BY_TABLE[table_name]
    except KeyError as error:
        raise ValueError(f"No DateTime64 mapping is defined for {table_name}.") from error


def epoch_millis_select_list(table_name: str, columns: Iterable[str]) -> list[str]:
    """Select DateTime64 fields as epoch milliseconds without changing aliases."""
    temporal_columns = set(datetime64_columns(table_name))
    return [
        f"toUnixTimestamp64Milli({column}) AS {column}"
        if column in temporal_columns
        else column
        for column in columns
    ]


def restore_datetime64_values(
    table_name: str,
    columns: Sequence[str],
    rows: Iterable[Sequence[object]],
) -> list[tuple[object, ...]]:
    """Turn epoch-millisecond result fields into aware UTC datetimes for local insert."""
    temporal_columns = set(datetime64_columns(table_name))
    temporal_indexes = {
        index for index, column in enumerate(columns) if column in temporal_columns
    }

    return [
        tuple(
            epoch_millis_to_utc_datetime(value) if index in temporal_indexes else value
            for index, value in enumerate(row)
        )
        for row in rows
    ]
