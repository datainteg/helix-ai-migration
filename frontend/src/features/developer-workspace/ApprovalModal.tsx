"use client";

export default function ApprovalModal({
  versionId,
  onApprove,
  onReject,
}: {
  versionId: string;
  onApprove: (notes: string) => void;
  onReject: (notes: string) => void;
}) {
  return (
    <div className="space-y-3">
      <h3 className="font-semibold text-sm">Review & Approve</h3>
      <p className="text-xs text-gray-500">Generated artifacts must be reviewed and approved before production use.</p>
      <textarea id="approval-notes" className="w-full rounded-lg border px-3 py-2 text-xs" rows={3} placeholder="Add review notes..." />
      <div className="flex gap-2">
        <button onClick={() => onApprove((document.getElementById("approval-notes") as HTMLTextAreaElement)?.value || "")}
          className="flex-1 rounded-lg bg-green-600 px-3 py-2 text-xs font-medium text-white hover:bg-green-700">
          Approve
        </button>
        <button onClick={() => onReject((document.getElementById("approval-notes") as HTMLTextAreaElement)?.value || "")}
          className="flex-1 rounded-lg border border-red-300 px-3 py-2 text-xs font-medium text-red-600 hover:bg-red-50">
          Reject
        </button>
      </div>
    </div>
  );
}
