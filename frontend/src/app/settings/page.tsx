"use client";

/**
 * /settings — per-user preferences.
 *
 * Sections:
 *  • Profile      — name + email (read-only until backend exposes user_profile PATCH).
 *  • Appearance   — mirrors TweaksPanel; writes to the same `useTweaks` store so changes
 *                   round-trip between the topbar drawer and this page.
 *  • Notifications — local toggles for now; backed by the same Zustand store.
 *  • Account      — sign-out.
 *
 * Future: when /api/v1/users/me PATCH lands, wire Save buttons here.
 */

import { useEffect, useState } from "react";
import { Laptop, Moon, RotateCcw, Sun, LogOut } from "lucide-react";

import { AppShell } from "@/components/layout/AppShell";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { useAuth } from "@/lib/auth-context";
import {
  Density,
  ThemeMode,
  TweaksState,
  useTweaks,
} from "@/lib/theme-store";

const PRESET_COLORS = [
  "#4F46E5",
  "#7C3AED",
  "#0EA5E9",
  "#15803D",
  "#D97757",
  "#0F172A",
];

const FONT_PRESETS = [11.5, 13.5, 15, 16];

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

export default function SettingsPage() {
  const { user, token, logout } = useAuth();
  const t = useTweaks();
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  return (
    <AppShell
      eyebrow="Account"
      title="Settings"
      description="Appearance tweaks save to this browser instantly and sync to your account in the background."
      crumbs={[{ label: "Settings" }]}
    >
      <div className="grid grid-cols-1 lg:grid-cols-[260px_1fr] gap-8 max-w-[1100px]">
        <SectionNav />
        <div className="space-y-8">
          <ProfileSection user={user} token={token} />
          {mounted && <AppearanceSection t={t} />}
          <NotificationsSection />
          <AccountSection onLogout={logout} />
        </div>
      </div>
    </AppShell>
  );
}

// ── Section nav ─────────────────────────────────────────────────────

function SectionNav() {
  const items = [
    { href: "#profile", label: "Profile" },
    { href: "#appearance", label: "Appearance" },
    { href: "#notifications", label: "Notifications" },
    { href: "#account", label: "Account" },
  ];
  return (
    <aside className="hidden lg:block">
      <nav className="sticky top-20 flex flex-col gap-px">
        {items.map((i) => (
          <a
            key={i.href}
            href={i.href}
            className="px-2.5 py-1.5 rounded-md text-[12.5px] text-ink-3 hover:bg-app-2 hover:text-ink-2 transition-colors"
          >
            {i.label}
          </a>
        ))}
      </nav>
    </aside>
  );
}

// ── Profile ─────────────────────────────────────────────────────────

function ProfileSection({
  user,
  token,
}: {
  user: { email: string; name: string } | null;
  token: string | null;
}) {
  const [name, setName] = useState(user?.name ?? "");
  const [saving, setSaving] = useState(false);
  const [savedAt, setSavedAt] = useState<number | null>(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    setName(user?.name ?? "");
  }, [user?.name]);

  const dirty = name.trim() !== "" && name.trim() !== (user?.name ?? "");

  const save = async () => {
    if (!dirty) return;
    setSaving(true);
    setErr("");
    setSavedAt(null);
    try {
      // SC-010: auth via the HttpOnly cookie (credentials:"include").
      const res = await fetch(`${API_BASE}/api/v1/users/me`, {
        method: "PATCH",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: name.trim() }),
      });
      if (!res.ok) {
        const j = await res.json().catch(() => ({ detail: "Save failed" }));
        throw new Error(j.detail || "Save failed");
      }
      setSavedAt(Date.now());
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Save failed");
    } finally {
      setSaving(false);
    }
  };

  return (
    <section id="profile">
      <SectionHeader
        title="Profile"
        subtitle="Your identity in this workspace."
        action={
          <Button variant="primary" size="sm" disabled={!dirty} loading={saving} onClick={save}>
            {savedAt && !dirty ? "Saved" : "Save"}
          </Button>
        }
      />
      <Card className="p-5 space-y-4">
        <Field label="Name">
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="w-full h-9 rounded-md border border-hx bg-surface px-3 text-[12.5px] text-ink focus-ring"
          />
        </Field>
        <Field label="Email">
          <input
            type="email"
            value={user?.email ?? ""}
            readOnly
            className="w-full h-9 rounded-md border border-hx bg-app-2 px-3 text-[12.5px] text-ink-2 font-mono"
          />
        </Field>
        {err && <p className="text-[11.5px] text-err">{err}</p>}
        <p className="text-[11.5px] text-ink-4">
          Email + password changes go through the auth flow (sign out, then use forgot-password).
        </p>
      </Card>
    </section>
  );
}

// ── Appearance (Tweaks) ─────────────────────────────────────────────

function AppearanceSection({ t }: { t: TweaksState }) {
  return (
    <section id="appearance">
      <SectionHeader
        title="Appearance"
        subtitle="Theme, density, type scale, and accent color. Mirrors the topbar Tweaks drawer."
        action={
          <Button variant="ghost" size="sm" onClick={t.reset}>
            <RotateCcw className="h-3.5 w-3.5 mr-1" />
            Reset
          </Button>
        }
      />
      <Card className="p-5 space-y-6">
        <Field label="Theme">
          <Segmented
            value={t.theme}
            options={[
              { value: "light", label: "Light", icon: Sun },
              { value: "dark", label: "Dark", icon: Moon },
              { value: "auto", label: "Auto", icon: Laptop },
            ]}
            onChange={(v) => t.setTheme(v as ThemeMode)}
          />
        </Field>

        <Field label="Density">
          <Segmented
            value={t.density}
            options={[
              { value: "compact", label: "Compact" },
              { value: "regular", label: "Regular" },
              { value: "comfy", label: "Comfy" },
            ]}
            onChange={(v) => t.setDensity(v as Density)}
          />
        </Field>

        <Field label={`Font size — ${t.fontSizePx}px`}>
          <input
            type="range"
            min="10"
            max="18"
            step="0.5"
            value={t.fontSizePx}
            onChange={(e) => t.setFontSize(parseFloat(e.target.value))}
            className="w-full accent-[var(--con-brand)]"
          />
          <div className="flex gap-1.5 mt-2">
            {FONT_PRESETS.map((px) => (
              <button
                key={px}
                onClick={() => t.setFontSize(px)}
                className={
                  "flex-1 h-8 rounded-md text-[12px] font-medium border transition-colors " +
                  (Math.abs(t.fontSizePx - px) < 0.1
                    ? "border-con-brand text-con-brand bg-con-brand/5"
                    : "border-hx text-ink-3 hover:bg-app-2")
                }
              >
                {px}px
              </button>
            ))}
          </div>
        </Field>

        <Field label="Surface tint">
          <Segmented
            value={t.surfaceTint}
            options={[
              { value: "warm", label: "Warm" },
              { value: "neutral", label: "Neutral" },
              { value: "cool", label: "Cool" },
            ]}
            onChange={(v) => t.setSurfaceTint(v as "warm" | "neutral" | "cool")}
          />
        </Field>

        <Field label="Primary color">
          <div className="grid grid-cols-6 gap-2">
            {PRESET_COLORS.map((color) => (
              <button
                key={color}
                aria-label={`Set primary color to ${color}`}
                onClick={() => t.setPrimaryColor(color)}
                className={
                  "aspect-square rounded-md border-2 transition-transform hover:scale-105 " +
                  (t.primaryColor.toLowerCase() === color.toLowerCase()
                    ? "border-ink"
                    : "border-hx hover:border-hx-2")
                }
                style={{ background: color }}
              />
            ))}
          </div>
          <div className="mt-3 flex items-center gap-2">
            <input
              type="color"
              value={t.primaryColor}
              onChange={(e) => t.setPrimaryColor(e.target.value)}
              className="h-8 w-12 rounded-md border border-hx bg-surface cursor-pointer"
            />
            <input
              type="text"
              value={t.primaryColor}
              onChange={(e) => t.setPrimaryColor(e.target.value)}
              className="flex-1 h-8 rounded-md border border-hx bg-surface px-2 text-[12px] font-mono focus-ring"
              spellCheck={false}
            />
          </div>
        </Field>
      </Card>
    </section>
  );
}

// ── Notifications ───────────────────────────────────────────────────

function NotificationsSection() {
  const [emailDigest, setEmailDigest] = useState(true);
  const [workflowAlerts, setWorkflowAlerts] = useState(true);
  const [validationFail, setValidationFail] = useState(true);

  return (
    <section id="notifications">
      <SectionHeader
        title="Notifications"
        subtitle="Stored locally for now — server-side delivery follows once email/webhook config ships."
      />
      <Card className="p-5 space-y-3">
        <Toggle
          label="Daily migration digest"
          description="Summary of project activity, sent each morning."
          checked={emailDigest}
          onChange={setEmailDigest}
        />
        <Toggle
          label="Workflow approval requests"
          description="Alert me when a BMAD workflow is waiting on my decision."
          checked={workflowAlerts}
          onChange={setWorkflowAlerts}
        />
        <Toggle
          label="Validation failures"
          description="Notify on validation runs that miss the configured threshold."
          checked={validationFail}
          onChange={setValidationFail}
        />
      </Card>
    </section>
  );
}

// ── Account ─────────────────────────────────────────────────────────

function AccountSection({ onLogout }: { onLogout: () => void }) {
  return (
    <section id="account">
      <SectionHeader title="Account" subtitle="Sign out of this browser." />
      <Card className="p-5 flex items-center justify-between gap-4">
        <div>
          <p className="text-[13px] font-medium text-ink">Sign out</p>
          <p className="text-[11.5px] text-ink-3 mt-0.5">
            Removes your access token from this device. You will need to log in again.
          </p>
        </div>
        <Button variant="secondary" onClick={onLogout}>
          <LogOut className="h-3.5 w-3.5 mr-1.5" />
          Sign out
        </Button>
      </Card>
    </section>
  );
}

// ── Shared sub-components ───────────────────────────────────────────

function SectionHeader({
  title,
  subtitle,
  action,
}: {
  title: string;
  subtitle?: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="mb-3 flex items-end justify-between gap-3">
      <div>
        <h2 className="text-[15px] font-semibold text-ink leading-tight">{title}</h2>
        {subtitle && <p className="text-[12px] text-ink-3 mt-1">{subtitle}</p>}
      </div>
      {action}
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <p className="eyebrow mb-2">{label}</p>
      {children}
    </div>
  );
}

function Segmented<T extends string>({
  value,
  options,
  onChange,
}: {
  value: T;
  options: { value: T; label: string; icon?: React.ComponentType<{ className?: string }> }[];
  onChange: (v: T) => void;
}) {
  return (
    <div className="inline-flex w-full p-0.5 rounded-md bg-app-2 border border-hx">
      {options.map((o) => {
        const active = o.value === value;
        const Icon = o.icon;
        return (
          <button
            key={String(o.value)}
            onClick={() => onChange(o.value)}
            className={
              "flex-1 inline-flex items-center justify-center gap-1.5 h-8 px-2 text-[12px] font-medium rounded transition-colors " +
              (active
                ? "bg-surface text-ink shadow-xs"
                : "text-ink-3 hover:text-ink-2")
            }
          >
            {Icon && <Icon className="h-[13px] w-[13px]" />}
            {o.label}
          </button>
        );
      })}
    </div>
  );
}

function Toggle({
  label,
  description,
  checked,
  onChange,
}: {
  label: string;
  description?: string;
  checked: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <label className="flex items-start justify-between gap-4 py-2 cursor-pointer">
      <div className="flex-1">
        <p className="text-[13px] font-medium text-ink">{label}</p>
        {description && <p className="text-[11.5px] text-ink-3 mt-0.5">{description}</p>}
      </div>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        onClick={() => onChange(!checked)}
        className={
          "relative h-5 w-9 rounded-full transition-colors flex-shrink-0 mt-0.5 " +
          (checked ? "bg-con-brand" : "bg-app-2 border border-hx")
        }
      >
        <span
          className={
            "absolute top-0.5 h-4 w-4 rounded-full bg-white shadow transition-transform " +
            (checked ? "translate-x-[18px]" : "translate-x-0.5")
          }
        />
      </button>
    </label>
  );
}
