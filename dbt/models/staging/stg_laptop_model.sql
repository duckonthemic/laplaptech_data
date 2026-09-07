{{ config(materialized='view') }}

SELECT
    id AS laptop_id,
    name AS laptop_name,

    brand_id,
    cpu_model_id,
    gpu_model_id,

    is_gaming_laptop,
    is_workstation,
    is_mobile_device,

    year_introduce AS introduction_year,

    battery_capacity_whr,

    screen_size,
    screen_dimension_width,
    screen_dimension_height,
    screen_ppi,

    laptop_weight,
    charger_weight,

    cpu_tdp,
    cpu_note,
    gpu_tdp,
    gpu_note,

    brand_model_codename,
    thumbnail_image_url,

    is_visible,
    is_active,

    created_on,
    changed_on,
    elton_created_at AS source_created_at,

    _ingested_at,
    _ingestion_batch_id,
    _source_system

FROM {{ source('raw', 'laptop_model') }}