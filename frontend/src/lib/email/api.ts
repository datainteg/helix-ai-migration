/**
 * Email / SMTP settings client (admin). Auth via HttpOnly cookie.
 * Secrets are write-only: the GET returns `*_set` booleans, never the values.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

export interface EmailSettings {
  configured: boolean;
  enabled: boolean;
  provider: "smtp" | "sendgrid";
  from_email: string;
  from_name: string;
  smtp_host: string;
  smtp_port: number;
  smtp_user: string;
  smtp_password_set: boolean;
  smtp_tls: boolean;
  sendgrid_api_key_set: boolean;
}

export interface EmailSettingsInput {
  enabled: boolean;
  provider: "smtp" | "sendgrid";
  from_email?: string;
  from_name?: string;
  smtp_host?: string;
  smtp_port?: number;
  smtp_user?: string;
  smtp_password?: string;     // blank keeps stored
  smtp_tls?: boolean;
  sendgrid_api_key?: string;  // blank keeps stored
}

async function req<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    credentials: "include",
    headers: { "Content-Type": "application/json", ...(init.headers || {}) },
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(detail.detail || `${path} → ${res.status}`);
  }
  const text = await res.text();
  return (text ? JSON.parse(text) : undefined) as T;
}

export function fetchEmailSettings(): Promise<EmailSettings> {
  return req<EmailSettings>(`/api/v1/email-settings`);
}

export function saveEmailSettings(data: EmailSettingsInput): Promise<EmailSettings> {
  return req<EmailSettings>(`/api/v1/email-settings`, { method: "PUT", body: JSON.stringify(data) });
}

export function testEmailSettings(data: EmailSettingsInput & { to: string }): Promise<{ ok: boolean; message: string }> {
  return req<{ ok: boolean; message: string }>(`/api/v1/email-settings/test`, { method: "POST", body: JSON.stringify(data) });
}
