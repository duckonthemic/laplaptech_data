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

`user_event_tracking` uses incremental batch ingestion. The initial planned
selection pattern is:

```sql
SELECT ...
FROM laplaptech.user_event_tracking
WHERE id > {last_id}
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

The repository contains a manually invoked 100-row local test-load script only.
It is not a production pipeline and must not be used for a full 766k-row load.
