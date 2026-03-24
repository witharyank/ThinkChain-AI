from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from workflows.main_flow import graph

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

# ✅ Home route
@app.get("/")
def home():
    return {"message": "AI Agent System Running 🚀"}

# ✅ Main route
@app.post("/run")
def run_agent(data: InputData):
    try:
        result = graph.invoke({"input": data.input_text})
        return {
            "final_output": result.get("final_output", {}),
            "agent_outputs": {
                "research": result.get("data", ""),
                "proposal": result.get("proposal", ""),
                "critique": result.get("critique", ""),
                "simulation": result.get("simulation", ""),
                "decision": result.get("decision", ""),
            },
        }
    except Exception as e:
        return {"error": str(e)}
