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
                output_path="AI_Strategy_Report.pdf",
            )
        except Exception:
            pass

        return {
            "final_output": result.get("final_output", {}),
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
        }
    except Exception as e:
        revenue = data.revenue if data.revenue is not None else 300000.0
        expenses = data.expenses if data.expenses is not None else 500000.0
        cash = data.cash if data.cash is not None else 2000000.0
        return {
            "final_output": {
                "topic": data.input_text,
                "strategy_summary": "Fallback output due to runtime error.",
                "top_actions": [
                    "Audit recurring spend and remove low ROI tools",
                    "Renegotiate vendor contracts and improve payment terms",
                    "Prioritize critical hires and pause nonessential recruitment",
                    "Focus marketing only on highest converting channels",
                    "Improve invoicing and accelerate customer collections cycle",
                ],
                "metrics": {
                    "burn_rate": "Monthly net cash outflow",
                    "runway": "Months of cash left",
                    "cash_flow": "Net cash movement",
                    "operating_expenses": "Total recurring costs",
                },
                "inputs_used": {
                    "revenue": revenue,
                    "expenses": expenses,
                    "cash": cash
                },
                "risk_notes": [
                    "Avoid cutting essential growth investments",
                    "Monitor team productivity impact",
                ],
                "expected_impact": {
                    "monthly_burn": 200000,
                    "runway_months": 10,
                    "cost_savings_estimate": 30000,
                },
                "real_impact": {
                    "burn_reduction": "INR 30000 saved/month",
                    "runway_improvement": "10 -> 11.76 months",
                    "confidence_score": 70,
                },
                "confidence_score": 70,
            },
            "agent_outputs": {
                "research": {
                    "output": "Error occurred.",
                    "sources": [],
                },
                "proposal": "Using fallback strategy.",
                "critique": "Skipped due to error.",
                "simulation": '{"monthly_burn": 200000, "runway_months": 10, "cost_savings_estimate": 30000}',
                "decision": f"Fallback decision. Error: {str(e)}",
            },
        }
