import { Route, Routes } from "react-router-dom";

import DashboardPage from "./pages/DashboardPage";
import NotFoundPage from "./pages/NotFoundPage";
import SystemHealthPage from "./pages/SystemHealthPage";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<DashboardPage />} />
      <Route path="/system" element={<SystemHealthPage />} />
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
}
