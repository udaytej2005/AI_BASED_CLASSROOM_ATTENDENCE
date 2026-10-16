import { Route, Routes } from "react-router-dom";

import RequireAuth from "./auth/RequireAuth";
import ChangePasswordPage from "./pages/ChangePasswordPage";
import DashboardPage from "./pages/DashboardPage";
import FacultyFormPage from "./pages/FacultyFormPage";
import FacultyPage from "./pages/FacultyPage";
import ForbiddenPage from "./pages/ForbiddenPage";
import LoginPage from "./pages/LoginPage";
import NotFoundPage from "./pages/NotFoundPage";
import StudentDetailPage from "./pages/StudentDetailPage";
import StudentFormPage from "./pages/StudentFormPage";
import StudentsPage from "./pages/StudentsPage";
import SystemHealthPage from "./pages/SystemHealthPage";
import UsersPage from "./pages/UsersPage";

/**
 * Route table. Each protected route names the roles allowed to open it. The API enforces the same rules.
 */
export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/forbidden" element={<ForbiddenPage />} />

      <Route path="/account/password" element={<RequireAuth><ChangePasswordPage /></RequireAuth>} />
      <Route path="/" element={<RequireAuth><DashboardPage /></RequireAuth>} />
      <Route path="/profile" element={<RequireAuth roles={["student"]}><StudentDetailPage mode="me" /></RequireAuth>} />

      <Route path="/students" element={<RequireAuth roles={["admin", "principal", "faculty"]}><StudentsPage /></RequireAuth>} />
      <Route path="/students/new" element={<RequireAuth roles={["admin"]}><StudentFormPage /></RequireAuth>} />
      <Route path="/students/:id" element={<RequireAuth roles={["admin", "principal", "faculty", "student"]}><StudentDetailPage /></RequireAuth>} />
      <Route path="/students/:id/edit" element={<RequireAuth roles={["admin"]}><StudentFormPage /></RequireAuth>} />

      <Route path="/faculty" element={<RequireAuth roles={["admin", "principal", "faculty"]}><FacultyPage /></RequireAuth>} />
      <Route path="/faculty/new" element={<RequireAuth roles={["admin"]}><FacultyFormPage /></RequireAuth>} />
      <Route path="/faculty/:id/edit" element={<RequireAuth roles={["admin"]}><FacultyFormPage /></RequireAuth>} />

      <Route path="/users" element={<RequireAuth roles={["admin"]}><UsersPage /></RequireAuth>} />
      <Route path="/system" element={<RequireAuth roles={["admin", "technical"]}><SystemHealthPage /></RequireAuth>} />

      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
}
