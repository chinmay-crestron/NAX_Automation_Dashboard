"""
Longevity Testing Page
======================
Visualises long-run device health data collected by
Longevity/backend/main_nax.py and stored in the event CSV.

Device names (not IPs) are listed in the selector; DM-NAX-8ZSA is the default.
A device keeps one history even when its IP changes (see scripts/longevity_data.py).
"""

import os
import sys

import altair as alt
import pandas as pd
import streamlit as st

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "scripts"))
from longevity_data import (  # noqa: E402
    CSV_PATH,
    build_device_options,
    default_device_index,
    filter_by_days,
    latest_model,
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
def _load(csv_path: str, mtime: float, code_mtime: float) -> pd.DataFrame:
    """Cached CSV load — invalidated when the CSV or the loader code changes."""
    return load_longevity_data(csv_path)


_mtime = os.path.getmtime(CSV_PATH) if os.path.exists(CSV_PATH) else 0.0
df = _load(CSV_PATH, _mtime, os.path.getmtime(load_longevity_data.__code__.co_filename))

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
label_to_key = {label: key for label, key in device_options}
selector_labels = list(label_to_key.keys())

RANGE_OPTIONS = {
    "Last 7 days": 7,
    "Last 30 days": 30,
    "Last 90 days": 90,
    "All data": None,
}

ctrl1, ctrl2, ctrl3 = st.columns([3, 2, 1])
with ctrl1:
    selected_label = st.selectbox(
        "Select device to view data", selector_labels,
        index=default_device_index(device_options), key="lng_device",
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
view_df = view_df[view_df["Device Key"] == label_to_key[selected_label]].copy()

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
# DEVICE VIEW
# ═══════════════════════════════════════════════════════════════════════════════

latest = view_df.iloc[-1]
model = latest_model(view_df)

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

st.markdown("<div class='lng-section'>Collected Records</div>", unsafe_allow_html=True)
st.dataframe(
    view_df[TABLE_COLUMNS].rename(columns={"Date Label": "Date"}).iloc[::-1],
    width="stretch",
    hide_index=True,
)
