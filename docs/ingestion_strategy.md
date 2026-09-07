# Ingestion Strategy

## Safety boundary

`laplaptech` is a read-only remote source. Ingestion clients may issue only
`SELECT` statements to that source. Every write must target `laplap_raw.*` on
the local ClickHouse instance configured by `LOCAL_CH_HOST`.

## Small master tables

The following small dimensions use full snapshot ingestion per batch:

- `brand`
- `cpu_model`
- `gpu_model`
- `laptop_model`
- `laptop_benchmark_result`

Their size is small enough that a complete source read is simple, auditable,
and avoids premature change-data-capture complexity. Each loaded row includes
an ingestion batch ID and timestamp, allowing later reconciliation.

## Clickstream events

`user_event_tracking` now has a manually confirmed initial load. Each batch uses:

```sql
SELECT ...
FROM laplaptech.user_event_tracking
WHERE id > {last_id}
  AND id <= {initial_high_watermark}
ORDER BY id
LIMIT {batch_size};
```

Keyset pagination is preferred to `OFFSET` pagination because it avoids
scanning and discarding prior rows on each batch. It is more predictable for a
growing table and resists shifting page boundaries as new rows arrive.

The watermark is `max(id)`. This assumes new events receive strictly increasing
IDs. That assumption must be validated before a production incremental pipeline
is implemented; late or out-of-order IDs would otherwise be skipped.

## Current status

Phase 3D implements the initial load commands. Implementation does not mean the
full load has run. Scheduled incremental ingestion is a future phase.

## Running plans and loads

Run from the repository root with the existing untracked environment configured:

```powershell
python -m ingestion.src.ingest_master_tables
python -m ingestion.src.initial_load_events --batch-size 10000
```

These commands print source counts, local counts and the planned actions without
writing data. A new event load aborts if the target contains existing test rows.
Inspect and resolve those rows manually before starting; the loader never clears
the event table. Local destinations must use a loopback host.

Only when the plan is acceptable, explicitly run:

```powershell
python -m ingestion.src.ingest_master_tables --confirm
python -m ingestion.src.initial_load_events --batch-size 10000 --confirm
```

A full snapshot reads a complete master table into memory, converts its dates,
then replaces that one local table. It preserves all source columns and compares
every value after insertion. Snapshot counts describe the rows actually fetched,
so a later source change does not change the expected count. Duplicate or null IDs
abort before clearing local data. Replacement uses TRUNCATE then INSERT and is
not atomic: an insert failure can leave that local master table empty. Rerun its
snapshot workflow deliberately after resolving the failure.

An initial load copies the event history for the first time. Batch ingestion
splits it into smaller requests, 10,000 rows by default. Keyset pagination starts
each next request after the last fetched ID. Gaps are valid: three IDs such as
1, 4, 103 mean three rows, not 103 rows. The first batch has no lower bound, so
zero and negative IDs are not silently omitted. OFFSET is avoided because it
repeatedly skips earlier rows and page positions can change on a live source.

The high watermark is the maximum source ID captured at the start. Keeping the
same upper bound for every batch prevents newer higher IDs from extending the
load forever. Save the printed watermark. This is a bounded ID range, not a
transactionally frozen snapshot: changes, deletions or late inserts below the
watermark can still affect results. Source IDs must be non-null and unique;
new rows must receive increasing IDs. The loader validates this basic key
contract, but it cannot prove future arrival order.

## Resume

After an interruption, first preview using the ORIGINAL printed watermark:

```powershell
python -m ingestion.src.initial_load_events --resume --high-watermark 767000 --batch-size 10000
```

Replace 767000 with the original value. Add `--confirm` only to execute. Resume
never captures a fresh maximum. It uses the local maximum ID as the last completed
boundary and checks source/local prefix counts and ranges before continuing.
Only resume a target containing the completed prefix of the same load, with one
writer. No automatic retry follows an uncertain insert outcome. Partial inserts,
concurrent writers, an incorrect watermark or modified source rows require
inspection. Counts/ranges cannot prove identical prefix contents; the final
sample is useful evidence, not a full-table checksum. Expected bounded row counts
are recalculated on resume because this version has no persisted run manifest.

## Validation and temporal fidelity

Source-to-target reconciliation compares what was read with what was stored.
Event completion requires bounded source and local count, uniqExact(id), min(id)
and max(id) to agree. It also rejects a count/range change from the start of that
execution. It compares every source field for the first and last 100 bounded IDs,
excluding ingestion metadata. Any mismatch exits nonzero. Metadata uses one UUID
per event batch (one per master snapshot), the local `_ingested_at` default, and
`_source_system = 'laplaptech'`.

Every mapped DateTime64(3) is read with `toUnixTimestamp64Milli`, converted by
the existing `temporal.py` helper to an aware UTC Python datetime, then inserted
with its original Bronze type. Null remains null. Reconciliation compares epoch
milliseconds, avoiding server display timezones and Windows naive-datetime
interpretation. No seven-hour adjustment is applied.

Future incremental loads will capture events arriving after this bounded initial
load, with durable checkpoints and a policy for late updates. They are not
implemented here. No scheduler or other platform services are introduced.

Offline tests:

```powershell
python -m unittest discover -s ingestion/tests -v
```

## Local-only integration test

```powershell
python -m ingestion.tests.integration_test_initial_load
python -m ingestion.tests.integration_test_initial_load --confirm
```

Without confirmation the command prints a plan without connecting. With confirmation,
it recreates `laplap_test_source` and `laplap_test_target` on local loopback ClickHouse
and drops these two disposable databases afterward, including on test failure.
Any existing contents of these dedicated test databases are discarded. Do not run
two instances concurrently. Production warehouse databases are not accessed.
Only LOCAL_CH_* connection settings are used; source credentials are not needed.

The harness uses the real Phase 3D loader with client adapters translating its
database references into test namespaces. It seeds 27 rows with gaps and nullable
JSON/date values, expects batches of 10/10/7, inserts an above-watermark event,
interrupts before the second batch and resumes with the original watermark.
It compares every source field, epoch milliseconds, metadata, row counts and ID
ranges, and checks the recorded insert batches to catch duplicate attempts even
if ReplacingMergeTree merges have already deduplicated stored rows. Successful
execution prints six PASS lines. A failure exits nonzero; no real integration
result is claimed until this command has been executed against local ClickHouse.
