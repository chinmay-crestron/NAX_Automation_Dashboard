"""
NAX Automation Dashboard — Main Entry Point
Run with: streamlit run app.py
"""

import streamlit as st

st.set_page_config(
    page_title="NAX Automation Dashboard",
    page_icon="\u2699",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ─── Navigation (sidebar hidden — custom HTML topbar used instead) ────────────
home   = st.Page("Dashboard_Home.py",      title="Home",          default=True, icon=":material/home:",           url_path="")
config = st.Page("nax_device_dashboard.py", title="Device Config",              icon=":material/settings:",       url_path="device_config")
status = st.Page("Devicestatus.py",         title="Device Status",               icon=":material/monitor_heart:",  url_path="device_status")
perf   = st.Page("Performance.py",          title="Performance",                 icon=":material/speed:",          url_path="performance")
reg    = st.Page("Regression.py",            title="Regression",                  icon=":material/bug_report:",     url_path="regression")

pg = st.navigation([home, config, status, perf, reg], position="hidden")

# ─── Global CSS ───────────────────────────────────────────────────────────────
st.markdown("""
<style>
    /* Remove Streamlit's default top header bar */
    [data-testid="stHeader"]        { display: none !important; }
    [data-testid="collapsedControl"] { display: none !important; }



    
    #MainMenu                        { display: none !important; }

    /* Topbar */
    .nax-topbar {
        position:        fixed;
        top:             0;
        left:            0;
        right:           0;
        height:          52px;
        background:      rgba(16, 19, 30, 0.97);
        backdrop-filter: blur(10px);
        -webkit-backdrop-filter: blur(10px);
        border-bottom:   1px solid rgba(255,255,255,0.07);
        display:         flex;
        align-items:     center;
        padding:         0 2.2rem;
        z-index:         9999;
    }
    .nax-topbar-brand {
        font-size:      0.95rem;
        font-weight:    700;
        color:          #E8ECF0;
        text-decoration: none;
        letter-spacing: 0.03em;
        white-space:    nowrap;
        flex:           0 0 auto;
    }
    /* Nav links — absolutely centered in the topbar */
    .nax-topbar-nav {
        position:  absolute;
        left:      50%;
        transform: translateX(-50%);
        display:   flex;
        gap:       0.3rem;
        align-items: center;
    }
    .nax-topbar a.nav-link {
        color:           rgba(232,236,240,0.78);
        text-decoration: none;
        font-size:       0.84rem;
        letter-spacing:  0.01em;
        padding:         0.32rem 1rem;
        border-radius:   5px;
        transition:      color 0.18s, background 0.18s;
        white-space:     nowrap;
    }
    .nax-topbar a.nav-link:hover {
        color:      #ffffff;
        background: rgba(255,255,255,0.08);
    }

    /* Push page content below fixed topbar */
    .block-container {
        padding-top:    0 !important;
        padding-bottom: 2rem !important;
    }
    .topbar-spacer { height: 56px; }
</style>

<div class="nax-topbar">
    <a class="nax-topbar-brand" href="/" target="_self">&#9881;&nbsp; NAX Automation</a>
    <div class="nax-topbar-nav">
        <a class="nav-link" href="/"             target="_self">Home</a>
        <a class="nav-link" href="/device_config" target="_self">Device Config</a>
        <a class="nav-link" href="/device_status" target="_self">Device Status</a>
        <a class="nav-link" href="/performance"   target="_self">Performance</a>
        <a class="nav-link" href="/regression"    target="_self">Regression</a>
    </div>
</div>
<div class="topbar-spacer"></div>
""", unsafe_allow_html=True)

# ─── Run active page ──────────────────────────────────────────────────────────
pg.run()
