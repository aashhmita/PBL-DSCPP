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
