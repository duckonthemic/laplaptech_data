WITH events AS (

    SELECT *
    FROM {{ ref('stg_user_events') }}

),

laptops AS (

    SELECT *
    FROM {{ ref('int_dim_laptop') }}

)

SELECT
    e.event_id,
    e.event_name,

    e.authenticated_user_id,
    e.visitor_id,
    e.session_id,

    e.event_local_timestamp,
    e.event_at_utc,

    e.event_received_on_server_timestamp,
    e.event_received_at_utc,

    e.search_keyword,
    e.page_name,
    e.page_url,
    e.referrer,

    e.laptop_id,

    -- Product enrichment
    l.laptop_name,
    l.brand_name,
    l.cpu_name,
    l.gpu_name,

    l.is_gaming_laptop,
    l.is_workstation,

    l.battery_capacity_whr,
    l.screen_size,
    l.screen_ppi,
    l.laptop_weight,

    -- Useful data-quality flags
    e.laptop_id IS NOT NULL AS has_laptop_reference,

    (
        e.laptop_id IS NOT NULL
        AND l.laptop_id IS NOT NULL
    ) AS is_laptop_reference_resolved,

    -- Client/device information
    e.device_type,
    e.device_brand,
    e.device_name,

    e.os_name,
    e.os_version,

    e.manufacturer,
    e.user_agent,

    e.app_version,

    e.event_data_raw,
    e.device_raw,

    e.source_created_at,
    e._ingested_at,
    e._ingestion_batch_id,
    e._source_system

FROM events AS e

LEFT JOIN laptops AS l
    ON e.laptop_id = l.laptop_id