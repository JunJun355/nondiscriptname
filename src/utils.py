"""Utility functions for PollEV automation."""
import json
from datetime import datetime, time
from typing import Any

from config import CLASSES_FILE


def load_classes() -> dict[str, Any]:
    """Load class definitions from JSON file."""
    with open(CLASSES_FILE, "r") as f:
        return json.load(f)


def parse_time(time_str: str) -> time | None:
    """Parse HH:MM:SS string to time object. Returns None if invalid."""
    if not time_str:
        return None
    try:
        return datetime.strptime(time_str, "%H:%M:%S").time()
    except (ValueError, TypeError):
        return None


def is_within_class_time(class_info: dict[str, Any], now: datetime | None = None) -> bool:
    """Check if current time is within class start and end times.
    Returns True if start_time is invalid (always active)."""
    if now is None:
        now = datetime.now()
    
    start = parse_time(class_info.get("start_time", ""))
    end = parse_time(class_info.get("end_time", ""))
    current = now.time()
    
    # If start_time is invalid, class is always "active"
    if start is None:
        return True
    
    # If end_time is invalid, only check start
    if end is None:
        return current >= start
    
    return start <= current <= end


def get_active_class(classes: dict[str, Any], now: datetime | None = None) -> tuple[str, dict] | None:
    """Return the first class that is currently active, or None."""
    if now is None:
        now = datetime.now()
    
    for name, info in classes.items():
        if is_within_class_time(info, now):
            return (name, info)
    return None


def time_until_next_class(classes: dict[str, Any], now: datetime | None = None) -> tuple[str, float] | None:
    """Return (class_name, seconds_until_start) for the next upcoming class today."""
    if now is None:
        now = datetime.now()
    
    current = now.time()
    best = None
    best_delta = None
    
    for name, info in classes.items():
        start = parse_time(info["start_time"])
        if start > current:
            # Calculate seconds until start
            today = now.date()
            start_dt = datetime.combine(today, start)
            delta = (start_dt - now).total_seconds()
            if best_delta is None or delta < best_delta:
                best = name
                best_delta = delta
    
    if best is not None:
        return (best, best_delta)
    return None
