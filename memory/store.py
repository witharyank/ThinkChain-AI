import json
import os
from datetime import datetime, timezone


DATA_DIR = os.path.join("memory")
DATA_FILE = os.path.join(DATA_DIR, "data.json")
MAX_RUNS = 5


def _ensure_store():
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, "w", encoding="utf-8") as file:
            json.dump([], file, indent=2)


def get_runs():
    """
    Return persisted runs (latest first in storage order), max 5.
    """
    _ensure_store()
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)
    except Exception:
        return []

    if not isinstance(data, list):
        return []
    return data[-MAX_RUNS:]


def save_run(data):
    """
    Save one run entry and keep only last 5 records.
    Expected shape: {topic, burn, runway, timestamp}
    """
    _ensure_store()
    runs = get_runs()

    entry = {
        "topic": str(data.get("topic", "N/A")),
        "burn": float(data.get("burn", 0)),
        "runway": float(data.get("runway", 0)),
        "timestamp": data.get("timestamp") or datetime.now(timezone.utc).isoformat(),
    }

    runs.append(entry)
    runs = runs[-MAX_RUNS:]

    with open(DATA_FILE, "w", encoding="utf-8") as file:
        json.dump(runs, file, indent=2)
