"""
NAX Automation Dashboard — Home Page
"""

import streamlit as st
import base64
import os


def load_bg_image():
    """Load background image as base64 — checks png, jpg, jpeg, webp."""
    base_dir = os.path.dirname(__file__)
    for ext, mime in [("png", "image/png"), ("jpg", "image/jpeg"),
                      ("jpeg", "image/jpeg"), ("webp", "image/webp")]:
        bg_path = os.path.join(base_dir, f"home_bg.{ext}")
        if os.path.exists(bg_path):
            with open(bg_path, "rb") as f:
                data = base64.b64encode(f.read()).decode()
            return f"data:{mime};base64,{data}"
    return None


bg_data = load_bg_image()

if bg_data:
    bg_css = f"""
        .stApp {{
            background-image: url("{bg_data}");
            background-size: cover;
            background-position: center top;
            background-repeat: no-repeat;
        }}
        /* Dark overlay so text stays readable */
        [data-testid="stAppViewContainer"]::before {{
            content: "";
            position: fixed;
            inset: 0;
            background: rgba(8, 10, 20, 0.60);
            z-index: 0;
            pointer-events: none;
        }}
    """
else:
    bg_css = """
        .stApp {
            background:
                radial-gradient(ellipse at 25% 85%, rgba(70, 0, 120, 0.55) 0%, transparent 55%),
                radial-gradient(ellipse at 80% 15%, rgba(0, 50, 120, 0.45) 0%, transparent 55%),
                radial-gradient(ellipse at 60% 55%, rgba(0, 20, 80, 0.3)  0%, transparent 50%),
                linear-gradient(180deg, #080A14 0%, #0C0F1E 100%);
        }
    """

st.markdown(f"""
<style>
    {bg_css}

    /* Transparent Streamlit background layers so .stApp bg shows through */
    [data-testid="stAppViewContainer"],
    [data-testid="stAppViewContainer"] > section,
    [data-testid="stMain"],
    [data-testid="stMainBlockContainer"] {{
        background: transparent !important;
    }}

    /* Center the home hero section */
    .home-hero {{
        display:         flex;
        flex-direction:  column;
        align-items:     center;
        justify-content: center;
        text-align:      center;
        padding-top:     14vh;
        padding-bottom:  3rem;
        position:        relative;
        z-index:         1;
    }}
    .home-title {{
        font-size:      4.5rem !important;
        font-weight:    700 !important;
        letter-spacing: -0.02em;
        line-height:    1.05 !important;
        color:          #FFFFFF !important;
        margin:         0 0 1.2rem 0;
        text-shadow:    0 2px 40px rgba(0,0,0,0.5);
    }}
    .home-title-accent {{ color: #4A9EFF; }}
    .home-desc {{
        font-size:   1.1rem;
        color:       rgba(220, 228, 240, 0.72);
        max-width:   600px;
        line-height: 1.75;
        margin:      0 0 3rem 0;
        text-shadow: 0 1px 8px rgba(0,0,0,0.4);
    }}
    /* Whiten the secondary (non-primary) button */
    div[data-testid="stHorizontalBlock"] .stButton > button {{
        font-size:   0.92rem;
        padding:     0.6rem 1.6rem;
        font-weight: 600;
    }}
    div[data-testid="stHorizontalBlock"] .stButton > button:not([kind="primaryFormSubmit"]):not([data-testid="baseButton-primary"]) {{
        background:  rgba(255,255,255,0.12) !important;
        border:      1px solid rgba(255,255,255,0.30) !important;
        color:       #FFFFFF !important;
    }}
    div[data-testid="stHorizontalBlock"] .stButton > button:not([kind="primaryFormSubmit"]):not([data-testid="baseButton-primary"]):hover {{
        background:  rgba(255,255,255,0.22) !important;
        border-color: rgba(255,255,255,0.5) !important;
    }}
    /* Center the button row */
    div[data-testid="stHorizontalBlock"] {{
        justify-content: center;
    }}
</style>

<div class="home-hero">
    <div class="home-title">NAX <span class="home-title-accent">Automation</span><br>Dashboard</div>
    <div class="home-desc">
        Centralized automation dashboard for device configuration and health monitoring.
        Manage, monitor, and control all NAX devices &mdash; visualize automation workflows
        and track device health from a single interface.
    </div>
</div>
""", unsafe_allow_html=True)

# Centered action buttons — row 1: Device Config + Device Status
_, btn_col1, gap1, btn_col2, _ = st.columns([2.6, 1.6, 0.2, 1.6, 2.6])

with btn_col1:
    if st.button("View Device Config", type="primary", width='stretch'):
        st.switch_page("nax_device_dashboard.py")

with btn_col2:
    if st.button("Check Device Status", width='stretch'):
        st.switch_page("Devicestatus.py")

st.markdown("<div style='height:0.6rem'></div>", unsafe_allow_html=True)

# Row 2: Performance + Regression
_, btn_col3, gap2, btn_col4, _ = st.columns([2.6, 1.6, 0.2, 1.6, 2.6])

with btn_col3:
    if st.button("Performance", width='stretch'):
        st.switch_page("Performance.py")

with btn_col4:
    if st.button("Regression", width='stretch'):
        st.switch_page("Regression.py")

st.markdown("<div style='height:0.6rem'></div>", unsafe_allow_html=True)

# Row 3: Longevity
_, btn_col5, _ = st.columns([3.5, 1.6, 3.5])

with btn_col5:
    if st.button("Longevity", width='stretch'):
        st.switch_page("Longevity.py")

