import os
import requests


TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")


def search_web(query: str):
    url = "https://api.tavily.com/search"

    payload = {
        "api_key": TAVILY_API_KEY,
        "query": query,
        "search_depth": "basic",
        "include_answer": True,
        "max_results": 3,
    }

    response = requests.post(url, json=payload, timeout=20)
    response.raise_for_status()
    data = response.json()

    results = []
    for r in data.get("results", []):
        results.append(f"{r.get('title')}: {r.get('content')}")

    return {
        "summary": "\n".join(results),
        "sources": data.get("results", []),
    }
