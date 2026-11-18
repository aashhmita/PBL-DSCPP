# StrayCare: stray-animal rescue management

Streamlit frontend (Python) → ctypes bridge (Python) → **C++ controller** → **C data structures**.
If the C/C++ part has not been compiled, the app falls back to a pure-Python copy of the same
backend, so it always runs.

## Quick start

```bash
pip install -r requirements.txt     # Streamlit
python build.py                     # compiles the C/C++ core into build/   (needs gcc + g++)
streamlit run app.py                # the sidebar shows which engine is running
```

Skip `python build.py` to run on the pure-Python backend.
Force an engine with the variable `STRAYCARE_BACKEND` = `auto` (default) | `native` | `python`.

### Windows
1. Install MinGW-w64 (64-bit), e.g. through MSYS2: `pacman -S mingw-w64-ucrt-x86_64-gcc`
2. Put its `bin` folder on your PATH, then check: `gcc --version` and `g++ --version`
3. The compiler must be 64-bit like your Python. Then run `python build.py` as above.

### Tests
```bash
python build.py --test               # C tests + C++ self-check (add --sanitize for memory checks)
python -m unittest discover -s tests -t . -v      # Python tests, both engines
```
The C/C++ engine is tested with the SAME controller test-suite as the Python engine, plus a test
that runs identical actions on both engines and compares every answer and the saved file.

## What the app can do

Register, **edit** and **delete** animals (deleting also removes that animal's medical notes), report emergencies,
update case status, list and collect food offers, record medical notes, plan shortest routes and multi-stop tours,
edit the road map. The sidebar's *Data tools* can restore the sample set or erase all records (both need a tick-box).

### Single-file edition
`python tools/bundle_single_file.py` writes `straycare_app.py`: the Python backend and the Streamlit pages in one file
(`pip install streamlit`, then `streamlit run straycare_app.py`). It uses the Python engine, not the C/C++ core.

## How the layers fit together

```
 Streamlit page (app.py)
      │  ctl.register_animal("Milo", ...)
      ▼
 backend/native_bridge.py          Python: turns arguments into text, calls the C function,
      │  sc_invoke(handle, "register_animal", args)    turns the JSON reply back into dicts
      ▼
 cpp_controller/integration.cpp    C++: 4 plain C functions (sc_create, sc_invoke, sc_free_string,
      │                            sc_destroy), a method table, JSON output, catches every exception
      ▼
 cpp_controller/controller.cpp     C++: validation, business rules, keeps all structures in step
      │
      ▼
 c_core/src/*.c                    C: hash table, min-heap, linked-list queue, linked list, graph
```

| Module | Structure | Used for | Cost |
|---|---|---|---|
| `animal_hash.c` | hash table, chaining | find an animal by ID | O(1) average |
| `triage_heap.c` | binary min-heap | most urgent case first | peek O(1), push/pop O(log n), build O(n) |
| `food_queue.c` | linked-list FIFO queue | collect the oldest donation first | enqueue/dequeue O(1) |
| `medical_log.c` | linked list + tail pointer | treatment history in order | append O(1) |
| `route_graph.c` | weighted graph + Dijkstra | shortest route | O((V+E) log V) |

Saving: the C++ side lives in memory. After every change the Python bridge asks it for its full
state (`export_state`) and writes `data/straycare.json`; at start-up the saved records are fed
back in (`restore_*`). Corrupt files are renamed to `.corrupt` and the app starts fresh.

## Files

```
c_core/include/*.h, c_core/src/*.c     the five C modules (+ straycare_types.h shared records)
c_core/tests/test_c_core.c             C tests (1,198 checks)
cpp_controller/controller.hpp/.cpp     StrayCareController
cpp_controller/integration.cpp         the C interface Python loads
cpp_controller/main.cpp                console program + self-check (no Python needed)
build.py                               compiles everything (no Makefile or CMake needed)
backend/native_bridge.py               ctypes bridge      backend/engine.py   chooses the engine
backend/*.py                           pure-Python fallback (same design, same behaviour)
app.py                                 Streamlit frontend
tools/bundle_single_file.py            builds straycare_app.py (everything in ONE file, Python backend)
```

Build by hand instead of `build.py` (Linux/macOS):
```bash
mkdir -p build && cd build
for f in ../c_core/src/*.c; do gcc -std=c11 -O2 -fPIC -I../c_core/include -c $f; done
for f in ../cpp_controller/controller.cpp ../cpp_controller/integration.cpp; do
  g++ -std=c++17 -O2 -fPIC -I../c_core/include -I../cpp_controller -c $f; done
g++ -shared -o libstraycare.so *.o
```

## Look and limits

- **Colours:** the stylesheet at the top of `app.py` sets every text, input, button, tab and message
  colour explicitly, so the page reads the same in Streamlit's light and dark themes.
  `.streamlit/config.toml` also sets Streamlit's theme to match, which recolours the tables.
- **Input limits (text boxes stop accepting more characters):** names and descriptions 60-80,
  places 60-80, conditions and notes 120, long notes and details 500, search 60.
  Servings 1-2000, road distance 0.1-200 km, visit date from 2020-01-01 up to today.
  The backend enforces its own, larger limits as well (200 / 1000), so nothing depends on the page.

## Known limits (say these in your viva before you are asked)

- Text limits are counted in bytes in C/C++ (200 for names and places, 1000 for notes), so a
  long Hindi name allows fewer letters than an English one. The Python engine counts characters.
- Search ignores upper/lower case for English letters only on the C++ engine.
- Road distances are the values stored in the road map (the starting set is sample data; edit it in the Route Planner). Travel time uses a fixed 25 km/h: no live traffic or map.
- The nearest-neighbour multi-stop tour is a greedy heuristic, not guaranteed optimal.
- The C++ controller is not thread-safe; the Python bridge serializes calls with a lock.
- One JSON file suits a single shelter, not many simultaneous users. No login.
- Medical notes are for coordination only, not a clinical record.
