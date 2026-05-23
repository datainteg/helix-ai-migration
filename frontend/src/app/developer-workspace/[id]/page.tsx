"use client";

import { useAuth } from "@/lib/auth-context";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

interface ReviewResult {
  id: string;
  summary: string;
  inputs_detected: string[];
  outputs_detected: string[];
  dependencies: string[];
  transformations_detected: string[];
  risks: { title: string; severity: string; impact: string; mitigation: string }[];
  quality_score: number;
  migration_suggestions: string[];
  validation_requirements: string[];
}

interface Artifact {
  id: string;
  filename: string;
  file_type: string;
  content_hash: string;
  storage_path: string;
}

export default function CodeReviewPage() {
  const { id } = useParams<{ id: string }>();
  const { token } = useAuth();
  const [artifact, setArtifact] = useState<Artifact | null>(null);
  const [review, setReview] = useState<ReviewResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  useEffect(() => {
    if (!token || !id) return;
    fetch(`${API}/api/v1/artifacts/${id}`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => (r.ok ? r.json() : null))
      .then(setArtifact);
  }, [id, token]);

  const runReview = async () => {
    if (!id || !token) return;
    setError("");
    setLoading(true);
    try {
      const res = await fetch(`${API}/api/v1/artifacts/${id}/review`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Review failed");
      }
      setReview(await res.json());
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Review failed");
    } finally {
      setLoading(false);
    }
  };

  const severityColor = (s: string) =>
    s === "high" ? "text-red-700 bg-red-50" : s === "medium" ? "text-amber-700 bg-amber-50" : "text-blue-700 bg-blue-50";

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <div className="flex items-center gap-4">
        <Link href="/developer-workspace" className="text-sm text-helix-600 hover:underline">
          &larr; Developer Workspace
        </Link>
        <h1 className="text-2xl font-bold text-gray-900">Code Review Center</h1>
      </div>

      {error && <div className="rounded-lg bg-red-50 px-4 py-2 text-sm text-red-700">{error}</div>}

      {artifact && (
        <div className="rounded-xl border bg-white p-6 shadow-sm">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="font-semibold text-lg">{artifact.filename}</h3>
              <p className="text-xs text-gray-500">
                .{artifact.file_type} • SHA256: {artifact.content_hash?.slice(0, 16)}...
              </p>
            </div>
            <button
              onClick={runReview}
              disabled={loading}
              className="rounded-lg bg-helix-600 px-4 py-2 text-sm font-medium text-white hover:bg-helix-700 disabled:opacity-50"
            >
              {loading ? "Running AI Review..." : review ? "Re-run AI Review" : "Run AI Review"}
            </button>
          </div>

          <div className="mt-4 p-4 rounded-lg bg-red-50 text-xs text-red-700">
            ⚠️ Read uploaded files as text only. Code is never executed. Reviews are draft and require human approval.
          </div>
        </div>
      )}

      {review && (
        <div className="space-y-4">
          {/* Summary + Score */}
          <div className="rounded-xl border bg-white p-6 shadow-sm">
            <div className="flex items-center justify-between mb-3">
              <h3 className="font-semibold">AI Review Summary</h3>
              <span className={`text-sm font-bold px-3 py-1 rounded ${review.quality_score >= 0.8 ? "bg-green-100 text-green-700" : review.quality_score >= 0.5 ? "bg-amber-100 text-amber-700" : "bg-red-100 text-red-700"}`}>
                Score: {(review.quality_score * 100).toFixed(0)}%
              </span>
            </div>
            <p className="text-sm text-gray-700">{review.summary}</p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Inputs & Outputs */}
            <div className="rounded-xl border bg-white p-6 shadow-sm">
              <h3 className="font-semibold text-sm mb-2">Detected I/O</h3>
              <div className="space-y-2 text-xs">
                <div><span className="text-gray-500">Inputs:</span> {review.inputs_detected?.join(", ") || "None"}</div>
                <div><span className="text-gray-500">Outputs:</span> {review.outputs_detected?.join(", ") || "None"}</div>
                <div><span className="text-gray-500">Dependencies:</span> {review.dependencies?.join(", ") || "None"}</div>
                <div><span className="text-gray-500">Transformations:</span> {review.transformations_detected?.join(", ") || "None"}</div>
              </div>
            </div>

            {/* Migration Suggestions */}
            <div className="rounded-xl border bg-white p-6 shadow-sm">
              <h3 className="font-semibold text-sm mb-2">Migration Suggestions</h3>
              <ul className="space-y-1 text-xs">
                {review.migration_suggestions?.map((s, i) => (
                  <li key={i} className="flex gap-2">
                    <span className="text-helix-600">→</span>
                    <span className="text-gray-700">{s}</span>
                  </li>
                ))}
              </ul>
            </div>

            {/* Risks */}
            <div className="rounded-xl border bg-white p-6 shadow-sm md:col-span-2">
              <h3 className="font-semibold text-sm mb-2">Risks Detected</h3>
              <div className="space-y-2">
                {review.risks?.map((r, i) => (
                  <div key={i} className="rounded-lg border px-3 py-2 text-sm">
                    <div className="flex items-center gap-2">
                      <span className={`text-xs px-2 py-0.5 rounded font-medium ${severityColor(r.severity)}`}>{r.severity}</span>
                      <span className="font-medium">{r.title}</span>
                    </div>
                    <p className="mt-1 text-xs text-gray-600">{r.impact}</p>
                    <p className="text-xs text-green-700 mt-0.5">Mitigation: {r.mitigation}</p>
                  </div>
                ))}
              </div>
            </div>

            {/* Validation Requirements */}
            <div className="rounded-xl border bg-white p-6 shadow-sm md:col-span-2">
              <h3 className="font-semibold text-sm mb-2">Validation Requirements</h3>
              <ul className="space-y-1 text-xs">
                {review.validation_requirements?.map((v, i) => (
                  <li key={i} className="flex gap-2">
                    <span className="text-helix-600">✓</span>
                    <span className="text-gray-700">{v}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      )}

      {!review && artifact && (
        <div className="rounded-xl border bg-white p-12 shadow-sm text-center text-gray-500">
          Click "Run AI Review" to analyze this artifact.
        </div>
      )}
    </div>
  );
}
