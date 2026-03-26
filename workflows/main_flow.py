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
from tools.search import search_web
from memory.store import get_runs, save_run

load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))
print("🔥 NEW CODE LOADED 🔥")

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
    session_id: str
    revenue: float
    expenses: float
    cash: float
    run_history: list[dict]
    research: str
    research_sources: list[dict]
    proposal: str
    critique: str
    critic_score: int
    critic_decision: str
    revision_count: int
    simulation: str
    simulation_data: dict
    finance_inputs: dict
    debate_history: list[dict]
    rejected_strategies: list[dict]
    decision_trace: list[str]
    best_strategy: dict
    impact_comparison: dict
    improvement_summary: list[str]
    memory_comparison: dict
    mode: str
    action_plan: list[dict]
    execution_timeline: dict
    kpi_metrics: list[dict]
    scenario_analysis: list[dict]
    confidence_breakdown: dict
    assumptions: list[str]
    decision: str
    decision_payload: dict
    burn_reduction_percent: float
    monthly_savings: float
    runway_months: float
    strategy: str
    final_output: dict


def clean_text(text: Any) -> str:
    if text is None:
        return ""
    return re.sub(r"\s+", " ", str(text).replace("\r", " ").strip())


def extract_financials(text: str) -> dict:
    text = (text or "").lower()

    def parse_value(num_str: str, unit: str, is_inr: bool) -> float:
        try:
            num = float(num_str.replace(",", ""))
        except ValueError:
            return None
        
        if unit in ("million", "m"):
            num *= 1_000_000
        elif unit == "lakh":
            num *= 100_000
        elif unit == "k":
            num *= 1_000

        # Enforce USD standardization
        if is_inr:
            num = num / 83.0

        return num

    def find_value(keyword_pattern: str):
        # Pattern 1: keyword ... currency number unit
        pattern1 = rf"(?:{keyword_pattern})[^\d]*?(inr|rs|₹|\$|usd)?\s*(\d+(?:,\d+)*(?:\.\d+)?)\s*(million|m|lakh|k)?"
        match1 = re.search(pattern1, text)
        if match1:
            currency = match1.group(1) or ""
            num_str = match1.group(2)
            unit = match1.group(3) or ""
            is_inr = currency in ["inr", "rs", "₹"]
            val = parse_value(num_str, unit, is_inr)
            if val is not None:
                return val

        # Pattern 2: currency number unit ... keyword
        pattern2 = rf"(inr|rs|₹|\$|usd)?\s*(\d+(?:,\d+)*(?:\.\d+)?)\s*(million|m|lakh|k)?\s*[^\d]*?(?:{keyword_pattern})"
        match2 = re.search(pattern2, text)
        if match2:
            currency = match2.group(1) or ""
            num_str = match2.group(2)
            unit = match2.group(3) or ""
            is_inr = currency in ["inr", "rs", "₹"]
            val = parse_value(num_str, unit, is_inr)
            if val is not None:
                return val

        return None

    return {
        "revenue": find_value("revenue"),
        "expenses": find_value("burn|expense|expenses|spending|spend"),
        "cash": find_value("cash|funding|bank|runway"),
    }


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
    session_id = clean_text(state.get("session_id", "default_session")) or "default_session"
    runs = get_runs(session_id)
    financial_inputs = extract_financials(state.get("input", ""))
    print("EXTRACTED:", financial_inputs)

    revenue = (
        financial_inputs["revenue"]
        if financial_inputs["revenue"] is not None
        else state.get("revenue", DEFAULT_REVENUE)
    )
    expenses = (
        financial_inputs["expenses"]
        if financial_inputs["expenses"] is not None
        else state.get("expenses", DEFAULT_EXPENSES)
    )
    cash = (
        financial_inputs["cash"]
        if financial_inputs["cash"] is not None
        else state.get("cash", DEFAULT_CASH)
    )

    print("FINAL VALUES:", revenue, expenses, cash)

    return {
        "session_id": session_id,
        "run_history": runs,
        "revision_count": state.get("revision_count", 0),
        "revenue": float(revenue),
        "expenses": float(expenses),
        "cash": float(cash),
    }


def research_agent(state: AgentState):
    print("RESEARCH START")
    try:
        query = state.get("input", "")
        try:
            memory_text = runs_summary(state.get("run_history", []))
        except Exception as e:
            print("Memory Error:", e)
            memory_text = "No previous runs"

        web_data = ""
        sources = []
        try:
            search_result = search_web(query)
            if isinstance(search_result, dict):
                web_data = clean_text(search_result.get("summary", ""))
                raw_sources = search_result.get("sources", [])
                sources = raw_sources if isinstance(raw_sources, list) else []
            elif isinstance(search_result, str):
                web_data = clean_text(search_result)
            else:
                web_data = ""
        except Exception as e:
            print("Tavily Error:", e)
            web_data = "No external data available"
            sources = []

        if not web_data:
            web_data = "No external data available"

        prompt = (
            f"Use this real-world data:\n{web_data}\n\n"
            f"Now analyze:\n{query}\n\n"
            f"Previous runs show: {memory_text}\n"
            "Return concise business context and constraints."
        )

        def generate():
            return call_groq_with_retry(prompt, "Basic market analysis generated")

        result = run_with_validation(
            generate,
            lambda x: bool(clean_text(x)),
            "Basic market analysis generated",
        )
        print("RESEARCH OUTPUT:", result)

        output = {
            "research": result if result else "Basic market analysis generated",
            "research_sources": sources if isinstance(sources, list) else [],
        }
        print("AFTER RESEARCH:", {**state, **output})
        return output
    except Exception as e:
        print("Research Agent Failed:", e)
        output = {
            "research": "Fallback research: basic business analysis applied",
            "research_sources": [],
        }
        print("AFTER RESEARCH:", {**state, **output})
        return output


def proposer_agent(state: AgentState):
    hint = similar_run_hint(state.get("input", ""), state.get("run_history", []))
    print("PROPOSER INPUT:", state.get("research"))
    research = state.get("research", "")
    if not research:
        research = "Basic business context"
    prompt = (
        f"Research context:\n{research}\n\n"
        f"Previous critique feedback:\n{state.get('critique', '')}\n\n"
        f"Bias instruction from memory: {hint}\n"
        "Propose 5 concise actionable bullet points for business impact."
    )

    def generate():
        return call_groq_with_retry(prompt, "Using cached/basic strategy")

    proposal = run_with_validation(generate, lambda x: bool(clean_text(x)), "Using cached/basic strategy")
    output = {"proposal": proposal}
    print("AFTER PROPOSER:", {**state, **output})
    return output


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
    if critic["decision"] == "revise":
        revision_count += 1
        
    history = list(state.get("debate_history", []))
    history.append({
        "round": len(history) + 1,
        "proposal": clean_text(state.get("proposal", ""))[:300] + "...",
        "critique": critic["feedback"],
        "revision": critic["decision"],
    })

    output = {
        "critique": critic["feedback"],
        "critic_score": critic["score"],
        "critic_decision": critic["decision"],
        "revision_count": revision_count,
        "debate_history": history,
    }
    print("AFTER CRITIC:", {**state, **output})
    return output


def simulation_agent(state: AgentState):
    revenue = float(state.get("revenue") or DEFAULT_REVENUE)
    expenses = float(state.get("expenses") or DEFAULT_EXPENSES)
    cash = float(state.get("cash") or DEFAULT_CASH)
    print("SIMULATION INPUT:", revenue, expenses, cash)

    monthly_burn = max(expenses - revenue, float(expenses)) if expenses else 50000.0
    if monthly_burn <= 0:
        monthly_burn = expenses or 50000.0

    runway_months = float(cash / monthly_burn) if monthly_burn > 0 else 0.0
    cost_savings_estimate = float(max(monthly_burn * 0.15, 0))

    simulation_data = {
        "monthly_burn": round(monthly_burn, 2),
        "runway_months": round(runway_months, 2),
        "cost_savings_estimate": round(cost_savings_estimate, 2),
    }

    output = {
        "simulation": json.dumps(simulation_data),
        "simulation_data": simulation_data,
        "finance_inputs": {
            "revenue": revenue,
            "expenses": expenses,
            "cash": cash,
        },
    }
    print("AFTER SIMULATION:", {**state, **output})
    return output


def decision_agent(state: AgentState):
    sim = state.get("simulation_data", {})
    prompt = (
        "You are the final decision-making agent.\n\n"
        "Based on:\n"
        "1. Proposal\n"
        "2. Critic feedback\n"
        "3. Simulation results\n\n"
        "Return STRICT JSON only:\n\n"
        "{\n"
        "  \"decision\": \"Final selected strategy\",\n"
        "  \"reasoning\": \"Why this strategy is optimal\",\n"
        "  \"impact_6_months\": \"Quantified expected outcome\",\n"
        "  \"actions\": [\"Action 1\", \"Action 2\", \"Action 3\"]\n"
        "}\n\n"
        f"Proposal: {state.get('proposal', '')}\n"
        f"Critique: {state.get('critique', '')}\n"
        f"Simulation: {json.dumps(sim)}\n"
    )

    def generate():
        fallback_json = '{"decision":"Balanced Strategy","reasoning":"Optimizes retention and reduces burn","impact_6_months":"Improved retention and extended runway","actions":["Improve retention","Reduce CAC","Test subscription"]}'
        raw = call_groq_with_retry(prompt, fallback_json)
        print("RAW DECISION AGENT OUTPUT:", raw)
        try:
            start = raw.find("{")
            end = raw.rfind("}")
            if start != -1 and end != -1:
                return json.loads(raw[start:end+1])
            return json.loads(raw)
        except Exception as e:
            print("DECISION PARSE FAILED. Raw:", raw, "Error:", str(e))
            return json.loads(fallback_json)

    result = run_with_validation(
        generate,
        lambda x: isinstance(x, dict) and "decision" in x,
        {"decision":"Balanced Strategy","reasoning":"Optimizes retention and reduces burn","impact_6_months":"Improved retention and extended runway","actions":["Improve retention","Reduce CAC","Test subscription"]}
    )
    
    # Store the actual decision data exactly as-is to ensure no data is lost
    decision_payload = {
        "decision": result.get("decision", "Balanced Strategy"),
        "reasoning": result.get("reasoning", "Optimizes retention and reduces burn"),
        "impact_6_months": result.get("impact_6_months", "Improved retention and extended runway"),
        "actions": result.get("actions", ["Improve retention", "Reduce CAC", "Test subscription"])
    }

    # Extract numerical fields for Task D (Phase 9 legacy)
    burn_reduction_percent = 15.0
    runway_months = sim.get("runway_months", 0.0)

    # MAP to legacy structures to protect phase 8 UI component tree
    mapped_best_strategy = {
        "strategy_name": decision_payload["decision"],
        "reason": decision_payload["reasoning"],
        "outcome": decision_payload["impact_6_months"]
    }
    
    raw_actions = decision_payload["actions"]
    if not isinstance(raw_actions, list):
        raw_actions = ["Improve retention", "Reduce CAC", "Test subscription"]
        
    mapped_action_plan = [
        {"action": act, "owner": "Operations", "timeline": "Immediate", "expected_impact": "High"} 
        for act in raw_actions
    ]

    output = {
        # Strict user-specified outputs
        "decision_payload": decision_payload,
        "burn_reduction_percent": burn_reduction_percent,
        "monthly_savings": sim.get("cost_savings_estimate", 0),
        "runway_months": runway_months,
        "strategy": decision_payload["decision"],
        
        # Original pipeline mappings
        "decision": json.dumps(decision_payload),
        "best_strategy": mapped_best_strategy,
        "action_plan": mapped_action_plan,
        "decision_trace": [decision_payload["reasoning"]],
        "rejected_strategies": [],
        "execution_timeline": {"immediate": raw_actions},
        "kpi_metrics": [{"metric": "Retention Rate", "target": "30%", "tracking_frequency": "Weekly"}],
        "scenario_analysis": [],
        "confidence_breakdown": {"overall_confidence": "85%"},
        "assumptions": ["Metrics hold true"]
    }
    print("AFTER DECISION:", {**state, **output})
    return output


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
    current_burn = max(float(sim.get("monthly_burn") or 0), 0)
    savings = max(float(sim.get("cost_savings_estimate") or 0), 0)
    current_runway = float(sim.get("runway_months") or 0)

    improved_burn = max(current_burn - savings, 1)
    cash = float(finance_inputs.get("cash") or DEFAULT_CASH)
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
            "revenue": float(finance_inputs.get("revenue") or DEFAULT_REVENUE),
            "expenses": float(finance_inputs.get("expenses") or DEFAULT_EXPENSES),
            "cash": float(finance_inputs.get("cash") or DEFAULT_CASH),
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
    current_burn = max(float(sim.get("monthly_burn") or 0), 0)
    savings = max(float(sim.get("cost_savings_estimate") or 0), 0)
    current_runway = float(sim.get("runway_months") or 0)
    improved_burn = max(current_burn - savings, 1)
    cash = float(finance_inputs.get("cash") or DEFAULT_CASH)
    improved_runway = round(cash / improved_burn, 2) if improved_burn > 0 else current_runway

    impact_comparison = {
        "burn": {
            "before": round(current_burn, 2),
            "after": round(improved_burn, 2)
        },
        "runway": {
            "before": round(current_runway, 2),
            "after": round(improved_runway, 2),
        },
        "savings": round(savings, 2)
    }
    
    decrease_pct = round((savings / current_burn * 100) if current_burn > 0 else 0, 1)
    runway_ext = round(improved_runway - current_runway, 1)
    
    improvement_summary = [
        f"Reduced monthly burn by {decrease_pct}% (INR {savings:,})",
        f"Extended runway by {runway_ext} months",
        "Maintained growth capability while cutting waste"
    ]
    
    history_runs = state.get("run_history", [])
    memory_comparison = None
    if history_runs:
        last = history_runs[-1]
        memory_comparison = {
            "previous_runway": round(last.get("runway", 0), 1),
            "current_runway": round(improved_runway, 1),
            "topic": last.get("topic", "")
        }

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
            state.get("session_id", "default_session"),
            {
                "topic": final_output.get("topic", "N/A"),
                "burn": float(final_output.get("expected_impact", {}).get("monthly_burn") or 0),
                "runway": float(final_output.get("expected_impact", {}).get("runway_months") or 0),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )
    except Exception:
        pass

    # Merge the exact decision outputs into final_output so it renders properly in UI
    decision_payload = state.get("decision_payload", {})
    if decision_payload:
        final_output["decision"] = decision_payload.get("decision", "")
        final_output["reasoning"] = decision_payload.get("reasoning", "")
        final_output["impact_6_months"] = decision_payload.get("impact_6_months", "")
        final_output["actions"] = decision_payload.get("actions", [])

    return {
        "final_output": final_output,
        "impact_comparison": impact_comparison,
        "improvement_summary": improvement_summary,
        "memory_comparison": memory_comparison,
        "decision_payload": decision_payload
    }


def route_after_critic(state: AgentState) -> str:
    score = int(state.get("critic_score", 0))
    decision = str(state.get("critic_decision", "revise")).lower()
    revision_count = int(state.get("revision_count", 0))

    if (decision == "revise" or score < 6) and revision_count <= MAX_CRITIC_REVISIONS:
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
