"""Chooses which backend the app uses.

    STRAYCARE_BACKEND=auto    (default) use the C/C++ native core if it has been built,
                              otherwise quietly fall back to the pure-Python backend
    STRAYCARE_BACKEND=native  require the C/C++ core (error if it is not built)
    STRAYCARE_BACKEND=python  always use the pure-Python backend

Both backends have the same methods, so the app works unchanged with either one.
"""

import os

from .controller import StrayCareController
from .native_bridge import NativeStrayCareController, NativeUnavailable


def create_controller(data_path, preference=None):
    """Return (controller, note). `note` is empty unless we had to fall back to Python."""
    preference = (preference or os.environ.get("STRAYCARE_BACKEND") or "auto").strip().lower()
    if preference not in ("auto", "native", "python"):
        raise ValueError("STRAYCARE_BACKEND must be auto, native or python.")

    if preference == "python":
        return StrayCareController(data_path=data_path), ""

    try:
        return NativeStrayCareController(data_path=data_path), ""
    except NativeUnavailable as error:
        if preference == "native":
            raise
        return StrayCareController(data_path=data_path), f"Using the Python backend. {error}"
