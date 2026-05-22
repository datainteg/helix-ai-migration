export default function SystemHealthPage() {
  const components = [
    { name: "Database", status: "healthy" },
    { name: "Redis", status: "unknown" },
    { name: "Temporal", status: "unknown" },
    { name: "Worker", status: "unknown" },
    { name: "Artifact Storage", status: "unknown" },
  ];

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <h1 className="text-2xl font-bold text-gray-900">System Health</h1>
      <div className="rounded-xl border bg-white p-6 shadow-sm">
        <div className="space-y-3">
          {components.map((c) => (
            <div key={c.name} className="flex items-center justify-between py-2 border-b last:border-0">
              <span className="text-sm font-medium">{c.name}</span>
              <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                c.status === "healthy" ? "bg-green-100 text-green-700" :
                c.status === "degraded" ? "bg-amber-100 text-amber-700" :
                "bg-gray-100 text-gray-600"
              }`}>{c.status}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
