{{ config(materialized='view') }}

SELECT
    id AS gpu_model_id,
    name AS gpu_name,
    brand_id AS gpu_brand_id,
    is_active,

    created_on,
    changed_on,
    elton_created_at AS source_created_at,

    _ingested_at,
    _ingestion_batch_id,
    _source_system

FROM {{ source('raw', 'gpu_model') }}