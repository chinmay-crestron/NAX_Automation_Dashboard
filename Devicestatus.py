"""
NAX Automation Dashboard — Device Status Page
Ping devices and track reachability via SQLite.
Supports category-based navigation (Regression / Performance / Longevity / Sanity).
"""

import streamlit as st
import json
import os
from nax_config import JSON_PATH, DEVICE_CATEGORIES
from device_status_db import (
    sync_devices_to_db, ping_device, update_device_status,
    get_all_devices, get_inactive_devices,
    get_devices_by_category, get_inactive_devices_by_category,
)

# ─── Helpers ──────────────────────────────────────────────────────────────────

def load_device_data():
    with open(JSON_PATH, "r") as f:
        return json.load(f)


def save_status_to_json(device_id, status):
    """Update the status field in the source JSON file (category-aware)."""
    with open(JSON_PATH, "r") as f:
        data = json.load(f)
    for cat_key in DEVICE_CATEGORIES:
        for model_name, devices in data.get(cat_key, {}).items():
            if device_id in devices:
                devices[device_id]["status"] = status
                break
    with open(JSON_PATH, "w") as f:
        json.dump(data, f, indent=2)


# Sync DB on every page load
data = load_device_data()
sync_devices_to_db(data)

# ─── Session state ────────────────────────────────────────────────────────────

if "status_active_category" not in st.session_state:
    st.session_state.status_active_category = None  # None = landing page

# ─── Page styles ──────────────────────────────────────────────────────────────

st.markdown("""
<style>
    /* Category landing hero */
    .status-hero {
        text-align:  center;
        padding:     8vh 1rem 2.5rem;
    }
    .status-title {
        font-size:      3.6rem !important;
        font-weight:    900 !important;
        color:          #FFFFFF !important;
        letter-spacing: -0.03em;
        line-height:    1.05 !important;
        margin-bottom:  0.7rem !important;
    }
    .status-title-accent { color: #4A9EFF; }
    .status-subtitle {
        font-size: 1rem !important;
        color:     rgba(220,228,240,0.55) !important;
    }
    /* Category card buttons */
    .cat-grid-row .stButton > button {
        min-height:     80px !important;
        font-size:      1.05rem !important;
        font-weight:    600 !important;
        background:     rgba(255,255,255,0.05) !important;
        border:         1px solid rgba(255,255,255,0.16) !important;
        color:          #E8ECF0 !important;
        border-radius:  10px !important;
    }
    .cat-grid-row .stButton > button:hover {
        background:   rgba(74,158,255,0.13) !important;
        border-color: #4A9EFF !important;
        color:        #4A9EFF !important;
    }
    /* Table column headers */
    div[data-testid="stHorizontalBlock"] p strong {
        font-size:      0.72rem;
        text-transform: uppercase;
        letter-spacing: 0.07em;
        opacity:        0.5;
    }
    code { font-size: 0.82rem !important; padding: 1px 6px !important; }
    div[data-testid="column"] .stButton > button { width: 100%; }
    div[data-testid="stHorizontalBlock"] { padding-top: 3px; padding-bottom: 3px; }
</style>
""", unsafe_allow_html=True)

# ─── CATEGORY LANDING PAGE ────────────────────────────────────────────────────

if st.session_state.status_active_category is None:

    st.markdown("""
<div class="status-hero">
    <div class="status-title">Device <span class="status-title-accent">Status</span></div>
    <div class="status-subtitle">Select a test category to check device connectivity and reachability.</div>
</div>
""", unsafe_allow_html=True)

    cat_keys = list(DEVICE_CATEGORIES.keys())
    for row_keys in [cat_keys[:2], cat_keys[2:]]:
        st.markdown('<div class="cat-grid-row">', unsafe_allow_html=True)
        _, gc1, _g, gc2, _ = st.columns([1.8, 2.8, 0.4, 2.8, 1.8])
        for col, cat_key in zip([gc1, gc2], row_keys):
            devices_in_cat   = get_devices_by_category(cat_key)
            inactive_in_cat  = [d for d in devices_in_cat if d["status"] == "inactive"]
            total            = len(devices_in_cat)
            inactive_count   = len(inactive_in_cat)
            inactive_badge   = f"  ·  {inactive_count} inactive" if inactive_count else ""
            with col:
                if st.button(
                    f"{DEVICE_CATEGORIES[cat_key]}{inactive_badge}",
                    key=f"status_land_{cat_key}",
                    width='stretch',
                ):
                    st.session_state.status_active_category = cat_key
                    st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    all_dev   = get_all_devices()
    all_inact = [d for d in all_dev if d["status"] == "inactive"]
    st.caption(f"Total devices: {len(all_dev)}   ·   Inactive: {len(all_inact)}")
    st.stop()


# ─── CATEGORY DEVICE STATUS VIEW ─────────────────────────────────────────────

cat_key     = st.session_state.status_active_category
cat_display = DEVICE_CATEGORIES.get(cat_key, cat_key)

# ─ Back button + title
col_back, col_hdr = st.columns([1, 9])
with col_back:
    if st.button("← Back", key="status_back"):
        st.session_state.status_active_category = None
        st.rerun()
with col_hdr:
    st.title(f"Device Status — {cat_display}")

st.caption("Ping devices to verify network reachability. Status updates are persisted.")

# ─ Inactive devices for this category
inactive = get_inactive_devices_by_category(cat_key)
if inactive:
    st.subheader(f"Inactive Devices  ·  {len(inactive)}")

    hdr = st.columns([2, 2, 2.5, 2, 2, 1.2, 1.2])
    hdr[0].markdown("**Device ID**")
    hdr[1].markdown("**Model**")
    hdr[2].markdown("**IP Address**")
    hdr[3].markdown("**Serial Number**")
    hdr[4].markdown("**Last Checked**")
    hdr[5].markdown("**Status**")
    hdr[6].markdown("**Action**")

    for d in inactive:
        row = st.columns([2, 2, 2.5, 2, 2, 1.2, 1.2])
        row[0].write(d["device_id"])
        row[1].write(d["model_name"])
        row[2].code(d["device_ip"])
        row[3].write(d["serial_number"] or "—")
        row[4].write(d["last_checked"] or "Never")
        row[5].write("🔴  Inactive")
        if row[6].button("Edit", key=f"edit_inactive_{d['device_id']}"):
            st.session_state.editing_device   = (d["model_name"], d["device_id"])
            st.session_state.editing_category = d.get("category")
            st.session_state.confirm_remove_device = False
            st.switch_page("nax_device_dashboard.py")

    st.divider()

# ─ Check All (category only)
if st.button("Check All Device Status", type="primary", key="check_all_cat"):
    cat_devices = get_devices_by_category(cat_key)
    progress = st.progress(0, text="Pinging devices...")
    total   = len(cat_devices)
    results = {"active": 0, "inactive": 0}

    for i, device in enumerate(cat_devices):
        reachable  = ping_device(device["device_ip"])
        new_status = "active" if reachable else "inactive"
        update_device_status(device["device_id"], new_status)
        save_status_to_json(device["device_id"], new_status)
        results[new_status] += 1
        progress.progress((i + 1) / total,
                          text=f"Checked {i + 1}/{total}  —  {device['device_id']}")

    progress.empty()
    st.success(f"Done. Active: {results['active']}  |  Inactive: {results['inactive']}")
    st.rerun()

st.divider()

# ─ All devices list for this category
st.subheader(f"All Devices  ·  {cat_display}")

all_devices = get_devices_by_category(cat_key)

if not all_devices:
    pass  # no devices yet — will populate once synced
else:
    hdr2 = st.columns([2, 2, 2.5, 2, 1.2, 1.5])
    hdr2[0].markdown("**Device Name**")
    hdr2[1].markdown("**Device ID**")
    hdr2[2].markdown("**IP Address**")
    hdr2[3].markdown("**Serial Number**")
    hdr2[4].markdown("**Status**")
    hdr2[5].markdown("**Action**")

    for device in all_devices:
        cols = st.columns([2, 2, 2.5, 2, 1.2, 1.5])
        cols[0].write(device["device_name"] or device["model_name"])
        cols[1].write(device["device_id"])
        cols[2].code(device["device_ip"])
        cols[3].write(device["serial_number"])
        s_label = "Active" if device["status"] == "active" else "Inactive"
        s_icon  = "🟢" if device["status"] == "active" else "🔴"
        cols[4].write(f"{s_icon}  {s_label}")
        if cols[5].button("Check", key=f"ping_{cat_key}_{device['device_id']}"):
            with st.spinner(f"Pinging {device['device_ip']}..."):
                reachable = ping_device(device["device_ip"])
            new_status = "active" if reachable else "inactive"
            update_device_status(device["device_id"], new_status)
            save_status_to_json(device["device_id"], new_status)
            if reachable:
                st.toast(f"{device['device_id']} is reachable.")
            else:
                st.toast(f"{device['device_id']} is not reachable.", icon="⚠️")
            st.rerun()

# Footer
st.divider()
inactive_count = len([d for d in all_devices if d["status"] == "inactive"])
st.caption(f"{cat_display}   ·   Total: {len(all_devices)}   ·   Inactive: {inactive_count}")

