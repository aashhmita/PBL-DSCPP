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

from backend import auth as _auth  # noqa: E402
from backend.auth import UserStore  # noqa: E402
from backend.controller import StrayCareController  # noqa: E402

_auth.ITERATIONS = 1000          # fast password hashing for tests (the real value is 200,000)

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


class StopSignal(Exception):
    """Raised by the fake st.stop(), which ends the script run like the real one."""


class AppRunner:
    def __init__(self, tmpdir, engine="python", app_path=None, role="admin"):
        self.app_path = app_path or APP
        self.engine = engine                      # "python" or "native" (the C/C++ core)
        self.role = role                          # who is signed in: "admin", "user" or None (nobody)
        self.data_path = os.path.join(tmpdir, "data.json")
        self.users_path = os.path.join(tmpdir, "users.json")
        self.users = UserStore(self.users_path)   # the very store the app will use (see cache_resource)
        self.radio_options = []
        self.inputs, self.clicked, self.seen_forms = {}, set(), set()
        self.st = self._build_fake()

    # ---- fake streamlit ---------------------------------------------------------
    def _build_fake(self):
        st = MagicMock(name="streamlit")
        st.session_state = SessionState()
        memo = {"get_users": self.users}

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
        def radio(label, options, key=None, **kw):
            if label == "WORKSPACE":
                self.radio_options = list(options)
            return widget_value(key, "radio", label, options[0])

        def stop():
            raise StopSignal()

        st.stop = stop
        st.radio = radio
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
        if self.role and "auth" not in self.st.session_state:
            name = f"{self.role}_tester"
            if not self.users.exists(name):
                self.users.add_user(name, "testpass1", self.role)
            self.st.session_state["auth"] = {"username": name}
        for name in ("error", "success", "info", "warning", "markdown", "dataframe"):
            getattr(self.st, name).reset_mock()
        old_module = sys.modules.get("streamlit")
        old_env = {name: os.environ.get(name) for name in ("STRAYCARE_DATA", "STRAYCARE_BACKEND", "STRAYCARE_USERS")}
        sys.modules["streamlit"] = self.st
        os.environ["STRAYCARE_DATA"] = self.data_path
        os.environ["STRAYCARE_USERS"] = self.users_path
        os.environ["STRAYCARE_BACKEND"] = self.engine
        try:
            runpy.run_path(self.app_path, run_name="__main__")
        except StopSignal:
            pass
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
