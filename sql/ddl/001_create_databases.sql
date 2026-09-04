-- Local-only databases for the LapLap Analytics warehouse layers.
-- This script is mounted into the official ClickHouse image and runs on first
-- initialization of the named volume. Each statement remains safe to rerun.

CREATE DATABASE IF NOT EXISTS laplap_raw;
CREATE DATABASE IF NOT EXISTS laplap_staging;
CREATE DATABASE IF NOT EXISTS laplap_intermediate;
CREATE DATABASE IF NOT EXISTS laplap_marts;
