"use client";

import { useState } from "react";
import { useAuth } from "@/lib/auth-context";

export default function FirstAdminSetupPage() {
  const { setupFirstAdmin } = useAuth();
  const [form, setForm] = useState({ email: "", name: "", password: "", organization_name: "", organization_slug: "" });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await setupFirstAdmin(form);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Setup failed");
    } finally {
      setLoading(false);
    }
  };

  const update = (field: string) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm((f) => ({ ...f, [field]: e.target.value }));

  return (
    <div className="max-w-md mx-auto mt-16">
      <div className="rounded-xl border bg-white p-8 shadow-sm">
        <h1 className="text-2xl font-bold text-helix-700 mb-6">First Admin Setup</h1>
        {error && <div className="mb-4 rounded-lg bg-red-50 px-4 py-2 text-sm text-red-700">{error}</div>}
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
            <input type="email" value={form.email} onChange={update("email")} className="w-full rounded-lg border border-gray-300 px-4 py-2 text-sm" placeholder="admin@example.com" required />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Name</label>
            <input type="text" value={form.name} onChange={update("name")} className="w-full rounded-lg border border-gray-300 px-4 py-2 text-sm" placeholder="Admin User" required />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Password</label>
            <input type="password" value={form.password} onChange={update("password")} className="w-full rounded-lg border border-gray-300 px-4 py-2 text-sm" placeholder="••••••••" required />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Organization Name</label>
            <input type="text" value={form.organization_name} onChange={update("organization_name")} className="w-full rounded-lg border border-gray-300 px-4 py-2 text-sm" placeholder="Acme Corp" required />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Organization Slug</label>
            <input type="text" value={form.organization_slug} onChange={update("organization_slug")} className="w-full rounded-lg border border-gray-300 px-4 py-2 text-sm" placeholder="acme-corp" required />
          </div>
          <button type="submit" disabled={loading} className="w-full rounded-lg bg-helix-600 px-4 py-2 text-white font-medium hover:bg-helix-700 disabled:opacity-50">
            {loading ? "Creating..." : "Create Admin Account"}
          </button>
        </form>
      </div>
    </div>
  );
}
