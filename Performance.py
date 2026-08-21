"""
Performance Testing Page
========================
Shows performance test counts by device, firmware version, IP, and test type.
Data sourced from C:\\nax-image-server\\document.csv
"""

import streamlit as st
import pandas as pd
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "scripts"))
from performance_data import (
    load_performance_data,
    get_versions_for_device,
    get_ips_for_device,
    get_test_types_for_device,
    compute_counts,
    get_total_device_count,
    ALL_TEST_TYPES,
    CSV_PATH,
)
from jenkins_links import get_jenkins_url

# ── Device buttons ────────────────────────────────────────────────────────────

PERF_DEVICES = [
    "DM-NAX-8ZSA",
    "DM-NAX-4ZSA",
    "DM-NAX-4ZSP",
    "DM-NAX-16AIN",
    "DM-NAX-AMP300",
    "Edge-Devices",
    "Saros",
]

# ── CSS — consistent with other dashboard pages ──────────────────────────────

st.markdown("""
<style>
    /* ── Performance hero ────────────────────────────────────────── */
    .perf-hero {
        text-align: center;
        padding: 4rem 0 2rem;
    }
    .perf-title {
        font-size: 3.2rem;
        font-weight: 800;
        line-height: 1.15;
        color: #E8ECF0;
    }
    .perf-title-accent { color: #4DA3FF; }
    .perf-subtitle {
        color: rgba(232,236,240,0.55);
        font-size: 1.05rem;
        margin-top: 0.8rem;
    }

    /* ── Detail page summary card ─────────────────────────────────── */
    .perf-summary {
        background: rgba(40, 55, 80, 0.35);
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 10px;
        padding: 1.2rem 1.8rem;
        margin: 1rem 0 1.5rem;
        display: flex;
        gap: 3rem;
        justify-content: center;
        font-size: 1.05rem;
    }
    .perf-summary .label { color: rgba(232,236,240,0.55); }
    .perf-summary .value { color: #E8ECF0; font-weight: 600; margin-left: 0.4rem; }

    /* ── Jenkins execution card ───────────────────────────────────── */
    .jenkins-card {
        background: rgba(40, 55, 80, 0.35);
        border: 1px solid rgba(77,163,255,0.2);
        border-radius: 14px;
        padding: 2.5rem 3rem;
        margin: 1.5rem auto;
        max-width: 680px;
        text-align: center;
    }
    .jenkins-card-title {
        font-size: 1.55rem;
        font-weight: 700;
        color: #E8ECF0;
        margin-bottom: 0.3rem;
    }
    .jenkins-card-subtitle {
        color: rgba(232,236,240,0.50);
        font-size: 0.95rem;
        margin-bottom: 2rem;
    }
    .jenkins-btn-row {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 1rem;
        max-width: 520px;
        margin: 0 auto;
    }
    .jenkins-btn {
        display: block;
        padding: 0.85rem 1rem;
        border-radius: 8px;
        font-size: 1rem;
        font-weight: 600;
        text-decoration: none !important;
        text-align: center;
        transition: filter 0.15s, transform 0.1s;
    }
    .jenkins-btn:hover { filter: brightness(1.15); transform: translateY(-1px); }
    .jenkins-btn-active {
        background: linear-gradient(135deg, #4DA3FF 0%, #1a6fd4 100%);
        color: #fff !important;
        border: none;
    }
    .jenkins-btn-disabled {
        background: rgba(255,255,255,0.06);
        color: rgba(232,236,240,0.35) !important;
        border: 1px solid rgba(255,255,255,0.08);
        cursor: not-allowed;
        pointer-events: none;
    }
</style>
""", unsafe_allow_html=True)

# ── Session state ─────────────────────────────────────────────────────────────

if "perf_view" not in st.session_state:
    st.session_state.perf_view = "landing"
if "perf_device" not in st.session_state:
    st.session_state.perf_device = None
if "perf_data" not in st.session_state:
    st.session_state.perf_data = None
if "exec_device" not in st.session_state:
    st.session_state.exec_device = None


def _load_data():
    st.session_state.perf_data = load_performance_data()


# ═══════════════════════════════════════════════════════════════════════════════
# LANDING PAGE
# ═══════════════════════════════════════════════════════════════════════════════

if st.session_state.perf_view == "landing":
    st.markdown("""
    <div class="perf-hero">
        <div class="perf-title">DM-NAX<br><span class="perf-title-accent">Performance Testing</span></div>
        <div class="perf-subtitle">Analyse performance test counts across devices, firmware versions, and test types.</div>
    </div>
    """, unsafe_allow_html=True)

    _, col_btn1, gap, col_btn2, _ = st.columns([2, 1.8, 0.4, 1.8, 2])
    with col_btn1:
        if st.button("Performance Counts", type="primary", use_container_width=True):
            _load_data()
            st.session_state.perf_view = "devices"
            st.rerun()
    with col_btn2:
        if st.button("Performance Execution", type="secondary", use_container_width=True):
            st.session_state.perf_view = "exec_devices"
            st.rerun()

    st.markdown("<div style='height:300px'></div>", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# DEVICE SELECTION PAGE
# ═══════════════════════════════════════════════════════════════════════════════

elif st.session_state.perf_view == "devices":
    if st.button("← Back", key="dev_back"):
        st.session_state.perf_view = "landing"
        st.rerun()

    st.markdown("""
    <div class="perf-hero" style="padding-top:2rem; padding-bottom:1rem;">
        <div class="perf-title" style="font-size:2.2rem;">Performance Counts</div>
        <div class="perf-subtitle">Select a device to view the performance count</div>
    </div>
    """, unsafe_allow_html=True)

    # 2-row grid, centred with spacer columns
    cols_per_row = 4
    for i in range(0, len(PERF_DEVICES), cols_per_row):
        chunk = PERF_DEVICES[i:i + cols_per_row]
        pad = cols_per_row - len(chunk)
        col_spec = [1.5] + [2] * len(chunk) + [2] * pad + [1.5]
        cols = st.columns(col_spec)
        for j, dev in enumerate(chunk):
            with cols[j + 1]:
                if st.button(dev, key=f"perf_dev_{dev}", width="stretch"):
                    st.session_state.perf_device = dev
                    st.session_state.perf_view = "detail"
                    st.rerun()
        st.markdown("<div style='height:0.6rem'></div>", unsafe_allow_html=True)

    st.markdown("<div style='height:250px'></div>", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# DETAIL VIEW — counts table
# ═══════════════════════════════════════════════════════════════════════════════

elif st.session_state.perf_view == "detail":
    device_name = st.session_state.perf_device

    if st.session_state.perf_data is None:
        _load_data()
    rows = st.session_state.perf_data

    # ── Top bar: Back + Reload ────────────────────────────────────────────
    top1, top2, _ = st.columns([1.2, 1.2, 5])
    with top1:
        if st.button("← Back to Devices", key="detail_back"):
            st.session_state.perf_view = "devices"
            st.rerun()
    with top2:
        if st.button("Reload Counts", key="reload_btn"):
            _load_data()
            rows = st.session_state.perf_data
            st.toast("Data reloaded from CSV.")
            st.rerun()

    st.markdown("")

    # ── Title ──────────────────────────────────────────────────────────────
    st.markdown(
        f"<div style='text-align:center; padding:0.5rem 0 0.2rem;'>"
        f"<span style='font-size:2rem; font-weight:700; color:#E8ECF0;'>{device_name}</span>"
        f"</div>",
        unsafe_allow_html=True,
    )
    st.divider()

    # ── Available options ─────────────────────────────────────────────────
    versions_avail   = get_versions_for_device(rows, device_name)  # latest first
    ips_avail        = get_ips_for_device(rows, device_name)
    test_types_avail = get_test_types_for_device(rows, device_name)

    if not versions_avail:
        st.info(f"No performance data found for **{device_name}** in the CSV.")
        st.stop()

    # Default firmware = latest version only
    default_ver = [versions_avail[0]] if versions_avail else []

    # ── Filter selects ────────────────────────────────────────────────────
    fc1, fc2, fc3 = st.columns(3)

    with fc1:
        sel_versions = st.multiselect(
            "Firmware Version",
            options=versions_avail,
            default=default_ver,
            key="perf_ver_sel",
        )
    with fc2:
        sel_ips = st.multiselect(
            "Device (IP)",
            options=ips_avail,
            default=ips_avail,
            key="perf_ip_sel",
        )
    with fc3:
        sel_types = st.multiselect(
            "Test Type",
            options=test_types_avail if test_types_avail else ALL_TEST_TYPES,
            default=test_types_avail if test_types_avail else ALL_TEST_TYPES,
            key="perf_type_sel",
        )

    # ── Display labels (show "All" when everything selected) ──────────────
    all_ver_selected  = set(sel_versions) == set(versions_avail) and len(sel_versions) > 0
    all_ip_selected   = set(sel_ips) == set(ips_avail) and len(sel_ips) > 0
    all_type_selected = set(sel_types) == set(test_types_avail) and len(sel_types) > 0

    ver_display  = "All" if all_ver_selected else (", ".join(sel_versions) if sel_versions else "None")
    ip_display   = "All" if all_ip_selected else (", ".join(sel_ips) if sel_ips else "None")
    type_display = "All" if all_type_selected else (", ".join(sel_types) if sel_types else "None")

    # Inject "Selected All" chip when all options are selected in a multiselect
    _replace_js = """
    <script>
    (function() {
        const checks = [
            { key: 'perf_ver_sel',  allSelected: %s },
            { key: 'perf_ip_sel',   allSelected: %s },
            { key: 'perf_type_sel', allSelected: %s },
        ];
        setTimeout(function() {
            const containers = document.querySelectorAll('[data-testid="stMultiSelect"]');
            checks.forEach(function(c, idx) {
                if (c.allSelected && containers[idx]) {
                    const tags = containers[idx].querySelectorAll('span[data-baseweb="tag"]');
                    if (tags.length > 1) {
                        tags.forEach(function(tag, i) {
                            if (i === 0) {
                                var span = tag.querySelector('span');
                                if (span) span.textContent = 'Selected All';
                            } else {
                                tag.style.display = 'none';
                            }
                        });
                    }
                }
            });
        }, 300);
    })();
    </script>
    """ % (
        "true" if all_ver_selected else "false",
        "true" if all_ip_selected else "false",
        "true" if all_type_selected else "false",
    )
    st.markdown(_replace_js, unsafe_allow_html=True)

    st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)

    # ── Summary card ──────────────────────────────────────────────────────
    total_devices = get_total_device_count(
        rows, device_name,
        versions=sel_versions or None,
        ips=sel_ips or None,
        test_types=sel_types or None,
    )

    st.markdown(
        f'<div class="perf-summary">'
        f'<div><span class="label">Firmware Version:</span><span class="value"> {ver_display}</span></div>'
        f'<div><span class="label">Total Device Count:</span><span class="value"> {total_devices}</span></div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # ── Counts table ──────────────────────────────────────────────────────
    counts = compute_counts(
        rows, device_name,
        versions=sel_versions or None,
        ips=sel_ips or None,
        test_types=sel_types or None,
    )

    display_types = sel_types if sel_types else ALL_TEST_TYPES
    table_data = [
        {"Performance Test Type": t, "Count": counts.get(t, 0)}
        for t in display_types
    ]
    total_count = sum(r["Count"] for r in table_data)
    table_data.append({"Performance Test Type": "Total", "Count": total_count})

    df = pd.DataFrame(table_data)

    # Centre the table
    _, tbl_col, _ = st.columns([1.5, 4, 1.5])
    with tbl_col:
        st.dataframe(
            df,
            hide_index=True,
            width='stretch',
            column_config={
                "Performance Test Type": st.column_config.TextColumn(width="large"),
                "Count": st.column_config.NumberColumn(width="small"),
            },
        )

    st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)

    # ── Download buttons ──────────────────────────────────────────────────
    _, dl1, dl2, dl3, _ = st.columns([2, 1.8, 1.8, 1.8, 2])

    csv_bytes = df.to_csv(index=False).encode("utf-8")
    with dl1:
        st.download_button(
            "Download as CSV",
            data=csv_bytes,
            file_name=f"performance_{device_name}.csv",
            mime="text/csv",
        )

    # HTML/PDF download
    html_table = (
        f"<html><head><title>Performance Counts \u2014 {device_name}</title>"
        "<style>"
        "body { font-family: 'Segoe UI', Arial, sans-serif; padding: 2rem; background: #1a1a2e; color: #e8ecf0; }"
        "h2 { color: #4DA3FF; }"
        "table { border-collapse: collapse; width: 60%; margin-top: 1rem; }"
        "th, td { border: 1px solid #444; padding: 10px 18px; text-align: left; }"
        "th { background: #263040; }"
        "tr:nth-child(even) { background: #1e2a38; }"
        "tr:last-child { font-weight: bold; background: #263040; }"
        ".meta { color: #aaa; margin-top: 0.5rem; }"
        "</style></head><body>"
        f"<h2>{device_name} \u2014 Performance Counts</h2>"
        f"<p class='meta'>Firmware: {ver_display} &nbsp;|&nbsp; Devices: {total_devices}</p>"
        "<table><tr><th>Performance Test Type</th><th>Count</th></tr>"
    )
    for row in table_data:
        html_table += f"<tr><td>{row['Performance Test Type']}</td><td>{row['Count']}</td></tr>"
    html_table += "</table><script>window.onload=function(){window.print();}</script></body></html>"

    with dl2:
        st.download_button(
            "Download as PDF (Print)",
            data=html_table.encode("utf-8"),
            file_name=f"performance_{device_name}.html",
            mime="text/html",
            help="Opens HTML \u2014 use Ctrl+P \u2192 Save as PDF",
        )

    with dl3:
        if os.path.exists(CSV_PATH):
            with open(CSV_PATH, "rb") as csvf:
                main_csv_bytes = csvf.read()
            st.download_button(
                "Download Main CSV",
                data=main_csv_bytes,
                file_name="document.csv",
                mime="text/csv",
            )
        else:
            st.button("Main CSV not found", disabled=True)


# ═══════════════════════════════════════════════════════════════════════════════
# EXECUTION — DEVICE SELECTION PAGE
# ═══════════════════════════════════════════════════════════════════════════════

elif st.session_state.perf_view == "exec_devices":
    if st.button("← Back", key="exec_dev_back"):
        st.session_state.perf_view = "landing"
        st.rerun()

    st.markdown("""
    <div class="perf-hero" style="padding-top:2rem; padding-bottom:1rem;">
        <div class="perf-title" style="font-size:2.2rem;">Performance Execution</div>
        <div class="perf-subtitle">Select a device to access its Jenkins execution pipelines</div>
    </div>
    """, unsafe_allow_html=True)

    cols_per_row = 4
    for i in range(0, len(PERF_DEVICES), cols_per_row):
        chunk = PERF_DEVICES[i:i + cols_per_row]
        pad = cols_per_row - len(chunk)
        col_spec = [1.5] + [2] * len(chunk) + [2] * pad + [1.5]
        cols = st.columns(col_spec)
        for j, dev in enumerate(chunk):
            with cols[j + 1]:
                if st.button(dev, key=f"exec_dev_{dev}", use_container_width=True):
                    st.session_state.exec_device = dev
                    st.session_state.perf_view = "exec_jenkins"
                    st.rerun()
        st.markdown("<div style='height:0.6rem'></div>", unsafe_allow_html=True)

    st.markdown("<div style='height:250px'></div>", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# EXECUTION — JENKINS BUTTONS PAGE
# ═══════════════════════════════════════════════════════════════════════════════

elif st.session_state.perf_view == "exec_jenkins":
    exec_device = st.session_state.exec_device or ""

    if st.button("← Back to Devices", key="exec_jenkins_back"):
        st.session_state.perf_view = "exec_devices"
        st.rerun()

    st.markdown(
        f"""
        <div class="perf-hero" style="padding-top:1.5rem; padding-bottom:0.5rem;">
            <div class="perf-title" style="font-size:2rem;">
                Access the Jenkins Execution
            </div>
            <div class="perf-subtitle" style="font-size:1.1rem; margin-top:0.4rem;">
                {exec_device}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.divider()

    EXEC_JOBS = [
        "Powercycle",
        "Network Outage",
        "Reboot",
        "Firmware Upgrade/Downgrade",
    ]

    # Build the 2×2 grid of Jenkins link buttons
    job_urls = {job: get_jenkins_url("performance_execution", exec_device, job) for job in EXEC_JOBS}

    btn_html = '<div class="jenkins-card"><div class="jenkins-btn-row">'
    for job in EXEC_JOBS:
        url = job_urls[job]
        if url:
            btn_html += (
                f'<a href="{url}" target="_blank" rel="noopener noreferrer" '
                f'class="jenkins-btn jenkins-btn-active">{job}</a>'
            )
        else:
            btn_html += (
                f'<span class="jenkins-btn jenkins-btn-disabled" '
                f'title="URL not configured yet">{job}</span>'
            )
    btn_html += '</div></div>'

    _, card_col, _ = st.columns([1, 4, 1])
    with card_col:
        st.markdown(btn_html, unsafe_allow_html=True)

    st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)

    # Info note for unconfigured buttons
    unconfigured = [j for j in EXEC_JOBS if not job_urls[j]]
    if unconfigured:
        _, note_col, _ = st.columns([1, 4, 1])
        with note_col:
            st.info(
                f"**{len(unconfigured)} pipeline(s) not yet configured:** "
                + ", ".join(unconfigured)
                + "  \nAdd URLs in `scripts/jenkins_links.py` under "
                + f'`performance_execution → {exec_device}`.'
            )

    st.markdown("<div style='height:200px'></div>", unsafe_allow_html=True)

