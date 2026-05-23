import Link from "next/link";

export default function AdminPage() {
  return (
    <div className="max-w-6xl mx-auto space-y-6">
      <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">Admin Panel</h1>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Link href="/admin/users" className="rounded-xl border dark:border-gray-800 bg-white dark:bg-gray-900 p-6 shadow-sm hover:shadow-md transition-shadow">
          <h3 className="font-semibold text-gray-900 dark:text-gray-100">User Management</h3>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">Manage users and roles</p>
        </Link>
        <Link href="/admin/llm-settings" className="rounded-xl border dark:border-gray-800 bg-white dark:bg-gray-900 p-6 shadow-sm hover:shadow-md transition-shadow">
          <h3 className="font-semibold text-gray-900 dark:text-gray-100">LLM Provider Settings</h3>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">Configure AI providers and model mapping</p>
        </Link>
        <Link href="/admin/system-health" className="rounded-xl border dark:border-gray-800 bg-white dark:bg-gray-900 p-6 shadow-sm hover:shadow-md transition-shadow">
          <h3 className="font-semibold text-gray-900 dark:text-gray-100">System Health</h3>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">Service status and metrics</p>
        </Link>
        <Link href="/admin/audit-logs" className="rounded-xl border dark:border-gray-800 bg-white dark:bg-gray-900 p-6 shadow-sm hover:shadow-md transition-shadow">
          <h3 className="font-semibold text-gray-900 dark:text-gray-100">Audit Logs</h3>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">Security and activity events</p>
        </Link>
      </div>
    </div>
  );
}
