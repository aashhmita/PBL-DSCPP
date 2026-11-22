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
