from fastapi import FastAPI
from fastapi.responses import FileResponse
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from workflows.main_flow import graph
from memory.store import get_runs
from reports.pdf_generator import generate_consulting_pdf

app = FastAPI()

# ✅ CORS fix
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ✅ Input model
class InputData(BaseModel):
    input_text: str
    session_id: str | None = None
    revenue: float | None = None
    expenses: float | None = None
    cash: float | None = None
    mode: str | None = "balanced"

# ✅ Home route
@app.get("/")
def home():
    return {"message": "AI Agent System Running 🚀"}


@app.get("/memory")
def memory_runs(session_id: str = "default_session"):
    return get_runs(session_id)


@app.get("/report")
def get_report():
    return FileResponse("AI_Strategy_Report.pdf", media_type="application/pdf", filename="AI_Strategy_Report.pdf")

# ✅ Main route
@app.post("/run")
def run_agent(data: InputData):
    try:
        session_id = data.session_id or "default_session"
        revenue = data.revenue if data.revenue is not None else 300000.0
        expenses = data.expenses if data.expenses is not None else 500000.0
        cash = data.cash if data.cash is not None else 2000000.0

        result = graph.invoke(
            {
                "input": data.input_text,
                "session_id": session_id,
                "revenue": revenue,
                "expenses": expenses,
                "cash": cash,
                "mode": data.mode or "balanced",
            }
        )
        # Generate consulting-style PDF report without changing API response structure.
        try:
            generate_consulting_pdf(
                topic=result.get("final_output", {}).get("topic", data.input_text),
                strategy_summary=result.get("final_output", {}).get("strategy_summary", ""),
                research_output=result.get("research", ""),
                proposal_output=result.get("proposal", ""),
                critique_output=result.get("critique", ""),
                simulation_output=result.get("simulation", ""),
                decision_output=result.get("decision", ""),
                risk_notes=result.get("final_output", {}).get("risk_notes", []),
                sources=result.get("research_sources", []),
                action_plan=result.get("action_plan", []),
                execution_timeline=result.get("execution_timeline", {}),
                kpi_metrics=result.get("kpi_metrics", []),
                scenario_analysis=result.get("scenario_analysis", []),
                confidence_breakdown=result.get("confidence_breakdown", {}),
                assumptions=result.get("assumptions", []),
                output_path="AI_Strategy_Report.pdf",
            )
        except Exception:
            pass

        print("PIPELINE SUCCESS. FINAL API RESPONSE PREPARED.")
        
        # Get explicitly requested components
        decision_payload = result.get("decision_payload", {})
        impact_comp = result.get("impact_comparison", {})
        
        final_response = {
            # EXPLICITLY REQUESTED KEYS FOR TASK 10 (STEP 3)
            "decision": decision_payload.get("decision", ""),
            "reasoning": decision_payload.get("reasoning", ""),
            "impact": decision_payload.get("impact_6_months", ""),
            "actions": decision_payload.get("actions", []),
            "impactComparison": impact_comp,
            "metrics": result.get("final_output", {}).get("metrics", {}),
            "strategy": decision_payload.get("decision", ""),
            
            # EXISTING UI DATA (DO NOT BREAK DASHBOARD)
            "final_output": result.get("final_output", {}),
            "debate_history": result.get("debate_history", []),
            "rejected_strategies": result.get("rejected_strategies", []),
            "decision_trace": result.get("decision_trace", []),
            "best_strategy": result.get("best_strategy", {}),
            "impact_comparison": result.get("impact_comparison", {}),
            "improvement_summary": result.get("improvement_summary", []),
            "memory_comparison": result.get("memory_comparison", None),
            "action_plan": result.get("action_plan", []),
            "execution_timeline": result.get("execution_timeline", {}),
            "kpi_metrics": result.get("kpi_metrics", []),
            "scenario_analysis": result.get("scenario_analysis", []),
            "confidence_breakdown": result.get("confidence_breakdown", {}),
            "assumptions": result.get("assumptions", []),
            "agent_outputs": {
                "research": {
                    "output": result.get("research", ""),
                    "sources": result.get("research_sources", []),
                },
                "proposal": result.get("proposal", ""),
                "critique": result.get("critique", ""),
                "simulation": result.get("simulation", ""),
                "decision": result.get("decision", ""),
            },
            "burn_reduction_percent": result.get("burn_reduction_percent", 0),
            "monthly_savings": result.get("monthly_savings", 0),
            "runway_months": result.get("runway_months", 0),
            "strategy": result.get("strategy", "")
        }
        
        print(f"FINAL DEBUG PAYLOAD LOGGING: {final_response['decision']} | ACTIONS: {len(final_response['actions'])}")
        return final_response
    except Exception as e:
        print("PIPELINE ERROR:", e)
        return {
            "final_output": {},
            "debate_history": [],
            "rejected_strategies": [],
            "decision_trace": [],
            "best_strategy": {},
            "impact_comparison": {},
            "improvement_summary": [],
            "memory_comparison": None,
            "action_plan": [],
            "execution_timeline": {},
            "kpi_metrics": [],
            "scenario_analysis": [],
            "confidence_breakdown": {},
            "assumptions": [],
            "research": "Fallback research",
            "research_sources": [],
            "agent_outputs": {},
            
            # Fallbacks for explicit keys
            "decision": "Fallback Strategy",
            "reasoning": "Pipeline failed to execute",
            "impact": "N/A",
            "actions": [],
            "impactComparison": {},
            "metrics": {},
            "strategy": "Fallback Strategy",
            "burn_reduction_percent": 0,
            "monthly_savings": 0,
            "runway_months": 0
        }
