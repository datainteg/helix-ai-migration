import { Routes, Route, Navigate } from "react-router-dom";

import { WebsiteLayout } from "@/components/layout/WebsiteLayout";
import { HomePage } from "@/pages/HomePage";
import { FeaturesPage } from "@/pages/FeaturesPage";
import { ArchitecturePage } from "@/pages/ArchitecturePage";
import { DocsPage } from "@/pages/DocsPage";
import { OpenSourcePage } from "@/pages/OpenSourcePage";

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
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </WebsiteLayout>
  );
}
