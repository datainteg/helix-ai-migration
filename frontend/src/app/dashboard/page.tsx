export default function DashboardPage() {
  return (
    <div className="max-w-6xl mx-auto space-y-6">
      <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="rounded-xl border bg-white p-4 shadow-sm"><p className="text-xs text-gray-500">Active Projects</p><p className="text-2xl font-bold text-helix-600">0</p></div>
        <div className="rounded-xl border bg-white p-4 shadow-sm"><p className="text-xs text-gray-500">Pending Approvals</p><p className="text-2xl font-bold text-amber-600">0</p></div>
        <div className="rounded-xl border bg-white p-4 shadow-sm"><p className="text-xs text-gray-500">Validation Status</p><p className="text-2xl font-bold text-green-600">—</p></div>
        <div className="rounded-xl border bg-white p-4 shadow-sm"><p className="text-xs text-gray-500">Artifacts</p><p className="text-2xl font-bold text-gray-600">0</p></div>
      </div>
      <div className="rounded-xl border bg-white p-6 shadow-sm">
        <h3 className="font-semibold text-lg">Recent Activity</h3>
        <p className="mt-4 text-sm text-gray-500">No activity yet. Create your first project to get started.</p>
      </div>
    </div>
  );
}
