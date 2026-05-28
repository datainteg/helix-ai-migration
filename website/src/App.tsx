import { Routes, Route } from "react-router-dom";

import { WebsiteLayout } from "@/components/layout/WebsiteLayout";
import { HomePage } from "@/pages/HomePage";
import { FeaturesPage } from "@/pages/FeaturesPage";
import { ArchitecturePage } from "@/pages/ArchitecturePage";
import { DocsPage } from "@/pages/DocsPage";
import { OpenSourcePage } from "@/pages/OpenSourcePage";
import { NotFoundPage } from "@/pages/NotFoundPage";

// /demo route was removed — visitors land on the static HTML console mock
// in `public/helix-console-demo.html` via the View Demo CTA instead.

export default function App() {
  return (
    <WebsiteLayout>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/features" element={<FeaturesPage />} />
        <Route path="/architecture" element={<ArchitecturePage />} />
        <Route path="/docs/*" element={<DocsPage />} />
        <Route path="/open-source" element={<OpenSourcePage />} />
        {/* L-012: render a real 404 page instead of silently redirecting
            unknown routes to "/" (which masked dead links from crawlers). */}
        <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </WebsiteLayout>
  );
}
