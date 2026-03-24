from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from workflows.main_flow import graph
from memory.store import get_runs

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
    revenue: float | None = None
    expenses: float | None = None
    cash: float | None = None

# ✅ Home route
@app.get("/")
def home():
    return {"message": "AI Agent System Running 🚀"}


@app.get("/memory")
def memory_runs():
    return get_runs()

# ✅ Main route
@app.post("/run")
def run_agent(data: InputData):
    try:
        revenue = data.revenue if data.revenue is not None else 300000.0
        expenses = data.expenses if data.expenses is not None else 500000.0
        cash = data.cash if data.cash is not None else 2000000.0

        result = graph.invoke(
            {
                "input": data.input_text,
                "revenue": revenue,
                "expenses": expenses,
                "cash": cash,
            }
        )
        return {
            "final_output": result.get("final_output", {}),
            "agent_outputs": {
                "research": {
                    "output": result.get("data", ""),
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
