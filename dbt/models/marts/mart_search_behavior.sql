WITH searches AS (

    SELECT *
    FROM {{ ref('int_events_enriched') }}
    WHERE event_name = 'search_for_device'

)

SELECT
    search_keyword,

    count() AS search_count,

    uniqExact(visitor_id) AS unique_visitors,

    uniqExact(session_id) AS unique_sessions

FROM searches

WHERE search_keyword IS NOT NULL

GROUP BY search_keyword