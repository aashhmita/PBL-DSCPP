"""Builds ONE self-contained file (straycare_app.py) from the project.

It pastes the pure-Python backend modules in dependency order, removes their relative imports,
then appends the Streamlit page code (app.py) with its backend imports replaced.

    python tools/bundle_single_file.py            ->  straycare_app.py in the project folder
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ORDER = ["constants", "triage_heap", "animal_hash", "food_queue", "medical_log",
         "route_graph", "storage", "controller"]


def read(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as handle:
        return handle.read()


def strip_module(text):
    """Drop the docstring header kept as a comment, relative imports and duplicate stdlib imports."""
    text = re.sub(r"^from \.[\w.]* import \(.*?\)\n", "", text, flags=re.S | re.M)   # multi-line
    text = re.sub(r"^from \.[\w.]* import .*\n", "", text, flags=re.M)
    return text


def main(out_path):
    parts = ['''"""StrayCare: stray-animal rescue management (single-file edition).

Everything is in this one file:  1) data structures  2) controller  3) Streamlit pages.
    pip install streamlit
    streamlit run straycare_app.py
Records are saved automatically to data/straycare.json next to this file.
"""

import functools
import heapq
import html
import json
import os
import tempfile
import threading
from datetime import date, datetime

import streamlit as st

''']
    for name in ORDER:
        body = strip_module(read("backend", name + ".py"))
        # remove the module docstring (it would become a stray string in the bundle) and imports
        body = re.sub(r'^""".*?"""\n', "", body, count=1, flags=re.S)
        body = re.sub(r"^(import|from) (functools|heapq|json|os|tempfile|threading|datetime)[^\n]*\n", "", body, flags=re.M)
        parts.append(f"# {'=' * 70}\n# BACKEND: {name}\n# {'=' * 70}\n{body.strip()}\n\n\n")

    app = read("app.py")
    app = re.sub(r'^""".*?"""\n', "", app, count=1, flags=re.S)
    app = re.sub(r"^import html\nimport os\nfrom datetime import date, datetime\n\nimport streamlit as st\n\n"
                 r"from backend\.constants import \(.*?\)\nfrom backend\.engine import create_controller\n",
                 "", app, count=1, flags=re.S | re.M)
    app = app.replace("    return create_controller(DATA_FILE)",
                      "    return StrayCareController(data_path=DATA_FILE), \"\"")
    app = app.replace("""    \"\"\"One backend (and one set of data structures) shared by every rerun and session.
    Uses the compiled C/C++ core when it has been built (python build.py), otherwise the
    pure-Python backend. See backend/engine.py.\"\"\"""",
                      """    \"\"\"One backend (and one set of data structures) shared by every rerun and session.\"\"\"""")
    parts.append(f"# {'=' * 70}\n# FRONTEND: Streamlit pages\n# {'=' * 70}\n{app.strip()}\n")
    with open(out_path, "w", encoding="utf-8") as handle:
        handle.write("".join(parts))
    print("wrote", out_path)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "straycare_app.py"))
