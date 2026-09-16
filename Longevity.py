"""
Longevity Testing Page
======================
Visualises long-run device health data collected by
Longevity/backend/main_nax.py and stored in the event CSV.

Device names (not IPs) are listed in the selector; "All Devices" is default.
"""

import os
import sys

import altair as alt
import pandas as pd
import streamlit as st

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "scripts"))
from longevity_data import (  # noqa: E402
    ALL_DEVICES_LABEL,
    CSV_PATH,
    build_device_options,
    cpu_breakdown_long,
    filter_by_days,
    latest_snapshot,
    load_longevity_data,
)

# ── CSS — consistent with the other dashboard pages ──────────────────────────

st.markdown("""
<style>
    .lng-hero {
        text-align: center;
        padding: 2.6rem 0 0.6rem;
    }
    .lng-title {
        font-size: 2.9rem;
        font-weight: 800;
        line-height: 1.15;
        color: #E8ECF0;
    }
    .lng-title-accent { color: #4DA3FF; }
    .lng-subtitle {
        color: rgba(232,236,240,0.55);
        font-size: 1rem;
        margin-top: 0.6rem;
    }
    .lng-section {
        font-size: 1.05rem;
        font-weight: 700;
        color: #E8ECF0;
        margin: 1.6rem 0 0.4rem;
        letter-spacing: 0.01em;
    }
    .lng-meta {
        color: rgba(232,236,240,0.45);
        font-size: 0.82rem;
        text-align: center;
        margin-bottom: 0.6rem;
    }
    div[data-testid="stMetricValue"] { font-size: 1.5rem !important; }
</style>
""", unsafe_allow_html=True)

# ── Header ────────────────────────────────────────────────────────────────────

st.markdown("""
<div class="lng-hero">
    <div class="lng-title">Longevity <span class="lng-title-accent">Device Health Summary</span></div>
    <div class="lng-subtitle">Uptime, memory and CPU trends captured from long-running NAX devices.</div>
</div>
""", unsafe_allow_html=True)


@st.cache_data(show_spinner=False)
def _load(csv_path: str, mtime: float) -> pd.DataFrame:
    """Cached CSV load — invalidated whenever the file is modified."""
    return load_longevity_data(csv_path)


_mtime = os.path.getmtime(CSV_PATH) if os.path.exists(CSV_PATH) else 0.0
df = _load(CSV_PATH, _mtime)

if df.empty:
    st.warning(
        f"No Longevity data available yet.\n\nExpected CSV: `{CSV_PATH}`\n\n"
        "Run `Longevity/backend/main_nax.py` (or the scheduled Jenkins job) to collect device health data."
    )
    st.stop()

st.markdown(
    f"<div class='lng-meta'>Source: {CSV_PATH} &nbsp;·&nbsp; "
    f"Last updated: {df['Date'].max().strftime('%d %b %Y')}</div>",
    unsafe_allow_html=True,
)

# ── Controls ──────────────────────────────────────────────────────────────────

device_options = build_device_options(df)
label_to_ip = {label: ip for label, ip in device_options}
selector_labels = [ALL_DEVICES_LABEL] + list(label_to_ip.keys())

RANGE_OPTIONS = {
    "Last 7 days": 7,
    "Last 30 days": 30,
    "Last 90 days": 90,
    "All data": None,
}

ctrl1, ctrl2, ctrl3 = st.columns([3, 2, 1])
with ctrl1:
    selected_label = st.selectbox(
        "Select device to view data", selector_labels, index=0, key="lng_device"
    )
with ctrl2:
    range_label = st.selectbox(
        "Date range", list(RANGE_OPTIONS.keys()), index=1, key="lng_range"
    )
with ctrl3:
    st.markdown("<div style='height:1.85rem'></div>", unsafe_allow_html=True)
    if st.button("Refresh", key="lng_refresh", use_container_width=True):
        _load.clear()
        st.rerun()

days = RANGE_OPTIONS[range_label]
view_df = filter_by_days(df, days)

if selected_label != ALL_DEVICES_LABEL:
    view_df = view_df[view_df["IP"] == label_to_ip[selected_label]].copy()

if view_df.empty:
    st.info("No records found for the selected device and date range.")
    st.stop()

view_df = view_df.sort_values("Date").reset_index(drop=True)


# ── Chart helpers ─────────────────────────────────────────────────────────────

DATE_AXIS = alt.Axis(
    format="%d %b",
    labelAngle=-40,
    tickCount={"interval": "day", "step": 1},
)

VALUE_AXIS = alt.Axis(format="d", tickMinStep=1)


def _trend_chart(data: pd.DataFrame, value_col: str, y_title: str,
                 color_col: str | None = None, y_domain=None, height: int = 300):
    """Line chart over Date. Columns are renamed internally to avoid Altair
    shorthand issues with spaces / parentheses in field names."""
    cols = {"Date": "Date", value_col: "Value"}
    if color_col:
        cols[color_col] = "Series"
    plot_df = data[list(cols.keys())].rename(columns=cols).dropna(subset=["Value"])
    if plot_df.empty:
        return None

    y_scale = alt.Scale(domain=y_domain) if y_domain else alt.Scale(zero=False)
    tooltip = [alt.Tooltip("Date:T", title="Date", format="%d %b %Y")]
    if color_col:
        tooltip.append(alt.Tooltip("Series:N", title="Device"))
    tooltip.append(alt.Tooltip("Value:Q", title=y_title))

    encodings = {
        "x": alt.X("Date:T", title="Date", axis=DATE_AXIS),
        "y": alt.Y("Value:Q", title=y_title, scale=y_scale, axis=VALUE_AXIS),
        "tooltip": tooltip,
    }
    if color_col:
        encodings["color"] = alt.Color("Series:N", title="Device")

    return (
        alt.Chart(plot_df)
        .mark_line(point=True, strokeWidth=2)
        .encode(**encodings)
        .properties(height=height)
    )


def _render(chart, empty_msg: str):
    if chart is None:
        st.info(empty_msg)
    else:
        st.altair_chart(chart, width="stretch")


TABLE_COLUMNS = [
    "Date Label", "Device", "IP", "Model", "Uptime (Days)", "RAM Usage (%)",
    "CPU Busy (%)", "User CPU (%)", "System CPU (%)", "Idle CPU (%)",
]

# ═══════════════════════════════════════════════════════════════════════════════
# ALL DEVICES VIEW
# ═══════════════════════════════════════════════════════════════════════════════

if selected_label == ALL_DEVICES_LABEL:
    snapshot = latest_snapshot(view_df)
    unreachable = int(snapshot["Uptime (Days)"].isna().sum())

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Devices Monitored", len(snapshot))
    m2.metric("Records", len(view_df))
    m3.metric(
        "Avg RAM Usage",
        f"{snapshot['RAM Usage (%)'].mean():.0f} %" if snapshot["RAM Usage (%)"].notna().any() else "—",
    )
    m4.metric("Unreachable (latest)", unreachable)

    st.markdown("<div class='lng-section'>Latest Snapshot</div>", unsafe_allow_html=True)
    snap_view = snapshot[[
        "Device", "IP", "Model", "Date Label", "Uptime (Days)",
        "RAM Usage (%)", "CPU Busy (%)",
    ]].rename(columns={"Date Label": "Last Seen"})
    st.dataframe(snap_view, width="stretch", hide_index=True)

    st.markdown("<div class='lng-section'>Uptime (Days) — All Devices</div>", unsafe_allow_html=True)
    _render(
        _trend_chart(view_df, "Uptime (Days)", "Uptime (Days)", color_col="Device"),
        "No uptime data in the selected range.",
    )

    st.markdown("<div class='lng-section'>RAM Usage (%) — All Devices</div>", unsafe_allow_html=True)
    _render(
        _trend_chart(view_df, "RAM Usage (%)", "RAM Usage (%)",
                     color_col="Device", y_domain=[0, 100]),
        "No memory data in the selected range.",
    )

    st.markdown("<div class='lng-section'>CPU Busy (%) — All Devices</div>", unsafe_allow_html=True)
    _render(
        _trend_chart(view_df, "CPU Busy (%)", "CPU Busy (%)",
                     color_col="Device", y_domain=[0, 100]),
        "No CPU data in the selected range.",
    )

    st.markdown("<div class='lng-section'>Latest RAM Usage by Device</div>", unsafe_allow_html=True)
    bar_df = snapshot[["Device", "RAM Usage (%)"]].rename(
        columns={"RAM Usage (%)": "Value"}
    ).dropna(subset=["Value"])
    if bar_df.empty:
        st.info("No memory data available for the latest snapshot.")
    else:
        bar = (
            alt.Chart(bar_df)
            .mark_bar(cornerRadiusEnd=4)
            .encode(
                x=alt.X("Device:N", title="Device", sort="-y", axis=alt.Axis(labelAngle=-30)),
                y=alt.Y("Value:Q", title="RAM Usage (%)", scale=alt.Scale(domain=[0, 100]),
                        axis=VALUE_AXIS),
                color=alt.Color("Device:N", legend=None),
                tooltip=[alt.Tooltip("Device:N"), alt.Tooltip("Value:Q", title="RAM Usage (%)")],
            )
            .properties(height=300)
        )
        st.altair_chart(bar, width="stretch")

    with st.expander("View raw records"):
        st.dataframe(
            view_df[TABLE_COLUMNS].rename(columns={"Date Label": "Date"}).iloc[::-1],
            width="stretch",
            hide_index=True,
        )


# ═══════════════════════════════════════════════════════════════════════════════
# SINGLE DEVICE VIEW
# ═══════════════════════════════════════════════════════════════════════════════

else:
    latest = view_df.iloc[-1]
    model = latest["Model"] if str(latest["Model"]).strip() else "Unknown"

    st.markdown(
        f"<div class='lng-section'>{selected_label} &nbsp;·&nbsp; "
        f"<span style='color:rgba(232,236,240,0.55); font-weight:500;'>"
        f"{latest['IP']} &nbsp;|&nbsp; {model}</span></div>",
        unsafe_allow_html=True,
    )

    def _fmt(value, suffix=""):
        return "—" if pd.isna(value) else f"{value:.0f}{suffix}"

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Uptime", _fmt(latest["Uptime (Days)"], " days"))
    m2.metric("RAM Usage", _fmt(latest["RAM Usage (%)"], " %"))
    m3.metric("CPU Busy", _fmt(latest["CPU Busy (%)"], " %"))
    m4.metric("Records", len(view_df))

    if pd.isna(latest["Uptime (Days)"]):
        st.error("Latest collection could not reach this device (login failed / no response).")

    st.markdown("<div class='lng-section'>Uptime (Days)</div>", unsafe_allow_html=True)
    _render(
        _trend_chart(view_df, "Uptime (Days)", "Uptime (Days)"),
        "No uptime data in the selected range.",
    )

    st.markdown("<div class='lng-section'>RAM Usage (%)</div>", unsafe_allow_html=True)
    _render(
        _trend_chart(view_df, "RAM Usage (%)", "RAM Usage (%)", y_domain=[0, 100]),
        "No memory data in the selected range.",
    )

    st.markdown("<div class='lng-section'>CPU Breakdown (%)</div>", unsafe_allow_html=True)
    cpu_df = cpu_breakdown_long(view_df)
    if cpu_df.empty:
        st.info("No CPU data in the selected range.")
    else:
        cpu_chart = (
            alt.Chart(cpu_df)
            .mark_line(point=True, strokeWidth=2)
            .encode(
                x=alt.X("Date:T", title="Date", axis=DATE_AXIS),
                y=alt.Y("Value:Q", title="CPU (%)", scale=alt.Scale(domain=[0, 100]),
                        axis=VALUE_AXIS),
                color=alt.Color("Metric:N", title="CPU Metric"),
                tooltip=[
                    alt.Tooltip("Date:T", title="Date", format="%d %b %Y"),
                    alt.Tooltip("Metric:N", title="Metric"),
                    alt.Tooltip("Value:Q", title="CPU (%)"),
                ],
            )
            .properties(height=320)
        )
        st.altair_chart(cpu_chart, width="stretch")

    st.markdown("<div class='lng-section'>Collected Records</div>", unsafe_allow_html=True)
    st.dataframe(
        view_df[TABLE_COLUMNS].rename(columns={"Date Label": "Date"}).iloc[::-1],
        width="stretch",
        hide_index=True,
    )
