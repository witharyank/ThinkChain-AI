from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime, timezone
from typing import Any, Callable, TypedDict

import groq
from dotenv import load_dotenv
from groq import Groq
from langgraph.graph import END, StateGraph

from tools.finance import calculate_burn
from memory.store import get_runs, save_run

load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

PRIMARY_MODEL = "llama-3.3-70b-versatile"
BACKUP_MODEL = "llama-3.1-8b-instant"
MAX_API_RETRIES = 2
MAX_AGENT_RETRIES = 1
RETRY_DELAY_SECONDS = 2
MAX_CRITIC_REVISIONS = 2

DEFAULT_REVENUE = 300000.0
DEFAULT_EXPENSES = 500000.0
DEFAULT_CASH = 2000000.0


class AgentState(TypedDict, total=False):
    input: str
    revenue: float
    expenses: float
    cash: float
    run_history: list[dict]
    data: str
    proposal: str
    critique: str
    critic_score: int
    critic_decision: str
    critic_can_retry: bool
    revision_count: int
    simulation: str
    simulation_data: dict
    finance_inputs: dict
    decision: str
    final_output: dict


def clean_text(text: Any) -> str:
    if text is None:
        return ""
    return re.sub(r"\s+", " ", str(text).replace("\r", " ").strip())


def extract_actions(text: str) -> list[str]:
    lines = []
    skip_prefixes = (
        "based on",
        "overall strategy",
        "improved strategy",
        "final strategy",
        "the improved strategy",
        "strategy",
    )
    for raw in str(text or "").splitlines():
        line = re.sub(r"^\s*(?:[-*]|[0-9]+\.)\s*", "", raw).strip()
        line = line.replace("**", "").replace("...", " ")
        line = clean_text(line)
        if not line:
            continue
        lowered = line.lower()
        if lowered.startswith(skip_prefixes):
            continue
        words = line.split()
        if 6 <= len(words) <= 12:
            lines.append(" ".join(words))
        elif len(words) > 12:
            lines.append(" ".join(words[:12]))

    unique = []
    seen = set()
    for line in lines:
        key = line.lower()
        if key not in seen:
            seen.add(key)
            unique.append(line)
        if len(unique) == 5:
            break

    defaults = [
        "Audit recurring spend and remove low ROI tools",
        "Renegotiate vendor contracts and improve payment terms",
        "Prioritize critical hires and pause nonessential recruitment",
        "Focus marketing on highest converting acquisition channels",
        "Improve invoicing and accelerate customer collections cycle",
    ]
    for item in defaults:
        if len(unique) == 5:
            break
        if item.lower() not in seen:
            unique.append(item)
            seen.add(item.lower())
    return unique[:5]


def confidence_from_critic(critic_score: int) -> int:
    return min(95, max(70, int(critic_score) * 10))


def call_groq_with_retry(prompt: str, fallback_text: str) -> str:
    models = [PRIMARY_MODEL, BACKUP_MODEL]
    for model_name in models:
        for attempt in range(MAX_API_RETRIES + 1):
            try:
                response = client.chat.completions.create(
                    model=model_name,
                    messages=[{"role": "user", "content": prompt}],
                )
                return response.choices[0].message.content or fallback_text
            except groq.RateLimitError:
                if attempt < MAX_API_RETRIES:
                    time.sleep(RETRY_DELAY_SECONDS)
                    continue
                break
            except Exception:
                if attempt < MAX_API_RETRIES:
                    time.sleep(RETRY_DELAY_SECONDS)
                    continue
                return fallback_text
    return fallback_text


def run_with_validation(
    generator: Callable[[], Any],
    validator: Callable[[Any], bool],
    fallback_value: Any,
) -> Any:
    for _ in range(MAX_AGENT_RETRIES + 1):
        try:
            output = generator()
            if validator(output):
                return output
        except Exception:
            pass
    return fallback_value


def similar_run_hint(topic: str, runs: list[dict]) -> str:
    """
    Find a simple similar run using token overlap and return one-line hint.
    """
    topic_tokens = set(re.findall(r"[a-z0-9]+", topic.lower()))
    best = None
    best_score = 0
    for run in runs:
        run_topic = str(run.get("topic", "")).lower()
        run_tokens = set(re.findall(r"[a-z0-9]+", run_topic))
        overlap = len(topic_tokens & run_tokens)
        if overlap > best_score:
            best_score = overlap
            best = run

    if best and best_score > 0:
        return (
            f"Similar topic '{best.get('topic', '')}' had burn {best.get('burn', 0)} "
            f"and runway {best.get('runway', 0)} months."
        )
    return "No directly similar topic found."


def runs_summary(runs: list[dict]) -> str:
    if not runs:
        return "No previous runs."
    recent = runs[-5:]
    chunks = []
    for run in recent:
        chunks.append(
            f"{run.get('topic', 'N/A')}: burn={run.get('burn', 0)}, runway={run.get('runway', 0)} months"
        )
    return "; ".join(chunks)


def parse_critic_payload(raw_text: str) -> dict:
    fallback = {"feedback": "Needs revision for stronger impact clarity.", "score": 5, "decision": "revise"}
    text = clean_text(raw_text)
    if not text:
        return fallback
    try:
        data = json.loads(text)
        score = int(data.get("score", 5))
        decision = str(data.get("decision", "revise")).lower()
        if decision not in {"approve", "revise"}:
            decision = "revise" if score < 6 else "approve"
        return {
            "feedback": clean_text(data.get("feedback", fallback["feedback"])),
            "score": max(0, min(10, score)),
            "decision": decision,
        }
    except Exception:
        score_match = re.search(r"score[^0-9]*([0-9]|10)", text, re.IGNORECASE)
        score = int(score_match.group(1)) if score_match else 5
        decision = "approve" if score >= 6 else "revise"
        return {"feedback": text[:250], "score": max(0, min(10, score)), "decision": decision}


def memory_agent(state: AgentState):
    """
    Load persistent run history and normalize dynamic finance inputs.
    """
    runs = get_runs()
    return {
        "run_history": runs,
        "revision_count": state.get("revision_count", 0),
        "revenue": float(state.get("revenue", DEFAULT_REVENUE)),
        "expenses": float(state.get("expenses", DEFAULT_EXPENSES)),
        "cash": float(state.get("cash", DEFAULT_CASH)),
    }


def research_agent(state: AgentState):
    memory_text = runs_summary(state.get("run_history", []))
    prompt = (
        f"Research enterprise strategy for: {state.get('input', '')}\n"
        f"Previous runs show: {memory_text}\n"
        "Return concise business context and constraints."
    )

    def generate():
        return call_groq_with_retry(prompt, "Rate limit reached. Try again later.")

    data_text = run_with_validation(generate, lambda x: bool(clean_text(x)), "Rate limit reached. Try again later.")
    return {"data": data_text}


def proposer_agent(state: AgentState):
    hint = similar_run_hint(state.get("input", ""), state.get("run_history", []))
    prompt = (
        f"Research context:\n{state.get('data', '')}\n\n"
        f"Previous critique feedback:\n{state.get('critique', '')}\n\n"
        f"Bias instruction from memory: {hint}\n"
        "Propose 5 concise actionable bullet points for business impact."
    )

    def generate():
        return call_groq_with_retry(prompt, "Using cached/basic strategy")

    proposal = run_with_validation(generate, lambda x: bool(clean_text(x)), "Using cached/basic strategy")
    return {"proposal": proposal}


def critic_agent(state: AgentState):
    prompt = (
        "Review the proposal below and respond STRICT JSON only in this format:\n"
        '{"feedback":"...", "score":0-10, "decision":"approve|revise"}\n\n'
        f"Proposal:\n{state.get('proposal', '')}\n\n"
        "Score quality, feasibility, and impact realism."
    )

    def generate():
        raw = call_groq_with_retry(prompt, '{"feedback":"API fallback","score":5,"decision":"revise"}')
        return parse_critic_payload(raw)

    critic = run_with_validation(
        generate,
        lambda x: isinstance(x, dict) and "score" in x and "decision" in x,
        {"feedback": "Fallback critique due to API failure.", "score": 5, "decision": "revise"},
    )

    revision_count = int(state.get("revision_count", 0))
    can_retry = False
    if critic["decision"] == "revise" and revision_count < MAX_CRITIC_REVISIONS:
        revision_count += 1
        can_retry = True

    return {
        "critique": critic["feedback"],
        "critic_score": critic["score"],
        "critic_decision": critic["decision"],
        "critic_can_retry": can_retry,
        "revision_count": revision_count,
    }


def simulation_agent(state: AgentState):
    revenue = float(state.get("revenue", DEFAULT_REVENUE))
    expenses = float(state.get("expenses", DEFAULT_EXPENSES))
    cash = float(state.get("cash", DEFAULT_CASH))

    burn_result = calculate_burn(expenses=expenses, revenue=revenue, cash=cash)
    monthly_burn = float(burn_result["monthly_burn"])
    runway_months = float(burn_result["runway_months"])
    cost_savings_estimate = float(max(monthly_burn * 0.15, 0))

    simulation_data = {
        "monthly_burn": round(monthly_burn, 2),
        "runway_months": round(runway_months, 2),
        "cost_savings_estimate": round(cost_savings_estimate, 2),
    }

    return {
        "simulation": json.dumps(simulation_data),
        "simulation_data": simulation_data,
        "finance_inputs": {
            "revenue": revenue,
            "expenses": expenses,
            "cash": cash,
        },
    }


def decision_agent(state: AgentState):
    sim = state.get("simulation_data", {})
    prompt = (
        "Create a concise final decision paragraph using this data:\n"
        f"Proposal: {state.get('proposal', '')}\n"
        f"Critique: {state.get('critique', '')}\n"
        f"Simulation: {sim}\n"
        "Include confidence score (0-100)."
    )

    def generate():
        return call_groq_with_retry(prompt, "Fallback decision. Confidence score: 60")

    decision = run_with_validation(generate, lambda x: bool(clean_text(x)), "Fallback decision. Confidence score: 60")
    return {"decision": decision}


def build_final_output(state: AgentState) -> dict:
    sim = state.get("simulation_data") or {
        "monthly_burn": 200000.0,
        "runway_months": 10.0,
        "cost_savings_estimate": 30000.0,
    }
    finance_inputs = state.get("finance_inputs") or {
        "revenue": DEFAULT_REVENUE,
        "expenses": DEFAULT_EXPENSES,
        "cash": DEFAULT_CASH,
    }
    current_burn = max(float(sim.get("monthly_burn", 0)), 0)
    savings = max(float(sim.get("cost_savings_estimate", 0)), 0)
    current_runway = float(sim.get("runway_months", 0))

    improved_burn = max(current_burn - savings, 1)
    cash = float(finance_inputs.get("cash", DEFAULT_CASH))
    improved_runway = round(cash / improved_burn, 2) if improved_burn > 0 else current_runway

    decision_text = clean_text(state.get("decision", "Fallback decision. Confidence score: 60"))
    summary_sentence = decision_text.split(".")[0].replace("**", "").strip()
    summary_words = summary_sentence.split()
    if not summary_words:
        summary = "Reduce burn by optimizing pricing, cutting waste, and improving retention."
    elif len(summary_words) <= 20:
        summary = " ".join(summary_words)
    else:
        summary = "Reduce burn by optimizing pricing, cutting waste, and improving retention."

    critic_score = int(state.get("critic_score", 7))
    confidence_score = confidence_from_critic(critic_score)

    return {
        "topic": clean_text(state.get("input", "")) or "N/A",
        "strategy_summary": summary,
        "top_actions": extract_actions(state.get("proposal", "")),
        "metrics": {
            "burn_rate": "Monthly net cash outflow",
            "runway": "Months of cash left",
            "cash_flow": "Net cash movement",
            "operating_expenses": "Total recurring costs",
        },
        "inputs_used": {
            "revenue": float(finance_inputs.get("revenue", DEFAULT_REVENUE)),
            "expenses": float(finance_inputs.get("expenses", DEFAULT_EXPENSES)),
            "cash": float(finance_inputs.get("cash", DEFAULT_CASH)),
        },
        "risk_notes": [
            "Avoid cutting essential growth investments",
            "Monitor team productivity impact",
        ],
        "expected_impact": {
            "monthly_burn": round(current_burn, 2),
            "runway_months": round(current_runway, 2),
            "cost_savings_estimate": round(savings, 2),
        },
        "real_impact": {
            "burn_reduction": f"INR {round(savings, 2)} saved/month",
            "runway_improvement": f"{round(current_runway, 2)} -> {improved_runway} months",
            "confidence_score": confidence_score,
        },
        "confidence_score": confidence_score,
    }


def format_output_agent(state: AgentState):
    final_output = run_with_validation(
        lambda: build_final_output(state),
        lambda x: isinstance(x, dict) and "topic" in x and "confidence_score" in x,
        {
            "topic": clean_text(state.get("input", "")) or "N/A",
            "strategy_summary": "Fallback output due to upstream failure.",
            "top_actions": extract_actions(""),
            "metrics": {
                "burn_rate": "Monthly net cash outflow",
                "runway": "Months of cash left",
                "cash_flow": "Net cash movement",
                "operating_expenses": "Total recurring costs",
            },
            "inputs_used": {
                "revenue": DEFAULT_REVENUE,
                "expenses": DEFAULT_EXPENSES,
                "cash": DEFAULT_CASH,
            },
            "risk_notes": [
                "Avoid cutting essential growth investments",
                "Monitor team productivity impact",
            ],
            "expected_impact": {
                "monthly_burn": 200000.0,
                "runway_months": 10.0,
                "cost_savings_estimate": 30000.0,
            },
            "real_impact": {
                "burn_reduction": "INR 30000 saved/month",
                "runway_improvement": "10.0 -> 11.76 months",
                "confidence_score": 70,
            },
            "confidence_score": 70,
        },
    )

    # Persist short memory record for dashboard + prompting.
    try:
        save_run(
            {
                "topic": final_output.get("topic", "N/A"),
                "burn": float(final_output.get("expected_impact", {}).get("monthly_burn", 0)),
                "runway": float(final_output.get("expected_impact", {}).get("runway_months", 0)),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )
    except Exception:
        pass

    return {"final_output": final_output}


def route_after_critic(state: AgentState) -> str:
    score = int(state.get("critic_score", 0))
    decision = str(state.get("critic_decision", "revise")).lower()
    can_retry = bool(state.get("critic_can_retry", False))

    if (decision == "revise" or score < 6) and can_retry:
        return "revise"
    return "approve"


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
builder.add_conditional_edges(
    "critic",
    route_after_critic,
    {
        "revise": "proposer",
        "approve": "simulation",
    },
)
builder.add_edge("simulation", "decision")
builder.add_edge("decision", "format_output")
builder.add_edge("format_output", END)

graph = builder.compile()
