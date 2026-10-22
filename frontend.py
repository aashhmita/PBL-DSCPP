import streamlit as st
from datetime import date, datetime
import pandas as pd

st.set_page_config(
    page_title="StrayCare | Rescue Management",
    page_icon="🐾",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ----------------------------- Theme -----------------------------------------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Manrope:wght@400;500;600;700;800&display=swap');
html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }
.stApp { background: #f4f7f6; color: #172b2a; }
[data-testid="stSidebar"] { background: #102d2b; }
[data-testid="stSidebar"] * { color: #eaf5f1 !important; }
[data-testid="stSidebar"] [data-testid="stRadio"] label { padding: 7px 10px; border-radius: 9px; }
h1, h2, h3 { font-family: 'Manrope', sans-serif; letter-spacing: -0.5px; }
.hero { background: linear-gradient(120deg,#123d38,#1b6255); padding: 27px 30px; border-radius: 18px; color: white; margin-bottom: 18px; }
.hero h1 { color: white; font-size: 31px; margin: 0 0 7px 0; }
.hero p { color: #d2e9e2; margin: 0; font-size: 14px; }
.eyebrow { color: #a6d9c8; font-size: 11px; font-weight: 800; letter-spacing: 2px; text-transform: uppercase; margin-bottom: 9px; }
.metric { background: white; border: 1px solid #e2ebe7; border-radius: 15px; padding: 17px 18px; min-height: 120px; }
.metric-label { color: #71817c; font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: .7px; }
.metric-value { color: #163b35; font-family: 'Manrope',sans-serif; font-size: 30px; font-weight: 800; margin: 7px 0 2px; }
.metric-note { color: #7a8c85; font-size: 12px; }
.panel { background: white; border: 1px solid #e2ebe7; border-radius: 15px; padding: 20px; }
.small-muted { color: #71817c; font-size: 13px; }
.pill { display:inline-block; padding:4px 9px; border-radius:99px; font-size:11px; font-weight:700; background:#e4f4ec; color:#176448; }
div[data-testid="stForm"] { background:white; border:1px solid #e2ebe7; padding:20px; border-radius:15px; }
.stButton > button[kind="primary"], .stFormSubmitButton > button { background:#17695a; border-color:#17695a; border-radius:9px; }
hr { border-color:#e1eae6; }
</style>
""", unsafe_allow_html=True)

# ----------------------------- Demo data -------------------------------------
if "animals" not in st.session_state:
    st.session_state.animals = [
        {"ID":"SC-1001","Name":"Milo","Species":"Dog","Location":"Clement Town, Dehradun","Condition":"Injured leg","Status":"Under treatment","Urgency":"High","Reported":"2026-10-21"},
        {"ID":"SC-1002","Name":"Luna","Species":"Cat","Location":"Sahastradhara Road","Condition":"Dehydration","Status":"Rescued","Urgency":"Medium","Reported":"2026-10-20"},
        {"ID":"SC-1003","Name":"Brownie","Species":"Dog","Location":"Prem Nagar","Condition":"Healthy / vaccination due","Status":"Monitoring","Urgency":"Low","Reported":"2026-10-19"},
        {"ID":"SC-1004","Name":"Unknown puppy","Species":"Dog","Location":"ISBT Dehradun","Condition":"Roadside emergency","Status":"Awaiting rescue","Urgency":"Critical","Reported":"2026-10-22"},
    ]
if "food_offers" not in st.session_state:
    st.session_state.food_offers = [
        {"Offer ID":"FD-201","Donor":"Green Bowl Cafe","Food":"Plain rice and vegetables","Servings":18,"Pickup area":"Clock Tower","Status":"Available"},
        {"Offer ID":"FD-202","Donor":"Campus Canteen","Food":"Unseasoned leftovers","Servings":12,"Pickup area":"GEU","Status":"Pickup pending"},
        {"Offer ID":"FD-203","Donor":"Community Kitchen","Food":"Rice","Servings":25,"Pickup area":"Clement Town","Status":"Available"},
    ]
if "medical_logs" not in st.session_state:
    st.session_state.medical_logs = [
        {"Date":"2026-10-21","Animal ID":"SC-1001","Treatment":"Initial examination","Volunteer":"Aarav","Notes":"Needs follow-up assessment"},
        {"Date":"2026-10-20","Animal ID":"SC-1002","Treatment":"Fluids and observation","Volunteer":"Meera","Notes":"Condition improving"},
    ]
if "activity" not in st.session_state:
    st.session_state.activity = [
        ("09:15 AM","New emergency reported","SC-1004 • ISBT Dehradun","Critical"),
        ("Yesterday","Medical update recorded","SC-1001 • Milo","Updated"),
        ("Yesterday","Food donation listed","FD-203 • Community Kitchen","Available"),
    ]

# ----------------------------- Sidebar ---------------------------------------
with st.sidebar:
    st.markdown("<div style='font-size:35px;margin:4px 0 0'>🐾</div><div style='font-family:Manrope;font-weight:800;font-size:25px'>StrayCare</div><div style='color:#a8c9bf;font-size:12px;margin-bottom:22px'>RESCUE • RECORD • RECONNECT</div>", unsafe_allow_html=True)
    st.markdown("---")
    page = st.radio("WORKSPACE", [
        "Overview", "Animal Registry", "Rescue & Triage",
        "Food Donations", "Medical Records", "Route Planner", "About Project"
    ], label_visibility="visible")
    st.markdown("---")
    st.markdown("**Phase 2 · UI Prototype**")
    st.caption("Demonstration data only. No live rescue service is connected.")
    st.markdown("<div style='font-size:11px;color:#a8c9bf;margin-top:18px'>STRAYCARE © 2026</div>", unsafe_allow_html=True)

# ----------------------------- Helpers ---------------------------------------
def hero(kicker, title, subtitle):
    st.markdown(f'<div class="hero"><div class="eyebrow">{kicker}</div><h1>{title}</h1><p>{subtitle}</p></div>', unsafe_allow_html=True)

def metric(label, value, note, icon):
    st.markdown(f'<div class="metric"><div style="font-size:21px">{icon}</div><div class="metric-label">{label}</div><div class="metric-value">{value}</div><div class="metric-note">{note}</div></div>', unsafe_allow_html=True)

def section_title(title, subtitle=None):
    st.markdown(f"### {title}")
    if subtitle:
        st.markdown(f'<div class="small-muted" style="margin-top:-10px;margin-bottom:15px">{subtitle}</div>', unsafe_allow_html=True)

def df_table(rows, use_container_width=True):
    st.dataframe(pd.DataFrame(rows), use_container_width=use_container_width, hide_index=True)


st.markdown('<div style="text-align:center;color:#8a9a94;font-size:11px;padding:24px 0 5px">STRAYCARE • PHASE 2 FRONTEND PROTOTYPE • DEMO DATA ONLY</div>', unsafe_allow_html=True)
