"""Safely verify source and local ClickHouse connectivity."""

from __future__ import annotations

from .connections import get_local_client, get_source_client


def main() -> None:
    source = None
    local = None
    try:
        source = get_source_client()
        source.command("SELECT version()")
        print("Source ClickHouse: connected")

        local = get_local_client()
        local.command("SELECT version()")
        print("Local ClickHouse: connected")

        # Read-only source verification. Never write to the remote client.
        source_event_rows = source.command(
            "SELECT count() FROM laplaptech.user_event_tracking"
        )
        print(f"Source event rows: {source_event_rows}")
    finally:
        if source is not None:
            source.close()
        if local is not None:
            local.close()


if __name__ == "__main__":
    main()
