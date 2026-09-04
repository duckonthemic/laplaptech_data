"""Read-only source and local ClickHouse client factories."""

from __future__ import annotations

import os

import clickhouse_connect
from clickhouse_connect.driver.client import Client

from .config import ClickHouseConnectionConfig, load_config


def _get_client(connection: ClickHouseConnectionConfig) -> Client:
    return clickhouse_connect.get_client(
        host=connection.host,
        port=connection.port,
        username=connection.username,
        password=connection.password,
        database=connection.database,
    )


def _bypass_proxy_for(host: str) -> None:
    """Keep direct ClickHouse traffic out of an unrelated HTTP proxy."""
    no_proxy = os.getenv("NO_PROXY") or os.getenv("no_proxy") or ""
    hosts = [entry.strip() for entry in no_proxy.split(",") if entry.strip()]
    if host not in hosts:
        hosts.append(host)
        os.environ["NO_PROXY"] = ",".join(hosts)


def get_source_client() -> Client:
    """Return a client for read-only queries against the remote source."""
    source = load_config().source
    _bypass_proxy_for(source.host)
    return _get_client(source)


def get_local_client() -> Client:
    """Return a client for local writes to laplap_raw only."""
    return _get_client(load_config().local)
