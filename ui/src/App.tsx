import { Navigate, Route, Routes } from "react-router-dom";

import { DashboardPage } from "./routes/DashboardPage";
import { RunDetailPage } from "./routes/RunDetailPage";

export function App(): JSX.Element {
  return (
    <Routes>
      <Route path="/" element={<DashboardPage />} />
      <Route path="/runs/:runId" element={<RunDetailPage />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
