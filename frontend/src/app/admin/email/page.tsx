"use client";

/**
 * /admin/email — SMTP / SendGrid mail configuration + test.
 *
 * Admins configure the org's mail transport and send a real test email to
 * verify it works before relying on it (notification emails, invites, resets).
 * Secrets are write-only — the API returns "set" booleans, never the values.
 */

import { useEffect, useState } from "react";
import { Save, Send, ShieldCheck, AlertTriangle, Mail } from "lucide-react";

import { AdminShell } from "@/components/layout";
import { Card, Button, Chip, Tabs, ErrorBanner, LoadingState } from "@/components/ui";
import {
  fetchEmailSettings, saveEmailSettings, testEmailSettings,
  type EmailSettings, type EmailSettingsInput,
} from "@/lib/email/api";

export default function EmailSettingsPage() {
  const [loading, setLoading] = useState(true);
  const [saved, setSaved] = useState<EmailSettings | null>(null);
  const [err, setErr] = useState("");
  const [ok, setOk] = useState("");
  const [saving, setSaving] = useState(false);

  // form
  const [enabled, setEnabled] = useState(false);
  const [provider, setProvider] = useState<"smtp" | "sendgrid">("smtp");
  const [fromEmail, setFromEmail] = useState("");
  const [fromName, setFromName] = useState("");
  const [smtpHost, setSmtpHost] = useState("");
  const [smtpPort, setSmtpPort] = useState("587");
  const [smtpUser, setSmtpUser] = useState("");
  const [smtpPassword, setSmtpPassword] = useState("");
  const [smtpTls, setSmtpTls] = useState(true);
  const [sendgridKey, setSendgridKey] = useState("");

  // test
  const [testTo, setTestTo] = useState("");
  const [testing, setTesting] = useState(false);
  const [testMsg, setTestMsg] = useState<{ ok: boolean; text: string } | null>(null);

  const hydrate = (s: EmailSettings) => {
    setSaved(s);
    setEnabled(s.enabled);
    setProvider(s.provider);
    setFromEmail(s.from_email);
    setFromName(s.from_name);
    setSmtpHost(s.smtp_host);
    setSmtpPort(String(s.smtp_port || 587));
    setSmtpUser(s.smtp_user);
    setSmtpTls(s.smtp_tls);
    setSmtpPassword("");
    setSendgridKey("");
  };

  const load = async () => {
    setLoading(true);
    try {
      hydrate(await fetchEmailSettings());
      setErr("");
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { void load(); }, []);

  const buildInput = (): EmailSettingsInput => ({
    enabled, provider,
    from_email: fromEmail || undefined,
    from_name: fromName || undefined,
    smtp_host: smtpHost || undefined,
    smtp_port: smtpPort ? Number(smtpPort) : undefined,
    smtp_user: smtpUser || undefined,
    smtp_password: smtpPassword || undefined,
    smtp_tls: smtpTls,
    sendgrid_api_key: sendgridKey || undefined,
  });

  const onSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true); setErr(""); setOk("");
    try {
      hydrate(await saveEmailSettings(buildInput()));
      setOk("Email settings saved.");
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : "Save failed");
    } finally {
      setSaving(false);
    }
  };

  const onTest = async () => {
    if (!testTo.trim()) { setTestMsg({ ok: false, text: "Enter a recipient address." }); return; }
    setTesting(true); setTestMsg(null);
    try {
      const r = await testEmailSettings({ ...buildInput(), to: testTo.trim() });
      setTestMsg({ ok: true, text: r.message });
    } catch (e: unknown) {
      setTestMsg({ ok: false, text: e instanceof Error ? e.message : "Test failed" });
    } finally {
      setTesting(false);
    }
  };

  const inputCls = "w-full h-9 px-2.5 text-[13px] rounded-[8px] border border-hx bg-surface focus-ring";

  return (
    <AdminShell
      title="Email / SMTP"
      subtitle="Configure the mail transport used for notifications, invitations, and password resets — then send a test to verify it works."
      page="Email / SMTP"
      actions={
        <Chip tone={saved?.enabled && (saved?.smtp_host || saved?.sendgrid_api_key_set) ? "ok" : "default"} dot>
          {saved?.enabled && (saved?.smtp_host || saved?.sendgrid_api_key_set) ? "Active" : "Not configured"}
        </Chip>
      }
    >
      {err && <ErrorBanner message={err} onDismiss={() => setErr("")} />}
      {ok && (
        <div className="flex items-center gap-2 px-3 py-2 rounded-[8px] border border-hx-2 bg-[var(--con-ok-soft,#ecfdf5)] text-[12.5px] text-ink-2">
          <ShieldCheck className="h-4 w-4 text-[var(--con-ok)]" /> {ok}
        </div>
      )}

      {loading ? (
        <LoadingState label="Loading email settings…" />
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-[1.3fr_1fr] gap-4">
          <Card title="Mail transport" description="Pick a provider and enter its connection details.">
            <form onSubmit={onSave} className="space-y-4">
              <label className="flex items-center gap-2.5">
                <button type="button" role="switch" aria-checked={enabled} onClick={() => setEnabled((v) => !v)}
                  className={`relative h-5 w-9 rounded-full transition-colors ${enabled ? "bg-[var(--con-brand)]" : "bg-app-2 border border-hx-2"}`}>
                  <span className={`absolute top-0.5 h-4 w-4 rounded-full bg-white shadow transition-all ${enabled ? "left-[18px]" : "left-0.5"}`} />
                </button>
                <span className="text-[13px] text-ink">Email enabled</span>
              </label>

              <Tabs tabs={[{ id: "smtp", label: "SMTP" }, { id: "sendgrid", label: "SendGrid" }]} value={provider} onChange={(v) => setProvider(v as "smtp" | "sendgrid")} variant="pill" />

              <div className="grid grid-cols-2 gap-3">
                <Field label="From email"><input type="email" value={fromEmail} onChange={(e) => setFromEmail(e.target.value)} placeholder="noreply@company.com" className={inputCls} /></Field>
                <Field label="From name"><input value={fromName} onChange={(e) => setFromName(e.target.value)} placeholder="Helix" className={inputCls} /></Field>
              </div>

              {provider === "smtp" ? (
                <>
                  <div className="grid grid-cols-[1fr_120px] gap-3">
                    <Field label="SMTP host"><input value={smtpHost} onChange={(e) => setSmtpHost(e.target.value)} placeholder="smtp.gmail.com" className={inputCls} /></Field>
                    <Field label="Port"><input type="number" value={smtpPort} onChange={(e) => setSmtpPort(e.target.value)} className={`${inputCls} font-mono`} /></Field>
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <Field label="Username"><input value={smtpUser} onChange={(e) => setSmtpUser(e.target.value)} placeholder="apikey / user" className={inputCls} /></Field>
                    <Field label={`Password${saved?.smtp_password_set ? " (set — blank keeps it)" : ""}`}>
                      <input type="password" value={smtpPassword} onChange={(e) => setSmtpPassword(e.target.value)} placeholder={saved?.smtp_password_set ? "••••••••" : ""} className={inputCls} />
                    </Field>
                  </div>
                  <label className="flex items-center gap-2.5">
                    <button type="button" role="switch" aria-checked={smtpTls} onClick={() => setSmtpTls((v) => !v)}
                      className={`relative h-5 w-9 rounded-full transition-colors ${smtpTls ? "bg-[var(--con-brand)]" : "bg-app-2 border border-hx-2"}`}>
                      <span className={`absolute top-0.5 h-4 w-4 rounded-full bg-white shadow transition-all ${smtpTls ? "left-[18px]" : "left-0.5"}`} />
                    </button>
                    <span className="text-[13px] text-ink">Use STARTTLS</span>
                  </label>
                </>
              ) : (
                <Field label={`SendGrid API key${saved?.sendgrid_api_key_set ? " (set — blank keeps it)" : ""}`}>
                  <input type="password" value={sendgridKey} onChange={(e) => setSendgridKey(e.target.value)} placeholder={saved?.sendgrid_api_key_set ? "••••••••" : "SG.xxxx"} className={`${inputCls} font-mono`} />
                </Field>
              )}

              <div className="pt-1"><Button type="submit" disabled={saving}><Save className="h-3.5 w-3.5" /> {saving ? "Saving…" : "Save settings"}</Button></div>
            </form>
          </Card>

          <Card title="Test connection" description="Send a real test email with the current form values — saved or not.">
            <div className="space-y-3">
              <Field label="Send test to">
                <input type="email" value={testTo} onChange={(e) => setTestTo(e.target.value)} placeholder="you@company.com" className={inputCls} />
              </Field>
              <Button variant="outline" onClick={onTest} loading={testing}><Send className="h-3.5 w-3.5" /> Send test email</Button>
              {testMsg && (
                <div className={`flex items-start gap-2 px-3 py-2 rounded-[8px] border border-hx-2 text-[12.5px] ${testMsg.ok ? "bg-[var(--con-ok-soft,#ecfdf5)] text-ink-2" : "bg-[var(--con-err-soft,#fef2f2)] text-ink-2"}`}>
                  {testMsg.ok ? <ShieldCheck className="h-4 w-4 mt-0.5 text-[var(--con-ok)] flex-shrink-0" /> : <AlertTriangle className="h-4 w-4 mt-0.5 text-[var(--con-err)] flex-shrink-0" />}
                  <span>{testMsg.text}</span>
                </div>
              )}
              <div className="flex items-start gap-2 text-[11.5px] text-ink-4 pt-1">
                <Mail className="h-3.5 w-3.5 mt-0.5 flex-shrink-0" />
                <span>The test uses what's in the form now (falling back to saved secrets for blank password / API-key fields), so you can verify before saving.</span>
              </div>
            </div>
          </Card>
        </div>
      )}
    </AdminShell>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="flex flex-col gap-1.5">
      <span className="text-[10px] uppercase tracking-wider font-mono text-ink-4">{label}</span>
      {children}
    </label>
  );
}
