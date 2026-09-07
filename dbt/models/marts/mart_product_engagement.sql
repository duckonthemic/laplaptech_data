WITH events AS (

    SELECT *
    FROM {{ ref('int_events_enriched') }}
    WHERE is_laptop_reference_resolved = true

)

SELECT
    laptop_id,
    laptop_name,
    brand_name,
    cpu_name,
    gpu_name,

    countIf(event_name = 'pageview') AS product_pageviews,

    countIf(
        event_name = 'select_device_for_comparison'
    ) AS comparison_selections,

    countIf(
        event_name = 'add_to_comparison'
    ) AS comparison_adds,

    count() AS total_product_events,

    uniqExact(visitor_id) AS unique_visitors,

    uniqExact(session_id) AS unique_sessions

FROM events

GROUP BY
    laptop_id,
    laptop_name,
    brand_name,
    cpu_name,
    gpu_name