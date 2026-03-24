import json
import os
import re


MEMORY_FILE = os.path.join("memory", "memory.json")
MAX_MEMORY_ENTRIES = 10


def _clean_text(value: str) -> str:
    if not value:
        return ""
    text = str(value).replace("**", " ").replace("\r", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _extract_first_sentence(text: str) -> str:
    cleaned = _clean_text(text)
    if not cleaned:
        return ""
    sentence = re.split(r"(?<=[.!?])\s+", cleaned)[0].strip(" .")
    if len(sentence) > 140:
        sentence = sentence[:137].rstrip() + "..."
    return sentence


def _normalize_score(value) -> int:
    if isinstance(value, int):
        return max(0, min(100, value))
    text = _clean_text(value)
    match = re.search(r"([0-9]{1,3})", text)
    score = int(match.group(1)) if match else 70
    return max(0, min(100, score))


def _normalize_entry(item: dict) -> dict:
    # Backward-compatible mapping from old memory schema:
    # - old: {"input": "...", "decision": "..."}
    # - new: {"topic": "...", "strategy": "...", "score": int}
    topic = _clean_text(item.get("topic") or item.get("input") or "")
    strategy = _clean_text(item.get("strategy") or "")
    score = _normalize_score(item.get("score", 70))

    if not strategy and item.get("decision"):
        strategy = _extract_first_sentence(item.get("decision", ""))
        decision_text = _clean_text(item.get("decision", ""))
        score = _normalize_score(decision_text)

    return {
        "topic": topic or "N/A",
        "strategy": strategy or "No strategy available",
        "score": score,
    }


def _dedupe_and_trim(entries: list[dict]) -> list[dict]:
    seen = set()
    result = []
    for raw in entries:
        entry = _normalize_entry(raw)
        key = (
            entry["topic"].lower(),
            entry["strategy"].lower(),
            int(entry["score"]),
        )
        if key in seen:
            continue
        seen.add(key)
        result.append(entry)

    # Keep latest entries only.
    return result[-MAX_MEMORY_ENTRIES:]


def load_memory() -> list[dict]:
    try:
        with open(MEMORY_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)
    except Exception:
        return []

    if not isinstance(data, list):
        return []

    return _dedupe_and_trim(data)


def save_memory(data: dict) -> None:
    memory = load_memory()
    memory.append(_normalize_entry(data))
    memory = _dedupe_and_trim(memory)

    with open(MEMORY_FILE, "w", encoding="utf-8") as file:
        json.dump(memory, file, indent=2)
