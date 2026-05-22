import Link from "next/link";

export default function ProjectsPage() {
  return (
    <div className="max-w-6xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Projects</h1>
        <Link href="/projects/new" className="rounded-lg bg-helix-600 px-4 py-2 text-sm font-medium text-white hover:bg-helix-700">
          New Project
        </Link>
      </div>
      <div className="rounded-xl border bg-white p-12 shadow-sm text-center">
        <p className="text-gray-500">No projects yet. Create your first migration project.</p>
      </div>
    </div>
  );
}
