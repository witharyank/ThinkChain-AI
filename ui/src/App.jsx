import { useRef, useState } from "react";
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
  const sessionId = useRef(null);
  if (!sessionId.current) {
    const uuid =
      globalThis?.crypto?.randomUUID?.() ??
      `session_${Date.now()}_${Math.floor(Math.random() * 1_000_000)}`;
    sessionId.current = uuid;
  }
  const [prompt, setPrompt] = useState("Reduce startup burn rate");
  const [status, setStatus] = useState("Idle");
  const [loading, setLoading] = useState(false);
  const [activeNode, setActiveNode] = useState(null);
  const [nodeOutputs, setNodeOutputs] = useState(DEFAULT_NODE_OUTPUTS);
  const [nodeStatus, setNodeStatus] = useState(DEFAULT_NODE_STATUS);
  const [selectedNode, setSelectedNode] = useState("research");
  const [finalOutput, setFinalOutput] = useState(null);
  const [error, setError] = useState("");
  const [researchSources, setResearchSources] = useState([]);
  const [debateHistory, setDebateHistory] = useState([]);
  const [rejectedStrategies, setRejectedStrategies] = useState([]);
  const [decisionTrace, setDecisionTrace] = useState([]);
  const [impactComparison, setImpactComparison] = useState(null);
  const [improvementSummary, setImprovementSummary] = useState([]);
  const [bestStrategy, setBestStrategy] = useState(null);
  const [memoryComparison, setMemoryComparison] = useState(null);
  const [actionPlan, setActionPlan] = useState([]);
  const [executionTimeline, setExecutionTimeline] = useState({});
  const [kpiMetrics, setKpiMetrics] = useState([]);
  const [scenarioAnalysis, setScenarioAnalysis] = useState([]);
  const [confidenceBreakdown, setConfidenceBreakdown] = useState({});
  const [assumptions, setAssumptions] = useState([]);
  const [showExplanation, setShowExplanation] = useState(false);
  const [revisionLabel, setRevisionLabel] = useState("");
  const [mode, setMode] = useState("balanced");
  const [isListening, setIsListening] = useState(false);
  const recognitionRef = useRef(null);

  const toggleListen = () => {
    if (isListening) {
      recognitionRef.current?.stop();
      setIsListening(false);
      return;
    }

    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      alert("Microphone input is not supported in this browser. Please use Chrome, Edge, or Safari.");
      return;
    }

    const recognition = new SpeechRecognition();
    recognition.continuous = false; // Stops when the user stops speaking
    recognition.interimResults = true;
    recognition.lang = 'en-US';

    recognition.onstart = () => setIsListening(true);
    
    recognition.onresult = (event) => {
      let transcript = Array.from(event.results)
        .map(result => result[0].transcript)
        .join('');
      setPrompt(transcript);
    };

    recognition.onerror = (event) => {
      console.error("Speech error:", event.error);
      setIsListening(false);
    };

    recognition.onend = () => {
      setIsListening(false);
    };

    recognitionRef.current = recognition;
    recognition.start();
  };

  const PRESETS = {
    saas: { prompt: "Reduce SaaS churn while maintaining 40% growth margin", mode: "balanced" },
    d2c: { prompt: "Optimize D2C logistics costs for a $5M revenue run-rate", mode: "aggressive" },
    fintech: { prompt: "Extend Fintech runway by 6 months ahead of Series B", mode: "conservative" }
  };

  const copySnapshot = () => {
    if (!finalOutput) return;
    const snapshot = {
      prompt, mode, bestStrategy, actionPlan, executionTimeline, impactComparison, kpiMetrics
    };
    navigator.clipboard.writeText(JSON.stringify(snapshot, null, 2));
    alert("Report snapshot JSON copied to clipboard!");
  };

  const downloadPDF = () => {
    window.open("http://127.0.0.1:8000/report", "_blank");
  };

  const runPipeline = async () => {
    if (!prompt.trim()) return;

    setLoading(true);
    setStatus("Running");
    setError("");
    setActiveNode(null);
    setFinalOutput(null);
    setResearchSources([]);
    setDebateHistory([]);
    setRejectedStrategies([]);
    setDecisionTrace([]);
    setImpactComparison(null);
    setImprovementSummary([]);
    setBestStrategy(null);
    setMemoryComparison(null);
    setActionPlan([]);
    setExecutionTimeline({});
    setKpiMetrics([]);
    setScenarioAnalysis([]);
    setConfidenceBreakdown({});
    setAssumptions([]);
    setShowExplanation(false);
    setRevisionLabel("");
    setNodeOutputs(DEFAULT_NODE_OUTPUTS);
    setNodeStatus(DEFAULT_NODE_STATUS);

    try {
      const response = await fetch("http://127.0.0.1:8000/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          input_text: prompt,
          session_id: sessionId.current,
          mode: mode
        }),
      });

      const payload = await response.json();
      if (!response.ok || payload.error) {
        throw new Error(payload.error || "Backend request failed");
      }

      const agentOutputs = payload.agent_outputs || {};
      const retryCount = Number(agentOutputs.retry_count || 0);
      const proposal = agentOutputs.proposal || "";
      const critique = agentOutputs.critique || "";

      setRejectedStrategies(payload.rejected_strategies || []);
      setDecisionTrace(payload.decision_trace || []);
      setImpactComparison(payload.impact_comparison || null);
      setImprovementSummary(payload.improvement_summary || []);
      setBestStrategy(payload.best_strategy || null);
      setMemoryComparison(payload.memory_comparison || null);
      setActionPlan(payload.action_plan || []);
      setExecutionTimeline(payload.execution_timeline || {});
      setKpiMetrics(payload.kpi_metrics || []);
      setScenarioAnalysis(payload.scenario_analysis || []);
      setConfidenceBreakdown(payload.confidence_breakdown || {});
      setAssumptions(payload.assumptions || []);

      const debateHistoryRaw = payload.debate_history || [];
      if (debateHistoryRaw.length > 0) {
        setDebateHistory(debateHistoryRaw);
      } else {
        const history = [];
        for (let i = 0; i <= retryCount; i++) {
          history.push({
            round: i + 1,
            proposal,
            critique,
          });
        }
        setDebateHistory(history);
      }
      
      if (retryCount > 0) {
        setRevisionLabel(`Revision Round ${retryCount + 1}`);
      }

      await runNodeSequence({
        sequence: AGENT_SEQUENCE,
        delayMs: 550,
        getOutputKey: (nodeId) => OUTPUT_KEY_MAP[nodeId],
        getOutputValue: (outputKey) => {
          if (outputKey === "research") {
            const researchPayload = agentOutputs.research;
            const researchText =
              (typeof researchPayload === "string" && researchPayload) ||
              (researchPayload && researchPayload.research) ||
              (researchPayload && researchPayload.output) ||
              "No research available";
            return researchText;
          }
          return agentOutputs[outputKey] || "No output generated";
        },
        onNodeStart: (nodeId) => {
          setActiveNode(nodeId);
          setNodeStatus((prev) => ({ ...prev, [nodeId]: "running" }));
          setNodeOutputs((prev) => ({ ...prev, [nodeId]: "Running..." }));
        },
        onNodeComplete: (nodeId, outputValue) => {
          setNodeOutputs((prev) => ({ ...prev, [nodeId]: outputValue }));
          if (nodeId === "research") {
            const researchPayload = agentOutputs.research;
            const sources = Array.isArray(agentOutputs.research_sources)
              ? agentOutputs.research_sources
              : Array.isArray(researchPayload && researchPayload.sources)
              ? researchPayload.sources
              : [];
            setResearchSources(Array.isArray(sources) ? sources : []);
          }
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
          <h1 style={{ background: "linear-gradient(90deg, #38bdf8, #818cf8)", WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent", fontSize: "2.5rem" }}>AI Business Co-Pilot</h1>
          <p style={{ fontSize: "1.1rem", color: "#94a3b8", marginTop: "8px" }}>An AI team that debates, simulates & executes decisions</p>
          <div style={{ display: "flex", gap: "10px", marginTop: "12px", marginBottom: "16px" }}>
            <span style={{ padding: "4px 10px", background: "rgba(56,189,248,0.1)", color: "#38bdf8", borderRadius: "12px", fontSize: "0.8rem", fontWeight: "bold", border: "1px solid rgba(56,189,248,0.2)" }}>🧠 Multi-Agent</span>
            <span style={{ padding: "4px 10px", background: "rgba(244,63,94,0.1)", color: "#f43f5e", borderRadius: "12px", fontSize: "0.8rem", fontWeight: "bold", border: "1px solid rgba(244,63,94,0.2)" }}>⚔️ Debate Engine</span>
            <span style={{ padding: "4px 10px", background: "rgba(34,197,94,0.1)", color: "#22c55e", borderRadius: "12px", fontSize: "0.8rem", fontWeight: "bold", border: "1px solid rgba(34,197,94,0.2)" }}>📊 Impact Simulator</span>
          </div>
        </div>
        <div className={`status-pill status-${status.toLowerCase().replace("...", "")}`}>
          {loading && <span className="spinner" />}
          {status}
        </div>
      </header>

      <section className="control-panel" style={{flexDirection: "column", gap: "16px", marginBottom: "32px"}}>
        <div style={{display: "flex", gap: "12px", width: "100%"}}>
          <div style={{ position: "relative", flex: 1, display: "flex" }}>
            <input
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder={isListening ? "Listening... (Speak now)" : "Describe your startup problem (e.g. revenue, burn, growth)"}
              style={{ width: "100%", padding: "16px 50px 16px 20px", borderRadius: "12px", border: "1px solid #334155", background: "#0b1326", color: "#e2e8f0", fontSize: "1.05rem", boxSizing: "border-box", outline: "none", boxShadow: "inset 0 2px 4px rgba(0,0,0,0.2)" }}
            />
            <button 
              type="button"
              onClick={toggleListen}
              title={isListening ? "Stop listening" : "Use Microphone"}
              style={{
                position: "absolute", right: "8px", top: "50%", transform: "translateY(-50%)", background: "rgba(30,41,59,0.8)", border: "1px solid #334155", borderRadius: "8px", cursor: "pointer", fontSize: "1.2rem", padding: "6px 8px", color: isListening ? "#ef4444" : "#94a3b8", transition: "0.2s"
              }}
            >
              {isListening ? "⏹️" : "🎙️"}
            </button>
          </div>
          <div style={{ display: "flex", background: "#0b1326", borderRadius: "12px", border: "1px solid #334155", padding: "4px" }}>
            {["conservative", "balanced", "aggressive"].map(m => (
              <button key={m} onClick={() => setMode(m)} style={{ background: mode === m ? "#38bdf8" : "transparent", color: mode === m ? "#0f172a" : "#94a3b8", border: "none", borderRadius: "8px", padding: "10px 16px", textTransform: "capitalize", fontWeight: "bold", cursor: "pointer", transition: "all 0.2s" }}>{m}</button>
            ))}
          </div>
          <button onClick={runPipeline} disabled={loading} style={{padding: "0 32px", fontSize: "1.1rem"}}>
            {loading ? "AI agents debating..." : "Run Simulator"}
          </button>
        </div>
        
        <div style={{display: "flex", gap: "10px", alignItems: "center"}}>
          <span style={{fontSize: "0.9rem", color: "#64748b", fontWeight: "bold", marginRight: "4px"}}>⚡ Try Demo Scenarios:</span>
          {Object.entries(PRESETS).map(([k, v]) => (
            <button key={k} onClick={() => {setPrompt(v.prompt); setMode(v.mode);}} style={{padding: "8px 16px", background: "rgba(51,65,85,0.4)", color: "#cbd5e1", border: "1px solid #334155", borderRadius: "16px", fontSize: "0.85rem", cursor: "pointer", transition: "0.2s"}} onMouseOver={(e)=>{e.target.style.background="#38bdf8";e.target.style.color="#0f172a"}} onMouseOut={(e)=>{e.target.style.background="rgba(51,65,85,0.4)";e.target.style.color="#cbd5e1"}}>
              {k === 'saas' ? 'SaaS Case' : k === 'd2c' ? 'D2C Case' : 'Fintech Case'}
            </button>
          ))}
        </div>
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
          {selectedNode === "research" && researchSources.length > 0 ? (
            <div>
              <h4>Sources</h4>
              {researchSources.slice(0, 3).map((s, i) => (
                <div key={i} className="source-item">
                  <a href={s.url} target="_blank" rel="noreferrer">
                    {s.title || s.url}
                  </a>
                </div>
              ))}
            </div>
          ) : null}
        </aside>
      </section>

      <section className="final-output-card insight-layer">
        {bestStrategy && Object.keys(bestStrategy).length > 0 && (
          <div style={{background: "linear-gradient(to right, #1e293b, #0f172a)", border: "1px solid #38bdf8", padding: "24px", borderRadius: "16px", marginBottom: "32px", boxShadow: "0 10px 30px -10px rgba(56,189,248,0.2)"}}>
            <h3 style={{color: "#38bdf8", marginTop: 0, display: "flex", alignItems: "center", gap: "8px"}}>🔥 Selected Strategy Highlight</h3>
            <h4 style={{margin: "0 0 12px 0", color: "#f8fafc", fontSize: "1.4rem"}}>{bestStrategy.strategy_name}</h4>
            <p style={{margin: "0 0 8px 0", color: "#cbd5e1", fontSize: "1.05rem"}}><strong>Reason:</strong> {bestStrategy.reason}</p>
            <p style={{margin: 0, color: "#94a3b8"}}><strong>Outcome:</strong> {bestStrategy.outcome}</p>
          </div>
        )}

        {impactComparison && Object.keys(impactComparison).length > 0 && (
          <div style={{marginBottom: "36px"}}>
             <div style={{display: "flex", gap: "20px", marginBottom: "24px", flexWrap: "wrap"}}>
               <div style={{flex: "1 1 min-content", padding: "20px", borderRadius: "16px", border: "1px solid #334155", background: "linear-gradient(145deg, #1e293b, #0f172a)", boxShadow: "0 10px 25px -5px rgba(0,0,0,0.5)", transition: "transform 0.2s", cursor: "default"}} onMouseOver={e=>e.currentTarget.style.transform="translateY(-4px)"} onMouseOut={e=>e.currentTarget.style.transform="translateY(0)"}>
                 <p style={{margin: "0 0 8px 0", fontSize: "0.9rem", color: "#94a3b8", fontWeight: "bold", textTransform: "uppercase", letterSpacing: "0.05em"}}>🔻 Burn Reduction</p>
                 <p style={{margin: "0 0 6px 0", fontSize: "1.4rem", fontWeight: "800", color: "#f8fafc"}}><span style={{color:"#64748b", fontWeight:"500", fontSize:"1.1rem"}}>INR {(impactComparison.burn?.before/1000).toFixed(0)}k</span> → {(impactComparison.burn?.after/1000).toFixed(0)}k</p>
                 <p style={{margin: 0, fontSize: "0.9rem", color: "#10b981", fontWeight: "bold", display: "inline-flex", alignItems: "center", background: "rgba(16,185,129,0.1)", padding: "4px 8px", borderRadius: "6px"}}>
                   {-(((impactComparison.burn?.before - impactComparison.burn?.after)/impactComparison.burn?.before)*100).toFixed(1)}% Improvement
                 </p>
               </div>
               <div style={{flex: "1 1 min-content", padding: "20px", borderRadius: "16px", border: "1px solid #334155", background: "linear-gradient(145deg, #1e293b, #0f172a)", boxShadow: "0 10px 25px -5px rgba(0,0,0,0.5)", transition: "transform 0.2s", cursor: "default"}} onMouseOver={e=>e.currentTarget.style.transform="translateY(-4px)"} onMouseOut={e=>e.currentTarget.style.transform="translateY(0)"}>
                 <p style={{margin: "0 0 8px 0", fontSize: "0.9rem", color: "#94a3b8", fontWeight: "bold", textTransform: "uppercase", letterSpacing: "0.05em"}}>⏳ Runway Extension</p>
                 <p style={{margin: "0 0 6px 0", fontSize: "1.4rem", fontWeight: "800", color: "#f8fafc"}}><span style={{color:"#64748b", fontWeight:"500", fontSize:"1.1rem"}}>{impactComparison.runway?.before?.toFixed(1)}</span> → {impactComparison.runway?.after?.toFixed(1)} mos</p>
                 <p style={{margin: 0, fontSize: "0.9rem", color: "#38bdf8", fontWeight: "bold", display: "inline-flex", alignItems: "center", background: "rgba(56,189,248,0.1)", padding: "4px 8px", borderRadius: "6px"}}>
                   +{(impactComparison.runway?.after - impactComparison.runway?.before).toFixed(1)} Months
                 </p>
               </div>
               <div style={{flex: "1 1 min-content", padding: "20px", borderRadius: "16px", border: "1px solid #334155", background: "linear-gradient(145deg, #1e293b, #0f172a)", boxShadow: "0 10px 25px -5px rgba(0,0,0,0.5)", transition: "transform 0.2s", cursor: "default"}} onMouseOver={e=>e.currentTarget.style.transform="translateY(-4px)"} onMouseOut={e=>e.currentTarget.style.transform="translateY(0)"}>
                 <p style={{margin: "0 0 8px 0", fontSize: "0.9rem", color: "#94a3b8", fontWeight: "bold", textTransform: "uppercase", letterSpacing: "0.05em"}}>💰 Monthly Savings</p>
                 <p style={{margin: "0", fontSize: "1.4rem", fontWeight: "800", color: "#f8fafc"}}>INR {impactComparison.savings?.toLocaleString()}</p>
                 <p style={{margin: 0, marginTop: "6px", fontSize: "0.9rem", color: "#10b981", fontWeight: "bold", display: "inline-flex", alignItems: "center", background: "rgba(16,185,129,0.1)", padding: "4px 8px", borderRadius: "6px"}}>
                   Immediate Impact
                 </p>
               </div>
             </div>

             <div style={{padding: "20px", border: "1px solid #334155", borderRadius: "16px", background: "linear-gradient(to right, #1e293b, #0f172a)"}}>
                <div style={{display: "flex", alignItems: "center", marginBottom: "16px"}}>
                   <span style={{width: "120px", fontSize: "0.9rem", fontWeight: "bold", color: "#94a3b8"}}>Current Burn</span>
                   <div style={{flex: 1, height: "24px", backgroundColor: "#0b1326", borderRadius: "6px", overflow: "hidden", border: "1px solid #1e293b"}}>
                     <div style={{width: '100%', height: '100%', backgroundColor: '#ef4444', boxShadow: "0 0 10px #ef4444"}}></div>
                   </div>
                </div>
                <div style={{display: "flex", alignItems: "center"}}>
                   <span style={{width: "120px", fontSize: "0.9rem", fontWeight: "bold", color: "#94a3b8"}}>Optimized Burn</span>
                   <div style={{flex: 1, height: "24px", backgroundColor: "#0b1326", borderRadius: "6px", overflow: "hidden", border: "1px solid #1e293b"}}>
                     <div style={{width: `${(impactComparison.burn?.after/impactComparison.burn?.before)*100}%`, height: '100%', backgroundColor: '#10b981', transition: "width 1.5s cubic-bezier(0.4, 0, 0.2, 1)", boxShadow: "0 0 10px #10b981"}}></div>
                   </div>
                </div>
             </div>
          </div>
        )}

        {improvementSummary.length > 0 && (
          <div style={{marginBottom: "32px", padding: "20px", backgroundColor: "rgba(16,185,129,0.05)", border: "1px solid rgba(16,185,129,0.2)", borderRadius: "16px"}}>
            <h4 style={{marginTop: 0, color: "#34d399", marginBottom: "12px", fontSize: "1.1rem"}}>Key Improvements</h4>
            <ul style={{margin: 0, paddingLeft: "20px", color: "#6ee7b7", lineHeight: "1.6"}}>
              {improvementSummary.map((item, i) => (
                <li key={i} style={{marginBottom: "6px"}}>{item}</li>
              ))}
            </ul>
          </div>
        )}

        {memoryComparison && Object.keys(memoryComparison).length > 0 && (
          <div style={{marginBottom: "32px", padding: "16px 20px", backgroundColor: "rgba(56,189,248,0.05)", borderLeft: "4px solid #38bdf8", borderRadius: "8px"}}>
            <p style={{margin: 0, color: "#bae6fd", fontSize: "0.95rem"}}><strong>Historical Context:</strong> Compared to previous run ({memoryComparison.topic}), runway improved from <b>{memoryComparison.previous_runway} months</b> to <b>{memoryComparison.current_runway} months</b>.</p>
          </div>
        )}

        {actionPlan.length > 0 && (
          <div style={{marginBottom: "32px", padding: "24px", border: "1px solid #334155", borderRadius: "16px", background: "linear-gradient(to bottom right, #1e293b, #0f172a)", boxShadow: "0 10px 30px -10px rgba(0,0,0,0.5)"}}>
            <h4 style={{marginTop: 0, color: "#f8fafc", marginBottom: "20px", fontSize: "1.2rem"}}>📋 Action Plan Framework</h4>
            <div style={{overflowX: "auto"}}>
              <table style={{width: "100%", borderCollapse: "collapse", color: "#cbd5e1", fontSize: "0.95rem"}}>
                <thead>
                  <tr style={{borderBottom: "2px solid #334155", color: "#94a3b8"}}>
                    <th style={{padding: "12px 16px", textAlign: "left"}}>Action</th>
                    <th style={{padding: "12px 16px", textAlign: "left"}}>Owner</th>
                    <th style={{padding: "12px 16px", textAlign: "left"}}>Timeline</th>
                    <th style={{padding: "12px 16px", textAlign: "left"}}>Impact</th>
                  </tr>
                </thead>
                <tbody>
                  {actionPlan.map((act, i) => (
                    <tr key={i} style={{borderBottom: "1px solid #1e293b", transition: "background 0.2s"}} onMouseOver={e=>e.currentTarget.style.background="rgba(15,23,42,0.6)"} onMouseOut={e=>e.currentTarget.style.background="transparent"}>
                      <td style={{padding: "16px", fontWeight: "bold", color: "#f8fafc"}}>{act.action}</td>
                      <td style={{padding: "16px"}}><span style={{background: "rgba(56,189,248,0.1)", color: "#38bdf8", padding: "4px 8px", borderRadius: "6px", fontSize: "0.85rem", whiteSpace:"nowrap"}}>{act.owner}</span></td>
                      <td style={{padding: "16px", whiteSpace:"nowrap"}}><span style={{background: "rgba(245,158,11,0.1)", color: "#f59e0b", padding: "4px 8px", borderRadius: "6px", fontSize: "0.85rem"}}>{act.timeline}</span></td>
                      <td style={{padding: "16px", color: "#10b981"}}>{act.expected_impact}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {Object.keys(executionTimeline).length > 0 && (
          <div style={{marginBottom: "32px", padding: "24px", border: "1px solid #334155", borderRadius: "16px", background: "linear-gradient(to bottom right, #1e293b, #0f172a)", boxShadow: "0 10px 30px -10px rgba(0,0,0,0.5)"}}>
            <h4 style={{marginTop: 0, color: "#f8fafc", marginBottom: "20px", fontSize: "1.2rem"}}>🕒 Staged Execution Timeline</h4>
            <div style={{display: "flex", gap: "20px", flexWrap: "wrap"}}>
              {Object.entries(executionTimeline).map(([phase, tasks], i) => (
                <div key={i} style={{flex: "1 1 min-content", padding: "20px", background: "rgba(15,23,42,0.6)", borderRadius: "12px", border: "1px solid #334155", position: "relative"}}>
                  <div style={{position:"absolute", top:0, left:0, height:"4px", width:"100%", background: phase.includes("immediate") ? "#ef4444" : phase.includes("short") ? "#f59e0b" : "#38bdf8", borderTopLeftRadius:"12px", borderTopRightRadius:"12px"}}></div>
                  <h5 style={{margin: "0 0 12px 0", textTransform: "capitalize", color: "#f8fafc", fontSize: "1.05rem"}}>{phase.replace("_", " ")}</h5>
                  <ul style={{margin: 0, paddingLeft: "16px", fontSize: "0.95rem", color: "#cbd5e1", lineHeight: "1.6"}}>
                    {tasks.map((t, idx) => <li key={idx} style={{marginBottom: "6px"}}>{t}</li>)}
                  </ul>
                </div>
              ))}
            </div>
          </div>
        )}

        {kpiMetrics.length > 0 && (
          <div style={{marginBottom: "32px", padding: "24px", border: "1px solid #334155", borderRadius: "16px", background: "linear-gradient(to bottom right, #1e293b, #0f172a)", boxShadow: "0 10px 30px -10px rgba(0,0,0,0.5)"}}>
            <h4 style={{marginTop: 0, color: "#f8fafc", marginBottom: "20px", fontSize: "1.2rem"}}>📊 KPI Tracking Metrics</h4>
            <div style={{display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "16px"}}>
              {kpiMetrics.map((kpi, i) => (
                <div key={i} style={{padding: "16px", background: "rgba(15,23,42,0.6)", borderRadius: "12px", border: "1px solid #334155", transition: "transform 0.2s"}} onMouseOver={e=>e.currentTarget.style.transform="scale(1.02)"} onMouseOut={e=>e.currentTarget.style.transform="scale(1)"}>
                  <div style={{color: "#38bdf8", fontSize: "0.8rem", fontWeight: "bold", marginBottom: "4px", textTransform: "uppercase", letterSpacing: "0.05em"}}>Track {kpi.tracking_frequency}</div>
                  <p style={{margin: "0 0 8px 0", fontWeight: "bold", fontSize: "1.1rem", color: "#f8fafc"}}>{kpi.metric}</p>
                  <p style={{margin: 0, fontSize: "0.95rem", color: "#10b981", fontWeight: "500", display: "inline-block", background: "rgba(16,185,129,0.1)", padding: "4px 8px", borderRadius: "6px"}}>Target: {kpi.target}</p>
                </div>
              ))}
            </div>
          </div>
        )}

        {scenarioAnalysis.length > 0 && (
          <div style={{marginBottom: "32px", padding: "24px", border: "1px solid #7f1d1d", borderRadius: "16px", background: "linear-gradient(to bottom right, #450a0a, #0f172a)"}}>
            <h4 style={{marginTop: 0, color: "#fecaca", marginBottom: "16px", fontSize: "1.2rem"}}>⚠️ Scenario Risk Analysis</h4>
            <div style={{display: "flex", flexDirection: "column", gap: "12px"}}>
              {scenarioAnalysis.map((scen, i) => (
                <div key={i} style={{padding: "16px", background: "rgba(69,10,10,0.4)", borderLeft: "4px solid #ef4444", borderRadius: "6px"}}>
                  <p style={{margin: "0 0 6px 0", fontWeight: "bold", color: "#fca5a5", fontSize: "1.05rem"}}>{scen.scenario}</p>
                  <p style={{margin: "0 0 4px 0", fontSize: "0.95rem", color: "#fecaca"}}><strong>Impact:</strong> {scen.impact}</p>
                  <p style={{margin: 0, fontSize: "0.95rem", color: "#fca5a5"}}><strong>Risk:</strong> {scen.risk}</p>
                </div>
              ))}
            </div>
          </div>
        )}

        {Object.keys(confidenceBreakdown).length > 0 && (
          <div style={{marginBottom: "32px", padding: "24px", border: "1px solid #334155", borderRadius: "16px", background: "linear-gradient(to bottom right, #1e293b, #0f172a)"}}>
            <h4 style={{marginTop: 0, color: "#f8fafc", marginBottom: "16px", fontSize: "1.2rem"}}>🛡️ AI Confidence Assessment</h4>
            <div style={{display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "16px"}}>
              {Object.entries(confidenceBreakdown).map(([k, v], i) => (
                <div key={i} style={{padding: "16px", background: "rgba(15,23,42,0.6)", borderRadius: "12px", border: "1px solid #334155"}}>
                  <p style={{margin: "0 0 6px 0", fontWeight: "bold", fontSize: "0.85rem", textTransform: "capitalize", color: "#94a3b8"}}>{k.replace(/_/g, " ")}</p>
                  <p style={{margin: 0, fontSize: "1.1rem", color: "#f8fafc", fontWeight: "bold"}}>{v}</p>
                </div>
              ))}
            </div>
          </div>
        )}

        {assumptions.length > 0 && (
          <div style={{marginBottom: "32px", padding: "24px", border: "1px solid #334155", borderRadius: "16px", background: "rgba(15,23,42,0.6)"}}>
            <h4 style={{marginTop: 0, color: "#f8fafc", marginBottom: "16px", fontSize: "1.2rem"}}>📌 Execution Assumptions</h4>
            <ul style={{margin: 0, paddingLeft: "24px", color: "#cbd5e1", fontSize: "1rem", lineHeight: "1.7"}}>
              {assumptions.map((item, i) => (
                <li key={i} style={{marginBottom: "8px"}}>{item}</li>
              ))}
            </ul>
          </div>
        )}

        <h3 style={{color: "#f8fafc", marginTop: "40px"}}>Detailed System Output</h3>
        {error ? <p className="error-text" style={{padding:"12px", background:"#450a0a", color:"#fca5a5", borderRadius:"8px", border:"1px solid #ef4444"}}>{error}</p> : null}
        <pre style={{padding:"20px", background:"#0b1326", border:"1px solid #334155", borderRadius:"12px"}}>{finalOutput ? JSON.stringify(finalOutput, null, 2) : "Run the workflow to view final output."}</pre>
        
        <div style={{display: "flex", gap: "12px", marginTop: "20px", marginBottom: "24px"}}>
          <button onClick={() => setShowExplanation(!showExplanation)} style={{background:"#1e293b", border:"1px solid #38bdf8", color:"#38bdf8", padding:"8px 16px", borderRadius:"8px", cursor:"pointer", transition:"0.2s"}} onMouseOver={e=>e.currentTarget.style.background="rgba(56,189,248,0.1)"} onMouseOut={e=>e.currentTarget.style.background="#1e293b"}>
            {showExplanation ? "Hide Explanation" : "📖 Explain this Decision simply"}
          </button>
          <button onClick={copySnapshot} disabled={!finalOutput} style={{background:"transparent", border:"1px solid #334155", color:"#cbd5e1", padding:"8px 16px", borderRadius:"8px", cursor:"pointer", transition:"0.2s", opacity: !finalOutput ? 0.5 : 1}} onMouseOver={e=>{if(finalOutput) {e.currentTarget.style.background="#334155";e.currentTarget.style.color="#f8fafc"}}} onMouseOut={e=>{if(finalOutput) {e.currentTarget.style.background="transparent";e.currentTarget.style.color="#cbd5e1"}}}>
            🔗 Copy Snapshot
          </button>
          <button onClick={downloadPDF} disabled={!finalOutput} style={{background:"transparent", border:"1px solid #334155", color:"#cbd5e1", padding:"8px 16px", borderRadius:"8px", cursor:"pointer", transition:"0.2s", opacity: !finalOutput ? 0.5 : 1}} onMouseOver={e=>{if(finalOutput) {e.currentTarget.style.background="#334155";e.currentTarget.style.color="#f8fafc"}}} onMouseOut={e=>{if(finalOutput) {e.currentTarget.style.background="transparent";e.currentTarget.style.color="#cbd5e1"}}}>
            📄 Download Report
          </button>
        </div>

        {showExplanation && (
          <div style={{marginBottom: "24px", padding: "20px", backgroundColor: "rgba(245,158,11,0.05)", border: "1px solid rgba(245,158,11,0.2)", borderRadius: "12px", color: "#fbbf24", fontSize: "1.05rem", lineHeight: "1.6"}}>
            <strong>Story Mode Explanation:</strong> Based on a multi-agent debate and quantitative simulations, the AI identified critical trade-offs between aggressive growth and runway survival. It selected `<strong style={{color:"#fcd34d"}}>{bestStrategy?.strategy_name || "this strategy"}</strong>` specifically because it seamlessly bridges structural cost-cutting with non-destructive scaling, heavily factoring in the mandated `<strong style={{color:"#fcd34d"}}>{mode}</strong>` execution philosophy.
          </div>
        )}
      </section>

      <section className="debate-panel" style={{background: "linear-gradient(to right, #111c34, #16233f)", padding: "24px", borderRadius: "16px", border: "1px solid #334155"}}>
        <h3 style={{fontSize:"1.4rem", marginBottom: "20px", color: "#f8fafc"}}>⚔️ Live Debate Protocol</h3>
        {revisionLabel ? <p className="revision-label" style={{marginBottom: "16px"}}>{revisionLabel}</p> : null}
        {debateHistory.length === 0 ? (
          <p className="debate-empty">Run the workflow to view live AI debate rounds.</p>
        ) : (
          <div style={{position: "relative", paddingLeft: "20px", borderLeft: "2px solid #334155"}}>
            {debateHistory.map((d, i) => (
              <div key={i} style={{background: "#1e293b", marginBottom: "20px", padding: "20px", border: "1px solid #334155", borderRadius: "12px", position: "relative"}}>
                <div style={{position:"absolute", left:"-27px", top:"20px", width:"12px", height:"12px", borderRadius:"50%", background:"#38bdf8", border:"3px solid #0f172a"}}></div>
                <p style={{margin:"0 0 12px 0", color:"#f8fafc", fontWeight:"bold", fontSize:"1.05rem"}}>
                  Round {d.round} {d.revision ? <span style={{color:"#f59e0b", fontSize:"0.85rem"}}>({d.revision})</span> : ""}
                </p>
                <div style={{background:"rgba(34,197,94,0.05)", padding:"16px", borderRadius:"8px", borderLeft:"3px solid #22c55e", marginBottom:"12px"}}>
                  <p style={{margin:0, color:"#4ade80", fontSize:"0.95rem", lineHeight: "1.6"}}><strong>💡 Proposal:</strong> {d.proposal || "No proposal available"}</p>
                </div>
                <div style={{background:"rgba(244,63,94,0.05)", padding:"16px", borderRadius:"8px", borderLeft:"3px solid #f43f5e"}}>
                  <p style={{margin:0, color:"#fb7185", fontSize:"0.95rem", lineHeight: "1.6"}}><strong>😈 Critic:</strong> {d.critique || "No critique available"}</p>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      {rejectedStrategies.length > 0 && (
        <section className="debate-panel rejected-strategies" style={{background: "#111c34", padding: "24px", borderRadius: "16px", border: "1px solid #334155", marginTop: "24px"}}>
          <h3 style={{color: "#fca5a5", fontSize:"1.3rem", marginBottom:"16px"}}>🚫 Rejected Strategies</h3>
          {rejectedStrategies.map((s, i) => (
            <div key={i} className="debate-card" style={{borderLeftColor: "#ef4444", backgroundColor: "rgba(69,10,10,0.3)", padding: "16px", border: "1px solid rgba(239,68,68,0.2)", borderRadius: "8px", marginBottom: "12px"}}>
              <p style={{margin: "0 0 8px 0", color: "#fecaca", fontSize: "1.05rem"}}><b>{s.strategy_name}</b></p>
              <p className="critique" style={{color: "#f87171", margin: 0, fontSize: "0.95rem"}}>Reason: {s.reason}</p>
            </div>
          ))}
        </section>
      )}

      {decisionTrace.length > 0 && (
        <section className="debate-panel decision-trace" style={{background: "#111c34", padding: "24px", borderRadius: "16px", border: "1px solid #334155", marginTop: "24px"}}>
          <h3 style={{color: "#818cf8", fontSize:"1.3rem"}}>🧠 Decision Trace</h3>
          <ul style={{textAlign: "left", color: "#cbd5e1", paddingLeft: "24px", marginTop: "16px", lineHeight: "1.7", fontSize: "1rem"}}>
            {decisionTrace.map((trace, i) => (
              <li key={i} style={{marginBottom: "8px"}}>{trace}</li>
            ))}
          </ul>
        </section>
      )}

      <footer style={{textAlign: "center", marginTop: "60px", color: "#64748b", fontSize: "1rem", borderTop: "1px solid #1e293b", padding: "30px 0"}}>
        From problem &rarr; debate &rarr; decision &rarr; execution in seconds. 🚀
      </footer>
    </div>
  );
}
