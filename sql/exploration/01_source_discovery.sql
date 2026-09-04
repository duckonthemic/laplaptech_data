-- READ-ONLY SOURCE DISCOVERY
-- Run these queries only against the remote `laplaptech` database using a
-- read-only credential. This file contains SELECT and DESCRIBE statements only.

-- 1. Table inventory
SELECT
    database,
    name AS table_name,
    engine
FROM system.tables
WHERE database = 'laplaptech'
ORDER BY table_name;

-- Inspect source schemas without modifying them.
DESCRIBE TABLE laplaptech.user_event_tracking;
DESCRIBE TABLE laplaptech.laptop_model;
DESCRIBE TABLE laplaptech.brand;
DESCRIBE TABLE laplaptech.cpu_model;
DESCRIBE TABLE laplaptech.gpu_model;
DESCRIBE TABLE laplaptech.laptop_benchmark_result;

-- 2. Event taxonomy
SELECT
    event_name,
    count() AS event_count
FROM laplaptech.user_event_tracking
GROUP BY event_name
ORDER BY event_count DESC, event_name;

-- 3. Event, anonymous user, session, and authenticated-user counts
SELECT
    count() AS event_count,
    uniqExact(user_psuedo_id) AS anonymous_user_count,
    uniqExact(session_id) AS session_count,
    uniqExact(user_id) AS authenticated_user_count
FROM laplaptech.user_event_tracking;

-- 4. Available event time range
SELECT
    min(timestamp) AS first_event_at,
    max(timestamp) AS last_event_at
FROM laplaptech.user_event_tracking;

-- 5. Null and empty-value profile for key event fields
SELECT
    count() AS total_rows,
    countIf(isNull(id)) AS null_id_rows,
    countIf(isNull(event_name) OR event_name = '') AS null_or_empty_event_name_rows,
    countIf(isNull(user_psuedo_id) OR user_psuedo_id = '') AS null_or_empty_user_psuedo_id_rows,
    countIf(isNull(session_id) OR session_id = '') AS null_or_empty_session_id_rows,
    countIf(isNull(device) OR device = '') AS null_or_empty_device_rows,
    countIf(isNull(event_data)) AS null_event_data_rows
FROM laplaptech.user_event_tracking;

-- Confirm whether valid user_login events explain null event_data values.
SELECT
    event_name,
    count() AS event_count,
    countIf(isNull(event_data)) AS null_event_data_rows
FROM laplaptech.user_event_tracking
GROUP BY event_name
ORDER BY event_count DESC, event_name;

-- 6. Duplicate event ID check
SELECT
    count() AS total_rows,
    uniqExact(id) AS unique_event_ids,
    count() - uniqExact(id) AS duplicate_event_ids
FROM laplaptech.user_event_tracking;

-- 7. Top-level keys found in the variable event_data JSON payload.
SELECT
    key_value.1 AS json_key,
    count() AS occurrence_count
FROM laplaptech.user_event_tracking
ARRAY JOIN JSONExtractKeysAndValuesRaw(ifNull(event_data, '{}')) AS key_value
GROUP BY json_key
ORDER BY occurrence_count DESC, json_key;

-- 8. Top-level keys found in the comparatively stable device JSON payload.
SELECT
    key_value.1 AS json_key,
    count() AS occurrence_count
FROM laplaptech.user_event_tracking
ARRAY JOIN JSONExtractKeysAndValuesRaw(ifNull(device, '{}')) AS key_value
GROUP BY json_key
ORDER BY occurrence_count DESC, json_key;

-- 9. Event device_id to laptop_model integrity. String coercion supports both
-- numeric and quoted JSON device IDs. The second query lists any orphan values.
SELECT
    count() AS events_with_device_id,
    countIf(event_device_id IN (SELECT toString(id) FROM laplaptech.laptop_model)) AS matched_events,
    countIf(event_device_id NOT IN (SELECT toString(id) FROM laplaptech.laptop_model)) AS unmatched_events
FROM
(
    SELECT coalesce(
        nullIf(JSONExtractString(ifNull(event_data, '{}'), 'device_id'), ''),
        JSONExtractRaw(ifNull(event_data, '{}'), 'device_id')
    ) AS event_device_id
    FROM laplaptech.user_event_tracking
    WHERE JSONHas(ifNull(event_data, '{}'), 'device_id') = 1
)
WHERE event_device_id != '';

SELECT
    event_device_id,
    count() AS event_count
FROM
(
    SELECT coalesce(
        nullIf(JSONExtractString(ifNull(event_data, '{}'), 'device_id'), ''),
        JSONExtractRaw(ifNull(event_data, '{}'), 'device_id')
    ) AS event_device_id
    FROM laplaptech.user_event_tracking
    WHERE JSONHas(ifNull(event_data, '{}'), 'device_id') = 1
)
WHERE event_device_id != ''
  AND event_device_id NOT IN (SELECT toString(id) FROM laplaptech.laptop_model)
GROUP BY event_device_id
ORDER BY event_count DESC, event_device_id;

-- 10. Laptop dimension integrity checks.
SELECT
    count() AS laptop_models,
    countIf(brand_id IN (SELECT id FROM laplaptech.brand)) AS brand_matched,
    countIf(brand_id NOT IN (SELECT id FROM laplaptech.brand)) AS brand_unmatched
FROM laplaptech.laptop_model;

SELECT
    count() AS laptop_models,
    countIf(cpu_model_id IN (SELECT id FROM laplaptech.cpu_model)) AS cpu_matched,
    countIf(cpu_model_id NOT IN (SELECT id FROM laplaptech.cpu_model)) AS cpu_unmatched
FROM laplaptech.laptop_model;

SELECT
    count() AS laptop_models,
    countIf(gpu_model_id IN (SELECT id FROM laplaptech.gpu_model)) AS gpu_matched,
    countIf(gpu_model_id NOT IN (SELECT id FROM laplaptech.gpu_model)) AS gpu_unmatched
FROM laplaptech.laptop_model;
