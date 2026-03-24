import { Handle, Position } from "reactflow";

function preview(text) {
  if (!text) return "No output yet";
  const normalized = String(text).replace(/\s+/g, " ").trim();
  if (normalized.length <= 90) return normalized;
  return `${normalized.slice(0, 87)}...`;
}

export default function NodeCard({ data }) {
  const statusClass = `node-card ${data.status || "idle"} ${data.active ? "active" : ""} ${
    data.selected ? "selected" : ""
  }`;
  const statusLabel =
    data.status === "running"
      ? "Running..."
      : data.status === "revised"
      ? "Revised"
      : data.status === "approved"
      ? "Approved"
      : data.status === "completed"
      ? "Completed"
      : data.status === "failed"
      ? "Failed"
      : "Idle";

  return (
    <div className={statusClass} onClick={() => data.onSelect(data.id)} role="button" tabIndex={0}>
      <Handle type="target" position={Position.Left} className="edge-handle" />

      <div className="node-title">{data.label}</div>
      <div className={`node-status node-status-${data.status || "idle"}`}>
        {data.status === "running" ? <span className="node-spinner" /> : null}
        {statusLabel}
      </div>
      <div className="node-preview">{preview(data.output)}</div>

      <Handle type="source" position={Position.Right} className="edge-handle" />
    </div>
  );
}
