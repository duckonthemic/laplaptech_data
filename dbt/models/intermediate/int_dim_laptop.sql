WITH laptops AS (

    SELECT *
    FROM {{ ref('stg_laptop_model') }}

),

brands AS (

    SELECT *
    FROM {{ ref('stg_brand') }}

),

cpus AS (

    SELECT *
    FROM {{ ref('stg_cpu_model') }}

),

gpus AS (

    SELECT *
    FROM {{ ref('stg_gpu_model') }}

)

SELECT
    l.laptop_id,
    l.laptop_name,

    l.brand_id,
    b.brand_name,

    l.cpu_model_id,
    c.cpu_name,

    l.gpu_model_id,
    g.gpu_name,

    l.is_gaming_laptop,
    l.is_workstation,
    l.is_mobile_device,

    l.introduction_year,

    l.battery_capacity_whr,

    l.screen_size,
    l.screen_dimension_width,
    l.screen_dimension_height,
    l.screen_ppi,

    l.laptop_weight,
    l.charger_weight,

    l.cpu_tdp,
    l.cpu_note,

    l.gpu_tdp,
    l.gpu_note,

    l.brand_model_codename,
    l.thumbnail_image_url,

    l.is_visible,
    l.is_active,

    l.source_created_at,
    l._ingested_at

FROM laptops AS l

LEFT JOIN brands AS b
    ON l.brand_id = b.brand_id

LEFT JOIN cpus AS c
    ON l.cpu_model_id = c.cpu_model_id

LEFT JOIN gpus AS g
    ON l.gpu_model_id = g.gpu_model_id