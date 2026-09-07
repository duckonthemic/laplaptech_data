WITH events AS (

    SELECT *
    FROM {{ ref('int_events_enriched') }}

),

/*
    1. Base session aggregation
*/
session_base AS (

    SELECT
        session_id AS session_id,
        visitor_id AS visitor_id,

        min(event_at_utc) AS session_start_at,
        max(event_at_utc) AS session_end_at,

        dateDiff(
            'second',
            min(event_at_utc),
            max(event_at_utc)
        ) AS session_duration_seconds,

        count() AS event_count,

        countIf(
            event_name = 'search_for_device'
        ) > 0 AS searched,

        countIf(
            event_name = 'pageview'
            AND laptop_id IS NOT NULL
        ) > 0 AS viewed_product,

        countIf(
            event_name = 'select_device_for_comparison'
        ) > 0 AS selected_for_comparison,

        countIf(
            event_name = 'add_to_comparison'
        ) > 0 AS added_to_comparison,

        uniqExactIf(
            laptop_id,
            laptop_id IS NOT NULL
        ) AS distinct_laptops_interacted,

        uniqExactIf(
            laptop_id,
            laptop_id IS NOT NULL
            AND is_laptop_reference_resolved
        ) AS distinct_resolved_laptops,

        /*
            Search đầu tiên trong session.
            Nếu không search -> NULL.
        */
        if(
            countIf(
                event_name = 'search_for_device'
            ) > 0,

            toNullable(
                minIf(
                    event_at_utc,
                    event_name = 'search_for_device'
                )
            ),

            NULL
        ) AS first_search_at

    FROM events

    GROUP BY
        session_id,
        visitor_id

),

/*
    2. Product view đầu tiên xảy ra SAU search.
*/
product_view_stage AS (

    SELECT
        e.session_id AS session_id,
        e.visitor_id AS visitor_id,

        if(
            countIf(
                s.first_search_at IS NOT NULL
                AND e.event_name = 'pageview'
                AND e.laptop_id IS NOT NULL
                AND e.event_at_utc >= s.first_search_at
            ) > 0,

            toNullable(
                minIf(
                    e.event_at_utc,
                    s.first_search_at IS NOT NULL
                    AND e.event_name = 'pageview'
                    AND e.laptop_id IS NOT NULL
                    AND e.event_at_utc >= s.first_search_at
                )
            ),

            NULL
        ) AS first_product_view_after_search_at

    FROM events AS e

    INNER JOIN session_base AS s
        ON e.session_id = s.session_id
       AND e.visitor_id = s.visitor_id

    GROUP BY
        e.session_id,
        e.visitor_id

),

/*
    3. Comparison selection đầu tiên
       xảy ra SAU product view hợp lệ.
*/
comparison_stage AS (

    SELECT
        e.session_id AS session_id,
        e.visitor_id AS visitor_id,

        if(
            countIf(
                p.first_product_view_after_search_at IS NOT NULL
                AND e.event_name = 'select_device_for_comparison'
                AND e.event_at_utc >= p.first_product_view_after_search_at
            ) > 0,

            toNullable(
                minIf(
                    e.event_at_utc,
                    p.first_product_view_after_search_at IS NOT NULL
                    AND e.event_name = 'select_device_for_comparison'
                    AND e.event_at_utc >= p.first_product_view_after_search_at
                )
            ),

            NULL
        ) AS first_comparison_after_view_at

    FROM events AS e

    INNER JOIN product_view_stage AS p
        ON e.session_id = p.session_id
       AND e.visitor_id = p.visitor_id

    GROUP BY
        e.session_id,
        e.visitor_id

),

/*
    4. Add comparison đầu tiên
       xảy ra SAU comparison selection hợp lệ.
*/
comparison_add_stage AS (

    SELECT
        e.session_id AS session_id,
        e.visitor_id AS visitor_id,

        if(
            countIf(
                c.first_comparison_after_view_at IS NOT NULL
                AND e.event_name = 'add_to_comparison'
                AND e.event_at_utc >= c.first_comparison_after_view_at
            ) > 0,

            toNullable(
                minIf(
                    e.event_at_utc,
                    c.first_comparison_after_view_at IS NOT NULL
                    AND e.event_name = 'add_to_comparison'
                    AND e.event_at_utc >= c.first_comparison_after_view_at
                )
            ),

            NULL
        ) AS first_add_after_selection_at

    FROM events AS e

    INNER JOIN comparison_stage AS c
        ON e.session_id = c.session_id
       AND e.visitor_id = c.visitor_id

    GROUP BY
        e.session_id,
        e.visitor_id

)

SELECT
    /*
        Explicit aliases ở final projection rất quan trọng
        với ClickHouse VIEW.
    */
    s.session_id AS session_id,
    s.visitor_id AS visitor_id,

    s.session_start_at AS session_start_at,
    s.session_end_at AS session_end_at,
    s.session_duration_seconds AS session_duration_seconds,

    s.event_count AS event_count,

    /*
        Participation flags:
        action từng xảy ra trong session,
        chưa xét sequence.
    */
    s.searched AS searched,
    s.viewed_product AS viewed_product,
    s.selected_for_comparison AS selected_for_comparison,
    s.added_to_comparison AS added_to_comparison,

    s.distinct_laptops_interacted AS distinct_laptops_interacted,
    s.distinct_resolved_laptops AS distinct_resolved_laptops,

    /*
        Strict funnel timestamps.
    */
    s.first_search_at AS first_search_at,

    p.first_product_view_after_search_at
        AS first_product_view_after_search_at,

    c.first_comparison_after_view_at
        AS first_comparison_after_view_at,

    a.first_add_after_selection_at
        AS first_add_after_selection_at,

    /*
        Strict sequence-aware funnel flags.
    */
    s.first_search_at IS NOT NULL
        AS reached_search,

    p.first_product_view_after_search_at IS NOT NULL
        AS reached_product_view_after_search,

    c.first_comparison_after_view_at IS NOT NULL
        AS reached_comparison_after_view,

    a.first_add_after_selection_at IS NOT NULL
        AS reached_add_after_selection

FROM session_base AS s

LEFT JOIN product_view_stage AS p
    ON s.session_id = p.session_id
   AND s.visitor_id = p.visitor_id

LEFT JOIN comparison_stage AS c
    ON s.session_id = c.session_id
   AND s.visitor_id = c.visitor_id

LEFT JOIN comparison_add_stage AS a
    ON s.session_id = a.session_id
   AND s.visitor_id = a.visitor_id