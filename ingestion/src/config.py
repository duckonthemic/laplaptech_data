"""Environment-only configuration for ClickHouse connections."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class ClickHouseConnectionConfig:
    host: str
    port: int
    database: str
    username: str
    password: str


@dataclass(frozen=True)
class AppConfig:
    source: ClickHouseConnectionConfig
    local: ClickHouseConnectionConfig


def _required(name: str) -> str:
    value = os.getenv(name)
    if value is None or not value.strip():
        raise RuntimeError(f"Required environment variable is missing: {name}")
    return value


def _port(name: str, value: str) -> int:
    try:
        port = int(value)
    except ValueError as error:
        raise RuntimeError(f"Environment variable {name} must be an integer.") from error

    if not 1 <= port <= 65535:
        raise RuntimeError(f"Environment variable {name} must be between 1 and 65535.")
    return port


def load_config() -> AppConfig:
    """Load connection settings from environment variables and an optional .env file."""
    load_dotenv(override=False)

    source = ClickHouseConnectionConfig(
        host=_required("SOURCE_CH_HOST"),
        port=_port("SOURCE_CH_PORT", _required("SOURCE_CH_PORT")),
        database=_required("SOURCE_CH_DATABASE"),
        username=_required("SOURCE_CH_USERNAME"),
        password=_required("SOURCE_CH_PASSWORD"),
    )
    local = ClickHouseConnectionConfig(
        host=os.getenv("LOCAL_CH_HOST", "localhost"),
        port=_port("LOCAL_CH_HTTP_PORT", os.getenv("LOCAL_CH_HTTP_PORT", "8123")),
        database="default",
        username=os.getenv("LOCAL_CH_USERNAME", "default"),
        password=os.getenv("LOCAL_CH_PASSWORD", ""),
    )
    return AppConfig(source=source, local=local)
