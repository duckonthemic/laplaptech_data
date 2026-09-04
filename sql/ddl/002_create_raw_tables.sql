-- LOCAL ONLY: Bronze/raw replicas of the read-only laplaptech source tables.
-- Do not run this file against the remote source database.
-- The source schemas retain their original column names and data types,
-- including the source typo `user_psuedo_id`.

CREATE TABLE IF NOT EXISTS laplap_raw.brand
(
    created_on Nullable(DateTime64(3)),
    changed_on Nullable(DateTime64(3)),
    id Nullable(Int64),
    name Nullable(String),
    created_by_fk Nullable(Int64),
    changed_by_fk Nullable(Int64),
    is_chip_brand Nullable(Bool),
    elton_created_at Nullable(DateTime64(3)),
    _ingested_at DateTime64(3) DEFAULT now64(3),
    _ingestion_batch_id String,
    _source_system LowCardinality(String) DEFAULT 'laplaptech'
)
ENGINE = ReplacingMergeTree(_ingested_at)
ORDER BY id
SETTINGS allow_nullable_key = 1;

CREATE TABLE IF NOT EXISTS laplap_raw.cpu_model
(
    created_on Nullable(DateTime64(3)),
    changed_on Nullable(DateTime64(3)),
    id Nullable(Int64),
    name Nullable(String),
    created_by_fk Nullable(Int64),
    changed_by_fk Nullable(Int64),
    brand_id Nullable(Int64),
    is_active Nullable(Bool),
    elton_created_at Nullable(DateTime64(3)),
    _ingested_at DateTime64(3) DEFAULT now64(3),
    _ingestion_batch_id String,
    _source_system LowCardinality(String) DEFAULT 'laplaptech'
)
ENGINE = ReplacingMergeTree(_ingested_at)
ORDER BY id
SETTINGS allow_nullable_key = 1;

CREATE TABLE IF NOT EXISTS laplap_raw.gpu_model
(
    created_on Nullable(DateTime64(3)),
    changed_on Nullable(DateTime64(3)),
    id Nullable(Int64),
    name Nullable(String),
    created_by_fk Nullable(Int64),
    changed_by_fk Nullable(Int64),
    brand_id Nullable(Int64),
    is_active Nullable(Bool),
    elton_created_at Nullable(DateTime64(3)),
    _ingested_at DateTime64(3) DEFAULT now64(3),
    _ingestion_batch_id String,
    _source_system LowCardinality(String) DEFAULT 'laplaptech'
)
ENGINE = ReplacingMergeTree(_ingested_at)
ORDER BY id
SETTINGS allow_nullable_key = 1;

CREATE TABLE IF NOT EXISTS laplap_raw.laptop_model
(
    created_on Nullable(DateTime64(3)),
    changed_on Nullable(DateTime64(3)),
    id Nullable(Int64),
    name Nullable(String),
    is_gaming_laptop Nullable(Bool),
    year_introduce Nullable(Int64),
    cpu_note Nullable(String),
    cpu_tdp Nullable(String),
    gpu_note Nullable(String),
    battery_capacity_whr Nullable(Float64),
    created_by_fk Nullable(Int64),
    changed_by_fk Nullable(Int64),
    brand_id Nullable(Int64),
    cpu_model_id Nullable(Int64),
    gpu_model_id Nullable(Int64),
    is_visible Nullable(Bool),
    is_active Nullable(Bool),
    gpu_tdp Nullable(String),
    screen_size Nullable(Float64),
    screen_dimension_width Nullable(Float64),
    screen_dimension_height Nullable(Float64),
    screen_ppi Nullable(Float64),
    laptop_weight Nullable(Float64),
    charger_weight Nullable(Float64),
    brand_model_codename Nullable(String),
    thumbnail_image_url Nullable(String),
    is_workstation Nullable(Bool),
    is_mobile_device Nullable(Bool),
    elton_created_at Nullable(DateTime64(3)),
    _ingested_at DateTime64(3) DEFAULT now64(3),
    _ingestion_batch_id String,
    _source_system LowCardinality(String) DEFAULT 'laplaptech'
)
ENGINE = ReplacingMergeTree(_ingested_at)
ORDER BY id
SETTINGS allow_nullable_key = 1;

CREATE TABLE IF NOT EXISTS laplap_raw.laptop_benchmark_result
(
    created_on Nullable(DateTime64(3)),
    changed_on Nullable(DateTime64(3)),
    id Nullable(Int64),
    office_battery_result_minutes Nullable(Float64),
    gaming_battery_result_minutes Nullable(Float64),
    note Nullable(String),
    laptop_model_id Nullable(Int64),
    created_by_fk Nullable(Int64),
    changed_by_fk Nullable(Int64),
    geekbench_6_compute_gpu_plugged_in Nullable(Float64),
    geekbench_6_compute_gpu_battery Nullable(Float64),
    is_active Nullable(Bool),
    geekbench_6_cpu_single_core_plugged_in Nullable(Float64),
    geekbench_6_cpu_single_core_battery Nullable(Float64),
    geekbench_6_cpu_multi_core_plugged_in Nullable(Float64),
    geekbench_6_cpu_multi_core_battery Nullable(Float64),
    review_video_url Nullable(String),
    foldable_opening_battery_result_minutes Nullable(Float64),
    geekbench_7_cpu_single_core_plugged_in Nullable(Float64),
    geekbench_7_cpu_single_core_battery Nullable(Float64),
    geekbench_7_cpu_multi_core_plugged_in Nullable(Float64),
    geekbench_7_cpu_multi_core_battery Nullable(Float64),
    geekbench_7_compute_gpu_plugged_in Nullable(Float64),
    geekbench_7_compute_gpu_battery Nullable(Float64),
    elton_created_at Nullable(DateTime64(3)),
    _ingested_at DateTime64(3) DEFAULT now64(3),
    _ingestion_batch_id String,
    _source_system LowCardinality(String) DEFAULT 'laplaptech'
)
ENGINE = ReplacingMergeTree(_ingested_at)
ORDER BY id
SETTINGS allow_nullable_key = 1;

CREATE TABLE IF NOT EXISTS laplap_raw.user_event_tracking
(
    id Nullable(Int64),
    event_name Nullable(String),
    user_id Nullable(Int64),
    event_data Nullable(String),
    device Nullable(String),
    event_local_timestamp Nullable(Int64),
    event_received_on_server_timestamp Nullable(Int64),
    session_id Nullable(String),
    user_psuedo_id Nullable(String),
    app_version Nullable(String),
    elton_created_at Nullable(DateTime64(3)),
    _ingested_at DateTime64(3) DEFAULT now64(3),
    _ingestion_batch_id String,
    _source_system LowCardinality(String) DEFAULT 'laplaptech'
)
ENGINE = ReplacingMergeTree(_ingested_at)
ORDER BY id
SETTINGS allow_nullable_key = 1;
