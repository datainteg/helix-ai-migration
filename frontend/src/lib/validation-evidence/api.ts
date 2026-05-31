/**
 * Validation evidence + QA review client. Backend: app/api/validation_evidence.py.
 * Upload is multipart (optional file + form fields); auth via HttpOnly cookie.
 */
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

async function req<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init, credentials: "include",
    headers: { "Content-Type": "application/json", ...(init.headers || {}) },
  });
  if (!res.ok) {
    const d = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error((d && (d.detail as string)) || `${path} → ${res.status}`);
  }
  const t = await res.text();
  return (t ? JSON.parse(t) : undefined) as T;
}

export interface ValidationEvidence {
  id: string; project_id: string; sprint_id: string | null; artifact_id: string | null;
  uploaded_by_user_id: string | null; evidence_type: string; title: string;
  description: string | null; file_path: string | null; content_json: unknown | null;
  status: "uploaded" | "under_review" | "accepted" | "rejected" | "changes_required";
  reviewed_by_agent: string | null; reviewed_by_user_id: string | null;
  review_summary: string | null; created_at: string | null;
}

export const listEvidence = (projectId: string) =>
  req<ValidationEvidence[]>(`/api/v1/projects/${projectId}/validation/evidence`);
export const getEvidence = (evidenceId: string) =>
  req<ValidationEvidence>(`/api/v1/validation/evidence/${evidenceId}`);

export async function uploadEvidence(projectId: string, form: {
  title: string; evidence_type: string; description?: string; content_json?: string; file?: File | null;
}): Promise<ValidationEvidence> {
  const fd = new FormData();
  fd.append("title", form.title);
  fd.append("evidence_type", form.evidence_type);
  if (form.description) fd.append("description", form.description);
  if (form.content_json) fd.append("content_json", form.content_json);
  if (form.file) fd.append("file", form.file);
  const res = await fetch(`${API_BASE}/api/v1/projects/${projectId}/validation/evidence`, {
    method: "POST", credentials: "include", body: fd,   // no Content-Type — browser sets the multipart boundary
  });
  if (!res.ok) {
    const d = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error((d && (d.detail as string)) || `upload → ${res.status}`);
  }
  return res.json();
}

export const qaReviewEvidence = (evidenceId: string) =>
  req<{ evidence_id: string; status: string; artifact_id: string; mode: string }>(`/api/v1/validation/evidence/${evidenceId}/qa-review`, { method: "POST" });
export const acceptEvidence = (evidenceId: string) =>
  req<ValidationEvidence>(`/api/v1/validation/evidence/${evidenceId}/accept`, { method: "POST" });
export const rejectEvidence = (evidenceId: string, comment: string) =>
  req<ValidationEvidence>(`/api/v1/validation/evidence/${evidenceId}/reject`, { method: "POST", body: JSON.stringify({ comment }) });
