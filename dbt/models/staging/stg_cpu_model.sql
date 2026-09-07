{{ config(materialized='view') }}

SELECT
    id AS cpu_model_id,
    name AS cpu_name,
    brand_id AS cpu_brand_id,
    is_active,

    created_on,
    changed_on,
    elton_created_at AS source_created_at,

    _ingested_at,
    _ingestion_batch_id,
    _source_system

FROM {{ source('raw', 'cpu_model') }}