"use client";

export default function AgentWorkflowPage() {
  const nodes = [
    { id: "1", label: "Business Analyst", status: "completed", x: 100, y: 50 },
    { id: "2", label: "Architect", status: "running", x: 300, y: 50 },
    { id: "3", label: "Human Approval", status: "pending", x: 500, y: 50 },
    { id: "4", label: "Data Engineer", status: "pending", x: 700, y: 50 },
    { id: "5", label: "QA / Validation", status: "pending", x: 900, y: 50 },
    { id: "6", label: "Recon", status: "pending", x: 1100, y: 50 },
  ];

  const statusColors: Record<string, string> = {
    completed: "bg-green-100 border-green-400 text-green-800",
    running: "bg-blue-100 border-blue-400 text-blue-800",
    pending: "bg-gray-100 border-gray-300 text-gray-600",
    failed: "bg-red-100 border-red-400 text-red-800",
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Agent Workflow</h1>
        <button className="rounded-lg bg-helix-600 px-4 py-2 text-sm font-medium text-white hover:bg-helix-700">
          Start Workflow
        </button>
      </div>

      <div className="rounded-xl border bg-white p-6 shadow-sm overflow-x-auto">
        <p className="text-xs text-gray-400 mb-4">BMAD Migration Workflow — React Flow canvas placeholder</p>
        <div className="flex gap-4 min-w-[1200px]">
          {nodes.map((node, i) => (
            <div key={node.id} className="flex items-center gap-2">
              <div className={`rounded-lg border-2 px-4 py-3 text-sm font-medium min-w-[150px] text-center ${statusColors[node.status]}`}>
                <div className="text-xs text-gray-400 mb-1">Step {i + 1}</div>
                {node.label}
                <div className="text-xs mt-1 capitalize">{node.status}</div>
              </div>
              {i < nodes.length - 1 && <div className="text-gray-300 text-lg">→</div>}
            </div>
          ))}
        </div>
      </div>

      <div className="rounded-xl border bg-white p-6 shadow-sm">
        <h3 className="font-semibold mb-3">Human Approval</h3>
        <p className="text-sm text-gray-500 mb-4">Review the Architect Agent output before proceeding to execution agents.</p>
        <div className="flex gap-3">
          <button className="rounded-lg bg-green-600 px-4 py-2 text-sm font-medium text-white hover:bg-green-700">Approve</button>
          <button className="rounded-lg border border-red-300 px-4 py-2 text-sm font-medium text-red-600 hover:bg-red-50">Reject</button>
          <button className="rounded-lg border px-4 py-2 text-sm font-medium text-gray-600 hover:bg-gray-50">Request Changes</button>
        </div>
      </div>
    </div>
  );
}
