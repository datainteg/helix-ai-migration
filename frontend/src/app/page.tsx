import Link from "next/link";

export default function HomePage() {
  return (
    <div className="max-w-4xl mx-auto space-y-8">
      <div className="text-center py-12">
        <h1 className="text-4xl font-bold text-helix-700">Helix Migration</h1>
        <p className="mt-4 text-lg text-gray-600 max-w-2xl mx-auto">
          Open-source AI-powered migration and validation platform. Plan, validate, reconcile, and manage
          complex data migrations using intelligent multi-agent workflows.
        </p>
        <div className="mt-8 flex gap-4 justify-center">
          <Link href="/setup/first-admin" className="rounded-lg bg-helix-600 px-6 py-3 text-white font-medium hover:bg-helix-700">
            Setup First Admin
          </Link>
          <Link href="/login" className="rounded-lg border border-gray-300 px-6 py-3 text-gray-700 font-medium hover:bg-gray-100">
            Login
          </Link>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="rounded-xl border bg-white p-6 shadow-sm">
          <h3 className="font-semibold text-lg">AI-Powered Planning</h3>
          <p className="mt-2 text-sm text-gray-600">Multi-agent BMAD workflows generate typed migration plans with human approval gates.</p>
        </div>
        <div className="rounded-xl border bg-white p-6 shadow-sm">
          <h3 className="font-semibold text-lg">Validation & Recon</h3>
          <p className="mt-2 text-sm text-gray-600">Schema checks, row counts, null detection, and reconciliation reports.</p>
        </div>
        <div className="rounded-xl border bg-white p-6 shadow-sm">
          <h3 className="font-semibold text-lg">Developer Workspace</h3>
          <p className="mt-2 text-sm text-gray-600">Upload .py and .sql files, get AI code review, and generate draft artifacts.</p>
        </div>
      </div>
    </div>
  );
}
