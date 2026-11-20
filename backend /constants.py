"""Shared vocabulary used by the backend and the Streamlit frontend."""

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
