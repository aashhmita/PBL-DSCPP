"""Bridge from Python to the compiled C/C++ backend (the shared library built by build.py).

NativeStrayCareController has exactly the same methods as the pure-Python StrayCareController,
so the Streamlit app does not know (or care) which one it is talking to.

How a call travels:

    Streamlit page  ->  NativeStrayCareController.register_animal(...)
        ->  ctypes calls the C function  sc_invoke(handle, "register_animal", args...)
        ->  C++ integration layer finds the method and calls the C++ controller
        ->  the controller validates, then uses the C data structures (hash, heap, queue ...)
        <-  the result comes back as JSON text, which Python turns into dicts and lists

Saving: the C++ side keeps everything in memory. After every change this bridge asks it for
its full state ("export_state"), and writes that to the JSON file. When the app starts, the
saved records are fed back in with the "restore_*" calls.
"""

import ctypes
import json
import os
import sys
import threading
from datetime import date, datetime

from .storage import load_json, save_json


class NativeUnavailable(RuntimeError):
    """The compiled library is missing or could not be loaded."""


def library_file_name():
    if sys.platform.startswith("win"):
        return "straycare.dll"
    if sys.platform == "darwin":
        return "libstraycare.dylib"
    return "libstraycare.so"


def default_library_path():
    override = os.environ.get("STRAYCARE_LIB")
    if override:
        return override
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(project_root, "build", library_file_name())


def load_library(path=None):
    path = path or default_library_path()
    if not os.path.exists(path):
        raise NativeUnavailable(
            f"Native library not found at {path}. Build it first with:  python build.py"
        )
    try:
        lib = ctypes.CDLL(path)
    except OSError as error:
        raise NativeUnavailable(
            f"Could not load {path} ({error}). Rebuild it with:  python build.py "
            "(on Windows the compiler must be 64-bit, like Python)."
        ) from error

    lib.sc_create.restype = ctypes.c_void_p
    lib.sc_create.argtypes = []
    lib.sc_destroy.restype = None
    lib.sc_destroy.argtypes = [ctypes.c_void_p]
    # restype c_void_p (not c_char_p): we must keep the raw pointer so we can free it.
    lib.sc_invoke.restype = ctypes.c_void_p
    lib.sc_invoke.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int,
                              ctypes.POINTER(ctypes.c_char_p)]
    lib.sc_free_string.restype = None
    lib.sc_free_string.argtypes = [ctypes.c_void_p]
    lib.sc_version.restype = ctypes.c_char_p
    lib.sc_version.argtypes = []
    return lib


def _text(value):
    """Turn any argument into text for the C side."""
    text = "" if value is None else str(value)
    if "\x00" in text:
        raise ValueError("Text cannot contain null characters.")
    return text


class NativeStrayCareController:
    engine = "C/C++ native core"

    def __init__(self, data_path=None, seed_demo=True, library_path=None):
        self._lib = load_library(library_path)
        self._handle = self._lib.sc_create()
        if not self._handle:
            raise NativeUnavailable("The native library could not create a controller (out of memory?).")
        self._lock = threading.RLock()           # the C++ side is not thread-safe, so calls take turns
        self._path = data_path
        self._seed_demo = seed_demo
        self.native_version = self._lib.sc_version().decode("utf-8")

        loaded = False
        if self._path:
            try:
                data = load_json(self._path)
                if data is not None:
                    self._restore(data)
                    loaded = True
            except (OSError, ValueError, KeyError, TypeError):
                self._quarantine_corrupt_file()
                self._call("reset_empty")
        if not loaded:
            self._call("reset_demo" if self._seed_demo else "reset_empty")
            self._save()

    def close(self):
        with self._lock:
            if getattr(self, "_handle", None):
                self._lib.sc_destroy(self._handle)
                self._handle = None

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass

    # ======================= the one place where Python talks to C =======================
    def _call(self, method, *args):
        with self._lock:
            if not self._handle:
                raise RuntimeError("The native controller has been closed.")
            encoded = [_text(a).encode("utf-8") for a in args]
            argv = (ctypes.c_char_p * len(encoded))(*encoded) if encoded else None
            pointer = self._lib.sc_invoke(self._handle, method.encode("ascii"), len(encoded), argv)
            if not pointer:
                raise MemoryError("The native library ran out of memory.")
            try:
                reply = json.loads(ctypes.string_at(pointer).decode("utf-8"))
            finally:
                self._lib.sc_free_string(pointer)      # the C side allocated it, so the C side frees it
        if reply["ok"]:
            return reply["data"]
        if reply.get("kind") == "validation":
            raise ValueError(reply["error"])           # same exception type as the Python backend
        raise RuntimeError(f"Native backend error: {reply['error']}")

    def _mutate(self, method, *args):
        """Run a method that changes data, then save. A rejected call raises and saves nothing."""
        with self._lock:
            result = self._call(method, *args)
            self._save()
            return result

    # ======================= saving and loading ==========================================
    def _save(self):
        if self._path:
            save_json(self._path, self._call("export_state"))

    def _restore(self, data):
        self._call("reset_empty")
        for a in data["animals"]:
            self._call("restore_animal", a["ID"], a["Name"], a["Species"], a["Location"],
                       a["Condition"], a["Status"], a["Urgency"], a["Reported"])
        for o in data["food_offers"]:
            self._call("restore_food", o["Offer ID"], o["Donor"], o["Food"], int(o["Servings"]),
                       o["Pickup area"], o["Status"])
        for m in data["medical_logs"]:
            self._call("restore_medical", m["Date"], m["Animal ID"], m["Treatment"],
                       m["Volunteer"], m["Notes"])
        for a, b, km in data["roads"]:
            self._call("restore_road", a, b, float(km))
        for item in data["activity"]:
            self._call("restore_activity", item["when"], item["title"], item["detail"], item["status"])
        self._call("set_counters", int(data["next_animal_no"]), int(data["next_food_no"]))

    def _quarantine_corrupt_file(self):
        try:
            os.replace(self._path, self._path + ".corrupt")
        except OSError:
            pass

    def reset_demo(self):
        return self._mutate("reset_demo" if self._seed_demo else "reset_empty")

    def clear_all_data(self):
        return self._mutate("reset_empty")

    # ======================= animals =====================================================
    def register_animal(self, name, species, location, condition="", urgency="Low", status="Reported"):
        return self._mutate("register_animal", name, species, location, condition, urgency, status)

    def report_emergency(self, description, location, urgency="Critical", species="Unknown",
                         condition="", details=""):
        return self._mutate("report_emergency", description, location, urgency, species, condition, details)

    def update_case_status(self, animal_id, new_status, note=""):
        return self._mutate("update_case_status", animal_id, new_status, note)

    def update_animal(self, animal_id, name, species, location, condition="", urgency="Low"):
        return self._mutate("update_animal", animal_id, name, species, location, condition, urgency)

    def delete_animal(self, animal_id):
        return self._mutate("delete_animal", animal_id)

    def get_animal(self, animal_id):
        return self._call("get_animal", animal_id)

    def list_animals(self, search="", species="All"):
        return self._call("list_animals", search, species)

    def animal_choices(self):
        return self._call("animal_choices")

    # ======================= triage ======================================================
    def triage_order(self):
        return self._call("triage_order")

    def priority_cases(self):
        return self._call("priority_cases")

    def most_urgent_case(self):
        return self._call("most_urgent_case")

    def urgency_counts(self):
        return self._call("urgency_counts")

    # ======================= food donations ==============================================
    def add_food_offer(self, donor, food, servings, pickup_area, safety_confirmed):
        try:
            servings = int(servings)
        except (TypeError, ValueError):
            raise ValueError("Servings must be a whole number.")
        return self._mutate("add_food_offer", donor, food, servings, pickup_area,
                            "1" if safety_confirmed else "0")

    def update_food_status(self, offer_id, new_status):
        return self._mutate("update_food_status", offer_id, new_status)

    def list_food_offers(self):
        return self._call("list_food_offers")

    def next_pickup(self):
        return self._call("next_pickup")

    def food_stats(self):
        return self._call("food_stats")

    # ======================= medical log =================================================
    def add_medical_entry(self, animal_id, treatment, volunteer, visit_date, notes=""):
        if isinstance(visit_date, datetime):
            visit_date = visit_date.date()
        if isinstance(visit_date, date):
            visit_date = visit_date.isoformat()
        if not isinstance(visit_date, str):
            raise ValueError("Visit date is required.")
        return self._mutate("add_medical_entry", animal_id, treatment, volunteer, visit_date, notes)

    def list_medical_entries(self, animal_id=None):
        return self._call("list_medical_entries", animal_id or "")

    # ======================= routes ======================================================
    def map_locations(self):
        return self._call("map_locations")

    def road_list(self):
        return self._call("road_list")

    def unmapped_locations(self):
        return self._call("unmapped_locations")

    def open_case_locations(self):
        return self._call("open_case_locations")

    def plan_route(self, start, destination):
        return self._call("plan_route", start, destination)

    def plan_multi_stop(self, start, stops):
        return self._call("plan_multi_stop", start, *list(stops))

    def add_road(self, a, b, km):
        try:
            km = float(km)
        except (TypeError, ValueError):
            raise ValueError("Distance must be a number.")
        self._mutate("add_road", a, b, repr(km))

    # ======================= dashboard ===================================================
    def recent_activity(self, limit=8):
        return self._call("recent_activity", int(limit))

    def stats(self):
        return self._call("stats")
