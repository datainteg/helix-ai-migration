export default function LLMSettingsPage() {
  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <h1 className="text-2xl font-bold text-gray-900">LLM Provider Settings</h1>

      {/* Provider List */}
      <div className="rounded-xl border bg-white p-6 shadow-sm">
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-semibold">Providers</h3>
          <button className="rounded-lg bg-helix-600 px-4 py-2 text-sm font-medium text-white hover:bg-helix-700">
            Add Provider
          </button>
        </div>
        <div className="text-sm text-gray-500">No providers configured. Add your first LLM provider.</div>
      </div>

      {/* Agent Model Mapping */}
      <div className="rounded-xl border bg-white p-6 shadow-sm">
        <h3 className="font-semibold mb-4">Agent Model Mapping</h3>
        <p className="text-sm text-gray-500">Map specific AI models to individual agents for cost optimization and flexibility.</p>
        <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-3 text-sm">
          {["BA Agent", "Architect Agent", "Data Engineer", "QA Agent", "Recon Agent", "DevOps Agent", "PM Agent"].map((agent) => (
            <div key={agent} className="flex items-center justify-between rounded-lg border px-3 py-2">
              <span className="font-medium">{agent}</span>
              <span className="text-gray-400 text-xs">Default</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
