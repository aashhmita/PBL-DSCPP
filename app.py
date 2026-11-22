"""StrayCare: stray-animal rescue management.

Frontend: this file (Streamlit). Backend: a C data-structure core + C++ controller, loaded
through backend/native_bridge.py. If the library has not been built, the app falls back to the
pure-Python backend automatically.

    python build.py            (once, to compile the C/C++ core)
    streamlit run app.py
"""

import html
import os
from datetime import date, datetime

import streamlit as st

from backend.constants import (
    CASE_STATUSES, FOOD_STATUSES, SPECIES, URGENCY_LEVELS,
)
from backend.auth import UserStore
from backend.engine import create_controller

st.set_page_config(
    page_title="StrayCare | Rescue Management",
    page_icon="🐾",
    layout="wide",
    initial_sidebar_state="expanded",
)

PAGES = [
    "Overview", "Animal Registry", "Rescue & Triage",
    "Food Donations", "Medical Records", "Route Planner", "About Project",
]
DATA_FILE = os.environ.get("STRAYCARE_DATA") or os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "data", "straycare.json"
)

USERS_FILE = os.environ.get("STRAYCARE_USERS") or os.path.join(os.path.dirname(DATA_FILE), "users.json")
ADMIN_ONLY_PAGES = ["User Management"]

# ----------------------------- Theme -----------------------------------------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Manrope:wght@400;500;600;700;800&display=swap');
html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }

/* ===== Page: always the same light look, whether Streamlit is in light or dark theme ===== */
.stApp, [data-testid="stAppViewContainer"], [data-testid="stMain"], section.main { background: #f4f7f6 !important; color: #172b2a !important; }
[data-testid="stHeader"] { background: #f4f7f6 !important; }
[data-testid="stHeader"] * { color: #172b2a !important; }
h1, h2, h3 { font-family: 'Manrope', sans-serif; letter-spacing: -0.5px; }

/* ===== Text colours (every text type is set explicitly, so nothing turns white-on-white) ===== */
.stApp [data-testid="stMarkdownContainer"] { color: #172b2a; }
.stApp [data-testid="stMarkdownContainer"] p, .stApp [data-testid="stMarkdownContainer"] li { color: #172b2a !important; }
.stApp [data-testid="stMarkdownContainer"] a { color: #17695a !important; }
.stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5, .stApp h6 { color: #163b35 !important; }
.stApp [data-testid="stWidgetLabel"], .stApp [data-testid="stWidgetLabel"] *, .stApp label, .stApp label * { color: #172b2a !important; }
.stApp [data-testid="stCaptionContainer"], .stApp [data-testid="stCaptionContainer"] * { color: #556a63 !important; }

/* ===== Inputs: white boxes with dark text ===== */
.stApp [data-baseweb="input"], .stApp [data-baseweb="base-input"], .stApp [data-baseweb="textarea"],
.stApp [data-baseweb="select"] > div { background: #ffffff !important; border-color: #c9d8d2 !important; }
.stApp input, .stApp textarea { background: #ffffff !important; color: #172b2a !important; -webkit-text-fill-color: #172b2a !important; caret-color: #172b2a !important; }
.stApp input::placeholder, .stApp textarea::placeholder { color: #667a73 !important; -webkit-text-fill-color: #667a73 !important; opacity: 1 !important; }
.stApp [data-baseweb="select"] * { color: #172b2a !important; }
.stApp [data-baseweb="select"] svg { fill: #172b2a !important; }
.stApp [data-baseweb="tag"] { background: #e4f4ec !important; }
.stApp [data-baseweb="tag"] * { color: #176448 !important; }
.stApp [data-testid="stNumberInput"] button { background: #eef4f1 !important; border-color: #c9d8d2 !important; }
.stApp [data-testid="stNumberInput"] button * { color: #172b2a !important; fill: #172b2a !important; }
.stApp [data-testid="stCheckbox"] [data-baseweb="checkbox"] > span:first-child { border-color: #6b807a !important; }

/* Drop-down lists open in a layer outside the page, so they are styled from `body` */
body [data-baseweb="popover"] ul[role="listbox"], body [data-baseweb="menu"] { background: #ffffff !important; }
body [data-baseweb="popover"] ul[role="listbox"] li, body [data-baseweb="menu"] li { background: #ffffff !important; color: #172b2a !important; }
body [data-baseweb="popover"] ul[role="listbox"] li *, body [data-baseweb="menu"] li * { color: #172b2a !important; }
body [data-baseweb="popover"] ul[role="listbox"] li:hover, body [data-baseweb="popover"] ul[role="listbox"] li[aria-selected="true"],
body [data-baseweb="menu"] li:hover { background: #e4f4ec !important; }

/* ===== No link icons beside headings (Streamlit adds them; they do nothing here) ===== */
[data-testid="stHeaderActionElements"], .stApp [data-testid="stHeaderActionElements"],
.stApp h1 a, .stApp h2 a, .stApp h3 a, .stApp h4 a, .stApp h5 a, .stApp h6 a { display: none !important; }

/* ===== Tabs ===== */
.stApp [data-baseweb="tab-list"] button, .stApp [data-baseweb="tab-list"] button * { color: #4d625b !important; }
.stApp [data-baseweb="tab-list"] button[aria-selected="true"], .stApp [data-baseweb="tab-list"] button[aria-selected="true"] * { color: #17695a !important; font-weight: 700; }
.stApp [data-baseweb="tab-highlight"] { background: #17695a !important; }
.stApp [data-baseweb="tab-border"] { background: #d5e2dc !important; }

/* ===== Buttons ===== */
.stApp .stButton > button[kind="primary"], .stApp .stFormSubmitButton > button,
.stApp [data-testid="stBaseButton-primary"], .stApp [data-testid="stBaseButton-primaryFormSubmit"] { background: #17695a !important; border: 1px solid #17695a !important; border-radius: 9px; }
.stApp .stButton > button[kind="primary"] *, .stApp .stFormSubmitButton > button *,
.stApp [data-testid="stBaseButton-primary"] *, .stApp [data-testid="stBaseButton-primaryFormSubmit"] * { color: #ffffff !important; }
.stApp .stButton > button[kind="secondary"], .stApp [data-testid="stBaseButton-secondary"] { background: #ffffff !important; border: 1px solid #17695a !important; border-radius: 9px; }
.stApp .stButton > button[kind="secondary"] *, .stApp [data-testid="stBaseButton-secondary"] * { color: #17695a !important; }
.stApp .stButton > button:disabled, .stApp .stFormSubmitButton > button:disabled { opacity: .45; }

/* ===== Message boxes (info / success / warning / error): dark text on their tinted background ===== */
.stApp [data-testid="stAlert"], .stApp [data-testid="stAlert"] *, .stApp [data-testid="stAlertContainer"] * { color: #172b2a !important; }

/* ===== Forms ===== */
div[data-testid="stForm"] { background: #ffffff !important; border: 1px solid #e2ebe7; padding: 20px; border-radius: 15px; }
hr { border-color: #e1eae6; }

/* ===== Custom cards (hero, metrics, panels, pills) ===== */
.hero { background: linear-gradient(120deg,#123d38,#1b6255); padding: 27px 30px; border-radius: 18px; color: white; margin-bottom: 18px; }
.eyebrow { font-size: 11px; font-weight: 800; letter-spacing: 2px; text-transform: uppercase; margin-bottom: 9px; }
.metric { background: white; border: 1px solid #e2ebe7; border-radius: 15px; padding: 17px 18px; min-height: 120px; }
.metric-label { font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: .7px; }
.metric-value { font-family: 'Manrope',sans-serif; font-size: 30px; font-weight: 800; margin: 7px 0 2px; }
.metric-note { font-size: 12px; }
.panel { background: white; border: 1px solid #e2ebe7; border-radius: 15px; padding: 20px; }
.small-muted { font-size: 13px; }
.pill { display:inline-block; padding:4px 9px; border-radius:99px; font-size:11px; font-weight:700; }
.stApp [data-testid="stMarkdownContainer"] .hero h1 { color: #ffffff !important; font-size: 31px; margin: 0 0 7px 0; }
.stApp [data-testid="stMarkdownContainer"] .hero p { color: #d2e9e2 !important; margin: 0; font-size: 14px; }
.stApp [data-testid="stMarkdownContainer"] .hero .eyebrow { color: #a6d9c8 !important; }
.stApp [data-testid="stMarkdownContainer"] .metric .metric-label { color: #556a63 !important; }
.stApp [data-testid="stMarkdownContainer"] .metric .metric-value { color: #163b35 !important; }
.stApp [data-testid="stMarkdownContainer"] .metric .metric-note { color: #5c6f69 !important; }
.stApp [data-testid="stMarkdownContainer"] .panel, .stApp [data-testid="stMarkdownContainer"] .panel b,
.stApp [data-testid="stMarkdownContainer"] .panel h3 { color: #172b2a !important; }
.stApp [data-testid="stMarkdownContainer"] .small-muted { color: #556a63 !important; }
.stApp [data-testid="stMarkdownContainer"] .pill { background: #e4f4ec !important; color: #176448 !important; }

/* ===== Sidebar: dark green with light text (written last, with extra weight, so it wins) ===== */
[data-testid="stSidebar"], [data-testid="stSidebar"] > div:first-child { background: #102d2b !important; }
html body .stApp [data-testid="stSidebar"], html body .stApp [data-testid="stSidebar"] * { color: #eaf5f1 !important; }
html body .stApp [data-testid="stSidebar"] [data-testid="stCaptionContainer"] * { color: #b9d6cc !important; }
html body .stApp [data-testid="stSidebar"] [data-testid="stRadio"] label { padding: 7px 10px; border-radius: 9px; }
html body .stApp [data-testid="stSidebar"] .stButton > button,
html body .stApp [data-testid="stSidebar"] [data-testid^="stBaseButton"] { background: rgba(255,255,255,.10) !important; border: 1px solid rgba(255,255,255,.40) !important; }
html body .stApp [data-testid="stSidebar"] .stButton > button *,
html body .stApp [data-testid="stSidebar"] [data-testid^="stBaseButton"] * { color: #eaf5f1 !important; }
html body .stApp [data-testid="stSidebar"] [data-baseweb="checkbox"] > span:first-child { border-color: #b9d6cc !important; }
</style>
""", unsafe_allow_html=True)
