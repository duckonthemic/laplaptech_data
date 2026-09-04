"""Manually invoked, limited local test ingestion for clickstream events."""

from __future__ import annotations

import argparse
import uuid

from .connections import get_local_client, get_source_client
from .temporal import epoch_millis_select_list, restore_datetime64_values


SOURCE_COLUMNS = [
    "id",
    "event_name",
    "user_id",
    "event_data",
    "device",
    "event_local_timestamp",
    "event_received_on_server_timestamp",
    "session_id",
    "user_psuedo_id",  # Preserve the source spelling in Bronze.
    "app_version",
    "elton_created_at",
]
LOCAL_TARGET_TABLE = "laplap_raw.user_event_tracking"
TEST_ROW_LIMIT = 100


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a 100-row local Bronze test load.")
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="required acknowledgement before writing to the local Bronze table",
    )
    args = parser.parse_args()
    if not args.confirm:
        parser.error("No data was written. Re-run with --confirm to load 100 rows locally.")
    return args


def main() -> None:
    parse_args()
    batch_id = str(uuid.uuid4())
    print(
        f"About to insert up to {TEST_ROW_LIMIT} rows into LOCAL table "
        f"{LOCAL_TARGET_TABLE} using batch {batch_id}."
    )

    source = None
    local = None
    try:
        source = get_source_client()
        local = get_local_client()

        # Remote source: SELECT only. This code never writes to laplaptech.
        result = source.query(
            "SELECT "
            + ", ".join(epoch_millis_select_list("user_event_tracking", SOURCE_COLUMNS))
            + " FROM laplaptech.user_event_tracking ORDER BY id LIMIT 100"
        )
        source_rows = restore_datetime64_values(
            "user_event_tracking", SOURCE_COLUMNS, result.result_rows
        )
        rows = [row + (batch_id,) for row in source_rows]

        # Local target only. Defaults populate _ingested_at and _source_system.
        local.insert(
            LOCAL_TARGET_TABLE,
            rows,
            column_names=[*SOURCE_COLUMNS, "_ingestion_batch_id"],
        )

        verification = local.query(
            "SELECT count(), uniqExact(id) "
            "FROM laplap_raw.user_event_tracking "
            "WHERE _ingestion_batch_id = {batch_id:String}",
            parameters={"batch_id": batch_id},
        ).result_rows[0]
        print(f"Local batch rows: {verification[0]}")
        print(f"Local batch unique IDs: {verification[1]}")
    finally:
        if source is not None:
            source.close()
        if local is not None:
            local.close()


if __name__ == "__main__":
    main()
