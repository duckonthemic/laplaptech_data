{{ config(materialized='view') }}

SELECT
    id AS brand_id,
    name AS brand_name,
    is_chip_brand,

    created_on,
    changed_on,
    elton_created_at AS source_created_at,

    _ingested_at,
    _ingestion_batch_id,
    _source_system

FROM {{ source('raw', 'brand') }}