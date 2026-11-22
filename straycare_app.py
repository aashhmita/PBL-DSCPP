"""StrayCare: stray-animal rescue management (single-file edition).

Everything is in this one file:  1) data structures  2) login accounts  3) controller  4) Streamlit pages.
    pip install streamlit
    streamlit run straycare_app.py
Records are saved automatically to data/straycare.json next to this file.
"""

import functools
import hashlib
import heapq
import hmac
import html
import json
import os
import re
import tempfile
import threading
import time
from datetime import date, datetime

import streamlit as st

# ======================================================================
# BACKEND: constants
# ======================================================================
SPECIES = ["Dog", "Cat", "Bird", "Other", "Unknown"]

URGENCY_LEVELS = ["Critical", "High", "Medium", "Low"]
URGENCY_RANK = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}   # smaller = more urgent

CASE_STATUSES = [
    "Reported", "Awaiting rescue", "Rescue assigned", "Rescued",
    "Under treatment", "Monitoring", "Closed",
]
RESOLVED_STATUSES = ("Rescued", "Closed")                          # no longer "unresolved"
OPEN_EMERGENCY_STATUSES = ("Awaiting rescue", "Rescue assigned")
PRIORITY_STATUSES = ("Awaiting rescue", "Rescue assigned", "Under treatment")

FOOD_STATUSES = ["Available", "Pickup pending", "Collected", "Cancelled"]
FOOD_INACTIVE_STATUSES = ("Collected", "Cancelled")                # leave the pickup queue

AVERAGE_SPEED_KMH = 25.0   # used only to turn kilometres into a rough ETA


# ======================================================================
# BACKEND: triage_heap
# ======================================================================
class MinHeap:
    """Generic min-heap. Items must be comparable (tuples work well)."""

    def __init__(self, items=None):
        self._data = list(items) if items else []
        # Bottom-up heapify: fix every non-leaf node, starting from the last one.
        for i in range(len(self._data) // 2 - 1, -1, -1):
            self._sift_down(i)

    def __len__(self):
        return len(self._data)

    def push(self, item):
        self._data.append(item)
        self._sift_up(len(self._data) - 1)

    def pop(self):
        if not self._data:
            raise IndexError("pop from an empty heap")
        top = self._data[0]
        last = self._data.pop()
        if self._data:                 # move the last leaf to the root, then sink it
            self._data[0] = last
            self._sift_down(0)
        return top

    def peek(self):
        if not self._data:
            raise IndexError("peek at an empty heap")
        return self._data[0]

    def copy(self):
        clone = MinHeap()
        clone._data = list(self._data)
        return clone

    def _sift_up(self, i):
        data = self._data
        while i > 0:
            parent = (i - 1) // 2
            if data[i] < data[parent]:
                data[i], data[parent] = data[parent], data[i]
                i = parent
            else:
                break

    def _sift_down(self, i):
        data = self._data
        n = len(data)
        while True:
            left, right, smallest = 2 * i + 1, 2 * i + 2, i
            if left < n and data[left] < data[smallest]:
                smallest = left
            if right < n and data[right] < data[smallest]:
                smallest = right
            if smallest == i:
                break
            data[i], data[smallest] = data[smallest], data[i]
            i = smallest


def _sequence_number(animal_id):
    """'SC-1004' -> 1004. Used as a tie-breaker so equal urgencies stay first-come first-served."""
    try:
        return int(str(animal_id).split("-")[-1])
    except ValueError:
        return 0


class TriageHeap:
    """Priority queue of rescue cases: most urgent first, oldest first on ties.

    Each entry is the tuple (urgency_rank, sequence_number, animal_id).
    Tuples compare element by element, which gives exactly that ordering.
    """

    def __init__(self, animals=None):
        entries = [self._entry(a) for a in (animals or [])]
        self._heap = MinHeap(entries)

    @staticmethod
    def _entry(animal):
        rank = URGENCY_RANK.get(animal["Urgency"], len(URGENCY_RANK))
        return (rank, _sequence_number(animal["ID"]), animal["ID"])

    def __len__(self):
        return len(self._heap)

    def push_case(self, animal):
        self._heap.push(self._entry(animal))

    def pop_case(self):
        """Remove and return the animal ID of the most urgent case."""
        return self._heap.pop()[2]

    def peek_case(self):
        """Return (without removing) the animal ID of the most urgent case."""
        return self._heap.peek()[2]

    def ordered_ids(self):
        """All IDs from most to least urgent, without destroying the heap (heap-sort on a copy)."""
        clone = self._heap.copy()
        return [clone.pop()[2] for _ in range(len(clone))]


# ======================================================================
# BACKEND: animal_hash
# ======================================================================
class AnimalHashTable:
    def __init__(self, capacity=8, max_load=0.75):
        self._capacity = max(4, capacity)
        self._max_load = max_load
        self._buckets = [[] for _ in range(self._capacity)]
        self._size = 0

    # ---- hashing -------------------------------------------------------------
    @staticmethod
    def _hash_text(key):
        """djb2 string hash (hash = hash * 33 + char), kept to 32 bits."""
        h = 5381
        for ch in str(key):
            h = ((h << 5) + h + ord(ch)) & 0xFFFFFFFF
        return h

    def _index(self, key):
        return self._hash_text(key) % self._capacity

    # ---- core operations -----------------------------------------------------
    def put(self, key, value):
        bucket = self._buckets[self._index(key)]
        for pair in bucket:
            if pair[0] == key:          # key already present -> overwrite
                pair[1] = value
                return
        bucket.append([key, value])
        self._size += 1
        if self._size / self._capacity > self._max_load:
            self._resize()

    def get(self, key, default=None):
        for k, v in self._buckets[self._index(key)]:
            if k == key:
                return v
        return default

    def remove(self, key):
        bucket = self._buckets[self._index(key)]
        for i, pair in enumerate(bucket):
            if pair[0] == key:
                del bucket[i]
                self._size -= 1
                return True
        return False

    def _resize(self):
        old_buckets = self._buckets
        self._capacity *= 2
        self._buckets = [[] for _ in range(self._capacity)]
        for bucket in old_buckets:
            for key, value in bucket:
                self._buckets[self._index(key)].append([key, value])

    # ---- conveniences --------------------------------------------------------
    def __contains__(self, key):
        return any(k == key for k, _ in self._buckets[self._index(key)])

    def __len__(self):
        return self._size

    def items(self):
        for bucket in self._buckets:
            for key, value in bucket:
                yield key, value

    def values(self):
        return [v for _, v in self.items()]

    def keys(self):
        return [k for k, _ in self.items()]

    @property
    def capacity(self):
        return self._capacity

    @property
    def load_factor(self):
        return self._size / self._capacity


# ======================================================================
# BACKEND: food_queue
# ======================================================================
class _FoodNode:
    __slots__ = ("data", "next")

    def __init__(self, data):
        self.data = data
        self.next = None


class FoodQueue:
    def __init__(self):
        self._head = None
        self._tail = None
        self._size = 0

    def __len__(self):
        return self._size

    def __iter__(self):
        node = self._head
        while node:
            yield node.data
            node = node.next

    def enqueue(self, offer):
        """Add an offer at the tail. O(1)."""
        node = _FoodNode(offer)
        if self._tail is None:
            self._head = self._tail = node
        else:
            self._tail.next = node
            self._tail = node
        self._size += 1

    def dequeue(self):
        """Remove and return the oldest offer. O(1)."""
        if self._head is None:
            raise IndexError("dequeue from an empty queue")
        node = self._head
        self._head = node.next
        if self._head is None:
            self._tail = None
        self._size -= 1
        return node.data

    def peek(self):
        """Return the oldest offer without removing it, or None if empty."""
        return self._head.data if self._head else None

    def remove(self, offer_id):
        """Remove an offer from anywhere in the queue (e.g. cancelled). O(n)."""
        prev, node = None, self._head
        while node:
            if node.data["Offer ID"] == offer_id:
                if prev:
                    prev.next = node.next
                else:
                    self._head = node.next
                if node is self._tail:
                    self._tail = prev
                self._size -= 1
                return True
            prev, node = node, node.next
        return False

    def to_list(self):
        return list(self)


# ======================================================================
# BACKEND: medical_log
# ======================================================================
class _LogNode:
    __slots__ = ("entry", "next")

    def __init__(self, entry):
        self.entry = entry
        self.next = None


class MedicalLog:
    def __init__(self):
        self._head = None
        self._tail = None
        self._size = 0

    def __len__(self):
        return self._size

    def __iter__(self):
        """Oldest entry first."""
        node = self._head
        while node:
            yield node.entry
            node = node.next

    def append(self, entry):
        node = _LogNode(entry)
        if self._tail is None:
            self._head = self._tail = node
        else:
            self._tail.next = node
            self._tail = node
        self._size += 1

    def to_list(self, newest_first=True):
        entries = list(self)
        return entries[::-1] if newest_first else entries

    def for_animal(self, animal_id, newest_first=True):
        entries = [e for e in self if e["Animal ID"] == animal_id]
        return entries[::-1] if newest_first else entries

    def remove_animal(self, animal_id):
        """Unlink every entry of one animal (used when the animal record is deleted). Returns the count."""
        removed = 0
        previous = None
        node = self._head
        while node:
            following = node.next
            if node.entry["Animal ID"] == animal_id:
                if previous is None:
                    self._head = following
                else:
                    previous.next = following
                removed += 1
            else:
                previous = node
            node = following
        self._tail = previous
        self._size -= removed
        return removed


# ======================================================================
# BACKEND: route_graph
# ======================================================================
INFINITY = float("inf")


class RouteGraph:
    def __init__(self):
        self._adj = {}

    # ---- building the map ----------------------------------------------------
    def add_location(self, name):
        self._adj.setdefault(name, {})

    def add_road(self, a, b, km):
        """Add (or update) a two-way road between two locations."""
        if a == b:
            raise ValueError("A road must connect two different locations.")
        if km <= 0:
            raise ValueError("Distance must be greater than zero.")
        self.add_location(a)
        self.add_location(b)
        self._adj[a][b] = float(km)
        self._adj[b][a] = float(km)

    def has_location(self, name):
        return name in self._adj

    def locations(self):
        return sorted(self._adj)

    def roads(self):
        """Each road once, as (a, b, km) with a < b."""
        seen = []
        for a, neighbours in self._adj.items():
            for b, km in neighbours.items():
                if a < b:
                    seen.append((a, b, km))
        return sorted(seen)

    # ---- shortest path -------------------------------------------------------
    def _dijkstra(self, start):
        dist = {node: INFINITY for node in self._adj}
        prev = {}
        dist[start] = 0.0
        heap = MinHeap([(0.0, start)])
        while len(heap):
            d, node = heap.pop()
            if d > dist[node]:           # stale heap entry, a shorter route was already found
                continue
            for neighbour, km in self._adj[node].items():
                candidate = d + km
                if candidate < dist[neighbour]:
                    dist[neighbour] = candidate
                    prev[neighbour] = node
                    heap.push((candidate, neighbour))
        return dist, prev

    def shortest_path(self, start, end):
        """Return (distance_km, [locations...]) or None if there is no route."""
        if start not in self._adj or end not in self._adj:
            raise ValueError("Both locations must exist on the map.")
        dist, prev = self._dijkstra(start)
        if dist[end] == INFINITY:
            return None
        path = [end]
        while path[-1] != start:
            path.append(prev[path[-1]])
        path.reverse()
        return dist[end], path

    # ---- multi-stop tour -----------------------------------------------------
    def tour(self, start, stops):
        """Visit every stop using the nearest-neighbour heuristic (a fast, good-enough greedy).

        From the current position, always drive to the closest stop not yet visited.
        This is NOT guaranteed optimal (that is the travelling-salesman problem), but it is
        simple and sensible for a handful of rescue calls.
        Returns {"order", "legs", "total_km", "unreachable"}.
        """
        if start not in self._adj:
            raise ValueError("Starting point must exist on the map.")
        remaining = [s for s in dict.fromkeys(stops) if s != start and s in self._adj]
        current, legs, total, order, unreachable = start, [], 0.0, [start], []
        while remaining:
            dist, prev = self._dijkstra(current)
            reachable = [s for s in remaining if dist[s] < INFINITY]
            if not reachable:
                unreachable.extend(remaining)
                break
            nxt = min(reachable, key=lambda s: dist[s])
            path = [nxt]
            while path[-1] != current:
                path.append(prev[path[-1]])
            path.reverse()
            legs.append({"from": current, "to": nxt, "km": dist[nxt], "path": path})
            total += dist[nxt]
            order.append(nxt)
            remaining.remove(nxt)
            current = nxt
        return {"order": order, "legs": legs, "total_km": total, "unreachable": unreachable}


# ======================================================================
# BACKEND: storage
# ======================================================================
def load_json(path):
    """Return the parsed JSON, or None if the file does not exist. Raises ValueError if corrupt."""
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)          # json.JSONDecodeError is a ValueError


def save_json(path, data):
    """Write atomically: write a temp file, then replace. A crash can never leave half a file."""
    folder = os.path.dirname(os.path.abspath(path))
    os.makedirs(folder, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=folder, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2, ensure_ascii=False)
        os.replace(tmp_path, path)
    except BaseException:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise


# ======================================================================
# BACKEND: auth
# ======================================================================
ROLES = ("admin", "user")
USERNAME_RULE = re.compile(r"^[a-z0-9_]{3,20}$")
MIN_PASSWORD = 6
MAX_PASSWORD = 64
ITERATIONS = 200_000          # slows down password guessing
MAX_FAILURES = 5              # wrong passwords allowed in a row ...
LOCK_SECONDS = 60             # ... before that username is locked for a minute


def _hash(password, salt):
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, ITERATIONS).hex()


def _check_username(username):
    name = str(username or "").strip().lower()
    if not USERNAME_RULE.match(name):
        raise ValueError("Username must be 3-20 characters: letters, numbers or underscore only.")
    return name


def _check_password(password):
    password = str(password or "")
    if len(password) < MIN_PASSWORD:
        raise ValueError(f"Password must be at least {MIN_PASSWORD} characters.")
    if len(password) > MAX_PASSWORD:
        raise ValueError(f"Password must be at most {MAX_PASSWORD} characters.")
    return password


class UserStore:
    def __init__(self, path):
        self._path = path
        self._lock = threading.RLock()
        self._failures = {}                       # username -> (count, time of last failure)
        self._users = self._load()

    # ---- file handling -------------------------------------------------------
    def _load(self):
        try:
            with open(self._path, encoding="utf-8") as handle:
                data = json.load(handle)
            users = data["users"]
            for name, record in users.items():
                if record["role"] not in ROLES:
                    raise ValueError("bad role")
                bytes.fromhex(record["salt"])
            return users
        except FileNotFoundError:
            return {}
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            try:                                   # unreadable file: keep a copy, start without accounts
                os.replace(self._path, self._path + ".corrupt")
            except OSError:
                pass
            return {}

    def _save(self):
        folder = os.path.dirname(self._path) or "."
        os.makedirs(folder, exist_ok=True)
        handle, temp_path = tempfile.mkstemp(dir=folder, suffix=".tmp")
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as out:
                json.dump({"users": self._users}, out, indent=2)
            os.replace(temp_path, self._path)      # atomic: never leaves a half-written file
        except BaseException:
            try:
                os.remove(temp_path)
            except OSError:
                pass
            raise

    # ---- queries ---------------------------------------------------------------
    def has_users(self):
        with self._lock:
            return bool(self._users)

    def has_admin(self):
        with self._lock:
            return any(u["role"] == "admin" for u in self._users.values())

    def exists(self, username):
        with self._lock:
            return str(username or "").strip().lower() in self._users

    def role_of(self, username):
        with self._lock:
            record = self._users.get(str(username or "").strip().lower())
            return record["role"] if record else None

    def list_users(self):
        with self._lock:
            return [{"Username": name, "Role": record["role"], "Created": record.get("created", "")}
                    for name, record in sorted(self._users.items())]

    # ---- changes ---------------------------------------------------------------
    def add_user(self, username, password, role="user"):
        name = _check_username(username)
        password = _check_password(password)
        if role not in ROLES:
            raise ValueError("Role must be admin or user.")
        with self._lock:
            if name in self._users:
                raise ValueError("That username is already taken.")
            salt = os.urandom(16)
            self._users[name] = {"role": role, "salt": salt.hex(), "hash": _hash(password, salt),
                                 "created": time.strftime("%Y-%m-%d")}
            self._save()
        return {"Username": name, "Role": role}

    def delete_user(self, username):
        name = str(username or "").strip().lower()
        with self._lock:
            record = self._users.get(name)
            if record is None:
                raise ValueError("No such user.")
            if record["role"] == "admin" and sum(u["role"] == "admin" for u in self._users.values()) == 1:
                raise ValueError("You cannot delete the only administrator.")
            del self._users[name]
            self._save()

    def set_password(self, username, new_password):
        name = str(username or "").strip().lower()
        new_password = _check_password(new_password)
        with self._lock:
            record = self._users.get(name)
            if record is None:
                raise ValueError("No such user.")
            salt = os.urandom(16)
            record["salt"], record["hash"] = salt.hex(), _hash(new_password, salt)
            self._save()

    def verify(self, username, password):
        """Return the role if the username and password are right, otherwise None.
        Raises ValueError when the username is temporarily locked after repeated wrong passwords."""
        name = str(username or "").strip().lower()
        with self._lock:
            count, last = self._failures.get(name, (0, 0.0))
            if count >= MAX_FAILURES:
                wait = LOCK_SECONDS - (time.time() - last)
                if wait > 0:
                    raise ValueError(f"Too many wrong passwords. Try again in {int(wait) + 1} seconds.")
                count = 0
            record = self._users.get(name)
            # always do the hashing work, so a wrong username and a wrong password take equal time
            salt = bytes.fromhex(record["salt"]) if record else b"\0" * 16
            candidate = _hash(str(password or "")[:MAX_PASSWORD], salt)
            stored = record["hash"] if record else "0" * 64
            if record and hmac.compare_digest(candidate, stored):
                self._failures.pop(name, None)
                return record["role"]
            self._failures[name] = (count + 1, time.time())
            return None


# ======================================================================
# BACKEND: controller
# ======================================================================
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


_NAME_PUNCTUATION = " .,'-&()/"


def _is_letter(ch):
    """A letter is an English letter or ANY non-ASCII character (so Hindi etc. is accepted).
    The C++ engine uses the same rule on bytes, so both engines agree."""
    return ("a" <= ch <= "z") or ("A" <= ch <= "Z") or ord(ch) > 127


def _clean_name(value, field, max_len=MAX_TEXT):
    """For names and places: required, must contain a letter (so '123' is rejected), and may only
    use letters, digits, spaces and . , ' - & ( ) /"""
    text = _clean(value, field, True, max_len)
    if not any(_is_letter(ch) for ch in text):
        raise ValueError(f"{field} must contain letters. A name cannot be only numbers or symbols, like 123.")
    for ch in text:
        if not (_is_letter(ch) or "0" <= ch <= "9" or ch in _NAME_PUNCTUATION):
            raise ValueError(f"{field} can only use letters, numbers, spaces and . , ' - & ( ) /")
    return text


def _clean_text(value, field, required=True, max_len=MAX_TEXT):
    """For descriptions: must contain a letter when filled in, but any punctuation is allowed."""
    text = _clean(value, field, required, max_len)
    if text and not any(_is_letter(ch) for ch in text):
        raise ValueError(f"{field} must contain letters, not only numbers or symbols.")
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
        name = _clean_name(name, "Animal name / identifier")
        location = _clean_name(location, "Location")
        condition = _clean_text(condition, "Condition", required=False) or "Not assessed"
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
        description = _clean_name(description, "Animal description")
        location = _clean_name(location, "Location")
        _choice(urgency, URGENCY_LEVELS, "Urgency")
        _choice(species, SPECIES, "Species")
        condition = (_clean_text(condition, "Condition", required=False)
                     or _clean_text(details, "Details", required=False, max_len=MAX_NOTES)
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
        name = _clean_name(name, "Animal name / identifier")
        location = _clean_name(location, "Location")
        condition = _clean_text(condition, "Condition", required=False) or "Not assessed"
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
        donor = _clean_name(donor, "Donor / organization")
        food = _clean_text(food, "Food description")
        pickup_area = _clean_name(pickup_area, "Pickup area")
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
            "Treatment": _clean_text(treatment, "Treatment / examination"),
            "Volunteer": _clean_name(volunteer, "Volunteer / care provider"),
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
        a, b = _clean_name(a, "First location"), _clean_name(b, "Second location")
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


# ======================================================================
# FRONTEND: Streamlit pages
# ======================================================================
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
    """One backend (and one set of data structures) shared by every rerun and session."""
    return StrayCareController(data_path=DATA_FILE), ""


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
