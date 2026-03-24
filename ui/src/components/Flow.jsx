import ReactFlow, { Background, Controls, MarkerType } from "reactflow";
import "reactflow/dist/style.css";
import NodeCard from "./NodeCard";

const NODE_META = [
  { id: "research", label: "Research Agent", x: 20, y: 180 },
  { id: "proposer", label: "Proposer Agent", x: 280, y: 70 },
  { id: "critic", label: "Critic Agent", x: 540, y: 180 },
  { id: "simulation", label: "Simulation Agent", x: 800, y: 70 },
  { id: "decision", label: "Decision Agent", x: 1060, y: 180 },
];

const EDGE_META = [
  ["research", "proposer"],
  ["proposer", "critic"],
  ["critic", "simulation"],
  ["simulation", "decision"],
];

const nodeTypes = { agentNode: NodeCard };

export default function Flow({ activeNode, nodeOutputs, nodeStatus, onNodeSelect, selectedNode }) {
  const doneStatuses = new Set(["completed", "revised", "approved"]);

  const nodes = NODE_META.map((node) => ({
    id: node.id,
    type: "agentNode",
    position: { x: node.x, y: node.y },
    data: {
      id: node.id,
      label: node.label,
      output: nodeOutputs[node.id],
      status: nodeStatus[node.id],
      active: activeNode === node.id,
      selected: selectedNode === node.id,
      onSelect: onNodeSelect,
    },
    draggable: false,
  }));

  const activeIndex = NODE_META.findIndex((n) => n.id === activeNode);
  const edges = EDGE_META.map(([source, target], index) => ({
    ...(() => {
      const sourceStatus = nodeStatus[source];
      const targetStatus = nodeStatus[target];
      let edgeState = "idle";
      if (sourceStatus === "failed" || targetStatus === "failed") edgeState = "failed";
      else if (doneStatuses.has(sourceStatus) && targetStatus === "running") edgeState = "active";
      else if (doneStatuses.has(sourceStatus) && (doneStatuses.has(targetStatus) || targetStatus === "idle")) {
        edgeState = "completed";
      }
      return { edgeState };
    })(),
    id: `${source}-${target}`,
    source,
    target,
    type: "smoothstep",
    animated: activeIndex >= index,
    className: `edge-${(() => {
      const sourceStatus = nodeStatus[source];
      const targetStatus = nodeStatus[target];
      if (sourceStatus === "failed" || targetStatus === "failed") return "failed";
      if (doneStatuses.has(sourceStatus) && targetStatus === "running") return "active";
      if (doneStatuses.has(sourceStatus) && (doneStatuses.has(targetStatus) || targetStatus === "idle")) return "completed";
      return "idle";
    })()}`,
    markerEnd: {
      type: MarkerType.ArrowClosed,
      width: 18,
      height: 18,
      color:
        nodeStatus[source] === "failed" || nodeStatus[target] === "failed"
          ? "#ef4444"
          : activeIndex >= index
          ? "#22d3ee"
          : "#475569",
    },
    style: {
      strokeWidth: 2.2,
      stroke:
        nodeStatus[source] === "failed" || nodeStatus[target] === "failed"
          ? "#ef4444"
          : activeIndex >= index
          ? "#22d3ee"
          : "#475569",
      filter:
        nodeStatus[source] === "failed" || nodeStatus[target] === "failed"
          ? "drop-shadow(0 0 8px rgba(239,68,68,.8))"
          : activeIndex >= index
          ? "drop-shadow(0 0 8px rgba(34,211,238,.8))"
          : "none",
    },
  }));

  return (
    <div className="flow-canvas">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        fitView
        minZoom={0.5}
        maxZoom={1.4}
        proOptions={{ hideAttribution: true }}
      >
        <Background color="#334155" gap={28} />
        <Controls />
      </ReactFlow>
    </div>
  );
}
