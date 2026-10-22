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

# ----------------------------- Pages -----------------------------------------
if page == "Overview":
    hero("COMMUNITY RESCUE NETWORK", "Every life deserves a chance.", "A single workspace to coordinate rescue reports, animal profiles, food donations and medical follow-ups.")
    animals = st.session_state.animals
    food = st.session_state.food_offers
    c1,c2,c3,c4 = st.columns(4)
    with c1: metric("Registered animals", len(animals), "Profiles in this demo", "🐕")
    with c2: metric("Open emergencies", sum(a["Status"]=="Awaiting rescue" for a in animals), "Need rescue coordination", "🚨")
    with c3: metric("Food offers", sum(f["Status"]!="Collected" for f in food), "Donation offers listed", "🥣")
    with c4: metric("Medical entries", len(st.session_state.medical_logs), "Treatment notes recorded", "🩺")
    st.write("")
    left,right = st.columns([1.35,1])
    with left:
        section_title("Priority rescue cases", "Cases that need attention first")
        priority = [a for a in animals if a["Status"] in ("Awaiting rescue","Under treatment")]
        priority.sort(key=lambda a: {"Critical":0,"High":1,"Medium":2,"Low":3}.get(a["Urgency"],4))
        if priority:
            df_table([{"Animal":a["Name"],"Location":a["Location"],"Urgency":a["Urgency"],"Status":a["Status"]} for a in priority])
        else: st.success("No open priority cases in the demo.")
        if st.button("＋ Report a rescue", type="primary"):
            st.session_state["page_jump"] = "Rescue & Triage"
            st.info("Choose **Rescue & Triage** from the sidebar to submit a report.")
    with right:
        section_title("Recent activity", "Latest changes in the workspace")
        for time_, title_, detail, status in st.session_state.activity:
            st.markdown(f'<div style="border-left:3px solid #69b69b;padding:2px 0 12px 13px;margin-bottom:8px"><div style="font-size:11px;color:#7b8e87">{time_}</div><b>{title_}</b><div class="small-muted">{detail}</div><span class="pill">{status}</span></div>', unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("---")
    section_title("How StrayCare works")
    a,b,c = st.columns(3)
    with a:
        st.markdown('<div class="panel"><div style="font-size:27px">📍</div><b>1. Report</b><p class="small-muted">Record an animal sighting, location and condition.</p></div>', unsafe_allow_html=True)
    with b:
        st.markdown('<div class="panel"><div style="font-size:27px">⚡</div><b>2. Prioritize</b><p class="small-muted">Highlight urgent cases for rescue coordination.</p></div>', unsafe_allow_html=True)
    with c:
        st.markdown('<div class="panel"><div style="font-size:27px">🤝</div><b>3. Coordinate care</b><p class="small-muted">Track donations, treatment and follow-ups.</p></div>', unsafe_allow_html=True)

elif page == "Animal Registry":
    hero("ANIMAL DIRECTORY", "Animal registry", "A searchable record of rescued animals and reported cases.")
    animals = st.session_state.animals
    search = st.text_input("Search by animal, ID, location or condition", placeholder="e.g. Milo, SC-1001, Clement Town")
    species = st.selectbox("Species", ["All","Dog","Cat","Other"], horizontal=True)
    filtered = [a for a in animals if (species=="All" or a["Species"]==species) and (not search or search.lower() in " ".join(str(v) for v in a.values()).lower())]
    df_table(filtered)
    st.markdown("---")
    section_title("Register an animal")
    with st.form("animal_form", clear_on_submit=True):
        x1,x2,x3 = st.columns(3)
        with x1: name = st.text_input("Animal name / identifier", placeholder="e.g. Brown puppy")
        with x2: sp = st.selectbox("Species", ["Dog","Cat","Bird","Other"])
        with x3: location = st.text_input("Location", placeholder="Area / landmark")
        x4,x5,x6 = st.columns(3)
        with x4: condition = st.text_input("Observed condition", placeholder="e.g. Needs examination")
        with x5: urgency = st.selectbox("Urgency", ["Low","Medium","High","Critical"])
        with x6: status = st.selectbox("Case status", ["Reported","Awaiting rescue","Rescued","Under treatment","Monitoring"])
        submitted = st.form_submit_button("Add animal profile", type="primary")
        if submitted:
            if name.strip() and location.strip():
                new_id = f"SC-{1001 + len(st.session_state.animals)}"
                st.session_state.animals.append({"ID":new_id,"Name":name.strip(),"Species":sp,"Location":location.strip(),"Condition":condition.strip() or "Not assessed","Status":status,"Urgency":urgency,"Reported":date.today().isoformat()})
                st.session_state.activity.insert(0,(datetime.now().strftime("%I:%M %p"),"Animal profile added",f"{new_id} • {name.strip()}","Created"))
                st.success(f"Added {name.strip()} with ID {new_id}.")
                st.rerun()
            else: st.error("Please enter at least an animal identifier and location.")

elif page == "Rescue & Triage":
    hero("FIELD RESPONSE", "Rescue & triage", "Capture sightings, surface urgent cases and follow each case through its status.")
    animals = st.session_state.animals
    counts = st.columns(4)
    for col, label, value in zip(counts,["Critical","High","Medium","Low"],[sum(a["Urgency"]==u and a["Status"]!="Rescued" for a in animals) for u in ["Critical","High","Medium","Low"]]):
        with col: metric(f"{label} priority", value, "Unresolved cases", {"Critical":"🚨","High":"🔴","Medium":"🟠","Low":"🟢"}[label])
    st.write("")
    ordered = sorted(animals, key=lambda a: {"Critical":0,"High":1,"Medium":2,"Low":3}.get(a["Urgency"],4))
    df_table([{"ID":a["ID"],"Animal":a["Name"],"Location":a["Location"],"Condition":a["Condition"],"Urgency":a["Urgency"],"Status":a["Status"]} for a in ordered])
    section_title("Update case status")
    with st.form("status_form"):
        case_id = st.selectbox("Select case", [a["ID"]+" — "+a["Name"] for a in animals])
        new_status = st.selectbox("New status", ["Reported","Awaiting rescue","Rescue assigned","Rescued","Under treatment","Monitoring","Closed"])
        note = st.text_input("Optional update note")
        update = st.form_submit_button("Update case", type="primary")
        if update:
            target = case_id.split(" — ")[0]
            for a in st.session_state.animals:
                if a["ID"] == target: a["Status"] = new_status
            st.session_state.activity.insert(0,(datetime.now().strftime("%I:%M %p"),"Rescue case updated",f"{target} • {note or new_status}",new_status))
            st.success("Case status updated in the demo.")
            st.rerun()
    st.markdown("---")
    section_title("Report a new emergency")
    with st.form("rescue_form", clear_on_submit=True):
        c1,c2 = st.columns(2)
        with c1: animal = st.text_input("Animal description", placeholder="e.g. Injured brown dog")
        with c2: loc = st.text_input("Exact area / landmark", placeholder="e.g. Near bus stand")
        c3,c4 = st.columns(2)
        with c3: urgency = st.selectbox("Urgency level", ["Critical","High","Medium","Low"])
        with c4: condition = st.text_input("Observed condition")
        details = st.text_area("Additional details", placeholder="Only include information relevant to the rescue.")
        report = st.form_submit_button("Submit rescue report", type="primary")
        if report:
            if animal.strip() and loc.strip():
                new_id = f"SC-{1001 + len(st.session_state.animals)}"
                st.session_state.animals.append({"ID":new_id,"Name":animal.strip(),"Species":"Unknown","Location":loc.strip(),"Condition":condition.strip() or details.strip() or "Assessment required","Status":"Awaiting rescue","Urgency":urgency,"Reported":date.today().isoformat()})
                st.session_state.activity.insert(0,(datetime.now().strftime("%I:%M %p"),"New emergency reported",f"{new_id} • {loc.strip()}",urgency))
                st.success(f"Demo rescue report created: {new_id}")
                st.rerun()
            else: st.error("Animal description and location are required.")

elif page == "Food Donations":
    hero("COMMUNITY FOOD NETWORK", "Food donations", "Connect safe surplus-food offers with shelters and community feeders.")
    offers = st.session_state.food_offers
    c1,c2,c3 = st.columns(3)
    with c1: metric("Total offers",len(offers),"All listed donations","🥣")
    with c2: metric("Servings listed",sum(int(o["Servings"]) for o in offers),"Across all offers","🍲")
    with c3: metric("Available",sum(o["Status"]=="Available" for o in offers),"Ready for coordination","📦")
    st.write("")
    df_table(offers)
    section_title("Register a food offer")
    with st.form("food_form", clear_on_submit=True):
        c1,c2 = st.columns(2)
        with c1: donor = st.text_input("Donor / organization")
        with c2: food_name = st.text_input("Food description", placeholder="e.g. Plain rice, vegetables")
        c3,c4 = st.columns(2)
        with c3: servings = st.number_input("Estimated servings", min_value=1, max_value=10000, value=10)
        with c4: pickup = st.text_input("Pickup area", placeholder="Area or landmark")
        safety = st.checkbox("I have checked that the food is appropriate for animal consumption.")
        add_offer = st.form_submit_button("Add donation offer", type="primary")
        if add_offer:
            if donor.strip() and food_name.strip() and pickup.strip() and safety:
                new_id = f"FD-{201 + len(st.session_state.food_offers)}"
                st.session_state.food_offers.append({"Offer ID":new_id,"Donor":donor.strip(),"Food":food_name.strip(),"Servings":int(servings),"Pickup area":pickup.strip(),"Status":"Available"})
                st.session_state.activity.insert(0,(datetime.now().strftime("%I:%M %p"),"Food donation listed",f"{new_id} • {donor.strip()}","Available"))
                st.success(f"Donation offer {new_id} added to the demo.")
                st.rerun()
            else: st.error("Complete all fields and confirm the food-safety check.")
    section_title("Manage an offer")
    if offers:
        chosen = st.selectbox("Offer", [o["Offer ID"]+" — "+o["Donor"] for o in offers])
        new_food_status = st.selectbox("Status", ["Available","Pickup pending","Collected","Cancelled"])
        if st.button("Save offer status"):
            target = chosen.split(" — ")[0]
            for o in st.session_state.food_offers:
                if o["Offer ID"] == target: o["Status"] = new_food_status
            st.success("Offer status updated.")
            st.rerun()
    st.caption("Demo interface only. Confirm food safety and suitability with a qualified shelter or veterinarian.")

elif page == "Medical Records":
    hero("CARE HISTORY", "Medical records", "Keep treatment notes organized and make follow-ups easier to track.")
    logs = st.session_state.medical_logs
    df_table(logs)
    st.markdown("---")
    section_title("Add a medical entry")
    animal_ids = [a["ID"]+" — "+a["Name"] for a in st.session_state.animals]
    with st.form("medical_form", clear_on_submit=True):
        c1,c2 = st.columns(2)
        with c1: selected = st.selectbox("Animal profile", animal_ids)
        with c2: visit_date = st.date_input("Date of visit", value=date.today())
        c3,c4 = st.columns(2)
        with c3: treatment = st.text_input("Treatment / examination", placeholder="e.g. Veterinary assessment")
        with c4: volunteer = st.text_input("Volunteer / care provider")
        notes = st.text_area("Notes and follow-up")
        save_log = st.form_submit_button("Save medical entry", type="primary")
        if save_log:
            if treatment.strip() and volunteer.strip():
                aid = selected.split(" — ")[0]
                st.session_state.medical_logs.insert(0,{"Date":visit_date.isoformat(),"Animal ID":aid,"Treatment":treatment.strip(),"Volunteer":volunteer.strip(),"Notes":notes.strip()})
                st.session_state.activity.insert(0,(datetime.now().strftime("%I:%M %p"),"Medical update recorded",f"{aid} • {treatment.strip()}","Updated"))
                st.success("Medical entry saved in this demo session.")
                st.rerun()
            else: st.error("Treatment and volunteer/care-provider fields are required.")
    st.info("This prototype stores data in the current Streamlit session only. It is not a medical record system for real clinical use.")

elif page == "Route Planner":
    hero("FIELD COORDINATION", "Route planner", "A frontend concept for coordinating visits and rescue locations.")
    st.markdown('<div class="panel"><div style="font-size:28px">🗺️</div><h3>Rescue route workspace</h3><p class="small-muted">The routing algorithm will be connected to the graph module in a later integration phase. This screen currently previews a route-planning workflow and does not calculate real routes.</p></div>', unsafe_allow_html=True)
    st.write("")
    locations = sorted(set(a["Location"] for a in st.session_state.animals))
    c1,c2 = st.columns(2)
    with c1: start = st.selectbox("Starting point", locations or ["Shelter / base"])
    with c2: destination = st.selectbox("Rescue destination", locations or ["Reported location"], index=min(1,len(locations)-1) if len(locations)>1 else 0)
    priority = st.selectbox("Route priority", ["Fastest response","Critical cases first","Visit multiple reports"])
    if st.button("Preview route plan", type="primary"):
        st.markdown("#### Proposed planning summary")
        st.write(f"**Start:** {start}")
        st.write(f"**Destination:** {destination}")
        st.write(f"**Planning preference:** {priority}")
        st.warning("Route preview only — no map, distance, ETA, or real-world navigation has been calculated.")
    st.markdown("---")
    section_title("Reported locations")
    df_table([{"Animal":a["Name"],"Location":a["Location"],"Urgency":a["Urgency"],"Status":a["Status"]} for a in st.session_state.animals])

else:
    hero("PROJECT INFORMATION", "About StrayCare", "A hybrid C/C++ backend concept with a Python frontend for coordinated stray-animal rescue management.")
    st.markdown("### The problem")
    st.write("Rescue reports, animal histories, food donations and follow-up information can become scattered across chats and individual records. StrayCare proposes a shared workspace for organizing these activities.")
    st.markdown("### Proposed system architecture")
    arch = [
        {"Layer":"Python frontend","Responsibility":"Dashboard, forms, tables and user interaction","Phase 2 demo":"Implemented in this file"},
        {"Layer":"C core — food_queue","Responsibility":"FIFO linked-list queue for food offers","Phase 2 demo":"Donation UI with sample/session data"},
        {"Layer":"C core — triage_heap","Responsibility":"Urgency-based rescue prioritization","Phase 2 demo":"Priority labels and sorted case view"},
        {"Layer":"C core — route_graph","Responsibility":"Represent locations and route paths","Phase 2 demo":"Route-planning screen mockup"},
        {"Layer":"C core — animal_hash","Responsibility":"Fast animal-profile lookup","Phase 2 demo":"Searchable animal registry"},
        {"Layer":"C core — medical_log","Responsibility":"Chronological medical history","Phase 2 demo":"Medical records table and form"},
        {"Layer":"C++ controller","Responsibility":"Expose backend functionality through APIs","Phase 2 demo":"Not connected in this UI-only prototype"},
    ]
    df_table(arch)
    st.markdown("### Scope of this prototype")
    st.markdown("""
- Demonstrates the intended user experience for Phase 2.
- Includes interactive navigation, searchable records, and forms.
- Uses fictional sample records and session-only state.
- Does **not** connect to C/C++ modules, a database, live maps, or a rescue service.
- Backend integration, persistent storage, authentication and real route calculation are future work.
""")
    st.markdown("### Suggested project folder")
    st.code("StrayCare/\n├── frontend/\n│   └── main.py          # This UI prototype\n├── backend/\n│   ├── c_core/           # Existing C data structures\n│   ├── cpp_controller/   # C++ API layer\n│   └── main.cpp\n└── tests/", language="text")

st.markdown('<div style="text-align:center;color:#8a9a94;font-size:11px;padding:24px 0 5px">STRAYCARE • PHASE 2 FRONTEND PROTOTYPE • DEMO DATA ONLY</div>', unsafe_allow_html=True)
