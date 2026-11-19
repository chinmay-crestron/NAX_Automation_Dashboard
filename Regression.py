"""
Regression Testing Page
=======================
Provides access to Regression Logs (shared drive) and
Regression Execution (Jenkins pipelines) for each device.
"""

import streamlit as st
import html
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "scripts"))
from jenkins_links import get_jenkins_url
from regression_paths import get_regression_log_path

# ── Device list (same across the dashboard) ───────────────────────────────────

REG_DEVICES = [
    "DM-NAX-8ZSA",
    "DM-NAX-4ZSA",
    "DM-NAX-4ZSP",
    "DM-NAX-16AIN",
    "DM-NAX-AMP300",
    "Edge-Devices",
    "Saros",
]

# ── CSS ───────────────────────────────────────────────────────────────────────

st.markdown("""
<style>
    .reg-hero {
        text-align: center;
        padding: 4rem 0 2rem;
    }
    .reg-title {
        font-size: 3.2rem;
        font-weight: 800;
        line-height: 1.15;
        color: #E8ECF0;
    }
    .reg-title-accent { color: #4DA3FF; }
    .reg-subtitle {
        color: rgba(232,236,240,0.55);
        font-size: 1.05rem;
        margin-top: 0.8rem;
    }
    .jenkins-card {
        background: rgba(40, 55, 80, 0.35);
        border: 1px solid rgba(77,163,255,0.2);
        border-radius: 16px;
        padding: 3rem 4rem;
        margin: 2rem auto;
        max-width: 600px;
        text-align: center;
    }
    .jenkins-btn {
        display: inline-block;
        padding: 0.85rem 2.5rem;
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
    .log-card {
        background: rgba(40, 55, 80, 0.35);
        border: 1px solid rgba(77,163,255,0.15);
        border-radius: 16px;
        padding: 2.5rem 3rem;
        margin: 2rem auto;
        max-width: 750px;
        text-align: center;
    }
    .log-path {
        font-size: 0.85rem;
        color: rgba(232,236,240,0.45);
        margin-top: 1rem;
        word-break: break-all;
    }
</style>
""", unsafe_allow_html=True)

# ── Session state ─────────────────────────────────────────────────────────────

if "reg_view" not in st.session_state:
    st.session_state.reg_view = "landing"
if "reg_device" not in st.session_state:
    st.session_state.reg_device = None
if "reg_exec_device" not in st.session_state:
    st.session_state.reg_exec_device = None


# ── Helper: copy-to-clipboard path rows ───────────────────────────────────────

_COPY_STYLE = """
<style>
    .nax-copy-box { max-width: 900px; margin: 0 auto; }
    .nax-copy-list { max-height: 520px; overflow-y: auto; margin-top: 0.6rem; }
    .nax-copy-row {
        display: flex; align-items: center; gap: 0.8rem;
        padding: 0.5rem 0.9rem; margin-bottom: 0.4rem;
        background: rgba(40, 55, 80, 0.35);
        border: 1px solid rgba(77,163,255,0.15); border-radius: 10px;
    }
    .nax-copy-label { flex: 0 0 auto; min-width: 7.5rem; font-weight: 600; color: #E8ECF0; }
    .nax-copy-label.grow { flex: 1 1 auto; font-weight: 500; word-break: break-all; }
    .nax-copy-val {
        flex: 1 1 auto; font-family: Consolas, monospace; font-size: 0.85rem;
        color: rgba(232,236,240,0.75); word-break: break-all;
    }
    .nax-copy-btn {
        flex: 0 0 auto; min-width: 5.5rem; padding: 0.35rem 0.9rem; cursor: pointer;
        color: #fff; background: linear-gradient(135deg, #4DA3FF 0%, #1a6fd4 100%);
        border: none; border-radius: 6px; font-weight: 600;
    }
    .nax-copy-btn:hover { filter: brightness(1.15); }
</style>
"""

# Listener is attached once per page; navigator.clipboard needs https, so fall back to execCommand.
_COPY_SCRIPT = """
<script>
(function () {
  if (window.__naxCopyBound) return;
  window.__naxCopyBound = true;
  function legacyCopy(text) {
    var ta = document.createElement('textarea');
    ta.value = text; ta.style.position = 'fixed'; ta.style.opacity = '0';
    document.body.appendChild(ta); ta.select();
    var ok = false;
    try { ok = document.execCommand('copy'); } catch (e) {}
    document.body.removeChild(ta);
    return ok;
  }
  document.addEventListener('click', function (e) {
    var btn = e.target.closest('.nax-copy-btn');
    if (!btn) return;
    var text = btn.getAttribute('data-copy');
    var done = function (ok) {
      btn.textContent = ok ? 'Copied!' : 'Copy failed';
      setTimeout(function () { btn.textContent = 'Copy'; }, 1500);
    };
    if (navigator.clipboard && window.isSecureContext) {
      navigator.clipboard.writeText(text).then(function () { done(true); },
                                               function () { done(legacyCopy(text)); });
    } else {
      done(legacyCopy(text));
    }
  });
})();
</script>
"""


def _copy_row(label: str, text: str, show_value: bool = True) -> str:
    esc = html.escape(text, quote=True)
    value = f'<span class="nax-copy-val">{esc}</span>' if show_value else ""
    cls = "nax-copy-label" if show_value else "nax-copy-label grow"
    return (
        f'<div class="nax-copy-row"><span class="{cls}">{html.escape(label)}</span>'
        f'{value}'
        f'<button type="button" class="nax-copy-btn" data-copy="{esc}">Copy</button></div>'
    )


def _render_copy_rows(rows_html: str):
    st.html(f'{_COPY_STYLE}<div class="nax-copy-box">{rows_html}</div>{_COPY_SCRIPT}', unsafe_allow_javascript=True)


# ── Helper: device button grid ────────────────────────────────────────────────

def _device_grid(key_prefix: str, target_view: str, device_state_key: str):
    """Render a 2-row grid of device buttons."""
    cols_per_row = 4
    for i in range(0, len(REG_DEVICES), cols_per_row):
        chunk = REG_DEVICES[i:i + cols_per_row]
        pad = cols_per_row - len(chunk)
        col_spec = [1.5] + [2] * len(chunk) + [2] * pad + [1.5]
        cols = st.columns(col_spec)
        for j, dev in enumerate(chunk):
            with cols[j + 1]:
                if st.button(dev, key=f"{key_prefix}_{dev}", use_container_width=True):
                    setattr(st.session_state, device_state_key, dev)
                    st.session_state.reg_view = target_view
                    st.rerun()
        st.markdown("<div style='height:0.6rem'></div>", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# LANDING PAGE
# ═══════════════════════════════════════════════════════════════════════════════

if st.session_state.reg_view == "landing":
    st.markdown("""
    <div class="reg-hero">
        <div class="reg-title">DM-NAX<br><span class="reg-title-accent">Regression Testing</span></div>
        <div class="reg-subtitle">Access regression logs and execution pipelines in a single interface.</div>
    </div>
    """, unsafe_allow_html=True)

    _, btn1, gap, btn2, _ = st.columns([2, 1.8, 0.4, 1.8, 2])
    with btn1:
        if st.button("Regression Logs", type="secondary", use_container_width=True):
            st.session_state.reg_view = "log_devices"
            st.rerun()
    with btn2:
        if st.button("Regression Execution", type="secondary", use_container_width=True):
            st.session_state.reg_view = "exec_devices"
            st.rerun()

    st.markdown("<div style='height:300px'></div>", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# REGRESSION LOGS — DEVICE SELECTION
# ═══════════════════════════════════════════════════════════════════════════════

elif st.session_state.reg_view == "log_devices":
    if st.button("← Back", key="log_dev_back"):
        st.session_state.reg_view = "landing"
        st.rerun()

    st.markdown("""
    <div class="reg-hero" style="padding-top:2rem; padding-bottom:1rem;">
        <div class="reg-title" style="font-size:2.2rem;">Regression Logs</div>
        <div class="reg-subtitle">Select a device to view regression log folder</div>
    </div>
    """, unsafe_allow_html=True)

    _device_grid("reg_log", "log_folder", "reg_device")

    st.markdown("<div style='height:250px'></div>", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# REGRESSION LOGS — FOLDER VIEW
# ═══════════════════════════════════════════════════════════════════════════════

elif st.session_state.reg_view == "log_folder":
    device = st.session_state.reg_device or ""

    if st.button("← Back to Devices", key="log_folder_back"):
        st.session_state.reg_view = "log_devices"
        st.rerun()

    st.markdown(
        f"<div class='reg-hero' style='padding-top:1.5rem; padding-bottom:0.5rem;'>"
        f"<div class='reg-title' style='font-size:2rem;'>Regression Logs</div>"
        f"<div class='reg-subtitle' style='font-size:1.1rem; margin-top:0.4rem;'>{device}</div>"
        f"</div>",
        unsafe_allow_html=True,
    )
    st.divider()

    log_path = get_regression_log_path(device)

    if log_path:
        st.info(
            "Click **Copy**, then paste the path into **File Explorer's** address bar, or into a "
            "**browser's** address bar (Chrome / Edge), to open the folder."
        )
        _render_copy_rows(_copy_row("Folder path", log_path))

        # List log folders if accessible
        log_folders = []
        if os.path.isdir(log_path):
            try:
                entries = sorted(os.listdir(log_path), reverse=True)
                log_folders = [e for e in entries if os.path.isdir(os.path.join(log_path, e))]
            except PermissionError:
                pass

        if log_folders:
            st.markdown(
                f"<div style='text-align:center; color:rgba(232,236,240,0.55); font-size:0.9rem; margin:1rem 0 0.4rem;'>"
                f"Found <b>{len(log_folders)}</b> log folder(s)"
                f"</div>",
                unsafe_allow_html=True,
            )
            _render_copy_rows(
                '<div class="nax-copy-list">'
                + "".join(_copy_row(folder, os.path.join(log_path, folder), show_value=False) for folder in log_folders)
                + "</div>"
            )
    else:
        st.warning(f"Log path not configured for **{device}**. Update `scripts/regression_paths.py`.")
# ═══════════════════════════════════════════════════════════════════════════════
# REGRESSION EXECUTION — DEVICE SELECTION
# ═══════════════════════════════════════════════════════════════════════════════

elif st.session_state.reg_view == "exec_devices":
    if st.button("← Back", key="exec_dev_back"):
        st.session_state.reg_view = "landing"
        st.rerun()

    st.markdown("""
    <div class="reg-hero" style="padding-top:2rem; padding-bottom:1rem;">
        <div class="reg-title" style="font-size:2.2rem;">Regression Execution</div>
        <div class="reg-subtitle">Select a device to access its Jenkins regression pipeline</div>
    </div>
    """, unsafe_allow_html=True)

    _device_grid("reg_exec", "exec_jenkins", "reg_exec_device")

    st.markdown("<div style='height:250px'></div>", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# REGRESSION EXECUTION — JENKINS LINK
# ═══════════════════════════════════════════════════════════════════════════════

elif st.session_state.reg_view == "exec_jenkins":
    device = st.session_state.reg_exec_device or ""

    if st.button("← Back to Devices", key="exec_jenkins_back"):
        st.session_state.reg_view = "exec_devices"
        st.rerun()

    st.markdown(
        f"""
        <div class="reg-hero" style="padding-top:1.5rem; padding-bottom:0.5rem;">
            <div class="reg-title" style="font-size:2rem;">
                Navigate to Regression Jenkins Pipeline
            </div>
            <div class="reg-subtitle" style="font-size:1.1rem; margin-top:0.4rem;">
                {device}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.divider()

    # Single regression job button per device
    job_name = f"{device}_Regression"
    url = get_jenkins_url("regression_execution", device, "Regression")

    if url:
        btn_html = (
            f'<div class="jenkins-card">'
            f'<a href="{url}" target="_blank" rel="noopener noreferrer" '
            f'class="jenkins-btn jenkins-btn-active">{job_name}</a>'
            f'</div>'
        )
    else:
        btn_html = (
            f'<div class="jenkins-card">'
            f'<span class="jenkins-btn jenkins-btn-disabled" '
            f'title="URL not configured">{job_name}</span>'
            f'</div>'
        )

    _, card_col, _ = st.columns([1, 4, 1])
    with card_col:
        st.markdown(btn_html, unsafe_allow_html=True)

    if not url:
        _, note_col, _ = st.columns([1, 4, 1])
        with note_col:
            st.info(
                f"Pipeline URL not yet configured for **{device}**.  \n"
                f"Add it in `scripts/jenkins_links.py` under "
                f"`regression_execution → {device} → Regression`."
            )

    st.markdown("<div style='height:200px'></div>", unsafe_allow_html=True)
