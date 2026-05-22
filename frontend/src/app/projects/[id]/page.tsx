import Link from "next/link";

export default function ProjectDetailPage() {
  return (
    <div className="max-w-6xl mx-auto space-y-6">
      <div className="flex items-center gap-4">
        <Link href="/projects" className="text-sm text-helix-600 hover:underline">&larr; Projects</Link>
        <h1 className="text-2xl font-bold text-gray-900">Project Workspace</h1>
      </div>
      <div className="flex gap-2 border-b pb-2 text-sm">
        <span className="px-3 py-1 rounded-t-lg bg-white border font-medium">Overview</span>
        <span className="px-3 py-1 text-gray-500">Requirements</span>
        <span className="px-3 py-1 text-gray-500">Agent Workflow</span>
        <span className="px-3 py-1 text-gray-500">Validation</span>
        <span className="px-3 py-1 text-gray-500">Reconciliation</span>
        <span className="px-3 py-1 text-gray-500">Reports</span>
      </div>
      <div className="rounded-xl border bg-white p-12 shadow-sm text-center">
        <p className="text-gray-500">Project workspace — select a tab to view details.</p>
      </div>
    </div>
  );
}
