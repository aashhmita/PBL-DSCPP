"""StrayCareController: the single entry point the frontend talks to.

It owns one instance of every data structure, validates input, keeps the structures
consistent with each other, logs activity and saves everything to a JSON file.
(In the original design this was the C++ controller; here it is plain Python.)

Rules the frontend can rely on:
  * Mutating methods raise ValueError with a user-friendly message on bad input.
  * Returned records are copies, so the UI can never corrupt internal state by accident.
"""

import functools
import os
import threading
from datetime import date, datetime

from .animal_hash import AnimalHashTable
from .constants import (
    AVERAGE_SPEED_KMH, CASE_STATUSES, FOOD_INACTIVE_STATUSES, FOOD_STATUSES,
    OPEN_EMERGENCY_STATUSES, PRIORITY_STATUSES, RESOLVED_STATUSES, SPECIES,
    URGENCY_LEVELS,
)
from .food_queue import FoodQueue
from .medical_log import MedicalLog
from .route_graph import RouteGraph
from .storage import load_json, save_json
from .triage_heap import TriageHeap

MAX_ACTIVITY = 200
MAX_TEXT = 200
MAX_NOTES = 1000


def _mutator(method):
    """Lock, run, then save to disk. If the method raises, nothing is saved."""
    @functools.wraps(method)
    def wrapper(self, *args, **kwargs):
        with self._lock:
            result = method(self, *args, **kwargs)
            self._save()
            return result
    return wrapper


def _reader(method):
    @functools.wraps(method)
    def wrapper(self, *args, **kwargs):
        with self._lock:
            return method(self, *args, **kwargs)
    return wrapper


def _clean(value, field, required=True, max_len=MAX_TEXT):
    text = str(value if value is not None else "").strip()
    if required and not text:
        raise ValueError(f"{field} is required.")
    if len(text) > max_len:
        raise ValueError(f"{field} is too long (maximum {max_len} characters).")
    return text


def _choice(value, allowed, field):
    if value not in allowed:
        raise ValueError(f"{field} must be one of: {', '.join(allowed)}.")
    return value


def _id_number(record_id):
    try:
        return int(str(record_id).split("-")[-1])
    except ValueError:
        return 0


class StrayCareController:
    engine = "Pure-Python backend"

    def __init__(self, data_path=None, seed_demo=True):
        self._lock = threading.RLock()
        self._path = data_path
        self._seed_demo = seed_demo
        self._reset_structures()
        loaded = False
        if self._path:
            try:
                data = load_json(self._path)
                if data is not None:
                    self._from_dict(data)
                    loaded = True
            except (OSError, ValueError, KeyError, TypeError):
                self._quarantine_corrupt_file()
                self._reset_structures()
        if not loaded:
            if seed_demo:
                self._load_demo_data()
            self._save()

    # ======================= internal state =======================================
    def _reset_structures(self):
        self._animals = AnimalHashTable()        # hash table: ID -> animal record
        self._food_offers = []                   # master list (history of every offer)
        self._food_queue = FoodQueue()           # linked-list queue: only ACTIVE offers
        self._medical = MedicalLog()             # linked list: chronological history
        self._graph = RouteGraph()               # weighted graph: roads between locations
        self._activity = []                      # newest first
        self._next_animal_no = 1001
        self._next_food_no = 201

    def _quarantine_corrupt_file(self):
        try:
            os.replace(self._path, self._path + ".corrupt")
        except OSError:
            pass

    def _load_demo_data(self):
        animals = [
            {"ID": "SC-1001", "Name": "Milo", "Species": "Dog", "Location": "Clement Town", "Condition": "Injured leg", "Status": "Under treatment", "Urgency": "High", "Reported": "2026-10-21"},
            {"ID": "SC-1002", "Name": "Luna", "Species": "Cat", "Location": "Sahastradhara Road", "Condition": "Dehydration", "Status": "Rescued", "Urgency": "Medium", "Reported": "2026-10-20"},
            {"ID": "SC-1003", "Name": "Brownie", "Species": "Dog", "Location": "Prem Nagar", "Condition": "Healthy / vaccination due", "Status": "Monitoring", "Urgency": "Low", "Reported": "2026-10-19"},
            {"ID": "SC-1004", "Name": "Unknown puppy", "Species": "Dog", "Location": "ISBT Dehradun", "Condition": "Roadside emergency", "Status": "Awaiting rescue", "Urgency": "Critical", "Reported": "2026-10-22"},
        ]
        for animal in animals:
            self._animals.put(animal["ID"], animal)
        self._next_animal_no = 1005

        offers = [
            {"Offer ID": "FD-201", "Donor": "Green Bowl Cafe", "Food": "Plain rice and vegetables", "Servings": 18, "Pickup area": "Clock Tower", "Status": "Available"},
            {"Offer ID": "FD-202", "Donor": "Campus Canteen", "Food": "Unseasoned leftovers", "Servings": 12, "Pickup area": "GEU", "Status": "Pickup pending"},
            {"Offer ID": "FD-203", "Donor": "Community Kitchen", "Food": "Rice", "Servings": 25, "Pickup area": "Clement Town", "Status": "Available"},
        ]
        for offer in offers:
            self._food_offers.append(offer)
            self._food_queue.enqueue(offer)
        self._next_food_no = 204

        for entry in (
            {"Date": "2026-10-20", "Animal ID": "SC-1002", "Treatment": "Fluids and observation", "Volunteer": "Meera", "Notes": "Condition improving"},
            {"Date": "2026-10-21", "Animal ID": "SC-1001", "Treatment": "Initial examination", "Volunteer": "Aarav", "Notes": "Needs follow-up assessment"},
        ):
            self._medical.append(entry)

        # Starting road distances in km (sample values, not surveyed);
        # edit them from the Route Planner page to match your real map.
        for a, b, km in (
            ("Shelter (Base)", "Clock Tower", 3.0),
            ("Clock Tower", "ISBT Dehradun", 3.5),
            ("Clock Tower", "Prem Nagar", 6.0),
            ("Clock Tower", "Sahastradhara Road", 8.0),
            ("ISBT Dehradun", "Clement Town", 7.5),
            ("ISBT Dehradun", "GEU", 6.5),
            ("Prem Nagar", "GEU", 4.0),
            ("Prem Nagar", "Clement Town", 5.5),
        ):
            self._graph.add_road(a, b, km)

        self._activity = [
            {"when": "2026-10-22T09:15:00", "title": "New emergency reported", "detail": "SC-1004 • ISBT Dehradun", "status": "Critical"},
            {"when": "2026-10-21T17:40:00", "title": "Medical update recorded", "detail": "SC-1001 • Milo", "status": "Updated"},
            {"when": "2026-10-21T12:05:00", "title": "Food donation listed", "detail": "FD-203 • Community Kitchen", "status": "Available"},
        ]

    # ======================= persistence ==========================================
    def _to_dict(self):
        return {
            "animals": sorted(self._animals.values(), key=lambda a: _id_number(a["ID"])),
            "food_offers": self._food_offers,
            "medical_logs": self._medical.to_list(newest_first=False),
            "activity": self._activity,
            "roads": [list(road) for road in self._graph.roads()],
            "next_animal_no": self._next_animal_no,
            "next_food_no": self._next_food_no,
        }

    def _from_dict(self, data):
        """Rebuild every data structure from saved records."""
        self._reset_structures()
        for animal in data["animals"]:
            self._animals.put(animal["ID"], animal)
        for offer in data["food_offers"]:
            self._food_offers.append(offer)
            if offer["Status"] not in FOOD_INACTIVE_STATUSES:
                self._food_queue.enqueue(offer)
        for entry in data["medical_logs"]:
            self._medical.append(entry)
        for a, b, km in data["roads"]:
            self._graph.add_road(a, b, km)
        self._activity = list(data["activity"])
        self._next_animal_no = int(data["next_animal_no"])
        self._next_food_no = int(data["next_food_no"])

    def _save(self):
        if self._path:
            save_json(self._path, self._to_dict())

    def _log(self, title, detail, status):
        self._activity.insert(0, {
            "when": datetime.now().isoformat(timespec="seconds"),
            "title": title, "detail": detail, "status": status,
        })
        del self._activity[MAX_ACTIVITY:]

    @_mutator
    def reset_demo(self):
        self._reset_structures()
        if self._seed_demo:
            self._load_demo_data()

    @_mutator
    def clear_all_data(self):
        """Erase every record (animals, offers, history, activity) but keep the road map empty too."""
        self._reset_structures()

    # ======================= animals ==============================================
    def _new_animal_id(self):
        new_id = f"SC-{self._next_animal_no}"
        self._next_animal_no += 1
        return new_id

    @_mutator
    def register_animal(self, name, species, location, condition="", urgency="Low", status="Reported"):
        # Validate everything FIRST, so a rejected form never uses up an ID number.
        name = _clean(name, "Animal name / identifier")
        location = _clean(location, "Location")
        condition = _clean(condition, "Condition", required=False) or "Not assessed"
        _choice(species, SPECIES, "Species")
        _choice(status, CASE_STATUSES, "Status")
        _choice(urgency, URGENCY_LEVELS, "Urgency")
        record = {
            "ID": self._new_animal_id(), "Name": name, "Species": species,
            "Location": location, "Condition": condition, "Status": status,
            "Urgency": urgency, "Reported": date.today().isoformat(),
        }
        self._animals.put(record["ID"], record)
        self._log("Animal profile added", f"{record['ID']} • {record['Name']}", "Created")
        return dict(record)

    @_mutator
    def report_emergency(self, description, location, urgency="Critical", species="Unknown",
                         condition="", details=""):
        description = _clean(description, "Animal description")
        location = _clean(location, "Location")
        _choice(urgency, URGENCY_LEVELS, "Urgency")
        _choice(species, SPECIES, "Species")
        condition = (_clean(condition, "Condition", required=False)
                     or _clean(details, "Details", required=False, max_len=MAX_NOTES)
                     or "Assessment required")
        record = {
            "ID": self._new_animal_id(), "Name": description, "Species": species,
            "Location": location, "Condition": condition, "Status": "Awaiting rescue",
            "Urgency": urgency, "Reported": date.today().isoformat(),
        }
        self._animals.put(record["ID"], record)
        self._log("New emergency reported", f"{record['ID']} • {location}", urgency)
        return dict(record)

    @_mutator
    def update_case_status(self, animal_id, new_status, note=""):
        animal = self._animals.get(animal_id)         # O(1) hash lookup
        if animal is None:
            raise ValueError(f"No animal with ID {animal_id}.")
        _choice(new_status, CASE_STATUSES, "Status")
        note = _clean(note, "Note", required=False)
        animal["Status"] = new_status
        self._log("Rescue case updated", f"{animal_id} • {note or new_status}", new_status)
        return dict(animal)

    @_mutator
    def update_animal(self, animal_id, name, species, location, condition="", urgency="Low"):
        animal = self._animals.get(animal_id)
        if animal is None:
            raise ValueError(f"No animal with ID {animal_id}.")
        # Validate everything first: a rejected edit must change nothing.
        name = _clean(name, "Animal name / identifier")
        location = _clean(location, "Location")
        condition = _clean(condition, "Condition", required=False) or "Not assessed"
        _choice(species, SPECIES, "Species")
        _choice(urgency, URGENCY_LEVELS, "Urgency")
        animal.update(Name=name, Species=species, Location=location,
                      Condition=condition, Urgency=urgency)
        self._log("Animal profile edited", f"{animal_id} • {name}", "Updated")
        return dict(animal)

    @_mutator
    def delete_animal(self, animal_id):
        animal = self._animals.get(animal_id)
        if animal is None:
            raise ValueError(f"No animal with ID {animal_id}.")
        removed = dict(animal)
        self._animals.remove(animal_id)
        self._medical.remove_animal(animal_id)     # no orphan history
        self._log("Animal record deleted", f"{animal_id} • {removed['Name']}", "Deleted")
        return removed

    @_reader
    def get_animal(self, animal_id):
        animal = self._animals.get(animal_id)
        return dict(animal) if animal else None

    @_reader
    def list_animals(self, search="", species="All"):
        needle = search.strip().lower()
        rows = []
        for animal in self._animals.values():
            if species != "All" and animal["Species"] != species:
                continue
            if needle and needle not in " ".join(str(v) for v in animal.values()).lower():
                continue
            rows.append(dict(animal))
        rows.sort(key=lambda a: _id_number(a["ID"]))
        return rows

    @_reader
    def animal_choices(self):
        """Labels like 'SC-1001 — Milo' for dropdowns, oldest ID first."""
        return [f"{a['ID']} — {a['Name']}" for a in self.list_animals()]

    # ======================= triage (heap) ========================================
    @_reader
    def triage_order(self):
        """Unresolved cases most-urgent-first, then resolved cases most-urgent-first."""
        animals = self._animals.values()
        by_id = {a["ID"]: a for a in animals}
        unresolved = TriageHeap(a for a in animals if a["Status"] not in RESOLVED_STATUSES)
        resolved = TriageHeap(a for a in animals if a["Status"] in RESOLVED_STATUSES)
        return [dict(by_id[i]) for i in unresolved.ordered_ids() + resolved.ordered_ids()]

    @_reader
    def priority_cases(self):
        """Cases that need action now (awaiting / assigned / under treatment), most urgent first."""
        selected = [a for a in self._animals.values() if a["Status"] in PRIORITY_STATUSES]
        by_id = {a["ID"]: a for a in selected}
        return [dict(by_id[i]) for i in TriageHeap(selected).ordered_ids()]

    @_reader
    def most_urgent_case(self):
        """Peek at the top of the heap of unresolved cases: O(1) after the heap is built."""
        unresolved = [a for a in self._animals.values() if a["Status"] not in RESOLVED_STATUSES]
        if not unresolved:
            return None
        heap = TriageHeap(unresolved)
        return dict(self._animals.get(heap.peek_case()))

    @_reader
    def urgency_counts(self):
        counts = {level: 0 for level in URGENCY_LEVELS}
        for animal in self._animals.values():
            if animal["Status"] not in RESOLVED_STATUSES:
                counts[animal["Urgency"]] += 1
        return counts

    # ======================= food donations (queue) ===============================
    @_mutator
    def add_food_offer(self, donor, food, servings, pickup_area, safety_confirmed):
        donor = _clean(donor, "Donor / organization")
        food = _clean(food, "Food description")
        pickup_area = _clean(pickup_area, "Pickup area")
        try:
            servings = int(servings)
        except (TypeError, ValueError):
            raise ValueError("Servings must be a whole number.")
        if not 1 <= servings <= 10000:
            raise ValueError("Servings must be between 1 and 10,000.")
        if not safety_confirmed:
            raise ValueError("Please confirm the food-safety check before listing the offer.")
        offer = {
            "Offer ID": f"FD-{self._next_food_no}", "Donor": donor, "Food": food,
            "Servings": servings, "Pickup area": pickup_area, "Status": "Available",
        }
        self._next_food_no += 1
        self._food_offers.append(offer)
        self._food_queue.enqueue(offer)
        self._log("Food donation listed", f"{offer['Offer ID']} • {donor}", "Available")
        return dict(offer)

    @_mutator
    def update_food_status(self, offer_id, new_status):
        _choice(new_status, FOOD_STATUSES, "Status")
        offer = next((o for o in self._food_offers if o["Offer ID"] == offer_id), None)
        if offer is None:
            raise ValueError(f"No food offer with ID {offer_id}.")
        was_active = offer["Status"] not in FOOD_INACTIVE_STATUSES
        offer["Status"] = new_status
        is_active = new_status not in FOOD_INACTIVE_STATUSES
        if was_active and not is_active:
            self._food_queue.remove(offer_id)         # collected / cancelled -> leaves the queue
        elif is_active and not was_active:
            self._food_queue.enqueue(offer)           # re-activated -> rejoins at the back
        self._log("Food offer updated", f"{offer_id} • {new_status}", new_status)
        return dict(offer)

    @_reader
    def list_food_offers(self):
        return [dict(o) for o in self._food_offers]

    @_reader
    def next_pickup(self):
        """The oldest active offer: the one to collect first (queue head)."""
        offer = self._food_queue.peek()
        return dict(offer) if offer else None

    @_reader
    def food_stats(self):
        active = self._food_queue.to_list()
        return {
            "total": len(self._food_offers),
            "active": len(active),
            "active_servings": sum(o["Servings"] for o in active),
            "available": sum(o["Status"] == "Available" for o in self._food_offers),
        }

    # ======================= medical log (linked list) ============================
    @_mutator
    def add_medical_entry(self, animal_id, treatment, volunteer, visit_date, notes=""):
        if self._animals.get(animal_id) is None:
            raise ValueError(f"No animal with ID {animal_id}.")
        if isinstance(visit_date, datetime):
            visit_date = visit_date.date()
        if isinstance(visit_date, str):
            try:
                visit_date = date.fromisoformat(visit_date)
            except ValueError:
                raise ValueError("Visit date must look like 2026-10-22.")
        if not isinstance(visit_date, date):
            raise ValueError("Visit date is required.")
        if visit_date > date.today():
            raise ValueError("Visit date cannot be in the future.")
        entry = {
            "Date": visit_date.isoformat(), "Animal ID": animal_id,
            "Treatment": _clean(treatment, "Treatment / examination"),
            "Volunteer": _clean(volunteer, "Volunteer / care provider"),
            "Notes": _clean(notes, "Notes", required=False, max_len=MAX_NOTES),
        }
        self._medical.append(entry)
        self._log("Medical update recorded", f"{animal_id} • {entry['Treatment']}", "Updated")
        return dict(entry)

    @_reader
    def list_medical_entries(self, animal_id=None):
        entries = self._medical.for_animal(animal_id) if animal_id else self._medical.to_list()
        return [dict(e) for e in entries]

    # ======================= routes (graph) =======================================
    @_reader
    def map_locations(self):
        return self._graph.locations()

    @_reader
    def road_list(self):
        return [{"From": a, "To": b, "Distance (km)": km} for a, b, km in self._graph.roads()]

    @_reader
    def unmapped_locations(self):
        """Animal locations that are not on the road map yet (so no route can be planned)."""
        return sorted({a["Location"] for a in self._animals.values()
                       if not self._graph.has_location(a["Location"])})

    @_reader
    def open_case_locations(self):
        """Mapped locations that currently have an open emergency."""
        return sorted({a["Location"] for a in self._animals.values()
                       if a["Status"] in OPEN_EMERGENCY_STATUSES
                       and self._graph.has_location(a["Location"])})

    @staticmethod
    def _eta_minutes(km):
        return round(km / AVERAGE_SPEED_KMH * 60)

    @_reader
    def plan_route(self, start, destination):
        if start == destination:
            raise ValueError("Start and destination are the same. Please choose different locations.")
        result = self._graph.shortest_path(start, destination)
        if result is None:
            raise ValueError("No connected road between those two locations.")
        km, path = result
        return {"km": km, "eta_minutes": self._eta_minutes(km), "path": path}

    @_reader
    def plan_multi_stop(self, start, stops):
        if not stops:
            raise ValueError("Choose at least one stop.")
        plan = self._graph.tour(start, stops)
        plan["eta_minutes"] = self._eta_minutes(plan["total_km"])
        return plan

    @_mutator
    def add_road(self, a, b, km):
        a, b = _clean(a, "First location"), _clean(b, "Second location")
        try:
            km = float(km)
        except (TypeError, ValueError):
            raise ValueError("Distance must be a number.")
        self._graph.add_road(a, b, km)          # raises ValueError if a == b or km <= 0
        self._log("Road map updated", f"{a} ↔ {b} • {km:g} km", "Updated")

    # ======================= dashboard ============================================
    @_reader
    def recent_activity(self, limit=8):
        return [dict(item) for item in self._activity[:limit]]

    @_reader
    def stats(self):
        animals = self._animals.values()
        return {
            "animals": len(animals),
            "open_emergencies": sum(a["Status"] in OPEN_EMERGENCY_STATUSES for a in animals),
            "active_food_offers": len(self._food_queue),
            "medical_entries": len(self._medical),
        }
