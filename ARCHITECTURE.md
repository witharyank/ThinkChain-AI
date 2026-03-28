# Nexus: Architecture Document
ET AI Hackathon 2026 Submission
**Autonomous Enterprise AI Agent System**

---

## System Overview
Nexus translates high-level business constraints into structured, auditable execution strategies. Unlike traditional generative chatbots that rely on single-pass stochastic guessing, Nexus employs a deterministic, state-driven multi-agent architecture. It autonomously debates, critiques, and simulates financial outcomes, delivering enterprise-grade reliability and precision while strictly operating without human-in-the-loop dependencies. This architecture guarantees deterministic, auditable decision execution rather than probabilistic text generation.

---

## Agent Architecture

1. **Memory Agent**
   - **Role**: Context Historian
   - **Input**: User prompt, Session ID
   - **Output**: Synthesized historical KPIs and past successful stategies
   - **Responsibility**: Prevents the system from repeating past operational errors and establishes baseline strategic guardrails.

2. **Research Agent**
   - **Role**: Data Enrichment
   - **Input**: User prompt + Memory context
   - **Output**: Real-time business context and environmental constraints
   - **Responsibility**: Scours external APIs to eliminate LLM hallucinations through live data grounding.

3. **Proposer Agent**
   - **Role**: Strategic Drafting
   - **Input**: Research context + Memory data
   - **Output**: A baseline 5-point strategic action plan
   - **Responsibility**: Generates actionable, context-aware initial strategies optimized for the specific enterprise constraint.

4. **Critic Agent**
   - **Role**: Adversarial Stress-Tester
   - **Input**: Proposed strategy
   - **Output**: JSON evaluation with Confidence Score (`0-10`) and Decision (`approve` or `revise`)
   - **Responsibility**: Flags logical flaws or unfeasible actions. If the score is `< 6/10`, it autonomously forces a revision loop back to the Proposer.

5. **Simulation Agent**
   - **Role**: Financial Quantification
   - **Input**: Approved strategic proposal + Enterprise financial inputs
   - **Output**: Deterministic impact metrics (e.g., projected burn rate, extended runway)
   - **Responsibility**: Converts qualitative strategic text into mathematical ROI projections.

6. **Decision Agent**
   - **Role**: Executive Synthesis
   - **Input**: Validated proposal + Financial simulation data
   - **Output**: Final structured JSON enterprise payload
   - **Responsibility**: Merges adversarial debate and numeric simulations into a clear, executable business directive.

---

## Workflow & Communication
**Execution Flow:** `User ➔ Memory ➔ Research ➔ Proposer ➔ Critic ➔ Simulation ➔ Decision`

- **Shared State**: All agents operate on a unified LangGraph `AgentState` object which functions as a shared operational ledger. Nodes mutate specific keys while preserving the holistic context.
- **Data Passing**: Agents do not pass raw text to one another directly. They read from and write to the state graph. Transition edges determine which agent executes next based on the graph definition.
- **Retry Loop (Critic)**: The Critic acts as an intelligent conditional edge. If the Critic's output dictates a "revise" command, the state loops backward, forcing the Proposer to execute up to two autonomous rewrites before proceeding.

---

## Tool & API Integration
- **Groq API**: Powers the cognitive reasoning of all agents (Llama-3.3-70b as primary, Llama-3.1-8b as fallback) for ultra-fast, low-latency execution.
- **Tavily API**: Utilized by the Research Agent to conduct real-time web intelligence, grounding the system in up-to-the-minute market realities.
- **FastAPI Backend**: Serves as the orchestration edge, exposing the highly complex LangGraph pipeline as robust RESTful endpoints.
- **React Flow Frontend**: Provides real-time visual telemetry, rendering the autonomous nodes, active state transitions, and final payloads for an executive-grade dashboard.
- **JSON Memory Store**: Handles localized data persistence, deduplicating and matching historical execution states to current queries.

---

##  Error Handling & Recovery
- **API Failure**: Built-in exponential backoff seamlessly routes execution from primary APIs (Llama-70b) to fallback models (Llama-8b), avoiding process termination during `429` rate limits.
- **Low-Quality Output**: Managed exclusively by the Critic Agent. Hallucinations or weak strategic proposals are mathematically flagged (`< 6`), triggering immediate, autonomous regeneration.
- **Missing Data**: If search APIs or internal telemetry drops, the system dynamically reverts to memory-synthesized historical context while simultaneously reducing the final Confidence Score, explicitly alerting leadership to the data gap.

---

##  System Diagram

```text
[User Input] ──▶ [Memory] ──▶ [Research] ──▶ [Proposer] ──▶ [Critic] ──▶ (Pass ≥ 6) ──▶ [Simulation] ──▶ [Decision] ──▶ [Output]
                                               ▲               │
                                               │               │
                                               └─ (Fail < 6) ──┘
```

---

## Key Design Advantages
- **Autonomy**: Absolute zero human intervention required from prompt input to final structured outcome.
- **Modularity**: Individual agents can be hot-swapped (e.g., swapping Llama for Claude in the Critic node) without breaking the overall pipeline.
- **Scalability**: The state graph architecture can infinitely expand to integrate new parallel validators (Legal, Compliance, HR) alongside the Critic.
- **Auditability**: Every single micro-step, critique, and mathematical projection is logged explicitly in the state graph, delivering total executive transparency.
- **Enterprise Readiness**: Designed to operate reliably in production environments with failure recovery and audit compliance.
