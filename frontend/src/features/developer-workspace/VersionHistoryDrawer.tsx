"use client";

const versions = [
  { id: "v1", number: "1", status: "uploaded", date: "2026-05-23" },
  { id: "v2", number: "2", status: "draft", date: "2026-05-23", agent: "Code Migration Agent" },
];

const statusColors: Record<string, string> = {
  uploaded: "bg-gray-100 text-gray-700",
  draft: "bg-amber-100 text-amber-700",
  approved: "bg-green-100 text-green-700",
  rejected: "bg-red-100 text-red-700",
};

export default function VersionHistoryDrawer() {
  return (
    <div className="text-xs">
      <h3 className="font-semibold text-sm mb-2">Version History</h3>
      {versions.map((v) => (
        <div key={v.id} className="flex items-center justify-between py-2 border-b last:border-0">
          <div>
            <span className="font-medium">v{v.number}</span>
            {v.agent && <span className="text-gray-400 ml-2">by {v.agent}</span>}
          </div>
          <div className="flex items-center gap-2">
            <span className="text-gray-400">{v.date}</span>
            <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${statusColors[v.status]}`}>
              {v.status.toUpperCase()}
            </span>
          </div>
        </div>
      ))}
    </div>
  );
}
