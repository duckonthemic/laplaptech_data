# Dashboard Runbook

The Streamlit dashboard reads only from the local ClickHouse warehouse. It
queries `laplap_marts`, `laplap_intermediate`, and `laplap_raw`; it never
connects to the remote ClickHouse source.

## Prerequisites

- Docker Desktop with the local ClickHouse service available on port `8123`.
- Python with a dedicated dashboard environment.
- A local `.env` when local ClickHouse uses non-default credentials. Do not
  commit that file or print its values.

## Start the Warehouse

From the repository root:

```powershell
docker compose up -d
Invoke-WebRequest http://localhost:8123/ping | Select-Object -ExpandProperty Content
```

The health check must return `Ok.`.

## Build the Warehouse Models

Use the real Bronze layer for the dashboard, not the development fixture:

```powershell
Remove-Item Env:DBT_RAW_SCHEMA -ErrorAction SilentlyContinue
Push-Location dbt
..\.venv-dbt\Scripts\dbt.exe build --profiles-dir .
Pop-Location
```

## Install Dashboard Dependencies

From the repository root, create a separate environment without changing
`.venv-dbt`:

```powershell
python -m venv .venv-dashboard
.\.venv-dashboard\Scripts\python.exe -m pip install --upgrade pip
.\.venv-dashboard\Scripts\python.exe -m pip install -r dashboards\requirements.txt
```

The dashboard reads `LOCAL_CH_HOST`, `LOCAL_CH_HTTP_PORT`,
`LOCAL_CH_USERNAME`, and `LOCAL_CH_PASSWORD` from the environment or untracked
`.env`. Its host is restricted to `localhost`, `127.0.0.1`, or `::1`.

## Start the Dashboard

```powershell
.\.venv-dashboard\Scripts\streamlit.exe run dashboards\app.py
```

Open [http://localhost:8501](http://localhost:8501). Use the in-app refresh
control after rebuilding dbt models or loading more local Bronze data.

## Troubleshooting

- `Unable to query the local ClickHouse warehouse`: verify the health endpoint,
  local connection variables, and that the dbt build completed successfully.
- Empty product section: `mart_product_engagement` only includes events with a
  resolved laptop reference; the dashboard intentionally does not infer missing
  product links.
- Empty or stale marts: clear `DBT_RAW_SCHEMA`, rerun `dbt build`, then refresh
  the dashboard.
- Port conflict: use `--server.port <PORT>` with Streamlit and open that local
  port instead.
