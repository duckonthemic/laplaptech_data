WITH sessions AS (

    SELECT *
    FROM {{ ref('int_sessions') }}

)

SELECT
    count() AS total_sessions,

    /*
        Stage 1:
        Session có Search.
    */
    countIf(
        reached_search
    ) AS search_sessions,

    /*
        Stage 2:
        Product View phải xảy ra SAU Search.
    */
    countIf(
        reached_product_view_after_search
    ) AS product_view_sessions,

    /*
        Stage 3:
        Select Comparison phải xảy ra
        SAU Product View hợp lệ.
    */
    countIf(
        reached_comparison_after_view
    ) AS comparison_selection_sessions,

    /*
        Stage 4:
        Add Comparison phải xảy ra
        SAU Select Comparison hợp lệ.
    */
    countIf(
        reached_add_after_selection
    ) AS comparison_add_sessions,

    /*
        Bao nhiêu % tất cả session có Search.
    */
    round(
        100.0
        * countIf(reached_search)
        / nullIf(count(), 0),
        2
    ) AS search_rate_pct,

    /*
        Trong số session đã Search,
        bao nhiêu % tiếp tục Product View.
    */
    round(
        100.0
        * countIf(reached_product_view_after_search)
        / nullIf(
            countIf(reached_search),
            0
        ),
        2
    ) AS search_to_product_view_pct,

    /*
        Trong số session đã Product View sau Search,
        bao nhiêu % tiếp tục Select Comparison.
    */
    round(
        100.0
        * countIf(reached_comparison_after_view)
        / nullIf(
            countIf(reached_product_view_after_search),
            0
        ),
        2
    ) AS product_view_to_comparison_pct,

    /*
        Trong số session đã Select Comparison hợp lệ,
        bao nhiêu % tiếp tục Add Comparison.
    */
    round(
        100.0
        * countIf(reached_add_after_selection)
        / nullIf(
            countIf(reached_comparison_after_view),
            0
        ),
        2
    ) AS comparison_to_add_pct

FROM sessions