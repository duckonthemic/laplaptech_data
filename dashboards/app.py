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
CHART_COLORS = ["#007C78", "#2155CD", "#D95D39", "#D89325", "#596A7A"]


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
        template="plotly_white",
        height=height,
        margin={"l": 8, "r": 8, "t": 16, "b": 8},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"family": "Inter, Arial, sans-serif", "color": "#172033"},
        legend_title_text="",
        hoverlabel={
            "bgcolor": "#172033",
            "bordercolor": "#172033",
            "font": {"color": "#FFFFFF"},
        },
    )
    figure.update_xaxes(gridcolor="#DCE5EA", zerolinecolor="#DCE5EA")
    figure.update_yaxes(gridcolor="#DCE5EA", zerolinecolor="#DCE5EA")
    return figure


def render_funnel(funnel: pd.DataFrame) -> None:
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
        st.plotly_chart(styled_chart(figure, 390), width="stretch")
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
        st.dataframe(stage_table, hide_index=True, width="stretch", height=305)


def render_products(products: pd.DataFrame) -> None:
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
    st.plotly_chart(styled_chart(figure, 430), width="stretch")
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
        height=390,
    )


def render_searches(searches: pd.DataFrame) -> None:
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
    st.plotly_chart(styled_chart(figure, 420), width="stretch")
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
        height=390,
    )


def render_device_behavior(data: dict[str, pd.DataFrame]) -> None:
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


def render_section_heading(eyebrow: str, title: str, description: str) -> None:
    st.markdown(
        f"""
        <div class="section-heading">
            <p class="section-eyebrow">{eyebrow}</p>
            <h2>{title}</h2>
            <p>{description}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def apply_dashboard_styles() -> None:
    st.markdown(
        """
        <style>
        :root {
            --ink: #172033;
            --muted: #596A7A;
            --line: #DCE5EA;
            --surface: #FFFFFF;
            --canvas: #F4F7F9;
            --teal: #007C78;
            --navy: #102A43;
            --blue: #2155CD;
        }

        .stApp, [data-testid="stAppViewContainer"], [data-testid="stMain"] {
            background: var(--canvas);
            color: var(--ink);
        }

        [data-testid="stHeader"] {
            background: rgba(244, 247, 249, 0.96);
            border-bottom: 1px solid var(--line);
        }

        .block-container {
            max-width: 1440px;
            padding-top: 2.5rem;
            padding-bottom: 4rem;
        }

        [data-testid="stSidebar"] {
            background: var(--navy);
            border-right: 1px solid #254563;
        }

        [data-testid="stSidebar"] * { color: #E9F0F4; }
        [data-testid="stSidebar"] [data-testid="stCaptionContainer"] p { color: #B9C8D5; }
        [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h3 {
            color: #FFFFFF;
            font-size: 1.05rem;
            margin-top: 1.75rem;
        }

        [data-testid="stSidebar"] [data-testid="stAlert"] {
            background: #174E4B;
            border: 1px solid #257872;
            border-radius: 4px;
        }

        .sidebar-mark {
            border-bottom: 1px solid #36536D;
            padding: 0.4rem 0 1.25rem;
        }

        .sidebar-mark p {
            color: #73D4C6 !important;
            font-size: 0.7rem;
            font-weight: 700;
            letter-spacing: 0.11em;
            margin: 0 0 0.45rem;
        }

        .sidebar-mark h2 {
            color: #FFFFFF;
            font-size: 1.55rem;
            letter-spacing: 0;
            margin: 0;
        }

        .report-header {
            align-items: flex-start;
            border-bottom: 1px solid var(--line);
            display: flex;
            gap: 1.5rem;
            justify-content: space-between;
            margin-bottom: 1.4rem;
            padding-bottom: 1.85rem;
        }

        .report-eyebrow, .section-eyebrow {
            color: var(--teal);
            font-size: 0.72rem;
            font-weight: 700;
            letter-spacing: 0.1em;
            margin: 0 0 0.5rem;
        }

        .report-title {
            color: var(--ink);
            font-size: 2.55rem;
            font-weight: 750;
            letter-spacing: 0;
            line-height: 1.08;
            margin: 0;
            max-width: 720px;
        }

        .report-subtitle {
            color: var(--muted);
            font-size: 1rem;
            line-height: 1.55;
            margin: 0.7rem 0 0;
            max-width: 650px;
        }

        .report-status {
            background: #E2F4F0;
            border: 1px solid #A9DCD4;
            border-radius: 999px;
            color: #075E58;
            font-size: 0.78rem;
            font-weight: 700;
            margin-top: 0.25rem;
            padding: 0.42rem 0.7rem;
            white-space: nowrap;
        }

        .pipeline-line {
            color: var(--muted);
            font-size: 0.82rem;
            margin: 0 0 2rem;
        }

        .pipeline-line strong { color: var(--ink); }

        .section-heading { margin: 1rem 0 0.9rem; }
        .section-heading h2 {
            color: var(--ink);
            font-size: 1.4rem;
            letter-spacing: 0;
            margin: 0;
        }

        .section-heading > p:last-child {
            color: var(--muted);
            font-size: 0.9rem;
            margin: 0.35rem 0 0;
        }

        [data-testid="stMetric"] {
            background: var(--surface);
            border: 1px solid var(--line);
            border-radius: 5px;
            border-top: 3px solid var(--teal);
            box-shadow: none;
            min-height: 112px;
            padding: 1rem 1rem 0.85rem;
        }

        [data-testid="stMetricLabel"] {
            color: var(--muted) !important;
            font-size: 0.76rem;
            font-weight: 650;
            letter-spacing: 0.025em;
        }

        [data-testid="stMetricValue"] {
            color: var(--ink) !important;
            font-size: 1.8rem;
            font-weight: 720;
        }

        [data-testid="stTabs"] [data-baseweb="tab-list"] {
            border-bottom: 1px solid var(--line);
            gap: 1.8rem;
        }

        [data-testid="stTabs"] button[data-baseweb="tab"] {
            color: var(--muted);
            font-size: 0.88rem;
            font-weight: 650;
            letter-spacing: 0;
            padding: 0.6rem 0;
        }

        [data-testid="stTabs"] button[aria-selected="true"] { color: var(--teal); }
        [data-testid="stTabs"] [data-baseweb="tab-highlight"] { background-color: var(--teal); }

        .stButton > button {
            background: #FFFFFF;
            border: 1px solid #7091A9;
            border-radius: 4px;
            color: var(--navy);
            font-weight: 650;
        }

        .stButton > button:hover {
            background: #E2F4F0;
            border-color: #73B9B1;
            color: #075E58;
        }

        [data-testid="stSidebar"] .stButton > button {
            background: transparent;
            border-color: #60809A;
            color: #FFFFFF;
        }

        [data-testid="stSidebar"] .stButton > button:hover {
            background: #1B455E;
            border-color: #80B7C5;
            color: #FFFFFF;
        }

        [data-testid="stDataFrame"] {
            border: 1px solid var(--line);
            border-radius: 5px;
            overflow: hidden;
        }

        [data-testid="stPlotlyChart"] { border-bottom: 1px solid #E8EEF1; }
        hr { border-color: var(--line); margin: 2.5rem 0; }

        @media (max-width: 760px) {
            .block-container { padding: 1.5rem 1rem 3rem; }
            .report-header { display: block; }
            .report-title { font-size: 2rem; }
            .report-status { display: inline-block; margin-top: 1rem; }
            [data-testid="stTabs"] [data-baseweb="tab-list"] { gap: 1rem; overflow-x: auto; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def main() -> None:
    st.set_page_config(
        page_title="LapLap Analytics",
        page_icon=":material/insights:",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    apply_dashboard_styles()

    with st.sidebar:
        st.markdown(
            """
            <div class="sidebar-mark">
                <p>ANALYTICS WORKSPACE</p>
                <h2>LapLap</h2>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.subheader("Warehouse")
        st.caption("Local ClickHouse only")
        if st.button("Refresh data", icon=":material/refresh:", width="stretch"):
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

    st.markdown(
        """
        <div class="report-header">
            <div>
                <p class="report-eyebrow">CLICKSTREAM INTELLIGENCE</p>
                <h1 class="report-title">LapLap Analytics</h1>
                <p class="report-subtitle">Product discovery and comparison behavior, modeled from the local ClickHouse warehouse.</p>
            </div>
            <div class="report-status">LOCAL WAREHOUSE ONLINE</div>
        </div>
        <p class="pipeline-line"><strong>Pipeline</strong> &nbsp; Remote ClickHouse &rarr; Python ingestion &rarr; Bronze &rarr; dbt &rarr; Gold marts</p>
        """,
        unsafe_allow_html=True,
    )

    funnel = data["funnel"]
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
        for column, (label, value) in zip(st.columns(3), metrics[:3]):
            column.metric(label, display_number(value))

        for column, (label, value) in zip(st.columns(2), metrics[3:]):
            column.metric(label, display_number(value))

    overview_tab, products_tab, audience_tab, quality_tab = st.tabs(
        ["Overview", "Products & Search", "Audience", "Data Quality"]
    )

    with overview_tab:
        render_section_heading(
            "JOURNEY PERFORMANCE",
            "Strict session funnel",
            "Every stage must occur after the prior action in the same session.",
        )
        render_funnel(funnel)

    with products_tab:
        render_section_heading(
            "PRODUCT INTEREST",
            "Product engagement",
            "Top resolved laptop interactions across pageviews and comparison actions.",
        )
        render_products(data["products"])
        st.divider()
        render_section_heading(
            "DISCOVERY INPUT",
            "Search behavior",
            "Search terms are shown as recorded in the source data.",
        )
        render_searches(data["searches"])

    with audience_tab:
        render_section_heading(
            "PLATFORM MIX",
            "Device and OS behavior",
            "Event volume and comparison actions grouped by client environment.",
        )
        render_device_behavior(data)
        st.divider()
        render_section_heading(
            "SESSION DEPTH",
            "Session behavior",
            "Duration and event intensity across the observed clickstream sessions.",
        )
        render_session_behavior(data["session_summary"])

    with quality_tab:
        render_section_heading(
            "WAREHOUSE HEALTH",
            "Data quality",
            "Local Bronze completeness and product-reference coverage for analytical context.",
        )
        render_quality(data["quality"])


if __name__ == "__main__":
    main()
