import json
import os
from datetime import datetime, timezone


DATA_DIR = os.path.join("memory")
DATA_FILE = os.path.join(DATA_DIR, "data.json")
MAX_RUNS = 5
DEFAULT_SESSION = "default_session"


def _ensure_store():
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, "w", encoding="utf-8") as file:
            json.dump({}, file, indent=2)


def _read_store():
    _ensure_store()
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)
            if isinstance(data, dict):
                return data
            # Backward compatibility for old list-only schema.
            if isinstance(data, list):
                return {DEFAULT_SESSION: data[-MAX_RUNS:]}
    except Exception:
        pass
    return {}


def _write_store(store):
    with open(DATA_FILE, "w", encoding="utf-8") as file:
        json.dump(store, file, indent=2)


def get_runs(session_id=DEFAULT_SESSION):
    """
    Return persisted runs for one session (last 5).
    """
    sid = str(session_id or DEFAULT_SESSION)
    store = _read_store()
    runs = store.get(sid, [])
    if not isinstance(runs, list):
        return []
    return runs[-MAX_RUNS:]


def save_run(session_id, run_data):
    """
    Save one run entry for a session and keep only last 5 records.
    Expected shape: {topic, burn, runway, timestamp}
    """
    sid = str(session_id or DEFAULT_SESSION)
    store = _read_store()

    entry = {
        "topic": str(run_data.get("topic", "N/A")),
        "burn": float(run_data.get("burn", 0)),
        "runway": float(run_data.get("runway", 0)),
        "timestamp": run_data.get("timestamp") or datetime.now(timezone.utc).isoformat(),
    }

    session_runs = store.get(sid, [])
    if not isinstance(session_runs, list):
        session_runs = []
    session_runs.append(entry)
    store[sid] = session_runs[-MAX_RUNS:]

    _write_store(store)
