WITH searches AS (

    SELECT
        search_keyword AS raw_search_keyword,
        visitor_id,
        session_id
    FROM {{ ref('int_events_enriched') }}
    WHERE event_name = 'search_for_device'
      AND search_keyword IS NOT NULL

),

normalized_searches AS (

    SELECT
        nullIf(
            lowerUTF8(trimBoth(raw_search_keyword)),
            ''
        ) AS normalized_search_keyword,
        visitor_id,
        session_id,
        raw_search_keyword
    FROM searches

)

SELECT
    normalized_search_keyword AS search_keyword,

    count() AS search_count,

    uniqExact(visitor_id) AS unique_visitors,

    uniqExact(session_id) AS unique_sessions,

    uniqExact(raw_search_keyword) AS raw_search_variants

FROM normalized_searches

WHERE normalized_search_keyword IS NOT NULL

GROUP BY normalized_search_keyword
