from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import clickhouse_connect
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}
CHART_COLORS = ["#0F766E", "#2563EB", "#E76F51", "#D97706", "#64748B"]


def local_connection_settings() -> dict[str, Any]:
    load_dotenv(PROJECT_ROOT / ".env", override=False)
    host = os.getenv("LOCAL_CH_HOST", "localhost").strip().lower()
    if host not in LOCAL_HOSTS:
        raise RuntimeError("Dashboard connections are restricted to local ClickHouse hosts.")
    try:
        port = int(os.getenv("LOCAL_CH_HTTP_PORT", "8123"))
    except ValueError as error:
        raise RuntimeError("LOCAL_CH_HTTP_PORT must be an integer.") from error
    return {
        "host": host,
        "port": port,
        "username": os.getenv("LOCAL_CH_USERNAME", "default"),
        "password": os.getenv("LOCAL_CH_PASSWORD", ""),
        "database": "default",
    }


@st.cache_resource
def get_local_client():
    client = clickhouse_connect.get_client(**local_connection_settings())
    client.command("SELECT 1")
    return client


def query_frame(sql: str) -> pd.DataFrame:
    return get_local_client().query_df(sql)


@st.cache_data(ttl=60, show_spinner=False)
def load_dashboard_data() -> dict[str, pd.DataFrame]:
    return {
        "funnel": query_frame(
            "SELECT * FROM laplap_marts.mart_session_funnel LIMIT 1"
        ),
        "products": query_frame(
            "SELECT laptop_name, brand_name, total_product_events, product_pageviews, "
            "comparison_selections, comparison_adds, unique_visitors, unique_sessions "
            "FROM laplap_marts.mart_product_engagement "
            "ORDER BY total_product_events DESC, laptop_name ASC LIMIT 10"
        ),
        "searches": query_frame(
            "SELECT search_keyword, search_count, unique_visitors, unique_sessions "
            "FROM laplap_marts.mart_search_behavior "
            "ORDER BY search_count DESC, search_keyword ASC LIMIT 15"
        ),
        "device_types": query_frame(
            "SELECT device_type, sum(total_events) AS total_events "
            "FROM laplap_marts.mart_device_behavior "
            "GROUP BY device_type ORDER BY total_events DESC LIMIT 10"
        ),
        "operating_systems": query_frame(
            "SELECT os_name, sum(total_events) AS total_events "
            "FROM laplap_marts.mart_device_behavior "
            "GROUP BY os_name ORDER BY total_events DESC LIMIT 10"
        ),
        "device_interactions": query_frame(
            "SELECT device_type, sum(pageviews) AS pageviews, "
            "sum(search_events) AS search_events, "
            "sum(comparison_selection_events) AS comparison_selections, "
            "sum(comparison_add_events) AS comparison_adds "
            "FROM laplap_marts.mart_device_behavior "
            "GROUP BY device_type ORDER BY sum(total_events) DESC LIMIT 8"
        ),
        "session_summary": query_frame(
            "SELECT round(avg(session_duration_seconds), 2) AS average_duration_seconds, "
            "quantile(0.5)(session_duration_seconds) AS p50_duration_seconds, "
            "quantile(0.9)(session_duration_seconds) AS p90_duration_seconds, "
            "round(avg(event_count), 2) AS average_events_per_session, "
            "countIf(searched) AS searched_sessions, "
            "countIf(NOT searched) AS non_searched_sessions "
            "FROM laplap_intermediate.int_sessions"
        ),
        "quality": query_frame(
            "SELECT raw.event_count, raw.unique_event_ids, raw.latest_ingested_at, "
            "products.product_count, reference_quality.unresolved_reference_events "
            "FROM (SELECT count() AS event_count, uniqExact(id) AS unique_event_ids, "
            "max(_ingested_at) AS latest_ingested_at "
            "FROM laplap_raw.user_event_tracking) AS raw "
            "CROSS JOIN (SELECT count() AS product_count "
            "FROM laplap_intermediate.int_dim_laptop) AS products "
            "CROSS JOIN (SELECT countIf(has_laptop_reference "
            "AND NOT is_laptop_reference_resolved) AS unresolved_reference_events "
            "FROM laplap_intermediate.int_events_enriched) AS reference_quality"
        ),
    }


def number(value: Any) -> int:
    if value is None or pd.isna(value):
        return 0
    return int(value)


def display_number(value: Any) -> str:
    return f"{number(value):,}"


def styled_chart(figure: go.Figure, height: int = 360) -> go.Figure:
    figure.update_layout(
        height=height,
        margin={"l": 8, "r": 8, "t": 26, "b": 8},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"color": "#1F2937"},
        legend_title_text="",
    )
    figure.update_xaxes(gridcolor="#E5E7EB", zerolinecolor="#E5E7EB")
    figure.update_yaxes(gridcolor="#E5E7EB", zerolinecolor="#E5E7EB")
    return figure


def render_funnel(funnel: pd.DataFrame) -> None:
    st.header("Strict Session Funnel")
    st.caption(
        "Every stage occurs after the prior stage: Search -> Product View -> "
        "Comparison Selection -> Add to Comparison."
    )
    if funnel.empty:
        st.warning("No session-funnel data is available in the local Gold mart.")
        return

    values = funnel.iloc[0]
    stages = [
        "Sessions",
        "Search",
        "Product View",
        "Comparison Selection",
        "Comparison Add",
    ]
    counts = [
        number(values["total_sessions"]),
        number(values["search_sessions"]),
        number(values["product_view_sessions"]),
        number(values["comparison_selection_sessions"]),
        number(values["comparison_add_sessions"]),
    ]
    conversion_rates = [
        None,
        values["search_rate_pct"],
        values["search_to_product_view_pct"],
        values["product_view_to_comparison_pct"],
        values["comparison_to_add_pct"],
    ]

    chart_column, table_column = st.columns((3, 2), gap="large")
    with chart_column:
        figure = go.Figure(
            go.Funnel(
                y=stages,
                x=counts,
                textinfo="value+percent previous",
                marker={"color": CHART_COLORS},
            )
        )
        st.plotly_chart(styled_chart(figure), width="stretch")
    with table_column:
        stage_table = pd.DataFrame(
            {
                "Stage": stages,
                "Sessions": [f"{count:,}" for count in counts],
                "Conversion from prior": [
                    "Baseline" if rate is None else f"{float(rate):.2f}%"
                    for rate in conversion_rates
                ],
            }
        )
        st.dataframe(stage_table, hide_index=True, width="stretch")


def render_products(products: pd.DataFrame) -> None:
    st.header("Product Engagement")
    if products.empty:
        st.info(
            "No resolved laptop-linked events are currently available in "
            "mart_product_engagement. The dashboard does not infer product metrics."
        )
        return

    ordered = products.sort_values("total_product_events", ascending=True)
    figure = px.bar(
        ordered,
        x="total_product_events",
        y="laptop_name",
        color="brand_name",
        orientation="h",
        labels={
            "total_product_events": "Product events",
            "laptop_name": "Laptop",
            "brand_name": "Brand",
        },
        color_discrete_sequence=CHART_COLORS,
    )
    st.plotly_chart(styled_chart(figure), width="stretch")
    st.dataframe(
        products.rename(
            columns={
                "laptop_name": "Laptop",
                "brand_name": "Brand",
                "total_product_events": "Product events",
                "product_pageviews": "Pageviews",
                "comparison_selections": "Comparison selections",
                "comparison_adds": "Comparison adds",
                "unique_visitors": "Unique visitors",
                "unique_sessions": "Unique sessions",
            }
        ),
        hide_index=True,
        width="stretch",
    )


def render_searches(searches: pd.DataFrame) -> None:
    st.header("Search Behavior")
    st.caption("Search terms are shown as recorded in the source data.")
    if searches.empty:
        st.info("No search terms are available in the local Gold mart.")
        return

    ordered = searches.sort_values("search_count", ascending=True)
    figure = px.bar(
        ordered,
        x="search_count",
        y="search_keyword",
        orientation="h",
        labels={"search_count": "Searches", "search_keyword": "Search term"},
        color_discrete_sequence=["#2563EB"],
    )
    st.plotly_chart(styled_chart(figure), width="stretch")
    st.dataframe(
        searches.rename(
            columns={
                "search_keyword": "Search term",
                "search_count": "Searches",
                "unique_visitors": "Unique visitors",
                "unique_sessions": "Unique sessions",
            }
        ),
        hide_index=True,
        width="stretch",
    )


def render_device_behavior(data: dict[str, pd.DataFrame]) -> None:
    st.header("Device and OS Behavior")
    device_column, os_column = st.columns(2, gap="large")
    with device_column:
        figure = px.bar(
            data["device_types"].sort_values("total_events", ascending=True),
            x="total_events",
            y="device_type",
            orientation="h",
            labels={"total_events": "Events", "device_type": "Device type"},
            color_discrete_sequence=["#0F766E"],
        )
        st.plotly_chart(styled_chart(figure, 320), width="stretch")
    with os_column:
        figure = px.bar(
            data["operating_systems"].sort_values("total_events", ascending=True),
            x="total_events",
            y="os_name",
            orientation="h",
            labels={"total_events": "Events", "os_name": "Operating system"},
            color_discrete_sequence=["#E76F51"],
        )
        st.plotly_chart(styled_chart(figure, 320), width="stretch")

    interactions = data["device_interactions"].melt(
        id_vars="device_type",
        value_vars=[
            "pageviews",
            "search_events",
            "comparison_selections",
            "comparison_adds",
        ],
        var_name="Interaction",
        value_name="Events",
    )
    figure = px.bar(
        interactions,
        x="device_type",
        y="Events",
        color="Interaction",
        barmode="group",
        labels={"device_type": "Device type"},
        color_discrete_sequence=CHART_COLORS,
    )
    st.plotly_chart(styled_chart(figure, 360), width="stretch")


def render_session_behavior(summary: pd.DataFrame) -> None:
    st.header("Session Behavior")
    if summary.empty:
        st.info("No session-level data is available in the local intermediate layer.")
        return

    values = summary.iloc[0]
    metric_columns = st.columns(4)
    metric_columns[0].metric("Average duration", f"{float(values['average_duration_seconds']):.1f} s")
    metric_columns[1].metric("P50 duration", f"{float(values['p50_duration_seconds']):.1f} s")
    metric_columns[2].metric("P90 duration", f"{float(values['p90_duration_seconds']):.1f} s")
    metric_columns[3].metric("Average events / session", f"{float(values['average_events_per_session']):.1f}")

    participation = pd.DataFrame(
        {
            "Session group": ["Searched", "Did not search"],
            "Sessions": [
                number(values["searched_sessions"]),
                number(values["non_searched_sessions"]),
            ],
        }
    )
    figure = px.bar(
        participation,
        x="Session group",
        y="Sessions",
        color="Session group",
        text="Sessions",
        color_discrete_sequence=["#0F766E", "#94A3B8"],
    )
    figure.update_traces(texttemplate="%{text:,}", textposition="outside")
    st.plotly_chart(styled_chart(figure, 300), width="stretch")


def render_quality(quality: pd.DataFrame) -> None:
    st.header("Data Quality")
    st.caption("Local warehouse checks surfaced for analytical context.")
    if quality.empty:
        st.info("No local quality summary is available.")
        return

    values = quality.iloc[0]
    columns = st.columns(5)
    columns[0].metric("Bronze events", display_number(values["event_count"]))
    columns[1].metric("Unique event IDs", display_number(values["unique_event_ids"]))
    columns[2].metric("Product dimension rows", display_number(values["product_count"]))
    columns[3].metric("Unresolved references", display_number(values["unresolved_reference_events"]))
    latest = values["latest_ingested_at"]
    columns[4].metric("Latest Bronze ingestion", "Unavailable" if pd.isna(latest) else str(latest))


def main() -> None:
    st.set_page_config(
        page_title="LapLap Analytics",
        page_icon=None,
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.markdown(
        """
        <style>
        .stApp { background: #F6F8FA; }
        [data-testid="stMetric"] {
            background: #FFFFFF;
            border: 1px solid #DDE3EA;
            border-radius: 6px;
            padding: 14px 16px;
        }
        [data-testid="stMetricLabel"] { color: #475569; }
        [data-testid="stMetricValue"] { color: #0F172A; }
        h1, h2, h3 { color: #0F172A; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.title("LapLap Analytics - Clickstream and Product Engagement")
    st.caption("Clickstream analytics pipeline built with Python, ClickHouse, and dbt.")
    st.markdown(
        "**Data pipeline:** Remote ClickHouse -> Python Ingestion -> Bronze -> "
        "dbt Staging -> Intermediate -> Gold Marts"
    )

    with st.sidebar:
        st.subheader("Warehouse")
        st.caption("Local ClickHouse only")
        if st.button("Refresh data", width="stretch"):
            st.cache_data.clear()
            st.cache_resource.clear()
            st.rerun()

    try:
        data = load_dashboard_data()
        settings = local_connection_settings()
    except Exception:
        st.error("Unable to query the local ClickHouse warehouse. Check the dashboard runbook.")
        st.stop()

    with st.sidebar:
        st.success("Connected")
        st.caption(f"{settings['host']}:{settings['port']}")
        st.caption("Sources: laplap_marts, laplap_intermediate, laplap_raw")

    funnel = data["funnel"]
    st.header("Executive KPIs")
    if funnel.empty:
        st.warning("No funnel KPI data is available in the local Gold mart.")
    else:
        values = funnel.iloc[0]
        metrics = [
            ("Total sessions", values["total_sessions"]),
            ("Search sessions", values["search_sessions"]),
            ("Product view sessions", values["product_view_sessions"]),
            ("Comparison selections", values["comparison_selection_sessions"]),
            ("Comparison adds", values["comparison_add_sessions"]),
        ]
        for column, (label, value) in zip(st.columns(5), metrics):
            column.metric(label, display_number(value))

    render_funnel(funnel)
    render_products(data["products"])
    render_searches(data["searches"])
    render_device_behavior(data)
    render_session_behavior(data["session_summary"])
    render_quality(data["quality"])


if __name__ == "__main__":
    main()
