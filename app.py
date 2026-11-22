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
