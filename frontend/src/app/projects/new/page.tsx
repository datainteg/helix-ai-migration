"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

export default function NewProjectPage() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [riskLevel, setRiskLevel] = useState("unknown");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    // API call placeholder — will wire to backend in Task 5+
    console.log({ name, description, risk_level: riskLevel });
    router.push("/projects");
  };

  return (
    <div className="max-w-xl mx-auto mt-8">
      <h1 className="text-2xl font-bold text-gray-900 mb-6">New Project</h1>
      <form onSubmit={handleSubmit} className="space-y-4 rounded-xl border bg-white p-6 shadow-sm">
        <div>
          <label className="block text-sm font-medium mb-1">Project Name</label>
          <input value={name} onChange={(e) => setName(e.target.value)} required className="w-full rounded-lg border px-4 py-2 text-sm" placeholder="Oracle to Snowflake Migration" />
        </div>
        <div>
          <label className="block text-sm font-medium mb-1">Description</label>
          <textarea value={description} onChange={(e) => setDescription(e.target.value)} className="w-full rounded-lg border px-4 py-2 text-sm" rows={3} placeholder="Migrate CRM and billing data..." />
        </div>
        <div>
          <label className="block text-sm font-medium mb-1">Risk Level</label>
          <select value={riskLevel} onChange={(e) => setRiskLevel(e.target.value)} className="w-full rounded-lg border px-4 py-2 text-sm">
            <option value="unknown">Unknown</option>
            <option value="low">Low</option>
            <option value="medium">Medium</option>
            <option value="high">High</option>
          </select>
        </div>
        <button type="submit" className="w-full rounded-lg bg-helix-600 px-4 py-2 text-white font-medium hover:bg-helix-700">Create Project</button>
      </form>
    </div>
  );
}
