"""
NAX Device Config Dashboard
============================
Streamlit app to view/edit device configs from Nax_Devices.json and commit to SVN.
Supports JSON schema v2: Regression_devices / Performance_devices /
Longevity_devices / Sanity_devices sections.

Run:
    pip install streamlit
    streamlit run app.py
"""

import streamlit as st
import json
import os
import subprocess
import shutil
import copy
import time
from datetime import datetime
from nax_config import JSON_PATH, SVN_URL, SVN_USER, SVN_PASS, SVN_BIN, DEVICE_CATEGORIES
from device_status_db import get_device_status_map

# ─── CONFIG ───────────────────────────────────────────────────────────────────

COMMITTED_SNAPSHOT_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), ".nax_committed.json"
)


def save_committed_snapshot(data):
    """Persist the committed state of the JSON after a successful SVN commit."""
    with open(COMMITTED_SNAPSHOT_PATH, "w") as f:
        json.dump(data, f, indent=2)


def load_committed_snapshot():
    """Return last-committed JSON dict, or None if no commit has been made."""
    if not os.path.exists(COMMITTED_SNAPSHOT_PATH):
        return None
    try:
        with open(COMMITTED_SNAPSHOT_PATH, "r") as f:
            return json.load(f)
    except Exception:
        return None


def has_uncommitted_changes():
    """
    Compare the current JSON against the committed snapshot.
    On first run (no snapshot), bootstrap a baseline so future saves are flagged.
    Ignores the `last_updated` timestamp to avoid false positives.
    """
    committed = load_committed_snapshot()
    if committed is None:
        # Bootstrap: record current state as the baseline.
        try:
            save_committed_snapshot(load_json())
        except Exception:
            pass
        return False
    try:
        current = load_json()
        return current.get("devices") != committed.get("devices")
    except Exception:
        return False


EDITABLE_FIELDS = [
    "device_ip", "device_username", "device_password", "serial_number",
    "pdu_ip", "pdu_password", "power_slot", "pdu_user",
    "network_switch_ip", "network_switch_user", "network_switch_password",
    "network_slot_rx", "inputs", "new_firmware"
]

# ─── HELPERS ──────────────────────────────────────────────────────────────────

def load_json():
    with open(JSON_PATH, "r") as f:
        return json.load(f)


def save_json(data):
    """Write data to JSON. Status is managed exclusively in SQLite — not stored in JSON."""
    data["last_updated"] = datetime.now().strftime("%Y-%m-%d")
    with open(JSON_PATH, "w") as f:
        json.dump(data, f, indent=2)


def save_committed_snapshot(data):
    with open(COMMITTED_SNAPSHOT_PATH, "w") as f:
        json.dump(data, f, indent=2)


def load_committed_snapshot():
    if not os.path.exists(COMMITTED_SNAPSHOT_PATH):
        return None
    try:
        with open(COMMITTED_SNAPSHOT_PATH, "r") as f:
            return json.load(f)
    except Exception:
        return None


def has_uncommitted_changes():
    committed = load_committed_snapshot()
    if committed is None:
        try:
            save_committed_snapshot(load_json())
        except Exception:
            pass
        return False
    try:
        current = load_json()
        return any(current.get(k) != committed.get(k) for k in DEVICE_CATEGORIES)
    except Exception:
        return False


def resolve_svn_executable():
    if SVN_BIN and os.path.exists(SVN_BIN):
        return SVN_BIN
    return shutil.which("svn")


def svn_commit(message):
    svn_executable = resolve_svn_executable()
    if not svn_executable:
        return 127, "", (
            "SVN client not found. Install Subversion and ensure 'svn' is on PATH, "
            "or set NAX_SVN_BIN to the full path of svn.exe."
        )
    cmd = [
        svn_executable, "commit", JSON_PATH,
        "-m", message,
        "--username", SVN_USER,
        "--password", SVN_PASS,
        "--non-interactive",
        "--no-auth-cache"
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.returncode, result.stdout, result.stderr
    except FileNotFoundError as exc:
        return 127, "", f"SVN executable not found: {exc}"
    except Exception as exc:
        return 1, "", f"Unexpected SVN error: {exc}"


def build_device_table(data, category_key):
    status_map = get_device_status_map()
    rows = []
    for model_name, devices in data.get(category_key, {}).items():
        for device_id, config in devices.items():
            rows.append({
                "Device ID": device_id,
                "IP Address": config.get("device_ip", ""),
                "Serial Number": config.get("serial_number", ""),
                "Model": model_name,
                "Status": status_map.get(device_id, "active"),
            })
    return rows


def compute_changes(original, modified):
    changes = []
    for cat_key in DEVICE_CATEGORIES:
        for model_name, devices in modified.get(cat_key, {}).items():
            for device_id, mod_dev in devices.items():
                orig_dev = original.get(cat_key, {}).get(model_name, {}).get(device_id, {})
                for field in EDITABLE_FIELDS:
                    old_val = orig_dev.get(field, "")
                    new_val = mod_dev.get(field, "")
                    if old_val != new_val:
                        changes.append({
                            "Device": device_id,
                            "Category": DEVICE_CATEGORIES[cat_key],
                            "Field": field,
                            "Old Value": old_val,
                            "New Value": new_val,
                        })
        for model_name, devices in original.get(cat_key, {}).items():
            for device_id in devices:
                if device_id not in modified.get(cat_key, {}).get(model_name, {}):
                    orig_ip = original[cat_key][model_name][device_id].get("device_ip", "")
                    changes.append({
                        "Device": device_id,
                        "Category": DEVICE_CATEGORIES[cat_key],
                        "Field": "(device removed)",
                        "Old Value": orig_ip,
                        "New Value": "— removed —",
                    })
    return changes


def find_device_category(data, model_name, device_id):
    """Search all categories to find which one contains (model_name, device_id)."""
    for cat_key in DEVICE_CATEGORIES:
        if device_id in data.get(cat_key, {}).get(model_name, {}):
            return cat_key
    return None


# ─── SESSION STATE INIT ──────────────────────────────────────────────────────

if "data" not in st.session_state:
    st.session_state.data = load_json()
    committed_snapshot = load_committed_snapshot()
    st.session_state.original = (
        committed_snapshot if committed_snapshot is not None
        else copy.deepcopy(st.session_state.data)
    )

if "active_category" not in st.session_state:
    st.session_state.active_category = None   # None = category landing page

if "editing_device" not in st.session_state:
    st.session_state.editing_device = None    # (model_name, device_id)

if "editing_category" not in st.session_state:
    st.session_state.editing_category = None  # category_key of device being edited

if "adding_device" not in st.session_state:
    st.session_state.adding_device = None     # (category_key, model_name)

if "pending_changes" not in st.session_state:
    st.session_state.pending_changes = has_uncommitted_changes()

if "show_commit_dialog" not in st.session_state:
    st.session_state.show_commit_dialog = False

if "commit_success_message" not in st.session_state:
    st.session_state.commit_success_message = None

if "confirm_remove_device" not in st.session_state:
    st.session_state.confirm_remove_device = False


# ─── PAGE STYLES ─────────────────────────────────────────────────────────────

st.markdown("""
<style>
    /* Full-width buttons inside column layouts */
    div[data-testid="column"] .stButton > button { width: 100%; }
    /* Muted uppercase column headers in device tables */
    div[data-testid="stHorizontalBlock"] p strong {
        font-size: 0.72rem;
        text-transform: uppercase;
        letter-spacing: 0.07em;
        opacity: 0.5;
    }
    /* Compact IP code blocks */
    code { font-size: 0.82rem !important; padding: 1px 6px !important; }
    /* Page padding */
    .block-container { padding-top: 1.6rem !important; padding-bottom: 2rem !important; }
    div[data-testid="stHorizontalBlock"] { padding-top: 3px; padding-bottom: 3px; }

    /* ── Category landing page ──────────────────────────────── */
    .config-hero {
        text-align: center;
        padding: 10vh 1rem 2.5rem;
    }
    .config-title {
        font-size: 3.6rem !important;
        font-weight: 900 !important;
        color: #FFFFFF !important;
        letter-spacing: -0.03em;
        line-height: 1.05 !important;
        margin-bottom: 0.7rem !important;
    }
    .config-title-accent { color: #4A9EFF; }
    .config-subtitle {
        font-size: 1rem !important;
        color: rgba(220,228,240,0.55) !important;
        margin-bottom: 0 !important;
    }
</style>
""", unsafe_allow_html=True)


# ─── COMMIT DIALOG ───────────────────────────────────────────────────────────
if st.session_state.show_commit_dialog:
    col_title, col_cancel_top = st.columns([5, 1])
    with col_title:
        st.subheader("Review Changes & Commit to SVN")
    with col_cancel_top:
        if st.button("Cancel", key="commit_cancel_top"):
            st.session_state.show_commit_dialog = False
            st.rerun()

    changes = compute_changes(st.session_state.original, st.session_state.data)
    if not changes:
        st.info("No changes detected.")
    else:
        st.dataframe(changes, width='stretch', hide_index=True)
        commit_msg = st.text_input(
            "Commit message",
            value=f"[NAX Config] Updated {len(changes)} field(s) — {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        )
        svn_executable = resolve_svn_executable()
        if not svn_executable:
            st.warning("SVN client is not available. Install SVN and add it to PATH, "
                       "or set NAX_SVN_BIN to svn.exe path.")
        if st.button("Commit to SVN", type="primary", disabled=not bool(svn_executable)):
            save_json(st.session_state.data)
            rc, stdout, stderr = svn_commit(commit_msg)
            if rc == 0:
                save_committed_snapshot(st.session_state.data)
                st.session_state.original = copy.deepcopy(st.session_state.data)
                st.session_state.pending_changes = False
                st.session_state.show_commit_dialog = False
                st.session_state.commit_success_message = "Committed to SVN successfully."
                st.rerun()
            else:
                st.error(f"SVN commit failed (exit code {rc})\n\n**stderr:** {stderr}\n\n**stdout:** {stdout}")
    st.stop()


# ─── ADD DEVICE VIEW ─────────────────────────────────────────────────────────
if st.session_state.adding_device is not None:
    add_cat_key, add_model_name = st.session_state.adding_device

    if st.button("← Back", key="add_back"):
        st.session_state.adding_device = None
        st.rerun()

    st.subheader(f"Add New Device — {add_model_name}  ({DEVICE_CATEGORIES[add_cat_key]})")
    st.divider()

    col1, col2 = st.columns(2)
    with col1:
        new_device_id = st.text_input(
            "Device ID *",
            placeholder=f"e.g. {add_model_name.split('-')[-1]}_device_new",
            key="new_device_id"
        )
    with col2:
        new_device_name = st.text_input("Device Name", value=add_model_name, key="new_device_name")

    st.markdown("##### Device Configuration")
    form_col1, form_col2 = st.columns(2)
    new_values = {}
    for i, field in enumerate(EDITABLE_FIELDS):
        target_col = form_col1 if i % 2 == 0 else form_col2
        with target_col:
            is_password = "password" in field.lower()
            new_values[field] = st.text_input(
                field, value="", key=f"new_{field}",
                type="password" if is_password else "default"
            )

    st.divider()
    col_save, col_cancel = st.columns(2)
    with col_save:
        if st.button("Add Device", type="primary"):
            device_id_clean = new_device_id.strip()
            if not device_id_clean:
                st.error("Device ID is required.")
            elif device_id_clean in st.session_state.data.get(add_cat_key, {}).get(add_model_name, {}):
                st.error(f"Device ID '{device_id_clean}' already exists in {add_model_name}.")
            else:
                new_config = {field: new_values[field] for field in EDITABLE_FIELDS}
                new_config["device_name"] = new_device_name.strip() or add_model_name
                st.session_state.data[add_cat_key][add_model_name][device_id_clean] = new_config
                st.session_state.pending_changes = True
                save_json(st.session_state.data)
                st.toast(f"Device '{device_id_clean}' added.")
                st.session_state.adding_device = None
                st.rerun()
    with col_cancel:
        if st.button("Cancel", key="add_cancel"):
            st.session_state.adding_device = None
            st.rerun()
    st.stop()


# ─── EDIT DEVICE VIEW ────────────────────────────────────────────────────────
if st.session_state.editing_device is not None:
    model_name, device_id = st.session_state.editing_device
    cat_key = st.session_state.editing_category

    # Resolve category if not set (e.g. navigated from Device Status page)
    if cat_key is None:
        cat_key = find_device_category(st.session_state.data, model_name, device_id)

    if cat_key is None:
        st.error(f"Device '{device_id}' not found in any category.")
        if st.button("Back to Device Config"):
            st.session_state.editing_device = None
            st.session_state.editing_category = None
            st.rerun()
        st.stop()

    device_config = st.session_state.data[cat_key][model_name][device_id]
    cat_display = DEVICE_CATEGORIES.get(cat_key, cat_key)

    if st.button("← Back", key="edit_back"):
        st.session_state.editing_device = None
        st.session_state.editing_category = None
        st.session_state.confirm_remove_device = False
        st.session_state.active_category = cat_key
        st.rerun()

    st.subheader(f"Edit Device — {device_id}  ({model_name}  ·  {cat_display})")
    st.divider()
    # ── Editable Device ID ────────────────────────────────────────────────────
    new_device_id = st.text_input(
        "Device ID",
        value=device_id,
        key=f"edit_device_id_{device_id}",
        help="Must be unique within this category across all model families."
    )
    new_device_id_clean = new_device_id.strip()
    edited_values = {}
    col1, col2 = st.columns(2)
    for i, field in enumerate(EDITABLE_FIELDS):
        current_val = device_config.get(field, "")
        target_col = col1 if i % 2 == 0 else col2
        with target_col:
            is_password = "password" in field.lower()
            edited_values[field] = st.text_input(
                field, value=current_val,
                key=f"edit_{device_id}_{field}",
                type="password" if is_password else "default"
            )

    st.divider()

    if st.session_state.confirm_remove_device:
        st.warning(f"Are you sure you want to remove **{device_id}**? This cannot be undone.")
        col_confirm, col_abort, _ = st.columns([1, 1, 3])
        with col_confirm:
            if st.button("Yes, Remove", type="primary", key="confirm_remove"):
                del st.session_state.data[cat_key][model_name][device_id]
                st.session_state.pending_changes = True
                st.session_state.confirm_remove_device = False
                save_json(st.session_state.data)
                st.session_state.editing_device = None
                st.session_state.editing_category = None
                st.session_state.active_category = cat_key
                st.rerun()
        with col_abort:
            if st.button("Cancel", key="abort_remove"):
                st.session_state.confirm_remove_device = False
                st.rerun()
    else:
        col_save, col_cancel, col_remove = st.columns([1.2, 1.2, 1])
        with col_save:
            if st.button("Save Changes", type="primary", key="edit_save"):
                # ── Validate new device ID ────────────────────────────────
                if not new_device_id_clean:
                    st.error("Device ID cannot be empty.")
                    st.stop()
                if new_device_id_clean != device_id:
                    # Check uniqueness across ALL model families in this category
                    all_ids_in_cat = [
                        did
                        for mname, devs in st.session_state.data.get(cat_key, {}).items()
                        for did in devs
                    ]
                    if new_device_id_clean in all_ids_in_cat:
                        st.error(f"Device ID **{new_device_id_clean}** already exists in {DEVICE_CATEGORIES[cat_key]}. Choose a unique ID.")
                        st.stop()
                    # Rename key in data
                    st.session_state.data[cat_key][model_name][new_device_id_clean] = \
                        st.session_state.data[cat_key][model_name].pop(device_id)
                    device_config = st.session_state.data[cat_key][model_name][new_device_id_clean]

                # ── Save field edits ──────────────────────────────────────
                changed = new_device_id_clean != device_id
                for field in EDITABLE_FIELDS:
                    if device_config.get(field, "") != edited_values[field]:
                        device_config[field] = edited_values[field]
                        changed = True
                if changed:
                    st.session_state.pending_changes = True
                    save_json(st.session_state.data)
                    st.toast(f"{new_device_id_clean} config saved locally.")
                else:
                    st.toast("No changes detected.")
                st.session_state.editing_device = None
                st.session_state.editing_category = None
                st.session_state.active_category = cat_key
                st.rerun()
        with col_cancel:
            if st.button("Cancel", key="edit_cancel"):
                st.session_state.confirm_remove_device = False
                st.session_state.editing_device = None
                st.session_state.editing_category = None
                st.session_state.active_category = cat_key
                st.rerun()
        with col_remove:
            if st.button("Remove Device", key="edit_remove"):
                st.session_state.confirm_remove_device = True
                st.rerun()
    st.stop()

# ─── FIRMWARE UPDATE DIALOG ──────────────────────────────────────────────────────────────

@st.dialog("Update Firmware Version", width="large")
def fw_update_dialog(cat_key: str, model_name: str):
    """Modal dialog for bulk-updating new_firmware across devices in a model section."""
    devices = st.session_state.data.get(cat_key, {}).get(model_name, {})
    device_ids = list(devices.keys())

    st.markdown(
        f"<div style='color:rgba(232,236,240,0.65); font-size:0.9rem; margin-bottom:0.9rem;'>"
        f"<b>{model_name}</b>&nbsp;·&nbsp;{DEVICE_CATEGORIES.get(cat_key, cat_key)}</div>",
        unsafe_allow_html=True,
    )

    # Firmware version input + Save button on the same row
    in_col, btn_col = st.columns([5, 1])
    with in_col:
        new_ver = st.text_input(
            "New firmware version",
            placeholder="e.g. v3.2.0106.06528",
            key=f"fw_ver_input_{cat_key}_{model_name}",
            label_visibility="collapsed",
        )
    with btn_col:
        save_clicked = st.button(
            "Save", type="primary",
            key=f"fw_save_{cat_key}_{model_name}",
            width="stretch",
        )

    st.divider()
    st.markdown("**Select devices to update:**")

    # Individual device checkboxes — all selected by default
    selected: dict = {}
    for did in device_ids:
        ip     = devices[did].get("device_ip", "—")
        cur_fw = devices[did].get("new_firmware", "not set")
        selected[did] = st.checkbox(
            f"{did}  ·  {ip}  (current: {cur_fw})",
            value=True,
            key=f"fw_dev_{cat_key}_{model_name}_{did}",
        )

    # Validate & save
    if save_clicked:
        ver_clean = new_ver.strip()
        if not ver_clean:
            st.error("Please enter a firmware version.")
        elif not any(selected.values()):
            st.error("Select at least one device.")
        else:
            for did, is_sel in selected.items():
                if is_sel:
                    st.session_state.data[cat_key][model_name][did]["new_firmware"] = ver_clean
            save_json(st.session_state.data)
            st.session_state.pending_changes = True
            st.rerun()

# ─── CATEGORY DEVICE LIST ────────────────────────────────────────────────────
if st.session_state.active_category is not None:
    cat_key     = st.session_state.active_category
    cat_display = DEVICE_CATEGORIES.get(cat_key, cat_key)

    # Success / pending banners
    if st.session_state.commit_success_message:
        _sp = st.empty()
        _sp.success(st.session_state.commit_success_message)
        time.sleep(5)
        _sp.empty()
        st.session_state.commit_success_message = None

    if st.session_state.pending_changes:
        _chg = compute_changes(st.session_state.original, st.session_state.data)
        if _chg:
            st.warning(f"You have **{len(_chg)}** unsaved change(s) pending SVN commit.")
            _bc1, _bc2, _bc3 = st.columns([2, 2, 5])
            with _bc1:
                if st.button("View Changes & Commit", type="primary", key="list_commit_btn"):
                    st.session_state.show_commit_dialog = True
                    st.rerun()
            with _bc2:
                if st.button("Revert Changes", key="list_revert_btn"):
                    _snap = load_committed_snapshot()
                    _rev = copy.deepcopy(_snap) if _snap is not None else copy.deepcopy(st.session_state.original)
                    st.session_state.data = _rev
                    save_json(st.session_state.data)
                    st.session_state.pending_changes = False
                    st.session_state.original = copy.deepcopy(st.session_state.data)
                    st.toast("Changes reverted to last committed state.")
                    st.rerun()
        else:
            st.session_state.pending_changes = False

    col_back, col_hdr = st.columns([1, 9])
    with col_back:
        if st.button("← Back", key="list_back"):
            st.session_state.active_category = None
            st.rerun()
    with col_hdr:
        st.subheader(cat_display)
    st.divider()

    rows = build_device_table(st.session_state.data, cat_key)

    for model_name in st.session_state.data.get(cat_key, {}):
        model_rows = [r for r in rows if r["Model"] == model_name]
        if not model_rows:
            continue

        st.markdown(f"**{model_name}   ·   {len(model_rows)} device(s)**")

        hdr = st.columns([2, 2.5, 2.5, 1.2, 1.5])
        hdr[0].markdown("**Device ID**")
        hdr[1].markdown("**IP Address**")
        hdr[2].markdown("**Serial Number**")
        hdr[3].markdown("**Status**")
        hdr[4].markdown("**Action**")

        for row in model_rows:
            cols = st.columns([2, 2.5, 2.5, 1.2, 1.5])
            cols[0].write(row["Device ID"])
            cols[1].code(row["IP Address"])
            cols[2].write(row["Serial Number"])
            s_label = "Active" if row["Status"] == "active" else "Inactive"
            s_icon  = "🟢" if row["Status"] == "active" else "🔴"
            cols[3].write(f"{s_icon}  {s_label}")
            if cols[4].button("Edit", key=f"btn_{cat_key}_{row['Device ID']}"):
                st.session_state.confirm_remove_device = False
                st.session_state.editing_category = cat_key
                st.session_state.editing_device = (row["Model"], row["Device ID"])
                st.rerun()

        _ab, _space, _fwb, _ = st.columns([1, 3, 1,0.5])
        with _ab:
            if st.button(f"Add Device  —  {model_name}", key=f"add_btn_{cat_key}_{model_name}", width="stretch"):
                st.session_state.adding_device = (cat_key, model_name)
                st.rerun()
        with _fwb:
            if st.button("Update Firmware Version", key=f"fw_btn_{cat_key}_{model_name}", width="stretch"):
                fw_update_dialog(cat_key, model_name)

        st.markdown("---")

    total = sum(len(st.session_state.data.get(cat_key, {}).get(m, {}))
                for m in st.session_state.data.get(cat_key, {}))
    st.caption(f"Schema v{st.session_state.data.get('schema_version', '?')}   ·   "
               f"{cat_display}: {total} device(s)   ·   SVN: {SVN_URL}")
    st.stop()


# ─── CATEGORY LANDING PAGE ────────────────────────────────────────────────────

if st.session_state.commit_success_message:
    _sp = st.empty()
    _sp.success(st.session_state.commit_success_message)
    time.sleep(5)
    _sp.empty()
    st.session_state.commit_success_message = None

if st.session_state.pending_changes:
    _chg = compute_changes(st.session_state.original, st.session_state.data)
    if _chg:
        st.warning(f"You have **{len(_chg)}** unsaved change(s) pending SVN commit.")
        _lc1, _lc2, _lc3 = st.columns([2, 2, 5])
        with _lc1:
            if st.button("View Changes & Commit", type="primary"):
                st.session_state.show_commit_dialog = True
                st.rerun()
        with _lc2:
            if st.button("Revert Changes", key="land_revert_btn"):
                _snap = load_committed_snapshot()
                _rev = copy.deepcopy(_snap) if _snap is not None else copy.deepcopy(st.session_state.original)
                st.session_state.data = _rev
                save_json(st.session_state.data)
                st.session_state.pending_changes = False
                st.session_state.original = copy.deepcopy(st.session_state.data)
                st.toast("Changes reverted to last committed state.")
                st.rerun()
    else:
        st.session_state.pending_changes = False

# Hero heading (styled like Dashboard Home)
st.markdown("""
<div class="config-hero">
    <div class="config-title">DM-NAX<br><span class="config-title-accent">Device Configuration</span></div>
    <div class="config-subtitle">Select a test category to view and manage device configurations.</div>
</div>
""", unsafe_allow_html=True)

# 2 × 2 category button grid — centered with spacer columns
cat_keys = list(DEVICE_CATEGORIES.keys())

for row_keys in [cat_keys[:2], cat_keys[2:]]:
    st.markdown('<div class="cat-grid-row">', unsafe_allow_html=True)
    _, gc1, gsp, gc2, _ = st.columns([1.8, 2.8, 0.4, 2.8, 1.8])
    for col, cat_key in zip([gc1, gc2], row_keys):
        with col:
            if st.button(DEVICE_CATEGORIES[cat_key],
                         key=f"land_{cat_key}", width='stretch'):
                st.session_state.active_category = cat_key
                st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

st.markdown("<div style='height:300px'></div>", unsafe_allow_html=True)

st.caption(
    f"Schema v{st.session_state.data.get('schema_version', '?')} · "
    f"Last updated: {st.session_state.data.get('last_updated', 'N/A')} · "
    f"SVN: {SVN_URL}"
)



