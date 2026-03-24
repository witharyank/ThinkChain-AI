from __future__ import annotations

import os
import time
from typing import TypedDict

import groq
from dotenv import load_dotenv
from groq import Groq
from langgraph.graph import END, StateGraph

from agents.memory import load_memory, save_memory
from workflows.formatter import clean_text, format_output, normalize_confidence

# Initialize environment and LLM client.
load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

PRIMARY_MODEL = "llama-3.3-70b-versatile"
BACKUP_MODEL = "llama-3.1-8b-instant"
MAX_RETRIES = 2
RETRY_DELAY_SECONDS = 2


class AgentState(TypedDict, total=False):
    input: str
    memory: list[dict]
    data: str
    proposal: str
    critique: str
    simulation: str
    decision: str
    final_output: dict


def memory_context(memory: list[dict]) -> str:
    """Build compact memory context for prompt injection."""
    if not memory:
        return "No prior successful strategies."

    items = []
    for entry in memory[-10:]:
        topic = clean_text(str(entry.get("topic", "")))
        strategy = clean_text(str(entry.get("strategy", "")))
        score = normalize_confidence(str(entry.get("score", 85)))
        if topic and strategy:
            items.append(f"{topic}: {strategy} (score {score})")
    return "; ".join(items) if items else "No prior successful strategies."


def call_groq_with_retry(prompt: str, fallback_text: str, rate_limit_text: str) -> str:
    """
    Call Groq safely with retries and model fallback.
    - Retries up to 2 times per model.
    - Sleeps 2 seconds between retries.
    - On repeated rate limit, switches to backup model.
    """
    models = [PRIMARY_MODEL, BACKUP_MODEL]
    saw_rate_limit = False

    for model_name in models:
        for attempt in range(MAX_RETRIES + 1):
            try:
                response = client.chat.completions.create(
                    model=model_name,
                    messages=[{"role": "user", "content": prompt}],
                )
                return response.choices[0].message.content
            except groq.RateLimitError:
                saw_rate_limit = True
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_DELAY_SECONDS)
                    continue
                break
            except Exception:
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_DELAY_SECONDS)
                    continue
                return fallback_text

    if saw_rate_limit:
        return rate_limit_text
    return fallback_text


def memory_agent(state: AgentState):
    """Load memory first so all downstream nodes can leverage it."""
    try:
        return {"memory": load_memory()}
    except Exception:
        return {"memory": []}


def research_agent(state: AgentState):
    prompt = (
        f"Research about: {state.get('input', '')}\n"
        f"Based on past successful strategies: {memory_context(state.get('memory', []))}\n"
        "Keep it concise and actionable."
    )
    try:
        data_text = call_groq_with_retry(
            prompt=prompt,
            fallback_text="Error occurred while generating research.",
            rate_limit_text="Rate limit reached. Try again later.",
        )
        return {"data": data_text}
    except groq.RateLimitError:
        return {"data": "Rate limit reached. Try again later."}
    except Exception:
        return {"data": "Error occurred while generating research."}


def proposer_agent(state: AgentState):
    prompt = (
        f"Based on this research:\n{state.get('data', '')}\n\n"
        f"Based on past successful strategies: {memory_context(state.get('memory', []))}\n"
        "Suggest best strategy in short bullet points."
    )
    try:
        proposal_text = call_groq_with_retry(
            prompt=prompt,
            fallback_text="Using cached/basic strategy",
            rate_limit_text="Using cached/basic strategy",
        )
        return {"proposal": proposal_text}
    except groq.RateLimitError:
        return {"proposal": "Using cached/basic strategy"}
    except Exception:
        return {"proposal": "Using cached/basic strategy"}


def critic_agent(state: AgentState):
    prompt = f"Criticize this strategy briefly:\n{state.get('proposal', '')}"
    try:
        critique_text = call_groq_with_retry(
            prompt=prompt,
            fallback_text="Skipped due to API limit",
            rate_limit_text="Skipped due to API limit",
        )
        return {"critique": critique_text}
    except groq.RateLimitError:
        return {"critique": "Skipped due to API limit"}
    except Exception:
        return {"critique": "Skipped due to API limit"}


def simulation_agent(state: AgentState):
    prompt = (
        "Given this strategy:\n"
        f"{state.get('proposal', '')}\n\n"
        "Predict short values only:\n"
        "- ROI (%)\n"
        "- Risk level (Low/Medium/High)\n"
        "- Time to results"
    )
    try:
        simulation_text = call_groq_with_retry(
            prompt=prompt,
            fallback_text="ROI: 20-30%, Risk level: Medium, Time: 1-3 months",
            rate_limit_text="ROI: 20-30%, Risk level: Medium, Time: 1-3 months",
        )
        return {"simulation": simulation_text}
    except groq.RateLimitError:
        return {"simulation": "ROI: 20-30%, Risk level: Medium, Time: 1-3 months"}
    except Exception:
        return {"simulation": "ROI: 20-30%, Risk level: Medium, Time: 1-3 months"}


def decision_agent(state: AgentState):
    prompt = (
        f"Research:\n{state.get('data', '')}\n\n"
        f"Proposal:\n{state.get('proposal', '')}\n\n"
        f"Critique:\n{state.get('critique', '')}\n\n"
        f"Simulation:\n{state.get('simulation', '')}\n\n"
        "Provide a concise final strategy and confidence score (0-100)."
    )
    try:
        decision_text = call_groq_with_retry(
            prompt=prompt,
            fallback_text="Fallback decision. Confidence score: 50",
            rate_limit_text="Fallback decision. Confidence score: 50",
        )
        return {"decision": decision_text}
    except groq.RateLimitError:
        return {"decision": "Fallback decision. Confidence score: 50"}
    except Exception:
        return {"decision": "Fallback decision. Confidence score: 50"}


def format_output_agent(state: AgentState):
    """
    Always produce strict UI-ready JSON, even when upstream used fallbacks.
    """
    try:
        final_output = format_output(
            topic=state.get("input", ""),
            raw_summary=state.get("data", ""),
            raw_actions=state.get("proposal", ""),
            raw_critique=state.get("critique", ""),
            raw_simulation=state.get("simulation", ""),
            raw_decision=state.get("decision", ""),
        )
    except Exception:
        final_output = {
            "topic": clean_text(state.get("input", "")) or "N/A",
            "strategy_summary": "Rate limit reached. Try again later.",
            "top_actions": [
                "Review monthly expenses and cut low value costs",
                "Pause noncritical hiring until cash flow stabilizes",
                "Renegotiate contracts with vendors for better terms",
                "Prioritize high ROI channels for revenue growth",
                "Track burn runway and weekly net cash movement",
            ],
            "metrics": {
                "burn_rate": "Monthly net cash outflow",
                "runway": "Months of cash left",
                "cash_flow": "Net cash movement",
                "operating_expenses": "Total recurring costs",
            },
            "risk_notes": [
                "Avoid cutting essential growth investments",
                "Monitor team productivity impact",
            ],
            "expected_impact": {
                "roi": "20-30%",
                "risk_level": "Medium",
                "time_to_results": "1-3 months",
            },
            "confidence_score": 50,
        }

    # Persist compact learning memory for future prompts.
    try:
        save_memory(
            {
                "topic": final_output["topic"],
                "strategy": final_output["strategy_summary"],
                "score": final_output["confidence_score"],
            }
        )
    except Exception:
        pass

    return {"final_output": final_output}


# Build and compile workflow graph.
builder = StateGraph(AgentState)
builder.add_node("memory", memory_agent)
builder.add_node("research", research_agent)
builder.add_node("proposer", proposer_agent)
builder.add_node("critic", critic_agent)
builder.add_node("simulation", simulation_agent)
builder.add_node("decision", decision_agent)
builder.add_node("format_output", format_output_agent)

builder.set_entry_point("memory")
builder.add_edge("memory", "research")
builder.add_edge("research", "proposer")
builder.add_edge("proposer", "critic")
builder.add_edge("critic", "simulation")
builder.add_edge("simulation", "decision")
builder.add_edge("decision", "format_output")
builder.add_edge("format_output", END)

graph = builder.compile()
