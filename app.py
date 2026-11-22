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


# ----------------------------- Backend ---------------------------------------
@st.cache_resource
def get_backend():
    """One backend (and one set of data structures) shared by every rerun and session.
    Uses the compiled C/C++ core when it has been built (python build.py), otherwise the
    pure-Python backend. See backend/engine.py."""
    return create_controller(DATA_FILE)


@st.cache_resource
def get_users():
    """The account list (shared by every session so the wrong-password counter is shared too)."""
    return UserStore(USERS_FILE)


ctl, engine_note = get_backend()
users = get_users()

if "page" not in st.session_state:
    st.session_state.page = "Overview"


# ----------------------------- Helpers ---------------------------------------
def esc(value):
    """Escape user text before placing it inside raw HTML (prevents HTML injection)."""
    return html.escape(str(value))


def hero(kicker, title, subtitle):
    st.markdown(
        f'<div class="hero"><div class="eyebrow">{kicker}</div><h1>{title}</h1><p>{subtitle}</p></div>',
        unsafe_allow_html=True,
    )


def metric(label, value, note, icon):
    st.markdown(
        f'<div class="metric"><div style="font-size:21px">{icon}</div>'
        f'<div class="metric-label">{label}</div><div class="metric-value">{value}</div>'
        f'<div class="metric-note">{note}</div></div>',
        unsafe_allow_html=True,
    )


def section_title(title, subtitle=None):
    st.markdown(f"### {title}")
    if subtitle:
        st.markdown(
            f'<div class="small-muted" style="margin-top:-10px;margin-bottom:15px">{subtitle}</div>',
            unsafe_allow_html=True,
        )


def df_table(rows):
    """Show a list of dicts as a table. Works on old and new Streamlit versions."""
    if not rows:
        st.caption("Nothing to show yet.")
        return
    try:
        st.dataframe(rows, width="stretch", hide_index=True)
    except TypeError:  # older Streamlit without width="stretch"
        st.dataframe(rows, use_container_width=True, hide_index=True)


def flash(message, kind="success"):
    """Keep a message across the st.rerun() that follows a successful action."""
    st.session_state.flash = (message, kind)


def show_flash():
    if "flash" in st.session_state:
        message, kind = st.session_state.pop("flash")
        getattr(st, kind)(message)


def form_key(name):
    """Forms get a new key after every successful action, which resets their fields.
    On a validation error the key is unchanged, so what the user typed is kept."""
    return f"{name}_{st.session_state.get('form_nonce', 0)}"


def run_action(action, success_message):
    """Call a controller method. Validation errors are shown; success flashes and reruns."""
    try:
        result = action()
    except ValueError as error:
        st.error(str(error))
        return
    st.session_state.form_nonce = st.session_state.get("form_nonce", 0) + 1
    flash(success_message(result))
    st.rerun()


def pretty_time(iso_text):
    try:
        moment = datetime.fromisoformat(iso_text)
    except (TypeError, ValueError):
        return str(iso_text)
    days_ago = (date.today() - moment.date()).days
    if days_ago == 0:
        return moment.strftime("%I:%M %p")
    if days_ago == 1:
        return "Yesterday"
    return moment.strftime("%d %b %Y")


def label_id(label):
    """'SC-1001 — Milo'  ->  'SC-1001'"""
    return label.split(" — ")[0]


def go_to(page_name):
    """Button callback. Callbacks run before the rerun, so they may set the radio's key."""
    st.session_state.page = page_name


def current_user():
    """Who is signed in? The role is read from the account file on EVERY run, never trusted from
    the browser session, so removing or demoting an account takes effect immediately."""
    info = st.session_state.get("auth")
    if not info:
        return None
    role = users.role_of(info.get("username"))
    if role is None:
        st.session_state.pop("auth", None)
        return None
    return {"username": info["username"], "role": role}


def sign_in(username):
    st.session_state.auth = {"username": username}
    st.session_state.page = "Overview"
    st.session_state.form_nonce = st.session_state.get("form_nonce", 0) + 1


def sign_out_callback():
    st.session_state.pop("auth", None)
    st.session_state.page = "Overview"
    flash("You have been signed out.", "info")


def login_screen():
    """Shown instead of the app until someone signs in. Ends the run with st.stop()."""
    hero("WELCOME", "Sign in to StrayCare",
         "Administrators can add, edit and delete records. Users can view everything and add new reports.")
    show_flash()
    _, middle, _ = st.columns([1, 1.6, 1])
    with middle:
        if not users.has_admin():
            section_title("Create the administrator account",
                          "No administrator exists yet. This first account controls everything else.")
            with st.form("setup_form"):
                admin_name = st.text_input("Admin username", placeholder="3-20 letters, numbers or _", max_chars=20)
                admin_pw = st.text_input("Admin password", type="password", max_chars=64)
                admin_pw2 = st.text_input("Confirm admin password", type="password", max_chars=64)
                create_admin = st.form_submit_button("Create administrator account", type="primary")
            if create_admin:
                try:
                    if admin_pw != admin_pw2:
                        raise ValueError("The two passwords do not match.")
                    account = users.add_user(admin_name, admin_pw, "admin")
                except ValueError as error:
                    st.error(str(error))
                else:
                    sign_in(account["Username"])
                    st.rerun()
        else:
            tab_in, tab_up = st.tabs(["Sign in", "Create user account"])
            with tab_in:
                with st.form("login_form"):
                    name = st.text_input("Username", max_chars=20)
                    password = st.text_input("Password", type="password", max_chars=64)
                    go = st.form_submit_button("Sign in", type="primary")
                if go:
                    try:
                        role = users.verify(name, password)
                    except ValueError as error:          # locked after too many wrong passwords
                        st.error(str(error))
                    else:
                        if role is None:
                            st.error("Wrong username or password.")
                        else:
                            sign_in(name.strip().lower())
                            st.rerun()
            with tab_up:
                st.caption("A new account is a normal user: it can view data and add new reports, but cannot edit or delete.")
                with st.form("signup_form"):
                    new_name = st.text_input("New username", placeholder="3-20 letters, numbers or _", max_chars=20)
                    new_pw = st.text_input("Choose a password", type="password", max_chars=64)
                    new_pw2 = st.text_input("Repeat the password", type="password", max_chars=64)
                    signup = st.form_submit_button("Create user account", type="primary")
                if signup:
                    try:
                        if new_pw != new_pw2:
                            raise ValueError("The two passwords do not match.")
                        account = users.add_user(new_name, new_pw, "user")
                    except ValueError as error:
                        st.error(str(error))
                    else:
                        flash(f"Account '{account['Username']}' created. You can sign in now.")
                        st.rerun()
    st.stop()


def restore_sample_callback():
    if not (current_user() or {}).get("role") == "admin":
        return
    get_backend()[0].reset_demo()
    st.session_state.confirm_restore = False
    flash("Sample records restored. Your earlier records were replaced.")


def erase_all_callback():
    if not (current_user() or {}).get("role") == "admin":
        return
    get_backend()[0].clear_all_data()
    st.session_state.confirm_erase = False
    flash("All records erased. You can start adding new ones.")


# ----------------------------- Sign-in gate ----------------------------------
user = current_user()
if user is None:
    login_screen()                      # never returns: it ends with st.stop()
is_admin = user["role"] == "admin"
visible_pages = PAGES + (ADMIN_ONLY_PAGES if is_admin else [])
if st.session_state.page not in visible_pages:
    st.session_state.page = "Overview"

# ----------------------------- Sidebar ---------------------------------------
with st.sidebar:
    st.markdown(
        "<div style='font-size:35px;margin:4px 0 0'>🐾</div>"
        "<div style='font-family:Manrope;font-weight:800;font-size:25px'>StrayCare</div>"
        "<div style='color:#a8c9bf;font-size:12px;margin-bottom:22px'>RESCUE • RECORD • RECONNECT</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        f"<div style='font-size:13px'>Signed in as <b>{esc(user['username'])}</b></div>"
        f"<div style='font-size:11px;color:#a8c9bf;margin-bottom:8px'>{'ADMINISTRATOR' if is_admin else 'USER'}</div>",
        unsafe_allow_html=True,
    )
    st.button("Sign out", on_click=sign_out_callback)
    st.markdown("---")
    st.radio("WORKSPACE", visible_pages, key="page")
    st.markdown("---")
    st.caption("Every change is saved automatically.")
    if is_admin:
        with st.expander("Data tools"):
            st.checkbox("Yes, replace all records with the sample set", key="confirm_restore")
            st.button("Restore sample data", on_click=restore_sample_callback,
                      disabled=not st.session_state.get("confirm_restore", False))
            st.checkbox("Yes, permanently erase every record", key="confirm_erase")
            st.button("Erase all records", on_click=erase_all_callback,
                      disabled=not st.session_state.get("confirm_erase", False))
    st.markdown("<div style='font-size:11px;color:#a8c9bf;margin-top:18px'>STRAYCARE © 2026</div>", unsafe_allow_html=True)

page = st.session_state.page

# ----------------------------- Pages -----------------------------------------
if page == "Overview":
    hero("COMMUNITY RESCUE NETWORK", "Every life deserves a chance.",
         "A single workspace to coordinate rescue reports, animal profiles, food donations and medical follow-ups.")
    show_flash()
    stats = ctl.stats()

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        metric("Registered animals", stats["animals"], "Animal profiles on record", "🐕")
    with c2:
        metric("Open emergencies", stats["open_emergencies"], "Need rescue coordination", "🚨")
    with c3:
        metric("Food offers", stats["active_food_offers"], "Active donation offers", "🥣")
    with c4:
        metric("Medical entries", stats["medical_entries"], "Treatment notes recorded", "🩺")
    st.write("")

    left, right = st.columns([1.35, 1])
    with left:
        section_title("Priority rescue cases", "Cases that need attention first")
        priority = ctl.priority_cases()
        if priority:
            df_table([{"Animal": a["Name"], "Location": a["Location"], "Urgency": a["Urgency"], "Status": a["Status"]}
                      for a in priority])
        else:
            st.success("No open priority cases right now.")
        st.button("＋ Report a rescue", type="primary", on_click=go_to, args=("Rescue & Triage",))
    with right:
        section_title("Recent activity", "Latest changes in the workspace")
        for item in ctl.recent_activity(8):
            st.markdown(
                f'<div style="border-left:3px solid #69b69b;padding:2px 0 12px 13px;margin-bottom:8px">'
                f'<div style="font-size:11px;color:#7b8e87">{esc(pretty_time(item["when"]))}</div>'
                f'<b>{esc(item["title"])}</b><div class="small-muted">{esc(item["detail"])}</div>'
                f'<span class="pill">{esc(item["status"])}</span></div>',
                unsafe_allow_html=True,
            )
    st.markdown("---")
    section_title("How StrayCare works")
    a, b, c = st.columns(3)
    with a:
        st.markdown('<div class="panel"><div style="font-size:27px">📍</div><b>1. Report</b><p class="small-muted">Record an animal sighting, location and condition.</p></div>', unsafe_allow_html=True)
    with b:
        st.markdown('<div class="panel"><div style="font-size:27px">⚡</div><b>2. Prioritize</b><p class="small-muted">A priority heap puts the most urgent case on top.</p></div>', unsafe_allow_html=True)
    with c:
        st.markdown('<div class="panel"><div style="font-size:27px">🤝</div><b>3. Coordinate care</b><p class="small-muted">Track donations, treatment and the shortest route to the animal.</p></div>', unsafe_allow_html=True)

elif page == "Animal Registry":
    hero("ANIMAL DIRECTORY", "Animal registry", "A searchable record of rescued animals and reported cases.")
    show_flash()
    search = st.text_input("Search by animal, ID, location or condition", placeholder="e.g. Milo, SC-1001, Clement Town", max_chars=60)
    species_filter = st.radio("Species", ["All"] + SPECIES, horizontal=True)
    rows = ctl.list_animals(search, species_filter)
    if rows:
        df_table(rows)
    else:
        st.info("No animals match your search.")

    st.markdown("---")
    section_title("Register an animal")
    with st.form(form_key("animal_form")):
        x1, x2, x3 = st.columns(3)
        with x1:
            name = st.text_input("Animal name / identifier", placeholder="e.g. Brown puppy", max_chars=60)
        with x2:
            sp = st.selectbox("Species", SPECIES)
        with x3:
            location = st.text_input("Location", placeholder="Area / landmark", max_chars=80)
        x4, x5, x6 = st.columns(3)
        with x4:
            condition = st.text_input("Observed condition", placeholder="e.g. Needs examination", max_chars=120)
        with x5:
            urgency = st.selectbox("Urgency", list(reversed(URGENCY_LEVELS)))
        with x6:
            status = st.selectbox("Case status", CASE_STATUSES)
        submitted = st.form_submit_button("Add animal profile", type="primary")
    if submitted:
        run_action(
            lambda: ctl.register_animal(name, sp, location, condition, urgency, status),
            lambda r: f"Added {r['Name']} with ID {r['ID']}.",
        )

    st.markdown("---")
    section_title("Edit or delete an animal", "Correct a profile, or remove a record entered by mistake")
    if is_admin:
        animal_choices = ctl.animal_choices()
        if not animal_choices:
            st.info("There are no animal records yet. Add one above.")
        else:
            picked = st.selectbox("Select animal", animal_choices, key=form_key("edit_pick"))
            picked_id = label_id(picked)
            record = ctl.get_animal(picked_id)
            if record:
                with st.form(form_key(f"edit_form_{picked_id}")):
                    e1, e2, e3 = st.columns(3)
                    with e1:
                        e_name = st.text_input("Animal name / identifier", value=record["Name"], max_chars=60)
                    with e2:
                        e_species = st.selectbox("Species", SPECIES,
                                                 index=SPECIES.index(record["Species"]) if record["Species"] in SPECIES else 0)
                    with e3:
                        e_location = st.text_input("Location", value=record["Location"], max_chars=80)
                    e4, e5 = st.columns(2)
                    with e4:
                        e_condition = st.text_input("Observed condition", value=record["Condition"], max_chars=120)
                    with e5:
                        levels = list(reversed(URGENCY_LEVELS))
                        e_urgency = st.selectbox("Urgency", levels,
                                                 index=levels.index(record["Urgency"]) if record["Urgency"] in levels else 0)
                    save_edit = st.form_submit_button("Save changes", type="primary")
                if save_edit:
                    run_action(
                        lambda: ctl.update_animal(picked_id, e_name, e_species, e_location, e_condition, e_urgency),
                        lambda r: f"Saved changes to {r['ID']} ({r['Name']}).",
                    )
                st.caption("To change the case status, use the 'Update case status' form on the Rescue & Triage page.")
                confirm_delete = st.checkbox(
                    f"Yes, delete {picked_id} and its medical notes permanently",
                    key=form_key(f"confirm_delete_{picked_id}"))
                if st.button("Delete animal record", disabled=not confirm_delete, key=form_key(f"delete_btn_{picked_id}")):
                    run_action(lambda: ctl.delete_animal(picked_id),
                               lambda r: f"Deleted {r['ID']} ({r['Name']}) and its medical notes.")
    else:
        st.info('Only administrators can edit or delete animal records. You can add new animals with the form above.')

elif page == "Rescue & Triage":
    hero("FIELD RESPONSE", "Rescue & triage", "Capture sightings, surface urgent cases and follow each case through its status.")
    show_flash()

    counts = ctl.urgency_counts()
    icons = {"Critical": "🚨", "High": "🔴", "Medium": "🟠", "Low": "🟢"}
    for col, level in zip(st.columns(4), URGENCY_LEVELS):
        with col:
            metric(f"{level} priority", counts[level], "Unresolved cases", icons[level])
    st.write("")

    top = ctl.most_urgent_case()
    if top:
        st.info(f"**Next case to handle:** {top['ID']} — {top['Name']} at {top['Location']} "
                f"({top['Urgency']}, {top['Status']})")
    df_table([{"ID": a["ID"], "Animal": a["Name"], "Location": a["Location"], "Condition": a["Condition"],
               "Urgency": a["Urgency"], "Status": a["Status"]} for a in ctl.triage_order()])

    section_title("Update case status")
    if is_admin:
        choices = ctl.animal_choices()
        with st.form(form_key("status_form")):
            case_label = st.selectbox("Select case", choices)
            new_status = st.selectbox("New status", CASE_STATUSES)
            note = st.text_input("Optional update note", max_chars=120)
            update = st.form_submit_button("Update case", type="primary")
        if update:
            if not choices:
                st.error("There are no cases to update yet.")
            else:
                run_action(
                    lambda: ctl.update_case_status(label_id(case_label), new_status, note),
                    lambda r: f"Case {r['ID']} updated to '{r['Status']}'.",
                )
    else:
        st.info('Only administrators can change a case status. You can report a new emergency below.')

    st.markdown("---")
    section_title("Report a new emergency")
    with st.form(form_key("rescue_form")):
        c1, c2 = st.columns(2)
        with c1:
            animal = st.text_input("Animal description", placeholder="e.g. Injured brown dog", max_chars=80)
        with c2:
            loc = st.text_input("Exact area / landmark", placeholder="e.g. Near bus stand", max_chars=80)
        c3, c4, c5 = st.columns(3)
        with c3:
            urgency = st.selectbox("Urgency level", URGENCY_LEVELS)
        with c4:
            sp = st.selectbox("Species", SPECIES, index=SPECIES.index("Unknown"))
        with c5:
            condition = st.text_input("Observed condition", max_chars=120)
        details = st.text_area("Additional details", placeholder="Only include information relevant to the rescue.", max_chars=500)
        report = st.form_submit_button("Submit rescue report", type="primary")
    if report:
        run_action(
            lambda: ctl.report_emergency(animal, loc, urgency, sp, condition, details),
            lambda r: f"Rescue report created: {r['ID']}",
        )

elif page == "Food Donations":
    hero("COMMUNITY FOOD NETWORK", "Food donations", "Connect safe surplus-food offers with shelters and community feeders.")
    show_flash()
    food = ctl.food_stats()

    c1, c2, c3 = st.columns(3)
    with c1:
        metric("Active offers", food["active"], "Not collected or cancelled", "🥣")
    with c2:
        metric("Servings listed", food["active_servings"], "Across active offers", "🍲")
    with c3:
        metric("Available", food["available"], "Ready for coordination", "📦")
    st.write("")

    nxt = ctl.next_pickup()
    if nxt:
        st.info(f"**Collect first (oldest active offer):** {nxt['Offer ID']} — {nxt['Donor']}, "
                f"{nxt['Food']} ({nxt['Servings']} servings) at {nxt['Pickup area']}")
    offers = ctl.list_food_offers()
    df_table(offers)

    section_title("Register a food offer")
    with st.form(form_key("food_form")):
        c1, c2 = st.columns(2)
        with c1:
            donor = st.text_input("Donor / organization", max_chars=80)
        with c2:
            food_name = st.text_input("Food description", placeholder="e.g. Plain rice, vegetables", max_chars=120)
        c3, c4 = st.columns(2)
        with c3:
            servings = st.number_input("Estimated servings", min_value=1, max_value=2000, value=10, step=1)
        with c4:
            pickup = st.text_input("Pickup area", placeholder="Area or landmark", max_chars=80)
        safety = st.checkbox("I have checked that the food is appropriate for animal consumption.")
        add_offer = st.form_submit_button("Add donation offer", type="primary")
    if add_offer:
        run_action(
            lambda: ctl.add_food_offer(donor, food_name, servings, pickup, safety),
            lambda r: f"Donation offer {r['Offer ID']} added.",
        )

    section_title("Manage an offer")
    if is_admin:
        if offers:
            chosen = st.selectbox("Offer", [o["Offer ID"] + " — " + o["Donor"] for o in offers])
            new_food_status = st.selectbox("Status", FOOD_STATUSES)
            if st.button("Save offer status"):
                run_action(
                    lambda: ctl.update_food_status(label_id(chosen), new_food_status),
                    lambda r: f"Offer {r['Offer ID']} set to '{r['Status']}'.",
                )
        else:
            st.info("No offers to manage yet.")
    else:
        st.info('Only administrators can change the status of an offer. You can add a new offer with the form above.')

    st.caption("Confirm food safety and suitability with a qualified shelter or veterinarian.")

elif page == "Medical Records":
    hero("CARE HISTORY", "Medical records", "Keep treatment notes organized and make follow-ups easier to track.")
    show_flash()
    choices = ctl.animal_choices()
    filter_label = st.selectbox("Show history for", ["All animals"] + choices)
    wanted = None if filter_label == "All animals" else label_id(filter_label)
    df_table(ctl.list_medical_entries(wanted))

    st.markdown("---")
    section_title("Add a medical entry")
    if not choices:
        st.info("Register an animal first, then you can add medical entries.")
    else:
        with st.form(form_key("medical_form")):
            c1, c2 = st.columns(2)
            with c1:
                selected = st.selectbox("Animal profile", choices)
            with c2:
                visit_date = st.date_input("Date of visit", value=date.today(), min_value=date(2020, 1, 1), max_value=date.today())
            c3, c4 = st.columns(2)
            with c3:
                treatment = st.text_input("Treatment / examination", placeholder="e.g. Veterinary assessment", max_chars=120)
            with c4:
                volunteer = st.text_input("Volunteer / care provider", max_chars=60)
            notes = st.text_area("Notes and follow-up", max_chars=500)
            save_log = st.form_submit_button("Save medical entry", type="primary")
        if save_log:
            run_action(
                lambda: ctl.add_medical_entry(label_id(selected), treatment, volunteer, visit_date, notes),
                lambda r: f"Medical entry saved for {r['Animal ID']}.",
            )
    st.info("These notes are for rescue coordination only. Follow a veterinarian's advice for treatment decisions.")

elif page == "Route Planner":
    hero("FIELD COORDINATION", "Route planner",
         "Shortest routes over a road map, calculated with Dijkstra's algorithm.")
    show_flash()
    st.caption("Distances come from the road map you maintain in the 'Road map' tab. "
               "Travel time is estimated from distance at a fixed average speed of 25 km/h.")
    locations = ctl.map_locations()
    unmapped = ctl.unmapped_locations()
    if unmapped:
        st.warning("These animal locations are not on the road map yet, so they cannot be routed: "
                   + ", ".join(unmapped) + ". Add a road to them in the 'Road map' tab.")

    tab_route, tab_tour, tab_map = st.tabs(["Shortest route", "Multi-stop tour", "Road map"])

    with tab_route:
        c1, c2 = st.columns(2)
        with c1:
            start = st.selectbox("Starting point", locations, key="route_start")
        with c2:
            destination = st.selectbox("Rescue destination", locations,
                                       index=1 if len(locations) > 1 else 0, key="route_dest")
        if st.button("Find shortest route", type="primary"):
            try:
                plan = ctl.plan_route(start, destination)
            except ValueError as error:
                st.error(str(error))
            else:
                m1, m2 = st.columns(2)
                with m1:
                    metric("Distance", f"{plan['km']:.1f} km", "Along the shortest road path", "📏")
                with m2:
                    metric("Estimated time", f"{plan['eta_minutes']} min", "Rough estimate, no traffic data", "⏱️")
                st.write("")
                st.markdown("**Route:** " + " → ".join(plan["path"]))

    with tab_tour:
        st.write("Pick the places to visit. The planner always drives to the nearest remaining stop (greedy nearest-neighbour).")
        tour_start = st.selectbox("Start from", locations, key="tour_start")
        stops = st.multiselect("Stops to visit", locations, default=ctl.open_case_locations())
        if st.button("Plan tour", type="primary"):
            try:
                plan = ctl.plan_multi_stop(tour_start, stops)
            except ValueError as error:
                st.error(str(error))
            else:
                m1, m2 = st.columns(2)
                with m1:
                    metric("Total distance", f"{plan['total_km']:.1f} km", f"{len(plan['legs'])} legs", "📏")
                with m2:
                    metric("Estimated time", f"{plan['eta_minutes']} min", "Driving only", "⏱️")
                st.write("")
                st.markdown("**Visit order:** " + " → ".join(plan["order"]))
                df_table([{"Leg": i + 1, "From": leg["from"], "To": leg["to"],
                           "Distance (km)": round(leg["km"], 1), "Via": " → ".join(leg["path"])}
                          for i, leg in enumerate(plan["legs"])])
                if plan["unreachable"]:
                    st.warning("No road connection to: " + ", ".join(plan["unreachable"]))

    with tab_map:
        df_table(ctl.road_list())
        if is_admin:
            section_title("Add or update a road", "Typing a new place name adds it to the map.")
            with st.form(form_key("road_form")):
                r1, r2, r3 = st.columns(3)
                with r1:
                    road_a = st.text_input("First location", placeholder="e.g. Clock Tower", max_chars=60)
                with r2:
                    road_b = st.text_input("Second location", placeholder="e.g. Rajpur Road", max_chars=60)
                with r3:
                    road_km = st.number_input("Distance (km)", min_value=0.1, max_value=200.0, value=2.0, step=0.5)
                add_road = st.form_submit_button("Save road", type="primary")
            if add_road:
                run_action(lambda: ctl.add_road(road_a, road_b, road_km),
                           lambda _: f"Road saved: {road_a.strip()} ↔ {road_b.strip()}")
        else:
            st.info('Only administrators can change the road map. Anyone can use it to plan routes.')

    st.markdown("---")
    section_title("Reported locations")
    df_table([{"Animal": a["Name"], "Location": a["Location"], "Urgency": a["Urgency"], "Status": a["Status"]}
              for a in ctl.list_animals()])

elif page == "User Management" and is_admin:
    hero("ADMINISTRATION", "User management", "Create accounts, reset passwords and remove accounts. Only administrators see this page.")
    show_flash()
    accounts = users.list_users()
    df_table(accounts)
    st.caption("Administrator: add, edit and delete records and manage accounts. User: view everything and add new reports only.")

    st.markdown("---")
    section_title("Create an account")
    with st.form(form_key("account_form")):
        a1, a2, a3 = st.columns(3)
        with a1:
            acc_name = st.text_input("Account username", placeholder="3-20 letters, numbers or _", max_chars=20)
        with a2:
            acc_pw = st.text_input("Account password", type="password", max_chars=64)
        with a3:
            acc_role = st.selectbox("Account role", ["user", "admin"])
        make_account = st.form_submit_button("Create account", type="primary")
    if make_account:
        run_action(lambda: users.add_user(acc_name, acc_pw, acc_role),
                   lambda r: f"Created {r['Role']} account '{r['Username']}'.")

    st.markdown("---")
    section_title("Reset a password")
    names = [a["Username"] for a in accounts]
    with st.form(form_key("reset_pw_form")):
        reset_who = st.selectbox("Reset password for", names)
        reset_pw = st.text_input("New password", type="password", max_chars=64)
        do_reset = st.form_submit_button("Reset password", type="primary")
    if do_reset:
        run_action(lambda: users.set_password(reset_who, reset_pw),
                   lambda _: f"Password changed for '{reset_who}'.")

    st.markdown("---")
    section_title("Delete an account")
    del_who = st.selectbox("Account to delete", names, key=form_key("delete_account_pick"))
    del_ok = st.checkbox(f"Yes, delete the account '{del_who}'", key=form_key(f"confirm_delete_account_{del_who}"))
    if st.button("Delete account", disabled=not del_ok, key=form_key("delete_account_btn")):
        if del_who == user["username"]:
            st.error("You cannot delete the account you are signed in with.")
        else:
            run_action(lambda: users.delete_user(del_who), lambda _: f"Deleted account '{del_who}'.")

else:  # About Project
    hero("PROJECT INFORMATION", "About StrayCare",
         "A Streamlit frontend on a C data-structure core, joined by a C++ controller (with a pure-Python fallback).")
    st.markdown("### The problem")
    st.write("Rescue reports, animal histories, food donations and follow-up information can become scattered across chats and individual records. StrayCare provides a shared workspace for organizing these activities.")
    st.markdown("### System architecture")
    df_table([
        {"Layer": "Python frontend (app.py)", "Responsibility": "Pages, forms, tables, flash messages", "Technique": "Streamlit reruns + session state"},
        {"Layer": "Python bridge (backend/native_bridge.py)", "Responsibility": "Calls the compiled library, saves data to JSON", "Technique": "ctypes + JSON"},
        {"Layer": "C++ integration (cpp_controller/integration.cpp)", "Responsibility": "Exposes the controller as 4 plain C functions", "Technique": "extern \"C\" + method table"},
        {"Layer": "C++ controller (cpp_controller/controller.cpp)", "Responsibility": "Validation, keeps all structures consistent, activity log", "Technique": "Facade class, RAII"},
        {"Layer": "C core: food_queue", "Responsibility": "Collect the oldest active donation first", "Technique": "Linked-list FIFO queue"},
        {"Layer": "C core: triage_heap", "Responsibility": "Most urgent rescue case first", "Technique": "Binary min-heap"},
        {"Layer": "C core: route_graph", "Responsibility": "Shortest road route and multi-stop tour", "Technique": "Weighted graph + Dijkstra"},
        {"Layer": "C core: animal_hash", "Responsibility": "Instant animal lookup by ID", "Technique": "Hash table with chaining"},
        {"Layer": "C core: medical_log", "Responsibility": "Chronological treatment history", "Technique": "Linked list with tail pointer"},
        {"Layer": "Sign-in (backend/auth.py)", "Responsibility": "Accounts, admin/user roles, salted password hashes", "Technique": "PBKDF2-SHA256 + role check on every run"},
        {"Layer": "Pure-Python backend (backend/*.py)", "Responsibility": "Same features, used if the C/C++ core is not built", "Technique": "Mirror of the C/C++ design"},
    ])
    st.caption(f"Running now on: {ctl.engine}")
    st.markdown("### Features")
    st.markdown("""
- Sign-in with two roles: administrators can add, edit and delete; users can view and add new reports.
- Names and places are validated (a name cannot be only numbers like 123).
- Register, edit and delete animal records; report emergencies; update case status.
- Food offers are collected oldest first; medical notes are kept in order for each animal.
- Shortest route and multi-stop tour over a road map you maintain; travel time is estimated at 25 km/h.
- Every change is saved automatically to `data/straycare.json` and reloaded at start-up.
- Search is case-insensitive for English letters only when running on the C++ engine.
""")
    st.markdown("### Future scope")
    st.markdown("""
- Password reset by e-mail and sign-in with a school or Google account.
- A real map display and live road data in place of the stored road map.
- A database server for many simultaneous users.
""")
    st.markdown("### Project folder")
    st.code(
        "straycare/\n"
        "├── app.py                    # Streamlit frontend\n"
        "├── build.py                  # compiles the C/C++ library\n"
        "├── c_core/                   # the five C data structures\n"
        "│   ├── include/*.h\n"
        "│   ├── src/*.c               # animal_hash, triage_heap, food_queue,\n"
        "│   │                         # medical_log, route_graph\n"
        "│   └── tests/test_c_core.c\n"
        "├── cpp_controller/           # C++ controller + integration\n"
        "│   ├── controller.hpp/.cpp   # StrayCareController\n"
        "│   ├── integration.cpp       # C interface for Python\n"
        "│   └── main.cpp              # console program + self-check\n"
        "├── backend/                  # Python side\n"
        "│   ├── native_bridge.py      # ctypes bridge to the library\n"
        "│   ├── engine.py             # picks C/C++ or Python backend\n"
        "│   ├── auth.py               # accounts, roles, password hashing\n"
        "│   └── controller.py ...     # pure-Python fallback\n"
        "├── build/                    # created by build.py\n"
        "├── tests/                    # Python tests\n"
        "└── data/straycare.json       # created on first run",
        language="text",
    )

st.markdown('<div style="text-align:center;color:#8a9a94;font-size:11px;padding:24px 0 5px">STRAYCARE • PYTHON + C++ + C</div>', unsafe_allow_html=True)
