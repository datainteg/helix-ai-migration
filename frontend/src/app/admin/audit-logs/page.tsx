export default function AuditLogsPage() {
  return (
    <div className="max-w-6xl mx-auto space-y-6">
      <h1 className="text-2xl font-bold text-gray-900">Audit Logs</h1>
      <div className="rounded-xl border bg-white p-6 shadow-sm">
        <p className="text-sm text-gray-500">Audit log entries will appear here. Logs track login events, admin changes, LLM provider modifications, agent workflow approvals, artifact actions, and report exports.</p>
      </div>
    </div>
  );
}
