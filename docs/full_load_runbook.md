# Full Load Runbook

Use this runbook only after the remote source is available. The remote
ClickHouse database is read-only. Never run `INSERT`, `UPDATE`, `DELETE`,
`TRUNCATE`, `ALTER`, `CREATE`, or `DROP` against it, and never print or commit
credentials.

## 1. Start Local ClickHouse

From the repository root:

```powershell
docker compose up -d
docker compose ps
Invoke-WebRequest http://localhost:8123/ping | Select-Object -ExpandProperty Content
```

The health endpoint must return `Ok.` before loading. The Docker Compose
healthcheck is also visible in `docker compose ps`.

## 2. Verify Read-Only Connectivity

Ensure the untracked local `.env` contains the required source and local
connection variables, then run:

```powershell
python -m ingestion.src.test_connections
python -m ingestion.src.diagnose_temporal_fidelity
```

Both commands query the source without writing to it. The temporal diagnostic
must report an aware UTC canonical datetime and a zero UTC-aware epoch delta.

## 3. Run Python Tests

```powershell
python -m pytest -v
```

Resolve any failure before changing local warehouse data.

## 4. Preview and Load Master Snapshots

First inspect the no-write plan:

```powershell
python -m ingestion.src.ingest_master_tables
```

When the counts and destination are correct, explicitly replace each local
master snapshot:

```powershell
python -m ingestion.src.ingest_master_tables --confirm
```

This command only writes local `laplap_raw` master tables. It reads each full
source table before replacing its corresponding local snapshot.

## 5. Prepare a New Event Load

For a new load, inspect the local target in a local ClickHouse SQL console:

```sql
SELECT count(), uniqExact(id), min(id), max(id)
FROM laplap_raw.user_event_tracking;
```

The count must be zero. Do not automatically truncate a populated real Bronze
event table. Investigate it, preserve its context, and decide on a deliberate
recovery procedure before starting over.

## 6. Capture and Record the Initial Watermark

Run the event plan without `--confirm`:

```powershell
python -m ingestion.src.initial_load_events --batch-size 10000
```

Record the printed `Initial high watermark` in the load record before executing
anything. The source IDs can contain gaps: row count is not `max(id)`.

## 7. Run the Bounded Initial Event Load

With the recorded plan accepted and an empty local event target:

```powershell
python -m ingestion.src.initial_load_events --batch-size 10000 --confirm
```

The loader reads only IDs up to the recorded high watermark with keyset
pagination. It validates bounded counts, unique IDs, ID range, and first/last
100 source-to-target field samples before reporting success.

## 8. Resume an Interrupted Load

Use the original recorded watermark, never a new source maximum. Preview first:

```powershell
python -m ingestion.src.initial_load_events --resume --high-watermark <ORIGINAL_ID> --batch-size 10000
```

After the prefix checks pass, resume explicitly:

```powershell
python -m ingestion.src.initial_load_events --resume --high-watermark <ORIGINAL_ID> --batch-size 10000 --confirm
```

Resume uses `max(id)` from the local target as its last completed boundary and
checks that the local prefix matches the original bounded source range. Do not
run concurrent writers or retry an uncertain insert automatically.

## 9. Reconcile Locally

The loader's final validation is the authoritative bounded-load reconciliation.
In a local SQL console, independently inspect the target summary:

```sql
SELECT count(), uniqExact(id), min(id), max(id)
FROM laplap_raw.user_event_tracking;
```

DateTime64 fidelity is validated in epoch milliseconds during ingestion; do not
compare formatted local timestamps as a timezone workaround.

## 10. Transform the Real Bronze Layer

Remove the development source override, then build dbt from the `dbt` directory:

```powershell
Remove-Item Env:DBT_RAW_SCHEMA -ErrorAction SilentlyContinue
Push-Location dbt
..\.venv-dbt\Scripts\dbt.exe build --profiles-dir .
..\.venv-dbt\Scripts\dbt.exe docs generate --profiles-dir .
Pop-Location
```

The default source is `laplap_raw`. Do not hardcode a development schema in
production configuration.

## 11. Validate Gold Marts

Query the local warehouse after a successful dbt build:

```sql
SELECT * FROM laplap_marts.mart_session_funnel;

SELECT count() FROM laplap_marts.mart_product_engagement;
SELECT count() FROM laplap_marts.mart_search_behavior;
SELECT count() FROM laplap_marts.mart_device_behavior;
```

Only proceed to dashboard work after the Bronze reconciliation and dbt build
have both succeeded.
