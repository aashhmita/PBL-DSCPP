"""Tests for the C/C++ backend, reached through the Python bridge.

The big idea: the SAME controller test-suite that checks the pure-Python backend is run again
here against the compiled C/C++ engine. If both pass, the two engines behave identically.

These tests are skipped (not failed) when the library has not been built yet:

    python build.py
    python -m unittest discover -s tests -t . -v
"""

import os
import tempfile
import unittest
from datetime import date

from backend.native_bridge import NativeStrayCareController, NativeUnavailable, default_library_path
from tests import test_backend as base

try:
    from backend.native_bridge import load_library
    load_library()
    NATIVE_READY = True
    SKIP_REASON = ""
except NativeUnavailable as error:
    NATIVE_READY = False
    SKIP_REASON = str(error)


@unittest.skipUnless(NATIVE_READY, SKIP_REASON)
class NativeControllerTests(base.ControllerTests):
    """Every ControllerTests case, but talking to the C/C++ engine."""

    @staticmethod
    def make_controller(path):
        return NativeStrayCareController(data_path=path)


@unittest.skipUnless(NATIVE_READY, SKIP_REASON)
class NativeBridgeTests(unittest.TestCase):
    """Things that only matter for the bridge itself."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "straycare.json")
        self.ctl = NativeStrayCareController(data_path=self.path)

    def tearDown(self):
        self.ctl.close()
        self.tmp.cleanup()

    def test_engine_label_and_version(self):
        self.assertEqual(self.ctl.engine, "C/C++ native core")
        self.assertIn("C core + C++ controller", self.ctl.native_version)

    def test_unicode_text_round_trips_through_c_and_json_file(self):
        record = self.ctl.register_animal("कालू 🐕", "Dog", "Rajpur Road — दून", 'Says "hi"\nsecond line\ttab \\')
        self.assertEqual(self.ctl.get_animal(record["ID"]), record)
        reopened = NativeStrayCareController(data_path=self.path)
        self.assertEqual(reopened.get_animal(record["ID"]), record)
        reopened.close()

    def test_unicode_search_and_limits(self):
        self.ctl.register_animal("कालू", "Dog", "GEU")
        self.assertEqual([a["Name"] for a in self.ctl.list_animals("कालू")], ["कालू"])
        with self.assertRaises(ValueError):                    # limit counts bytes: 70 x 3-byte letters
            self.ctl.register_animal("क" * 70, "Dog", "GEU")

    def test_null_character_is_rejected(self):
        with self.assertRaises(ValueError):
            self.ctl.register_animal("bad\x00name", "Dog", "GEU")

    def test_non_numeric_inputs_become_value_errors(self):
        with self.assertRaises(ValueError):
            self.ctl.add_road("A", "B", float("nan"))
        with self.assertRaises(ValueError):
            self.ctl.add_road("A", "B", float("inf"))
        with self.assertRaises(ValueError):
            self.ctl.add_medical_entry("SC-1001", "x", "y", None)
        with self.assertRaises(ValueError):
            self.ctl.add_medical_entry("SC-1001", "x", "y", "2026-02-30")   # no such day
        with self.assertRaises(ValueError):
            self.ctl.add_food_offer("Cafe", "Rice", 10**30, "GEU", True)    # absurdly large

    def test_leap_day_and_date_object(self):
        self.assertEqual(self.ctl.add_medical_entry("SC-1001", "x", "y", "2024-02-29")["Date"], "2024-02-29")
        self.assertEqual(self.ctl.add_medical_entry("SC-1001", "x", "y", date.today())["Date"], date.today().isoformat())

    def test_all_stops_unreachable_and_unmapped_stops_ignored(self):
        self.ctl.add_road("Lonely A", "Lonely B", 1.0)             # an island, not linked to the rest
        plan = self.ctl.plan_multi_stop("Shelter (Base)", ["Lonely A", "Nowhere", "Clock Tower"])
        self.assertEqual(plan["order"], ["Shelter (Base)", "Clock Tower"])
        self.assertEqual(plan["unreachable"], ["Lonely A"])

    def test_unknown_place_is_reported_cleanly(self):
        with self.assertRaises(ValueError):
            self.ctl.plan_route("Shelter (Base)", "Atlantis")
        with self.assertRaises(ValueError):
            self.ctl.plan_multi_stop("Atlantis", ["Clock Tower"])

    def test_unknown_method_is_an_internal_error_not_a_crash(self):
        with self.assertRaises(RuntimeError):
            self.ctl._call("no_such_method")
        with self.assertRaises(RuntimeError):
            self.ctl._call("stats", "unexpected argument")

    def test_closed_controller_refuses_calls(self):
        self.ctl.close()
        with self.assertRaises(RuntimeError):
            self.ctl.stats()
        self.ctl.close()                                           # closing twice is harmless

    def test_many_records_and_two_independent_controllers(self):
        for i in range(300):                                       # forces the C hash table to resize
            self.ctl.report_emergency(f"Dog {i}", "GEU", "Low")
        self.assertEqual(self.ctl.stats()["animals"], 304)
        self.assertEqual(self.ctl.get_animal("SC-1304")["Name"], "Dog 299")
        other = NativeStrayCareController(seed_demo=False)         # no file, no demo data
        self.assertEqual(other.stats()["animals"], 0)
        self.assertEqual(self.ctl.stats()["animals"], 304)         # unaffected
        other.close()


@unittest.skipUnless(NATIVE_READY, SKIP_REASON)
class EnginesAgreeTests(unittest.TestCase):
    """Run the same sequence of actions on both engines; every answer must be identical."""

    def test_same_actions_give_same_answers(self):
        from backend.controller import StrayCareController
        with tempfile.TemporaryDirectory() as tmp:
            py = StrayCareController(data_path=os.path.join(tmp, "py.json"))
            c = NativeStrayCareController(data_path=os.path.join(tmp, "c.json"))

            def both(method, *args):
                return getattr(py, method)(*args), getattr(c, method)(*args)

            def same(method, *args):
                left, right = both(method, *args)
                if isinstance(left, dict) and "when" in left:
                    left, right = dict(left, when=""), dict(right, when="")
                self.assertEqual(left, right, f"{method}{args}")

            same("register_animal", "Tiger", "Cat", "Prem Nagar", "Limping", "High", "Reported")
            same("report_emergency", "Injured cow", "Rajpur Road", "Critical", "Other", "", "Blocking traffic")
            same("update_case_status", "SC-1004", "Rescue assigned", "On the way")
            same("add_food_offer", "Cafe", "Rice", 14, "GEU", True)
            same("update_food_status", "FD-201", "Collected")
            same("add_medical_entry", "SC-1005", "Check-up", "Meera", "2026-10-01", "Fine")
            same("add_road", "Clock Tower", "Rajpur Road", 4.25)
            same("update_animal", "SC-1001", "Milo Jr", "Cat", "Prem Nagar", "Recovered", "Low")
            same("add_medical_entry", "SC-1002", "Follow-up", "Meera", "2026-10-02", "")
            same("delete_animal", "SC-1002")
            for method in ("stats", "triage_order", "priority_cases", "most_urgent_case", "urgency_counts",
                           "list_food_offers", "next_pickup", "food_stats", "list_medical_entries",
                           "map_locations", "road_list", "unmapped_locations", "open_case_locations",
                           "animal_choices"):
                same(method)
            same("list_animals", "cow", "All")
            same("list_animals", "", "Cat")
            same("plan_route", "Shelter (Base)", "Rajpur Road")
            same("plan_route", "GEU", "Clement Town")
            same("plan_multi_stop", "Shelter (Base)", ["GEU", "Rajpur Road", "Prem Nagar", "ISBT Dehradun"])
            same("plan_multi_stop", "Shelter (Base)", ["Rajpur Road", "Atlantis", "Rajpur Road"])
            same("list_medical_entries", "SC-1005")
            same("list_medical_entries", "SC-1002")
            left, right = both("recent_activity", 50)
            self.assertEqual([{k: v for k, v in i.items() if k != "when"} for i in left],
                             [{k: v for k, v in i.items() if k != "when"} for i in right])
            # the saved files hold the same data too (activity times aside)
            import json
            with open(os.path.join(tmp, "py.json"), encoding="utf-8") as handle:
                a = json.load(handle)
            with open(os.path.join(tmp, "c.json"), encoding="utf-8") as handle:
                b = json.load(handle)
            for state in (a, b):
                for item in state["activity"]:
                    item["when"] = ""
            self.assertEqual(a, b)
            c.close()


if __name__ == "__main__":
    unittest.main()
