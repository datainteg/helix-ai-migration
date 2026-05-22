import Link from "next/link";

export default function AdminPage() {
  return (
    <div className="max-w-6xl mx-auto space-y-6">
      <h1 className="text-2xl font-bold text-gray-900">Admin Panel</h1>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Link href="/admin/users" className="rounded-xl border bg-white p-6 shadow-sm hover:shadow-md transition-shadow">
          <h3 className="font-semibold">User Management</h3>
          <p className="mt-1 text-sm text-gray-500">Manage users and roles</p>
        </Link>
        <Link href="/admin/llm-settings" className="rounded-xl border bg-white p-6 shadow-sm hover:shadow-md transition-shadow">
          <h3 className="font-semibold">LLM Provider Settings</h3>
          <p className="mt-1 text-sm text-gray-500">Configure AI providers and model mapping</p>
        </Link>
        <Link href="/admin/system-health" className="rounded-xl border bg-white p-6 shadow-sm hover:shadow-md transition-shadow">
          <h3 className="font-semibold">System Health</h3>
          <p className="mt-1 text-sm text-gray-500">Service status and metrics</p>
        </Link>
        <Link href="/admin/audit-logs" className="rounded-xl border bg-white p-6 shadow-sm hover:shadow-md transition-shadow">
          <h3 className="font-semibold">Audit Logs</h3>
          <p className="mt-1 text-sm text-gray-500">Security and activity events</p>
        </Link>
      </div>
    </div>
  );
}
