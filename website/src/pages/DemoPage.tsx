import { Routes, Route, Navigate } from "react-router-dom";

import { DemoDashboard }         from "@/components/demo/DemoDashboard";
import { DemoProjectWorkspace }  from "@/components/demo/DemoProjectWorkspace";
import { DemoAgentWorkflow }     from "@/components/demo/DemoAgentWorkflow";
import { DemoValidationCenter }  from "@/components/demo/DemoValidationCenter";
import { DemoReconDashboard }    from "@/components/demo/DemoReconDashboard";
import { DemoDeveloperWorkspace } from "@/components/demo/DemoDeveloperWorkspace";
import { DemoConnectors }        from "@/components/demo/DemoConnectors";
import { DemoSprintMapping }     from "@/components/demo/DemoSprintMapping";
import { DemoAdminPanel }        from "@/components/demo/DemoAdminPanel";

export function DemoPage() {
  return (
    <Routes>
      <Route index                 element={<DemoDashboard />} />
      <Route path="project"        element={<DemoProjectWorkspace />} />
      <Route path="agents"         element={<DemoAgentWorkflow />} />
      <Route path="validation"     element={<DemoValidationCenter />} />
      <Route path="recon"          element={<DemoReconDashboard />} />
      <Route path="developer"      element={<DemoDeveloperWorkspace />} />
      <Route path="connectors"     element={<DemoConnectors />} />
      <Route path="sprint-mapping" element={<DemoSprintMapping />} />
      <Route path="admin"          element={<DemoAdminPanel />} />
      <Route path="*"              element={<Navigate to="/demo" replace />} />
    </Routes>
  );
}
