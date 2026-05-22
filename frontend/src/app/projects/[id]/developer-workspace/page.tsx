"use client";

export default function DeveloperWorkspacePage() {
  return (
    <div className="flex h-[calc(100vh-80px)] gap-0">
      {/* Left: Artifact Explorer */}
      <div className="w-64 border-r bg-white p-4 overflow-y-auto">
        <h3 className="font-semibold text-sm mb-3">Artifacts</h3>
        <div className="text-xs text-gray-500">No artifacts uploaded.</div>
        <button className="mt-4 w-full rounded-lg border border-dashed border-gray-300 px-3 py-2 text-xs text-gray-500 hover:border-helix-400 hover:text-helix-600">
          + Upload .py / .sql
        </button>
      </div>

      {/* Center: Code / Diff View */}
      <div className="flex-1 bg-white p-4 overflow-y-auto">
        <div className="flex gap-2 text-sm text-gray-500 border-b pb-2 mb-4">
          <span className="font-medium text-gray-900 border-b-2 border-helix-500 pb-2">Source</span>
          <span>Generated Draft</span>
          <span>Diff</span>
        </div>
        <div className="grid grid-cols-2 gap-4">
          <div className="rounded-lg border bg-gray-50 p-4 min-h-[300px]">
            <p className="text-xs text-gray-400">Original source code</p>
          </div>
          <div className="rounded-lg border bg-amber-50 p-4 min-h-[300px] border-dashed">
            <p className="text-xs text-amber-600">Generated draft — not yet approved</p>
          </div>
        </div>
      </div>

      {/* Right: AI Review Panel */}
      <div className="w-80 border-l bg-white p-4 overflow-y-auto">
        <h3 className="font-semibold text-sm mb-3">AI Review</h3>
        <div className="text-xs text-gray-500">Upload and analyze code to see AI review results.</div>
        <div className="mt-4 space-y-2">
          <div className="text-xs text-gray-400">Assumptions</div>
          <div className="text-xs text-gray-400">Limitations</div>
          <div className="text-xs text-gray-400">Security Findings</div>
          <div className="text-xs text-gray-400">Risks</div>
        </div>
      </div>
    </div>
  );
}
