import { useState } from "react";
import Flow from "./components/Flow";
import { runNodeSequence } from "./utils/execution";

const AGENT_SEQUENCE = ["research", "proposer", "critic", "simulation", "decision"];
const OUTPUT_KEY_MAP = {
  research: "research",
  proposer: "proposal",
  critic: "critique",
  simulation: "simulation",
  decision: "decision",
};

const DEFAULT_NODE_OUTPUTS = {
  research: "",
  proposer: "",
  critic: "",
  simulation: "",
  decision: "",
};

const DEFAULT_NODE_STATUS = {
  research: "idle",
  proposer: "idle",
  critic: "idle",
  simulation: "idle",
  decision: "idle",
};

function summarize(text) {
  if (!text) return "No output yet.";
  const clean = String(text).replace(/\s+/g, " ").trim();
  if (clean.length <= 120) return clean;
  return `${clean.slice(0, 117)}...`;
}

export default function App() {
  const [prompt, setPrompt] = useState("Reduce startup burn rate");
  const [status, setStatus] = useState("Idle");
  const [loading, setLoading] = useState(false);
  const [activeNode, setActiveNode] = useState(null);
  const [nodeOutputs, setNodeOutputs] = useState(DEFAULT_NODE_OUTPUTS);
  const [nodeStatus, setNodeStatus] = useState(DEFAULT_NODE_STATUS);
  const [selectedNode, setSelectedNode] = useState("research");
  const [finalOutput, setFinalOutput] = useState(null);
  const [error, setError] = useState("");

  const runPipeline = async () => {
    if (!prompt.trim()) return;

    setLoading(true);
    setStatus("Running");
    setError("");
    setActiveNode(null);
    setFinalOutput(null);
    setNodeOutputs(DEFAULT_NODE_OUTPUTS);
    setNodeStatus(DEFAULT_NODE_STATUS);

    try {
      const response = await fetch("http://127.0.0.1:8000/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ input_text: prompt }),
      });

      const payload = await response.json();
      if (!response.ok || payload.error) {
        throw new Error(payload.error || "Backend request failed");
      }

      const agentOutputs = payload.agent_outputs || {};

      await runNodeSequence({
        sequence: AGENT_SEQUENCE,
        delayMs: 550,
        getOutputKey: (nodeId) => OUTPUT_KEY_MAP[nodeId],
        getOutputValue: (outputKey) => agentOutputs[outputKey] || "No output generated",
        onNodeStart: (nodeId) => {
          setActiveNode(nodeId);
          setNodeStatus((prev) => ({ ...prev, [nodeId]: "running" }));
          setNodeOutputs((prev) => ({ ...prev, [nodeId]: "Running..." }));
        },
        onNodeComplete: (nodeId, outputValue) => {
          setNodeOutputs((prev) => ({ ...prev, [nodeId]: outputValue }));
          setNodeStatus((prev) => ({ ...prev, [nodeId]: "completed" }));
        },
        onSequenceDone: () => setActiveNode(null),
      });

      setFinalOutput(payload.final_output || {});
      setStatus("Success");
    } catch (runError) {
      setStatus("Failed");
      setError(runError.message || "Unexpected error");
      setActiveNode(null);
      setNodeStatus((prev) => ({
        ...prev,
        [activeNode || "research"]: "failed",
      }));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="app-shell">
      <header className="top-bar">
        <div>
          <h1>Debate-Driven AI Workflow</h1>
          <p>Interactive multi-agent execution graph powered by FastAPI + LangGraph</p>
        </div>
        <div className={`status-pill status-${status.toLowerCase().replace("...", "")}`}>
          {loading && <span className="spinner" />}
          {status}
        </div>
      </header>

      <section className="control-panel">
        <input
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          placeholder="Enter strategy problem..."
        />
        <button onClick={runPipeline} disabled={loading}>
          {loading ? "Running..." : "Run"}
        </button>
      </section>

      <section className="workspace">
        <div className="flow-zone">
          <Flow
            activeNode={activeNode}
            nodeOutputs={nodeOutputs}
            nodeStatus={nodeStatus}
            onNodeSelect={setSelectedNode}
            selectedNode={selectedNode}
            isRunning={loading}
          />
        </div>

        <aside className="side-panel">
          <h3>Node Details</h3>
          <p className="side-subtitle">{selectedNode?.toUpperCase() || "Select a node"}</p>
          <p className="side-summary">{summarize(nodeOutputs[selectedNode])}</p>
          <pre>{nodeOutputs[selectedNode] || "Click a node to inspect output."}</pre>
        </aside>
      </section>

      <section className="final-output-card">
        <h3>Final Decision</h3>
        {error ? <p className="error-text">{error}</p> : null}
        <pre>{finalOutput ? JSON.stringify(finalOutput, null, 2) : "Run the workflow to view final output."}</pre>
      </section>
    </div>
  );
}
