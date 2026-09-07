{{ config(materialized='view') }}

WITH source AS (
    SELECT *
    FROM {{ source('raw', 'user_event_tracking') }}
)

SELECT
    id AS event_id,
    event_name,

    user_id AS authenticated_user_id,
    user_psuedo_id AS visitor_id,
    session_id,
    app_version,

    event_local_timestamp,
    toDateTime(event_local_timestamp, 'UTC') AS event_at_utc,

    event_received_on_server_timestamp,
    toDateTime(
        event_received_on_server_timestamp,
        'UTC'
    ) AS event_received_at_utc,

    event_data AS event_data_raw,
    device AS device_raw,

    nullIf(
        JSONExtractString(ifNull(event_data, '{}'), 'keyword'),
        ''
    ) AS search_keyword,

    nullIf(
        JSONExtractString(ifNull(event_data, '{}'), 'page_name'),
        ''
    ) AS page_name,

    nullIf(
        JSONExtractString(ifNull(event_data, '{}'), 'url'),
        ''
    ) AS page_url,

    nullIf(
        JSONExtractString(ifNull(event_data, '{}'), 'referrer'),
        ''
    ) AS referrer,

    coalesce(
        JSONExtract(
            ifNull(event_data, '{}'),
            'device_id',
            'Nullable(Int64)'
        ),
        toInt64OrNull(
            JSONExtractString(
                ifNull(event_data, '{}'),
                'device_id'
            )
        )
    ) AS laptop_id,

    nullIf(
        JSONExtractString(ifNull(event_data, '{}'), 'sort_by'),
        ''
    ) AS comparison_sort_by,

    nullIf(
        JSONExtractString(
            ifNull(event_data, '{}'),
            'sort_direction'
        ),
        ''
    ) AS comparison_sort_direction,

    nullIf(
        JSONExtractString(ifNull(device, '{}'), 'device_type'),
        ''
    ) AS device_type,

    nullIf(
        JSONExtractString(ifNull(device, '{}'), 'device_brand'),
        ''
    ) AS device_brand,

    nullIf(
        JSONExtractString(ifNull(device, '{}'), 'device_name'),
        ''
    ) AS device_name,

    nullIf(
        JSONExtractString(ifNull(device, '{}'), 'os_name'),
        ''
    ) AS os_name,

    nullIf(
        JSONExtractString(ifNull(device, '{}'), 'os_version'),
        ''
    ) AS os_version,

    nullIf(
        JSONExtractString(ifNull(device, '{}'), 'manufacturer'),
        ''
    ) AS manufacturer,

    nullIf(
        JSONExtractString(ifNull(device, '{}'), 'user_agent'),
        ''
    ) AS user_agent,

    elton_created_at AS source_created_at,

    _ingested_at,
    _ingestion_batch_id,
    _source_system

FROM source