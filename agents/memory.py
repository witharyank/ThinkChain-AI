import json
import os
import re

# File path where memory is stored
MEMORY_FILE = os.path.join("memory", "memory.json")

# Maximum number of memory entries to keep
MAX_MEMORY_ENTRIES = 10


def _clean_text(value: str) -> str:
    """
    Cleans input text by:
    - Removing markdown (**)
    - Replacing carriage returns
    - Removing extra spaces
    """
    if not value:
        return ""
    text = str(value).replace("**", " ").replace("\r", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _extract_first_sentence(text: str) -> str:
    """
    Extracts the first sentence from the given text.
    - Cleans the text first
    - Splits by punctuation (. ! ?)
    - Limits sentence length to 140 characters
    """
    cleaned = _clean_text(text)
    if not cleaned:
        return ""

    # Split into sentences using regex
    sentence = re.split(r"(?<=[.!?])\s+", cleaned)[0].strip(" .")

    # Trim if too long
    if len(sentence) > 140:
        sentence = sentence[:137].rstrip() + "..."

    return sentence


def _normalize_score(value) -> int:
    """
    Normalizes score to integer between 0 and 100.
    - If already int → clamp between 0–100
    - If string → extract first number
    - Default → 70
    """
    if isinstance(value, int):
        return max(0, min(100, value))

    text = _clean_text(value)

    # Extract number from text
    match = re.search(r"([0-9]{1,3})", text)
    score = int(match.group(1)) if match else 70

    return max(0, min(100, score))


def _normalize_entry(item: dict) -> dict:
    """
    Converts old/new schema into a unified format:

    Old format:
        {"input": "...", "decision": "..."}

    New format:
        {"topic": "...", "strategy": "...", "score": int}

    Ensures all fields are present and cleaned.
    """
    # Extract topic (fallback to old "input")
    topic = _clean_text(item.get("topic") or item.get("input") or "")

    # Extract strategy
    strategy = _clean_text(item.get("strategy") or "")

    # Normalize score
    score = _normalize_score(item.get("score", 70))

    # If strategy missing but decision exists (old format)
    if not strategy and item.get("decision"):
        strategy = _extract_first_sentence(item.get("decision", ""))

        # Try extracting score from decision text
        decision_text = _clean_text(item.get("decision", ""))
        score = _normalize_score(decision_text)

    return {
        "topic": topic or "N/A",
        "strategy": strategy or "No strategy available",
        "score": score,
    }


def _dedupe_and_trim(entries: list[dict]) -> list[dict]:
    """
    Removes duplicate entries and keeps only latest entries.
    - Uses (topic, strategy, score) as uniqueness key
    - Trims list to MAX_MEMORY_ENTRIES
    """
    seen = set()
    result = []

    for raw in entries:
        entry = _normalize_entry(raw)

        # Unique key for deduplication
        key = (
            entry["topic"].lower(),
            entry["strategy"].lower(),
            int(entry["score"]),
        )

        if key in seen:
            continue

        seen.add(key)
        result.append(entry)

    # Keep only the most recent entries
    return result[-MAX_MEMORY_ENTRIES:]


def load_memory() -> list[dict]:
    """
    Loads memory from JSON file.
    - Returns empty list if file not found or invalid
    - Ensures data is cleaned and deduplicated
    """
    try:
        with open(MEMORY_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)
    except Exception:
        return []

    if not isinstance(data, list):
        return []

    return _dedupe_and_trim(data)


def save_memory(data: dict) -> None:
    """
    Saves a new memory entry:
    - Loads existing memory
    - Adds new normalized entry
    - Deduplicates and trims
    - Writes back to file
    """
    memory = load_memory()

    # Add new entry after normalization
    memory.append(_normalize_entry(data))

    # Remove duplicates and limit size
    memory = _dedupe_and_trim(memory)

    # Save updated memory back to file
    with open(MEMORY_FILE, "w", encoding="utf-8") as file:
        json.dump(memory, file, indent=2)