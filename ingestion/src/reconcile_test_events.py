"""Read-only reconciliation for a manually loaded 100-row Bronze test batch."""

from __future__ import annotations

import argparse

from .connections import get_local_client, get_source_client
from .temporal import epoch_millis_select_list
from .test_ingest_events import SOURCE_COLUMNS, TEST_ROW_LIMIT


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Reconcile a 100-row local Bronze test batch.")
    parser.add_argument("--batch-id", required=True, help="local ingestion batch UUID to verify")
    return parser.parse_args()


def _column_mismatch_count(
    source_by_id: dict[object, tuple[object, ...]],
    local_by_id: dict[object, tuple[object, ...]],
    column_index: int,
) -> int:
    return sum(
        source_by_id[event_id][column_index] != local_by_id[event_id][column_index]
        for event_id in source_by_id
    )


def main() -> None:
    args = parse_args()
    source = None
    local = None
    try:
        source = get_source_client()
        local = get_local_client()

        # Remote source: SELECT only. DateTime64 is compared as epoch milliseconds.
        select_list = ", ".join(epoch_millis_select_list("user_event_tracking", SOURCE_COLUMNS))
        source_rows = source.query(
            "SELECT "
            + select_list
            + " FROM laplaptech.user_event_tracking ORDER BY id LIMIT 100"
        ).result_rows
        local_rows = local.query(
            "SELECT "
            + select_list
            + " FROM laplap_raw.user_event_tracking "
            "WHERE _ingestion_batch_id = {batch_id:String} ORDER BY id",
            parameters={"batch_id": args.batch_id},
        ).result_rows

        source_by_id = {row[0]: tuple(row) for row in source_rows}
        local_by_id = {row[0]: tuple(row) for row in local_rows}
        failures: list[str] = []

        print(f"Rows: {len(source_rows)} == {len(local_rows)}")
        if len(source_rows) != TEST_ROW_LIMIT or len(local_rows) != TEST_ROW_LIMIT:
            failures.append("expected exactly 100 source and local rows")

        print(f"Unique IDs: {len(source_by_id)} == {len(local_by_id)}")
        if len(source_by_id) != TEST_ROW_LIMIT or len(local_by_id) != TEST_ROW_LIMIT:
            failures.append("expected 100 unique source and local IDs")
        if source_by_id.keys() != local_by_id.keys():
            failures.append("source and local ID sets differ")

        for index, column in enumerate(SOURCE_COLUMNS):
            if source_by_id.keys() != local_by_id.keys():
                print(f"{column}: NOT COMPARED")
                continue
            mismatch_count = _column_mismatch_count(source_by_id, local_by_id, index)
            label = f"{column} (epoch milliseconds)" if column == "elton_created_at" else column
            print(f"{label}: {'MATCH' if mismatch_count == 0 else f'MISMATCH ({mismatch_count})'}")
            if mismatch_count:
                failures.append(f"{column} has {mismatch_count} mismatches")

        if failures:
            raise SystemExit("Reconciliation failed: " + "; ".join(failures))
        print("Reconciliation: PASS")
    finally:
        if source is not None:
            source.close()
        if local is not None:
            local.close()


if __name__ == "__main__":
    main()
