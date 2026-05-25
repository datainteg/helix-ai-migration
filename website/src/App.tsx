import { Routes, Route, Navigate } from "react-router-dom";

import { WebsiteLayout } from "@/components/layout/WebsiteLayout";
import { HomePage } from "@/pages/HomePage";
import { FeaturesPage } from "@/pages/FeaturesPage";
import { ArchitecturePage } from "@/pages/ArchitecturePage";
import { DemoPage } from "@/pages/DemoPage";
import { DocsPage } from "@/pages/DocsPage";
import { OpenSourcePage } from "@/pages/OpenSourcePage";

export default function App() {
  return (
    <WebsiteLayout>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/features" element={<FeaturesPage />} />
        <Route path="/architecture" element={<ArchitecturePage />} />
        <Route path="/demo/*" element={<DemoPage />} />
        <Route path="/docs/*" element={<DocsPage />} />
        <Route path="/open-source" element={<OpenSourcePage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </WebsiteLayout>
  );
}
