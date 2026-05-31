/**
 * Recon agent + business report client. Backend: app/api/recon_reports.py.
 * Auth via HttpOnly cookie.
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

export interface ReconReport {
  id: string; project_id: string; report_type: string; status: string;
  report_markdown: string | null; has_pdf: boolean; generated_by_agent: string | null;
  approved_by_user_id: string | null; approved_at: string | null; created_at: string | null;
}

export const generateReconPlan = (projectId: string) =>
  req<{ artifact_id: string; artifact_type: string; status: string; title: string }>(`/api/v1/projects/${projectId}/recon/generate-plan`, { method: "POST" });
export const generateReconCode = (projectId: string) =>
  req<{ created: number; files: { id: string; file_name: string; file_type: string; status: string }[] }>(`/api/v1/projects/${projectId}/recon/generate-code`, { method: "POST" });
export const generateReconReport = (projectId: string) =>
  req<ReconReport>(`/api/v1/projects/${projectId}/recon/generate-report`, { method: "POST" });
export const listReconReports = (projectId: string) =>
  req<ReconReport[]>(`/api/v1/projects/${projectId}/recon/reports`);
export const getReconReport = (reportId: string) =>
  req<ReconReport>(`/api/v1/recon/reports/${reportId}`);
export const approveReconReport = (reportId: string, comment?: string) =>
  req<ReconReport>(`/api/v1/recon/reports/${reportId}/approve`, { method: "POST", body: JSON.stringify({ comment }) });
export const requestReconReportChanges = (reportId: string, comment: string) =>
  req<ReconReport>(`/api/v1/recon/reports/${reportId}/request-changes`, { method: "POST", body: JSON.stringify({ comment }) });

export async function downloadReconReportPdf(reportId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/api/v1/recon/reports/${reportId}/download`, { credentials: "include" });
  if (!res.ok) throw new Error(`download → ${res.status}`);
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = `recon-report-${reportId}.pdf`;
  document.body.appendChild(a); a.click(); a.remove();
  URL.revokeObjectURL(url);
}
