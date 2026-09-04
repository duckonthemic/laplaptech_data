"""Read-only diagnostic for ClickHouse DateTime64(3) transport behavior."""

from __future__ import annotations

from datetime import UTC

from .connections import get_local_client, get_source_client
from .temporal import epoch_millis_to_utc_datetime


def main() -> None:
    source = None
    local = None
    try:
        source = get_source_client()
        local = get_local_client()
        source_value = source.query(
            "SELECT elton_created_at FROM laplaptech.user_event_tracking "
            "WHERE elton_created_at IS NOT NULL ORDER BY id LIMIT 1"
        ).result_rows[0][0]
        source_epoch_millis = source.query(
            "SELECT toUnixTimestamp64Milli(elton_created_at) "
            "FROM laplaptech.user_event_tracking "
            "WHERE elton_created_at IS NOT NULL ORDER BY id LIMIT 1"
        ).result_rows[0][0]
        canonical_value = epoch_millis_to_utc_datetime(source_epoch_millis)

        print(f"Source timezone: {source.command('SELECT timezone()')}")
        print(f"Local timezone: {local.command('SELECT timezone()')}")
        print(f"Source Python datetime tzinfo: {source_value.tzinfo}")
        print(f"Canonical Python datetime tzinfo: {canonical_value.tzinfo}")
        print(
            "Naive Python epoch delta (ms): "
            f"{int(source_value.timestamp() * 1_000) - source_epoch_millis}"
        )
        print(
            "UTC-aware Python epoch delta (ms): "
            f"{int(canonical_value.timestamp() * 1_000) - source_epoch_millis}"
        )
        assert canonical_value.tzinfo is UTC
    finally:
        if source is not None:
            source.close()
        if local is not None:
            local.close()


if __name__ == "__main__":
    main()
