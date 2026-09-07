WITH events AS (

    SELECT *
    FROM {{ ref('int_events_enriched') }}

)

SELECT
    coalesce(device_type, 'Unknown') AS device_type,
    coalesce(os_name, 'Unknown') AS os_name,

    count() AS total_events,

    uniqExact(visitor_id) AS unique_visitors,
    uniqExact(session_id) AS unique_sessions,

    countIf(
        event_name = 'pageview'
    ) AS pageviews,

    countIf(
        event_name = 'search_for_device'
    ) AS search_events,

    countIf(
        event_name = 'select_device_for_comparison'
    ) AS comparison_selection_events,

    countIf(
        event_name = 'add_to_comparison'
    ) AS comparison_add_events

FROM events

GROUP BY
    device_type,
    os_name