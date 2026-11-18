"""UI smoke tests: run app.py against a tiny fake of Streamlit.

Why a fake? It lets us check the page logic (every page renders, forms validate, buttons call
the backend, flash messages appear) without a browser and without Streamlit installed.
It does NOT check real visuals or CSS; for that, run `streamlit run app.py` and click around.

    python -m unittest discover -s tests -t . -v
"""

import os
import runpy
import sys
import tempfile
import unittest
from unittest.mock import MagicMock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP = os.path.join(ROOT, "app.py")
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from backend.controller import StrayCareController  # noqa: E402

PAGES = ["Overview", "Animal Registry", "Rescue & Triage", "Food Donations",
         "Medical Records", "Route Planner", "About Project"]


class RerunSignal(Exception):
    """Raised by the fake st.rerun(), just like the real one interrupts the script."""


class SessionState(dict):
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)

    def __setattr__(self, name, value):
        self[name] = value


class AppRunner:
    def __init__(self, tmpdir, engine="python", app_path=None):
        self.app_path = app_path or APP
        self.engine = engine                      # "python" or "native" (the C/C++ core)
        self.data_path = os.path.join(tmpdir, "data.json")
        self.inputs, self.clicked, self.seen_forms = {}, set(), set()
        self.st = self._build_fake()

    # ---- fake streamlit ---------------------------------------------------------
    def _build_fake(self):
        st = MagicMock(name="streamlit")
        st.session_state = SessionState()
        memo = {}

        def cache_resource(fn=None, **_):
            def decorate(func):
                return lambda *a, **k: memo.setdefault(func.__name__, func(*a, **k))
            return decorate(fn) if fn else decorate

        def val(kind, label, default):
            return self.inputs.get(f"{kind}:{label}", self.inputs.get(label, default))

        missing = object()

        def widget_value(key, kind, label, default):
            """Mimic Streamlit: a user action (inputs) wins, else the stored state, else the default.
            Widgets with a key write their value into session_state."""
            supplied = self.inputs.get(f"{kind}:{label}", self.inputs.get(label, missing))
            if supplied is not missing:
                value = supplied
            elif key and key in st.session_state:
                value = st.session_state[key]
            else:
                value = default
            if key:
                st.session_state[key] = value
            return value

        def clicked(label, on_click=None, args=()):
            if label in self.clicked:
                if on_click:
                    on_click(*args)
                return True
            return False

        def form(key, **_):
            if key in self.seen_forms:
                raise AssertionError(f"duplicate form key {key!r}")
            self.seen_forms.add(key)
            return MagicMock()

        def rerun():
            raise RerunSignal()

        st.cache_resource = cache_resource
        st.rerun = rerun
        st.form = form
        st.columns = lambda spec, **_: [MagicMock() for _ in range(spec if isinstance(spec, int) else len(spec))]
        st.tabs = lambda labels, **_: [MagicMock() for _ in labels]
        st.text_input = lambda label, **kw: val("text_input", label, kw.get("value", ""))
        st.text_area = lambda label, **kw: val("text_area", label, "")
        st.selectbox = lambda label, options, index=0, key=None, **kw: widget_value(
            key, "selectbox", label, options[index] if options else None)
        st.radio = lambda label, options, key=None, **kw: widget_value(key, "radio", label, options[0])
        st.multiselect = lambda label, options, default=None, **kw: val("multiselect", label, default or [])
        st.checkbox = lambda label, key=None, **kw: widget_value(key, "checkbox", label, False)
        st.number_input = lambda label, **kw: val("number_input", label, kw.get("value", 1))
        st.date_input = lambda label, value=None, **kw: val("date_input", label, value)
        # A disabled button cannot be clicked in real Streamlit, so the fake ignores it too.
        st.button = lambda label, on_click=None, args=(), disabled=False, **kw: (
            not disabled and clicked(label, on_click, args))
        st.form_submit_button = lambda label, **kw: clicked(label)
        return st

    # ---- running the script -----------------------------------------------------
    def run(self, page, inputs=None, clicked=()):
        self.inputs, self.clicked, self.seen_forms = dict(inputs or {}), set(clicked), set()
        self.st.session_state["page"] = page
        for name in ("error", "success", "info", "warning", "markdown", "dataframe"):
            getattr(self.st, name).reset_mock()
        old_module = sys.modules.get("streamlit")
        old_env = {name: os.environ.get(name) for name in ("STRAYCARE_DATA", "STRAYCARE_BACKEND")}
        sys.modules["streamlit"] = self.st
        os.environ["STRAYCARE_DATA"] = self.data_path
        os.environ["STRAYCARE_BACKEND"] = self.engine
        try:
            runpy.run_path(self.app_path, run_name="__main__")
        finally:
            if old_module is None:
                sys.modules.pop("streamlit", None)
            else:
                sys.modules["streamlit"] = old_module
            for name, value in old_env.items():
                if value is None:
                    os.environ.pop(name, None)
                else:
                    os.environ[name] = value

    # ---- helpers for assertions ---------------------------------------------------
    def markdown_text(self):
        return "\n".join(str(c.args[0]) for c in self.st.markdown.call_args_list if c.args)

    def messages(self, kind):
        return [str(c.args[0]) for c in getattr(self.st, kind).call_args_list if c.args]

    def backend(self):
        """A separate controller of the same engine, reading the same data file."""
        if self.engine == "native":
            from backend.native_bridge import NativeStrayCareController
            return NativeStrayCareController(data_path=self.data_path)
        return StrayCareController(data_path=self.data_path)


class UiSmokeTests(unittest.TestCase):
    engine = "python"

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.app = AppRunner(self.tmp.name, self.engine)

    def tearDown(self):
        self.tmp.cleanup()

    def test_every_page_renders_without_errors(self):
        for page in PAGES:
            with self.subTest(page=page):
                self.app.run(page)
                self.assertEqual(self.app.messages("error"), [], page)

    def test_overview_shows_seed_metrics_and_escapes_html(self):
        self.app.run("Overview")
        self.assertIn("Registered animals", self.app.markdown_text())
        self.app.backend().report_emergency("<script>alert(1)</script>", "GEU", "High")
        self.app.run("Overview")
        self.assertNotIn("<script>alert(1)</script>", self.app.markdown_text())

    def test_report_button_navigates_to_triage(self):
        self.app.run("Overview", clicked={"＋ Report a rescue"})
        self.assertEqual(self.app.st.session_state["page"], "Rescue & Triage")

    def test_register_animal_success_then_flash_message(self):
        inputs = {"Animal name / identifier": "Test pup", "Location": "Prem Nagar"}
        with self.assertRaises(RerunSignal):
            self.app.run("Animal Registry", inputs, clicked={"Add animal profile"})
        self.assertEqual(self.app.backend().get_animal("SC-1005")["Name"], "Test pup")
        self.assertEqual(self.app.st.session_state["form_nonce"], 1)          # forms reset
        self.app.run("Animal Registry")                                       # the rerun
        self.assertTrue(any("SC-1005" in m for m in self.app.messages("success")))
        self.app.run("Animal Registry")                                       # flash shows only once
        self.assertEqual(self.app.messages("success"), [])

    def test_validation_error_is_shown_and_form_key_is_kept(self):
        self.app.run("Animal Registry", {"Animal name / identifier": "No location"},
                     clicked={"Add animal profile"})
        self.assertTrue(any("Location is required" in m for m in self.app.messages("error")))
        self.assertEqual(self.app.st.session_state.get("form_nonce", 0), 0)
        self.assertEqual(len(self.app.backend().list_animals()), 4)

    def test_species_filter_and_search(self):
        self.app.run("Animal Registry", {"radio:Species": "Cat"})
        rows = self.app.st.dataframe.call_args_list[0].args[0]
        self.assertEqual([r["Name"] for r in rows], ["Luna"])

    def test_emergency_report_creates_critical_case_on_top(self):
        inputs = {"Animal description": "Injured calf", "Exact area / landmark": "Prem Nagar"}
        with self.assertRaises(RerunSignal):
            self.app.run("Rescue & Triage", inputs, clicked={"Submit rescue report"})
        top = self.app.backend().most_urgent_case()
        self.assertEqual((top["ID"], top["Name"]), ("SC-1004", "Unknown puppy"))   # older critical stays first
        self.assertEqual(self.app.backend().get_animal("SC-1005")["Status"], "Awaiting rescue")

    def test_case_status_update(self):
        inputs = {"Select case": "SC-1004 — Unknown puppy", "New status": "Rescue assigned"}
        with self.assertRaises(RerunSignal):
            self.app.run("Rescue & Triage", inputs, clicked={"Update case"})
        self.assertEqual(self.app.backend().get_animal("SC-1004")["Status"], "Rescue assigned")

    def test_food_status_update_moves_queue(self):
        inputs = {"selectbox:Offer": "FD-201 — Green Bowl Cafe", "selectbox:Status": "Collected"}
        with self.assertRaises(RerunSignal):
            self.app.run("Food Donations", inputs, clicked={"Save offer status"})
        self.assertEqual(self.app.backend().next_pickup()["Offer ID"], "FD-202")

    def test_food_form_requires_safety_checkbox(self):
        inputs = {"Donor / organization": "Cafe", "Food description": "Rice", "Pickup area": "GEU"}
        self.app.run("Food Donations", inputs, clicked={"Add donation offer"})
        self.assertTrue(any("food-safety" in m for m in self.app.messages("error")))

    def test_medical_entry(self):
        inputs = {"Animal profile": "SC-1004 — Unknown puppy", "Treatment / examination": "Wound care",
                  "Volunteer / care provider": "Meera"}
        with self.assertRaises(RerunSignal):
            self.app.run("Medical Records", inputs, clicked={"Save medical entry"})
        self.assertEqual(self.app.backend().list_medical_entries("SC-1004")[0]["Treatment"], "Wound care")

    def test_shortest_route_displayed(self):
        inputs = {"Starting point": "Shelter (Base)", "Rescue destination": "ISBT Dehradun"}
        self.app.run("Route Planner", inputs, clicked={"Find shortest route"})
        self.assertIn("Shelter (Base) → Clock Tower → ISBT Dehradun", self.app.markdown_text())
        self.assertIn("6.5 km", self.app.markdown_text())

    def test_same_start_and_destination_is_rejected(self):
        inputs = {"Starting point": "GEU", "Rescue destination": "GEU"}
        self.app.run("Route Planner", inputs, clicked={"Find shortest route"})
        self.assertTrue(any("same" in m for m in self.app.messages("error")))

    def test_multi_stop_tour_uses_open_cases_by_default(self):
        self.app.run("Route Planner", {"Start from": "Shelter (Base)"}, clicked={"Plan tour"})
        self.assertIn("Visit order", self.app.markdown_text())
        self.assertIn("ISBT Dehradun", self.app.markdown_text())

    def test_unmapped_location_warning_and_road_form(self):
        self.app.backend().report_emergency("Dog", "Rajpur Road", "High")
        self.app.run("Route Planner")
        self.assertTrue(any("Rajpur Road" in m for m in self.app.messages("warning")))
        inputs = {"First location": "Clock Tower", "Second location": "Rajpur Road", "Distance (km)": 4.0}
        with self.assertRaises(RerunSignal):
            self.app.run("Route Planner", inputs, clicked={"Save road"})
        self.assertIn("Rajpur Road", self.app.backend().map_locations())

    def test_restore_sample_button_needs_confirmation(self):
        self.app.backend().register_animal("Temp", "Dog", "GEU")
        self.app.run("Overview", clicked={"Restore sample data"})              # box not ticked -> disabled
        self.assertEqual(len(self.app.backend().list_animals()), 5)
        confirm = {"checkbox:Yes, replace all records with the sample set": True}
        self.app.run("Overview", confirm, clicked={"Restore sample data"})     # box ticked -> works
        self.assertEqual(len(self.app.backend().list_animals()), 4)
        self.assertFalse(self.app.st.session_state["confirm_restore"])        # box un-ticks itself

    def test_erase_all_button_needs_confirmation(self):
        self.app.run("Overview", clicked={"Erase all records"})                # not ticked -> nothing
        self.assertEqual(len(self.app.backend().list_animals()), 4)
        confirm = {"checkbox:Yes, permanently erase every record": True}
        self.app.run("Overview", confirm, clicked={"Erase all records"})
        self.assertEqual(self.app.backend().list_animals(), [])
        self.app.run("Overview")                                               # empty pages still render
        for page in PAGES:
            self.app.run(page)
        self.assertFalse(self.app.st.session_state["confirm_erase"])

    def test_no_phase_or_demo_wording_anywhere(self):
        for page in PAGES:
            self.app.run(page)
            text = (self.app.markdown_text() + " ".join(
                str(c.args[0]) for c in self.app.st.caption.call_args_list if c.args)).lower()
            for banned in ("phase", "demo", "fictional", "not live", "not a clinical"):
                self.assertNotIn(banned, text, f"{banned!r} on {page}")

    def test_edit_animal_form_saves_changes(self):
        inputs = {"selectbox:Select animal": "SC-1001 — Milo", "Animal name / identifier": "Milo Senior",
                  "Location": "GEU"}
        with self.assertRaises(RerunSignal):
            self.app.run("Animal Registry", inputs, clicked={"Save changes"})
        animal = self.app.backend().get_animal("SC-1001")
        self.assertEqual((animal["Name"], animal["Location"]), ("Milo Senior", "GEU"))
        self.assertIn("Saved changes", self.app.st.session_state["flash"][0])

    def test_edit_animal_form_shows_validation_error(self):
        inputs = {"selectbox:Select animal": "SC-1001 — Milo", "Animal name / identifier": "  "}
        self.app.run("Animal Registry", inputs, clicked={"Save changes"})
        self.assertTrue(any("required" in m for m in self.app.messages("error")))
        self.assertEqual(self.app.backend().get_animal("SC-1001")["Name"], "Milo")

    def test_delete_animal_needs_confirmation(self):
        pick = {"selectbox:Select animal": "SC-1001 — Milo"}
        self.app.run("Animal Registry", pick, clicked={"Delete animal record"})
        self.assertIsNotNone(self.app.backend().get_animal("SC-1001"))         # not ticked -> disabled
        ticked = dict(pick, **{"checkbox:Yes, delete SC-1001 and its medical notes permanently": True})
        with self.assertRaises(RerunSignal):
            self.app.run("Animal Registry", ticked, clicked={"Delete animal record"})
        self.assertIsNone(self.app.backend().get_animal("SC-1001"))
        self.assertEqual(self.app.backend().list_medical_entries("SC-1001"), [])


BUNDLE = os.path.join(ROOT, "straycare_app.py")


@unittest.skipUnless(os.path.exists(BUNDLE), "single-file edition not built (python tools/bundle_single_file.py)")
class SingleFileUiSmokeTests(UiSmokeTests):
    """The very same page tests, run against the standalone straycare_app.py."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.app = AppRunner(self.tmp.name, "python", app_path=BUNDLE)

    def test_bundle_has_no_project_imports(self):
        with open(BUNDLE, encoding="utf-8") as handle:
            text = handle.read()
        self.assertNotIn("from backend", text)
        self.assertNotIn("import backend", text)


def _native_ready():
    try:
        from backend.native_bridge import load_library
        load_library()
        return True
    except Exception:
        return False


@unittest.skipUnless(_native_ready(), "C/C++ library not built (run: python build.py)")
class NativeUiSmokeTests(UiSmokeTests):
    """The very same page tests, but app.py runs on the compiled C/C++ engine."""
    engine = "native"

    def test_sidebar_reports_the_native_engine(self):
        self.app.run("Overview")
        captions = [str(c.args[0]) for c in self.app.st.caption.call_args_list if c.args]
        self.assertIn("Engine: C/C++ native core", captions)


class AutoFallbackTests(unittest.TestCase):
    def test_python_engine_is_reported_and_missing_library_falls_back(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = AppRunner(tmp, "python")
            app.run("Overview")
            captions = [str(c.args[0]) for c in app.st.caption.call_args_list if c.args]
            self.assertIn("Engine: Pure-Python backend", captions)

            # engine "auto" with a library path that does not exist -> Python backend + a note
            old = os.environ.get("STRAYCARE_LIB")
            os.environ["STRAYCARE_LIB"] = os.path.join(tmp, "missing.so")
            try:
                auto = AppRunner(tmp, "auto")
                auto.run("Overview")
            finally:
                if old is None:
                    os.environ.pop("STRAYCARE_LIB", None)
                else:
                    os.environ["STRAYCARE_LIB"] = old
            captions = [str(c.args[0]) for c in auto.st.caption.call_args_list if c.args]
            self.assertIn("Engine: Pure-Python backend", captions)
            self.assertTrue(any("Native library not found" in c for c in captions))
            self.assertEqual(auto.messages("error"), [])


if __name__ == "__main__":
    unittest.main()
