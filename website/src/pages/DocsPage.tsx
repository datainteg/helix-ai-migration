import { Link, Route, Routes, useParams } from "react-router-dom";

import { SectionHeader } from "@/components/layout/SectionHeader";
import { DocsLayout } from "@/components/docs/DocsLayout";
import { DocsPage as DocReader } from "@/components/docs/DocsPage";
import { FeatureDocCard } from "@/components/docs/FeatureDocCard";
import { DOCS, findDoc } from "@/data/docs-content";

function DocsIndex() {
  return (
    <DocsLayout>
      <div className="mb-10">
        <SectionHeader
          eyebrow="Documentation"
          title="Documentation"
          description="Helix Migration A-to-Z. Pick a topic from the sidebar or jump in here."
        />
      </div>
      <div className="grid sm:grid-cols-2 gap-4">
        {DOCS.map((doc) => (
          <FeatureDocCard key={doc.id} doc={doc} />
        ))}
      </div>
    </DocsLayout>
  );
}

function DocsDetail() {
  const params = useParams<{ id: string }>();
  const doc = params.id ? findDoc(params.id) : undefined;

  if (!doc) {
    return (
      <DocsLayout>
        <div className="max-w-[520px] py-12">
          <p className="eyebrow mb-2">404</p>
          <h1 className="text-[26px] font-semibold text-ink tracking-tight">
            Topic not found
          </h1>
          <p className="mt-2 text-[14px] text-ink-3 leading-relaxed">
            We couldn't find a doc with id{" "}
            <span className="font-mono text-ink-2">{params.id}</span>. The page may
            have moved or been renamed.
          </p>
          <Link
            to="/docs"
            className="mt-5 inline-flex items-center px-3.5 py-1.5 rounded-md text-[13px] font-medium bg-ink text-white hover:bg-zinc-800 focus-ring"
          >
            Back to documentation
          </Link>
        </div>
      </DocsLayout>
    );
  }

  return (
    <DocsLayout>
      <DocReader doc={doc} />
    </DocsLayout>
  );
}

export function DocsPage() {
  return (
    <Routes>
      <Route index element={<DocsIndex />} />
      <Route path=":id" element={<DocsDetail />} />
    </Routes>
  );
}
